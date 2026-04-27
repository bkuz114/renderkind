#!/usr/bin/env python3
"""
RenderKind: Markdown to static HTML documentation site generator.

Convert single markdown files or entire directories into styled, navigable
HTML pages with automatic table of contents, index page generation, and
responsive design.

Usage:
    renderkind INPUT [--output DIR] [--template FILE] [--force] [--strict]
               [--quiet] [--clean] [--no-recursive] [--no-index] [--index-name NAME]
               [--mode MODE]

Examples:
    # Single file mode (outputs to dist/index.html)
    renderkind docs/intro.md

    # Batch mode (process entire directory)
    renderkind docs/

    # Custom output directory
    renderkind docs/ --output site/

    # Force overwrite and clean output directory
    renderkind docs/ --clean --force

    # Suppress all non-error output (CI/CD friendly)
    renderkind docs/ --quiet

    # Disable index page generation
    renderkind docs/ --no-index

    # Custom index filename
    renderkind docs/ --index-name README.html

    # Process only top-level files (no recursion)
    renderkind docs/ --no-recursive

    # Require frontmatter title and description in every file
    renderkind docs/ --strict

    # Use custom HTML template
    renderkind docs/ --template path/to/custom.html

    # Force document to be "github" style (first h1 becomes doc title
    # if no 'title' key in YAML frontmatter. h1 in TOC links to #top)
    renderkind example.md --type github

    # Force docment to be "wiki" style (document title only comes from
    # YAML frontmatter, and if none, uses filename. TOC styled normally)
    renderkind example.md --type wiki

    # Force all documents to be wiki style
    renderkind docs/ --type wiki

    # Show version
    renderkind --version

Dependencies:
    pip install markdown beautifulsoup4 pyyaml

Output:
    Single file mode: Creates OUTPUT_DIR/index.html (default: dist/)
    Batch mode: Creates OUTPUT_DIR/ with preserved directory structure,
                index.html (auto-generated navigation), and assets/

Features:
    - YAML frontmatter for metadata (title, description)
    - Build-time table of contents (h1-h4 headings)
    - Automatic index page with directory tree (batch mode)
    - Responsive default template (dark mode, collapsible TOC)
    - Asset copying with correct relative paths at any depth

For more information, see README.md and CHANGELOG.md.
"""

import os
import sys
import argparse
import re
import json
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import yaml
import markdown
from bs4 import BeautifulSoup
import logging

# vendored template_utils package
from renderkind.vendor.template_utils import render_template

# set up template and assets defaults within the pip project
import renderkind

# Get the package root directory using __file__.
#
# Why not importlib.resources?
#   On Windows, importlib.resources returns a MultiplexedPath object that
#   cannot be converted to a real Path without ugly string hacks. The
#   __file__ approach is simpler and works reliably because setuptools
#   guarantees that package data (templates, assets) are installed to the
#   filesystem alongside the package.
#
# Assumption:
#   This assumes the package is installed to a filesystem directory
#   (not a zip file). For a CLI tool distributed via PyPI, this is true
#   for all normal installation methods (pip, pipx, etc.).
#
# Package structure expected:
#   renderkind/
#   ├── __init__.py
#   ├── cli.py
#   ├── templates/
#   │   └── default_template.html
#   └── assets/
#       ├── css/
#       └── js/
PACKAGE_ROOT = Path(renderkind.__file__).parent

# Verify the directory exists (helpful error if structure changes)
if not PACKAGE_ROOT.exists():
    raise RuntimeError(f"Package root not found at {PACKAGE_ROOT}")

# Default paths relative to package root
DEFAULT_TEMPLATE = PACKAGE_ROOT / "templates" / "default_template.html"
DEFAULT_ASSETS = PACKAGE_ROOT / "assets"

# ============================================================================
# CONFIGURATION
# ============================================================================

# Maximum heading depth for TOC (1=h1, 2=h2, 3=h3, 4=h4)
TOC_MAX_DEPTH = 4

# Markdown extensions
MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "codehilite",
    "smarty",
]

# document mode mapping
MODE_MAPPING = {"auto": 0, "wiki": 1, "github": 2}

# ============================================================================
# LOGGING
# ============================================================================


# Setup basic logging (called once in main)
def setup_logging(quiet: bool = False):
    """Configure logging based on quiet flag."""
    level = logging.ERROR if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",  # Just the message, no extra prefix
        stream=sys.stdout,
    )


# Get module logger
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_in_hidden_directory(path: Path, root_dir: Path) -> bool:
    """Check if path is inside a hidden directory (e.g., .git/, .venv/)."""
    rel_parts = path.relative_to(root_dir).parts
    return any(part.startswith(".") for part in rel_parts)


def discover_markdown_files(root_dir: Path, recursive: bool) -> List[Path]:
    """
    Discover markdown files in a directory.

    Args:
        root_dir: Directory to search
        recursive: If True, search subdirectories; if False, top-level only

    Returns:
        Sorted list of Path objects (absolute paths)

    Rules:
        - Excludes symlinks (prints warning to stderr)
        - Excludes files inside hidden directories (e.g., .git/, .venv/)
        - Includes hidden markdown files (e.g., .draft.md)
    """
    pattern = "**/*.md" if recursive else "*.md"
    all_files = list(root_dir.glob(pattern))

    files = []
    for f in all_files:
        # Skip symlinks with warning
        if f.is_symlink():
            logger.warning(f"   ⚠️  Skipping symlink: {f.relative_to(root_dir)}")
            continue

        # Skip files inside hidden directories
        if is_in_hidden_directory(f, root_dir):
            continue

        files.append(f)

    return sorted(files)


def read_markdown_file(markdown_path: Path) -> str:
    """
    Reads and validates input markdown file and returns raw content.

    Args:
        markdown_path: Path to markdown file.

    Returns:
        Raw text of markdown file.

    Raises:
        FileNotFoundError: If markdown_path doesn't exist.
        ValueError: If markdown_path isn't .md file
    """
    if not markdown_path.exists():
        raise FileNotFoundError(f"Input file not found: {markdown_path}")
    if not markdown_path.suffix.lower() != "md":
        raise ValueError(f"Input file not .md: {markdown_path}")

    with open(markdown_path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# MARKDOWN + YAML FRONTMATTER PROCESSING
# ============================================================================


def resolve_document_mode(
    frontmatter: Dict, cli_mode: int, markdown_content: str
) -> int:
    """
    Determine "document mode": i.e. if it's a wiki-style document with
    any number of h1s or a github-style document with a single h1 determining
    the ttiel). Determined based on following priority:
        1. CLI flag (--mode)
        2. 'type' field in YAML frontmatter
        3. Auto-detection (counts h1 headings: 1 h1 = github style md, > 1 h1 = wikistyle md)

    Args:
        frontmatter: dictionary of YAML key/values
        cli_mode: integer representation of user supplied --mode using MODE_MAPPING
            (i.e. --mode "auto" : 0, --mode "wiki": 1, --mode "github"  : 2)
        markdown_content: string content of an .md file

    Returns:
        int representating determined mode:
        - 1 for wiki documents (multiple h1s or --mode "wiki")
        - 2 for regular documents (single h1 or --mode "github")
    """
    # CLI takes precedence
    if cli_mode != 0:
        return cli_mode

    # Frontmatter override
    if "type" in frontmatter:
        frontmatter_type = frontmatter["type"].lower()
        # ensure in mode mapping
        if frontmatter_type not in MODE_MAPPING.keys():
            raise ValueError(
                f"'type' key in YAML frontmatter does not specify a valid document type.\n\tValid: {', '.join(list(MODE_MAPPING.keys()))}\n\tGiven: {frontmatter_type}"
            )
        return MODE_MAPPING[frontmatter_type]

    # Auto-detect based on h1 count
    h1_count = count_h1_headings(markdown_content)
    return 2 if h1_count == 1 else 1


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content and return both.

    Args:
        content: string content of an .md file (including YAML frontmatter)

    Returns:
        (metadata_dict, remaining_markdown_string)

    Frontmatter format:
        ---
        title: My Document
        description: Something useful
        ---
        # Rest of markdown...

    Graceful degradation:
        - No frontmatter → ({}, content)
        - No closing '---' → ({}, content)
        - Malformed YAML → ({}, content) with warning
    """
    lines = content.split("\n")

    # Check for opening --- (must be first line)
    if not lines or lines[0].strip() != "---":
        return {}, content

    # Find closing ---
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        # No closing delimiter — treat as no frontmatter
        return {}, content

    # Extract YAML block and remaining content
    yaml_block = "\n".join(lines[1:end_idx])
    rest_content = "\n".join(lines[end_idx + 1 :])

    # Parse YAML
    try:
        metadata = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as e:
        logger.warning(f"⚠️  Warning: Malformed frontmatter YAML: {e}")
        logger.warning("   Ignoring frontmatter and continuing.")
        return {}, content

    return metadata, rest_content


def extract_headings_and_add_ids(
    html_content: str, max_depth: int = 4
) -> Tuple[str, List[Dict]]:
    """
    Parse HTML, add missing IDs to headings, and build TOC structure.

    Args:
        html_content: HTML string from markdown conversion.
        max_depth: Maximum heading level to include (1-4).

    Returns:
        Tuple of (modified_html, toc_entries) where toc_entries is a list of
        dicts with keys: level, text, id.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    toc_entries = []

    # Find all headings
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        level = int(heading.name[1])
        if level > max_depth:
            continue

        # Ensure heading has an ID
        heading_id = heading.get("id")
        if not heading_id:
            # Generate an ID from text content
            text = heading.get_text(strip=True)
            heading_id = re.sub(r"[^a-z0-9]+", "-", text.lower())
            heading_id = re.sub(r"^-|-$", "", heading_id)
            heading["id"] = heading_id

        toc_entries.append(
            {
                "level": level,
                "text": heading.get_text(strip=True),
                "id": heading.get("id"),
            }
        )

    return str(soup), toc_entries


def extract_title(
    frontmatter: Dict, markdown_content: str, mode: int, file_path: Path, strict: bool
) -> str:
    """
    Extract document title basd on mode.

    Approach:
    For type 1 document (Wiki-style): YAML frontmatter 'title' → filename
    For type 2 document (Github-style): YAML frontmatter 'title' → first h1 → fallback

    Args:
        frontmatter: dictionary of the key/value pairs extracted from YAML frontmatter.
        markdown_content: string content of an .md file
        mode: int indicating document type. Options: 1 (github style), 2 (wiki style)
        file_path: Path to markdown file
        strict: If True, require 'title' frontmatter.

    Returns:
        Extracted title text (without '# ' prefix) or fallback string

    Example:
        Given first line '# Cleaning Chemistry'
        Returns 'Cleaning Chemistry'
    """

    fallback = "Untitled Document"
    filename = file_path.stem

    # Frontmatter title always wins
    if frontmatter.get("title"):
        return frontmatter["title"]
    elif strict:
        raise ValueError("--strict: 'title' field required in frontmatter")

    if mode == 2:
        # Github mode: use first h1
        first_h1 = extract_first_h1(markdown_content)
        if first_h1:
            return first_h1
        logger.warning(
            f"⚠️  Warning: No 'title' in {filename} frontmatter and no h1 found. Document title falls back to: {fallback}"
        )
    elif mode == 1:
        # Wiki mode: use filename (without extension)
        return filename
    else:
        raise ValueError(
            f"Invalid integer document type when trying to extract title: {str(mode)}. Valid values are 1 (wiki style) or 2 (github style)."
        )

    # Fallback title
    return fallback


def extract_description(frontmatter: Dict, strict: bool) -> str:
    """
    Extract document description from YAML frontmatter.

    Args:
        frontmatter: dictionary of the key/value pairs extracted from YAML frontmatter.
        strict: If True, require 'description' frontmatter.

    Returns:
        description string ("" if none in frontmatter)
    """
    # description key from YAML frontmatter
    if frontmatter.get("description"):
        return frontmatter["description"]

    # no description -- error or warn based on strict preference
    if strict:
        raise ValueError("--strict: 'description' field required in frontmatter")
    else:
        logger.warning(
            f"ℹ️  Info: No 'description' in frontmatter. <meta name='description'> will be empty. SEO may be affected."
        )

    return ""


def extract_first_h1(markdown: str) -> str:
    """
    Extract the first h1 from markdown file.

    Args:
        markdown: string content of an .md file

    Returns:
        Title text (without '# ' prefix) or None

    Example:
        Given first line '# Cleaning Chemistry'
        Returns 'Cleaning Chemistry'
    """
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()


def count_h1_headings(markdown: str) -> int:
    """
    Count number of h1 headings in markdown file.

    Args:
        markdown: string content of an .md file

    Returns:
        int number of h1 headings
    """
    num_headings = 0
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            num_headings += 1
    return num_headings


# ============================================================================
# DOCUMENT GENERATION
# ============================================================================


def render_toc(toc_entries: List[Dict], mode: int, current_depth: int = 1) -> str:
    """
    Render TOC entries as nested HTML list based on document mode.

    Args:
        toc_entries: List of dicts with 'level', 'text', 'id' keys
        mode: int indicating document type. Options: 1 (github style), 2 (wiki style)
            - Github mode: First h1 gets up-arrow anchored to #top in TOC
            - Wiki mode: All h1s as normal headings. Back to top link before all
        current_depth: Starting depth (default 1, for h1)

    Returns:
        HTML string of nested <ul> and <li> elements

    Note:
        This function uses recursion to handle nested heading levels.
        h1 is rendered as a special "Back to top" link.
    """

    # Filter to only include entries at or below max depth
    entries = [e for e in toc_entries if e["level"] <= TOC_MAX_DEPTH]

    html = '<ul class="toc-list">\n'

    # counter to offset which css styling class to use for heading entries
    # (wiki docs should use toc-level-h2 for h1, toc-level-h3 for h2, etc.)
    offset = 0

    # wiki mode: create anchor to top of document
    if mode == 1:
        html += f'  <li><a href="#top" class="toc-level-h1">↑ Start</a></li>\n'
        offset = 1

    # create <li> for each heading
    for entry in entries:
        level = entry["level"]
        text = entry["text"]
        anchor_id = entry["id"]
        level_class = f"toc-level-h{level + offset}"

        if level == 1 and mode == 2 and entry == entries[0]:
            # First h1 in document mode: up-arrow
            # Back to top link (uses #top anchor from <html id="top">)
            html += f'  <li><a href="#top" class="toc-level-h1">↑ {text}</a></li>\n'
        else:
            # Wiki mode or non-first h1 in document mode (shouldn't happen)
            html += (
                f'  <li><a href="#{anchor_id}" class="{level_class}">{text}</a></li>\n'
            )

    html += "</ul>\n"
    return html


def convert_markdown_to_html(md_content: str, mode: int) -> Tuple[str, str]:
    """
    Convert Markdown file to HTML using python-markdown.

    Args:
        md_content: extracted markdown content from .md file (should NOT include YAML frontmatter)
        mode: int indicating document type. Options: 1 (github style), 2 (wiki style)
            - Github mode: First h1 gets up-arrow anchored to #top in TOC
            - Wiki mode: All h1s as normal headings in TOC.

    Returns:
        Tuple: (
            HTML string with heading IDs added,
            HTML TOC string,
        )
    """

    # Convert markdown to HTML
    raw_html = markdown.markdown(md_content, extensions=MD_EXTENSIONS)

    # Add IDs to headings and extract TOC
    html_with_ids, toc_entries = extract_headings_and_add_ids(raw_html, TOC_MAX_DEPTH)

    # Re-parse after heading ID addition (or work with the modified soup directly)
    # Simpler: create a new soup from html_with_ids
    soup_with_ids = BeautifulSoup(html_with_ids, "html.parser")

    # Generate TOC HTML from entries
    toc_html = render_toc(toc_entries, mode)

    return str(soup_with_ids), toc_html


def template_html(
    template_path: Path,
    content: str,
    frontmatter: Dict[str, str],
    toc_html: str,
    asset_path_prefix: str,
) -> str:
    """
    Embed converted markdown content into template file.

    Args:
        template_path: Path to the template .html file.
        content: string of content to embed at {{content}} placeholder
        frontmatter: dictionary of the key/value pairs extracted from YAML frontmatter.
            Used to embed data to dcoument placeholders. Example:
            frontmatter = {"key1": "value1", "key2": "value2"},
            "value1" will be embedded at {{key1}} placeholder, "value2" at {{key2}}, etc.
        toc: string of content to embed at {{toc}} placeholder

    Returns:
        Content of template file with embedded markdown content and title.

    Raises:
        FileNotFoundError: If template_path doesn't exist.
        ValueError: If template_path isn't .html file
    """

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    if not template_path.suffix == ".html":
        raise ValueError(
            f"Template file expected .html file, got {template_path.suffix}: {template_path}"
        )

    # Read template file
    template_content = template_path.read_text(encoding="utf-8")

    # Build substitutions
    substitutions = {
        "content": content,
        "toc": toc_html,
        "asset_path_prefix": asset_path_prefix,
    }

    # merge frontmatter data
    substitutions |= frontmatter

    # Generate warning comment referencing the source template
    warning_msg = f"THIS FILE IS GENERATED. DO NOT EDIT DIRECTLY."

    # Inject content into HTML template
    full_content = render_template(
        template_content,
        substitutions,
        strict=True,
        warning_comment=warning_msg,
    )

    return full_content


def copy_assets_to_output(
    assets_path: Path, assets_dest_dir: Path, force: bool = False
) -> Path:
    """
    Copy the assets directory to the output file's parent directory.

    This function copies the entire assets directory (including all contents)
    to the same directory where the output file will live. This ensures that
    relative asset references (e.g., `assets/css/styles.css`) resolve correctly
    when the output file is opened in a browser.

    Args:
        assets_path: Path to the source assets directory.
        assets_dest_dir: Path to the copy assets to.
        force: If True, overwrite existing assets directory; if False, raise
               error if destination already exists.

    Returns: None

    Raises:
        FileNotFoundError: If assets_path does not exist.
        NotADirectoryError: If assets_path is not a directory.
        FileExistsError: If assets_dest_dir exists and force is False.
        OSError: For other file operation errors (permissions, disk full, etc.).

    Examples:
        >>> from pathlib import Path
        >>> assets = Path("/project/assets")
        >>> output = Path("/project/output/assets")
        >>> copy_assets_to_output(assets, output, force=True)
        # Copies /project/assets to /project/output/assets

    Notes:
        - Uses shutil.copytree for recursive directory copy.
        - The destination directory name matches the source directory name.
        - Existing symlinks are preserved (follow_symlinks=False).
        - If force=True, any existing destination is removed before copying.
    """
    # Validate source
    if not assets_path.exists():
        raise FileNotFoundError(f"Assets path does not exist: {assets_path}")

    if not assets_path.is_dir():
        raise NotADirectoryError(f"Assets path is not a directory: {assets_path}")

    # Handle existing destination
    if assets_dest_dir.exists():
        if force:
            shutil.rmtree(assets_dest_dir)  # Remove entire existing directory
        else:
            raise FileExistsError(
                f"Destination already exists: {assets_dest_dir}\n"
                f"Use force=True to overwrite."
            )

    # Copy the directory
    try:
        shutil.copytree(
            assets_path,
            assets_dest_dir,
            symlinks=False,  # Copy symlinks as links (not dereferenced)
            ignore_dangling_symlinks=True,
            dirs_exist_ok=False,  # Should not happen due to check above
        )
    except OSError as e:
        raise OSError(
            f"Failed to copy assets from {assets_path} to {assets_dest_dir}: {e}"
        )


def get_asset_path_prefix(html_path: Path, assets_dir: Path) -> str:
    """
    Calculate the relative filesystem path from an HTML file to an assets directory.

    This function is designed for static site generation where you need to insert
    asset paths (CSS, JS, images) into HTML files using relative URLs. For example,
    if your HTML file lives in a nested directory structure, this tells you how
    many "../" segments are needed to reach the assets directory from that HTML
    file's location.

    The returned path always uses POSIX-style forward slashes ("/") and includes
    a trailing slash for easy concatenation with filenames.

    Examples:
        >>> from pathlib import Path
        >>> html_path = Path("dist/getting-started/install.html")
        >>> assets_dir = Path("dist/assets/")
        >>> get_asset_path_prefix(html_path, assets_dir)
        '../assets/'

        >>> html_path = Path("dist/install.html")
        >>> assets_dir = Path("dist/assets/")
        >>> get_asset_path_prefix(html_path, assets_dir)
        'assets/'

        >>> html_path = Path("dist/index.html")
        >>> assets_dir = Path("dist/assets/")
        >>> get_asset_path_prefix(html_path, assets_dir)
        'assets/'

    Args:
        html_path: Path to the HTML file (may not exist on disk yet)
        assets_dir: Path to the directory containing assets (may not exist yet)

    Returns:
        A relative path string ending with "/". Returns empty string if the
        HTML file and assets directory are in the same directory.

    Notes:
        This function works with hypothetical paths that don't exist on disk.
        It performs purely lexical path manipulation without filesystem access.

    Why not use Path.relative_to()?
        Path.relative_to() only works when one path is a direct subpath of the
        other. In our typical use case, the HTML file is nested (e.g.,
        "docs/guide/install.html") while the assets directory is elsewhere
        (e.g., "assets/"). These are cousin paths, not parent-child, so
        relative_to() raises ValueError. We need to ascend using "../" segments,
        which os.path.relpath handles.
    """

    # Get the directory containing the HTML file
    html_dir = html_path.parent

    # Compute rel path from HTML dir to assets dir
    # - os.path.relpath() computes rel path from start to target
    #   e.g.: relpath("dist/getting-started", "dist/assets") -> "../assets"
    # - counts ".." segments automatically, even for deeply nested paths.
    # - returns OS-native separators
    rel_path = os.path.relpath(str(assets_dir), start=str(html_dir))

    # os.path.relpath returns . if both dirs same
    if rel_path == ".":
        return ""

    # Convert Windows backslashes to forward slashes for HTML compatibility
    return rel_path.replace("\\", "/") + "/"


def write_html_file(content: str, output: Path, force: bool) -> None:
    """
    Write the final HTML file, checking for existing file and --force flag.

    Args:
        content: Final HTML string.
        output: Path to write html file to
        force: Whether to overwrite existing file.

    Raises:
        FileExistsError: If file exists and force is False.
    """
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists. Use --force to overwrite.")

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        logger.info(f"✅ Generated: {output}")
        f.write(content)


def process_single_file(
    input_path: Path,
    output_path: Path,
    template_path: Path,
    assets_path: Path,
    final_assets_dir: Path,
    force: bool,
    strict: bool,
    mode: int,
) -> Path:
    """
    Process a single markdown file and return the output path.

    This function handles the complete conversion pipeline for one file:
    reading, frontmatter parsing, markdown conversion, template rendering,
    and writing the output HTML.

    Args:
        input_path: Path to the source markdown file.
        output_path: Path where the generated HTML file will be written.
        template_path: Path to the HTML template file.
        assets_path: Path to the source assets directory (css/, js/).
        final_assets_dir: Path where assets will be copied in the output
            directory (e.g., dist/assets/).
        force: If True, overwrite existing output files. If False, raise
            FileExistsError when output already exists.
        strict: If True, require 'title' and 'description' in frontmatter.
            If False, use fallbacks (first h1 for title, empty for description).
        mode: int indicating document type. Options: 1 (github style), 2 (wiki style)
            - Github mode: First h1 gets up-arrow anchored to #top in TOC;
              doc title extracted from first h1 if not in frontmatter.
            - Wiki mode: All h1s as normal headings in TOC; doc title
              based on filename if not in frontmatter.

    Returns:
        Path to the generated HTML file (same as output_path).

    Raises:
        FileExistsError: If output_path exists and force is False.
        ValueError: If strict is True and frontmatter is missing required fields.
        Various exceptions from markdown conversion or file I/O.

    Example:
        >>> process_single_file(
        ...     Path("docs/intro.md"),
        ...     Path("dist/intro.html"),
        ...     Path("templates/default.html"),
        ...     Path("assets"),
        ...     Path("dist/assets"),
        ...     force=True,
        ...     strict=False
        ...     )
        PosixPath('dist/intro.html')
    """

    # Read and parse
    raw_content = read_markdown_file(input_path)
    metadata, markdown_content = parse_frontmatter(raw_content)

    # Determine "document type" for TOC styling:
    # - wiki style (multiple h1s) or github style (one h1 with title)
    # - Priority: 1. CLI --mode arg, 2. YAML frontmatter 'type' key, 3. auto-detect based on h1 count
    document_mode = resolve_document_mode(metadata, mode, markdown_content)

    # Extract title (get from YAML frontmatter, markdown if document mode, or filename if wiki mode)
    title = extract_title(metadata, markdown_content, document_mode, input_path, strict)

    # Extract description for description HTML metadata
    description = extract_description(metadata, strict)

    # merge determined title and description into metadata for HTML formatting
    metadata["title"] = title
    metadata["description"] = description

    # Convert markdown to HTML
    html_content, toc = convert_markdown_to_html(markdown_content, document_mode)

    # Calculate asset path prefix
    asset_path_prefix = get_asset_path_prefix(output_path, final_assets_dir)

    # Render template
    final_html = template_html(
        template_path,
        html_content,
        metadata,
        toc,
        asset_path_prefix,
    )

    # Write output
    write_html_file(final_html, output_path, force)

    return output_path


def process_all_files(
    md_files_mapping: Dict[Path, Path],
    template_path: Path,
    assets_path: Path,
    final_assets_dir: Path,
    force: bool,
    strict: bool,
    mode: int,
) -> List[Path]:
    """
    Process all markdown files from a mapping dictionary.

    Iterates through each (input_path, output_path) pair and calls
    process_single_file(). Handles error aggregation and optional fast-fail
    when strict mode is enabled. Copies assets to the output directory once
    after all files are processed.

    Args:
        md_files_mapping: Dictionary mapping source markdown files to their
            destination HTML paths. Typically created by build_file_mapping().
        template_path: Path to the HTML template file (passed to each file).
        assets_path: Path to the source assets directory (css/, js/).
        final_assets_dir: Path where assets will be copied in the output
            directory (e.g., dist/assets/).
        force: If True, overwrite existing output files. If False, raise
            FileExistsError when output already exists.
        strict: If True, abort on first error and re-raise the exception.
            If False, log errors and continue processing remaining files.
        mode: int indicating document type. Options: 1 (github style), 2 (wiki style)
            - Github mode: First h1 gets up-arrow anchored to #top in TOC;
              doc title extracted from first h1 if not in frontmatter.
            - Wiki mode: All h1s as normal headings in TOC; doc title
              based on filename if not in frontmatter.

    Returns:
        List of successfully generated HTML file paths.

    Note:
        Assets are copied once after all files are processed, not per file.
        This assumes all HTML files share the same assets directory, which
        is true for the current design.

    Example:
        >>> mapping = {
        ...     Path("docs/intro.md"): Path("dist/intro.html"),
        ...     Path("docs/guide.md"): Path("dist/guide.html"),
        ... }
        >>> process_all_files(mapping, Path("template.html"), Path("assets"),
        ...                   Path("dist/assets"), force=True, strict=False)
        [PosixPath('dist/intro.html'), PosixPath('dist/guide.html')]
    """

    if not md_files_mapping:
        return []

    output_paths = []
    failed_count = 0

    for md_file, file_output_path in md_files_mapping.items():
        try:
            output_file = process_single_file(
                md_file,
                file_output_path,
                template_path,
                assets_path,
                final_assets_dir,
                force,
                strict,
                mode,
            )
            output_paths.append(output_file)
        except Exception as e:
            logger.error(f"   ❌ Failed: {md_file} - {e}")
            failed_count += 1
            if strict:
                raise  # Fail fast in strict mode

    # Copy assets once after all files processed (or before, doesn't matter)
    copy_assets_to_output(assets_path, final_assets_dir, force)

    logger.info(f"\n✅ Processed {len(output_paths)} of {len(md_files_mapping)} files")
    if failed_count > 0 and not strict:
        logger.error(f"   ⚠️  {failed_count} file(s) failed")

    return output_paths


def build_file_mapping(
    input_path: Path, output_dir: Path, recursive: bool
) -> Dict[Path, Path]:
    """
    Build a mapping from source markdown files to their output HTML paths.

    Accepts either a single file or a directory. For a directory, discovers
    all markdown files (respecting recursive flag, excluding symlinks and
    hidden directories) and preserves the directory structure in the output.

    Args:
        input_path: Path to either a single .md file or a directory
            containing .md files.
        output_dir: Base output directory (e.g., "dist/"). Output paths
            preserve subdirectory structure relative to input_path.
        recursive: If True and input_path is a directory, search
            subdirectories recursively. If False, only top-level files.
            Ignored when input_path is a single file.

    Returns:
        Dictionary mapping each source markdown file (Path) to its
        corresponding output HTML path (Path).

    Raises:
        SystemExit: If input_path does not exist.

    Example:
        >>> mapping = build_file_mapping(
        ...     Path("docs/"), Path("dist/"), recursive=True
        ... )
        >>> mapping[Path("docs/getting-started/install.md")]
        PosixPath('dist/getting-started/install.html')

    Note:
        For single-file input, output_dir is treated as the destination
        directory, and the output filename is derived from the input
        filename with .html extension.
    """

    md_files_mapping = {}
    md_files = []
    input_dir = None
    if input_path.is_file():
        # Single file mode
        md_files = [input_path]
        input_dir = input_path.parent
    elif input_path.is_dir():
        # Batch mode
        input_dir = input_path

        # Discover markdown files
        md_files = discover_markdown_files(input_dir, recursive)

        if not md_files:
            logger.warning(f"⚠️  No markdown files found in {input_dir}")

        logger.info(f"\n📁 Found {len(md_files)} markdown file(s) to process")
    else:
        logger.error(f"❌ Error: Input path does not exist: {input_path}")
        sys.exit(1)

    # Create mapping of input md file -> output path

    for md_file in md_files:
        # Compute relative path from input_dir
        rel_path = md_file.relative_to(input_dir)
        # Change extension from .md to .html
        rel_html = rel_path.with_suffix(".html")
        # Build output path preserving directory structure
        file_output_path = output_dir / rel_html
        # create input / output mapping
        md_files_mapping[md_file] = file_output_path

    return md_files_mapping


# ============================================================================
# INDEX PAGE GENERATION
# ============================================================================


def generate_index_page(
    output_dir: Path,
    file_mapping: Dict[Path, Path],
    index_path: Path,
    template_path: Path,
    final_assets_dir: Path,
    force: bool,
) -> Path:
    """
    Generate an index page linking to all processed markdown files.

    Builds a nested directory tree from the file mapping, extracts link text
    from each markdown file (frontmatter title or filename), and renders an
    HTML index page using the shared template.

    Args:
        output_dir: Base output directory (e.g., Path("dist/")).
        file_mapping: Dictionary mapping source markdown files to their
            output HTML paths. Typically from build_file_mapping().
        index_path: Full path where index.html will be written.
        template_path: Path to the HTML template file.
        final_assets_dir: Path to assets directory in output
            (e.g., Path("dist/assets/")).
        force: If True, overwrite existing index.html.

    Returns:
        Path to the generated index.html file.

    Example:
        >>> generate_index_page(
        ...     Path("dist/"),
        ...     {Path("docs/intro.md"): Path("dist/intro.html")},
        ...     Path("dist/index.html"),
        ...     Path("templates/default.html"),
        ...     Path("dist/assets/"),
        ...     force=True
        ...     )
        PosixPath('dist/index.html')
    """

    logger.info(f"\n📑 Create index page linking to all generated docs...")
    # Build tree structure
    tree = {}
    for md_file, html_path in file_mapping.items():
        # Get relative path from output_dir
        rel_path = html_path.relative_to(output_dir)
        parts = list(rel_path.parent.parts)
        filename = rel_path.name

        # Get link text
        link_text = _get_link_text(md_file)

        # Navigate/create tree
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[filename] = link_text

    # Render HTML
    index_content = _render_tree(tree, output_dir)

    # Calculate asset path prefix
    asset_path_prefix = get_asset_path_prefix(index_path, final_assets_dir)

    # Create dummy YAML frontmatter for templating
    metadata = {
        "title": "Documentation Index",
        "description": "Index of generated documentation",
    }

    # Reuse template
    final_html = template_html(
        template_path,
        index_content,
        metadata,
        "",  # Empty TOC
        asset_path_prefix,
    )

    write_html_file(final_html, index_path, force)

    return index_path


def _get_link_text(md_file: Path) -> str:
    """
    Extract display title from markdown file for index page links.

    Priority:
        1. 'title' field from YAML frontmatter (if present)
        2. Filename stem (e.g., "getting-started" from "getting-started.md")

    Args:
        md_file: Path to markdown file.

    Returns:
        Display title string.

    Example:
        >>> _get_link_text(Path("docs/intro.md"))
        'Getting Started'  # from frontmatter title: "Getting Started"
        >>> _get_link_text(Path("docs/config.md"))
        'config'  # no frontmatter, falls back to filename
    """
    raw = read_markdown_file(md_file)
    metadata, _ = parse_frontmatter(raw)
    return metadata.get("title", md_file.stem)


def _render_tree(tree: dict, base_path: Path = Path("")) -> str:
    """
    Recursively render a directory tree as nested HTML <ul> elements.

    This function traverses the tree dictionary and generates semantic HTML
    with proper indentation. Directories are rendered as <li> with a folder
    span, containing a nested <ul> of their children. Files are rendered as
    <li> with an <a> link.

    Args:
        tree: Nested dictionary where:
            - Keys are directory names or filenames
            - Values are either:
                - Another dict (for directories)
                - A string (link text for files)
        base_path: Path object for building hrefs (used recursively).
            Defaults to empty Path, which resolves to current directory.

    Returns:
        HTML string with nested <ul> structure, with href backslashes escaped.

    Example:
        >>> tree = {
        ...     "getting-started": {
        ...         "install.html": "Installation Guide",
        ...         "quickstart.html": "Quick Start"
        ...     },
        ...     "intro.html": "Introduction"
        ... }
        >>> _render_tree(tree)
        '<ul class="index-tree"><li><span class="index-folder">getting-started/</span><ul><li><a href="getting-started/install.html">Installation Guide</a></li><li><a href="getting-started/quickstart.html">Quick Start</a></li></ul></li><li><a href="intro.html">Introduction</a></li></ul>'

    Note:
        This function is recursive. For large directory trees (1000+ files),
        recursion depth may be a concern, but typical documentation sites
        have shallow nesting (2-4 levels).
    """
    if not tree:
        return ""

    html = '<ul class="index-tree">'

    for key, value in sorted(tree.items()):
        if isinstance(value, dict):
            # Directory: render folder name, then recurse into children
            html += f'  <li><span class="index-folder">{key}/</span>'
            html += _render_tree(value, base_path / key)
            html += "  </li>"
        else:
            # File: render link with href from base_path and key
            href = str(base_path / key)
            html += f'  <li><a href="{href}">{value}</a></li>'

    html += "</ul>"
    return html


# ============================================================================
# MAIN
# ============================================================================


def main():

    # Handle --version before argparse because:
    # 1. --version should exit without requiring the 'input' argument
    # 2. argparse's required argument validation would otherwise reject this call
    # 3. Reading version from installed package metadata ensures a single source of truth
    #    (the version in pyproject.toml) without duplication or sync issues
    if "--version" in sys.argv or "-v" in sys.argv:
        try:
            from importlib.metadata import version as get_version

            __version__ = get_version("renderkind")
        except ImportError:
            __version__ = (
                "unknown"  # Fallback when running outside an installed package
            )
        print(f"renderkind {__version__}")
        return

    # help string to add to path arguments
    path_help = (
        "Relative paths are resolved relative to the current working directory "
        "(not necessarily this script's dir)."
    )

    parser = argparse.ArgumentParser(
        description="Generate a static HTML page from Markdown which includes navigation and theme selection.",
        epilog="Example: renderkind input.md --output index.html --template templates/default_template.html --force",
    )
    parser.add_argument(
        "input",
        type=Path,
        help=f"Path to the Markdown input file (e.g., input.md). {path_help}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=False,
        default="dist",
        help=f"Path to output dir (e.g., dist). {path_help}",
    )
    parser.add_argument(
        "--assets",
        type=Path,
        required=False,
        default=DEFAULT_ASSETS,
        help=f"Path to assets directory (e.g., assets). {path_help}",
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=False,
        default=DEFAULT_TEMPLATE,
        help=f"Path to template file (e.g., templates/default_template.html). {path_help}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file if it exists",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete output directory before processing (requires --force)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require 'title' and 'description' in frontmatter (exits with error if missing)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Process only top-level directory (do not recurse into subdirectories)",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip index page generation in batch mode",
    )
    parser.add_argument(
        "--index-name",
        type=str,
        default="index.html",
        help="Custom filename for index page (default: index.html)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["auto", "github", "wiki"],
        default="auto",
        help="Document mode: auto (detect), github (single h1 -- doc title), wiki (multiple h1s)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all non-error output (useful for scripting)",
    )

    args = parser.parse_args()

    # Setup logging before any script logic
    setup_logging(quiet=args.quiet)

    # Resolve all paths to absolute (handles relative, symlinks, etc.)
    # rel paths will be evaluated rel callers cwd, NOT script dir
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    template_path = args.template.resolve()
    assets_path = args.assets.resolve()

    # standardize document mode
    if not args.mode in MODE_MAPPING:
        raise ValueError(
            f"Bug: --mode passed argparse validation, but not valid via MODE_MAPPING:\n\tValid: {', '.join(list(MODE_MAPPING.keys()))}\n\tGiven: {args.mode}"
        )
    document_mode = MODE_MAPPING[args.mode]

    # delete output dir if exists and --clean provided
    if args.clean:
        if not args.force:
            logger.error("❌ Error: --clean requires --force")
            sys.exit(1)
        if output_path.exists():
            shutil.rmtree(output_path)
            logger.info(f"🧹 Cleaned output directory: {output_path}")

    try:
        # Collect input markdown files
        # (returns dict of <input md Path> -> <output Path>)
        md_files_mapping = build_file_mapping(
            input_path, output_path, not args.no_recursive
        )

        # Final assets directory (shared across all files)
        final_assets_dir = output_path / "assets"

        # Process all the files
        process_all_files(
            md_files_mapping,
            template_path,
            assets_path,
            final_assets_dir,
            args.force,
            args.strict,
            document_mode,
        )

        # Generate index page (batch mode only, not --no-index)
        if not args.no_index and input_path.is_dir():
            index_path = output_path / args.index_name
            generate_index_page(
                output_path,
                md_files_mapping,
                index_path,
                template_path,
                final_assets_dir,
                args.force,
            )

    except FileNotFoundError as e:
        logger.error(f"\n❌ Error:\n{e}\n")
        sys.exit(1)
    except FileExistsError as e:
        logger.error(f"\n⚠️  Error:\n{e}\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
