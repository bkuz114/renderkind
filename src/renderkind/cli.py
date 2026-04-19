#!/usr/bin/env python3
"""
Generate a convenient-to-navigate, customizable, static HTML page from Markdown.

Usage:
    renderkind INPUT [--output] [--template] [--force] [--strict]

Example:
    renderkind \
            input.md.md \
            dist/index.html \
            templates/default_template.html \
            --force

Dependencies:
    pip install markdown beautifulsoup4 yaml

Output:
    html file specified at path OUTPUT (only this file is generated)

CSS/JS are static files you maintain separately in css/ and js/ directories.
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

# ============================================================================
# LOGGING
# ============================================================================


# Setup basic logging (called once in main)
def setup_logging(quiet: bool = False):
    """Configure logging based on quiet flag."""
    level = logging.WARNING if quiet else logging.INFO
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


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Full markdown string

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


def extract_data_from_frontmatter(
    metadata: dict, md_content: str, strict: bool
) -> Tuple[str, str]:
    """
    Extracts title and description values from parsed YAML frontmatter.

    Args:
        metadata: dict of key/values extracted from yaml markdown (see parse_frontmatter)
        md_content: raw markdown from markdown file (for logging only)
        strict: boolean that requires keys to exist in metadata else throws ValueError

    Returns:
        Tuple (
            extracted title [falls back to first h1, then "Untitled Document"],
            extracted description [falls back to nothing]
        )

    Raises:
        ValueError: If strict and metadata is None (means there was no metadata found)
        ValueError: If strict and no title in metadata
        ValueError: If strict and no description in metadata
    """

    # Strict validation
    if strict and not metadata:
        raise ValueError("--strict: No frontmatter found in markdown file")

    # Extract or validate title
    title = metadata.get("title")
    if not title:
        if strict:
            raise ValueError("--strict: 'title' field required in frontmatter")
        else:
            # Extract title from markdown as fallback
            title = extract_title_from_markdown(md_content)
            if title:
                logger.warning(f"⚠️  Warning: No 'title' in frontmatter.")
                logger.warning(f'    Using first h1 as title: "{title}"')
                logger.warning(f"    This fallback will be deprecated in v2.0.")
                logger.warning(f'    Add frontmatter: title: "{title}"')
            else:
                title = "Untitled Document"
                logger.warning(
                    f"⚠️  Warning: No 'title' in frontmatter and no h1 found."
                )
                logger.warning(f'    Using fallback: "{title}"')
                logger.warning(f'    Add frontmatter: title: "{title}"')

    # Extract description
    description = metadata.get("description", "")
    if not description:
        if strict:
            raise ValueError("--strict: 'description' field required in frontmatter")
        else:
            logger.warning(f"ℹ️  Info: No 'description' in frontmatter.")
            logger.warning(
                f"    <meta name='description'> will be empty. SEO may be affected."
            )

    return title, description


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


def extract_title_from_markdown(markdown: str) -> str:
    """
    Extract the first h1 from markdown file.

    Args:
        markdown: string content of an .md file

    Returns:
        Title text (without '# ' prefix) or fallback string

    Example:
        Given first line '# Cleaning Chemistry'
        Returns 'Cleaning Chemistry'
    """
    fallback = "Untitle Document"
    if not markdown:
        return fallback

    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()

    return fallback


def render_toc(toc_entries: List[Dict], current_depth: int = 1) -> str:
    """
    Render TOC entries as nested HTML list.

    Args:
        toc_entries: List of dicts with 'level', 'text', 'id' keys
        current_depth: Starting depth (default 1, for h1)

    Returns:
        Tuple of (
            HTML string of nested <ul> and <li> elements,
            string page anchor based on h1; defaults to "#top" if no h1
        )

    Note:
        This function uses recursion to handle nested heading levels.
        h1 is rendered as a special "Back to top" link.
    """
    if not toc_entries:
        return ""

    # Filter to only include entries at or below max depth
    entries = [e for e in toc_entries if e["level"] <= TOC_MAX_DEPTH]

    # anchor to top of page (default to #top)
    top_anchor = "#top"

    html = '<ul class="toc-list">\n'

    for entry in entries:
        level = entry["level"]
        text = entry["text"]
        anchor_id = entry["id"]

        if level == 1:
            # Special case: h1 as "Back to top"
            top_anchor = f"#{anchor_id}"
            html += (
                f'  <li><a href="{top_anchor}" class="toc-level-h1">↑ {text}</a></li>\n'
            )
        else:
            level_class = f"toc-level-h{level}"
            html += (
                f'  <li><a href="#{anchor_id}" class="{level_class}">{text}</a></li>\n'
            )

    html += "</ul>\n"
    return html, top_anchor


def convert_markdown_to_html(md_content: str) -> Tuple[str, str, str]:
    """
    Convert Markdown file to HTML using python-markdown.

    Args:
        md_content: extracted markdown content from .md file (should NOT include YAML frontmatter)

    Returns:
        Tuple: (
            HTML string with heading IDs added,
            HTML TOC string,
            string of anchor to top of page i.e. "#top"
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
    toc_html, top_anchor = render_toc(toc_entries)

    return str(soup_with_ids), toc_html, top_anchor


def template_html(
    template_path: Path,
    title: str,
    description: str,
    content: str,
    toc_html: str,
    top_anchor: str,
    asset_path_prefix: str,
) -> str:
    """
    Embed converted markdown content into template file.

    Args:
        template_path: Path to the template .html file.
        title: document title to embed at {{title}} placeholder
        description: document description to embed at {{description}} placeholder
        content: string of content to embed at {{content}} placeholder
        toc: string of content to embed at {{toc}} placeholder
        top_anchor: string (an anchor to top of page) to embed at {{anchor_top}} placeholder

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
        "title": title,
        "description": description,
        "toc": toc_html,
        "anchor-top": top_anchor,
        "asset_path_prefix": asset_path_prefix,
    }

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
    title, description = extract_data_from_frontmatter(
        metadata, markdown_content, strict
    )

    # Convert markdown to HTML
    html_content, toc, top_anchor = convert_markdown_to_html(markdown_content)

    # Calculate asset path prefix
    asset_path_prefix = get_asset_path_prefix(output_path, final_assets_dir)

    # Render template
    final_html = template_html(
        template_path,
        title,
        description,
        html_content,
        toc,
        top_anchor,
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

    # Reuse template
    final_html = template_html(
        template_path,
        "Documentation Index",
        "Index of generated documentation",
        index_content,
        "",  # Empty TOC
        "",
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

    For Windows paths, backslashes in href attributes are doubled to prevent
    them from being interpreted as escape sequences by re.sub() during
    template rendering.

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
            # escape backslashes in href for Windows paths
            href_escaped = href.replace("\\", "\\\\")
            html += f'  <li><a href="{href_escaped}">{value}</a></li>'

    html += "</ul>"
    return html


# ============================================================================
# MAIN
# ============================================================================


def main():

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
            logger.info(f"📑 Generated index: {index_path}")

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
