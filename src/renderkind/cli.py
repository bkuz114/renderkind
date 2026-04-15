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
# HELPER FUNCTIONS
# ============================================================================


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
        print(f"⚠️  Warning: Malformed frontmatter YAML: {e}", file=sys.stderr)
        print("   Ignoring frontmatter and continuing.", file=sys.stderr)
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
    if title:
        print(f"   Title from frontmatter: {title}")
    elif strict:
        raise ValueError("--strict: 'title' field required in frontmatter")
    else:
        # Extract title from markdown as fallback
        title = extract_title_from_markdown(md_content)
        if title:
            print(f"⚠️  Warning: No 'title' in frontmatter.", file=sys.stderr)
            print(f'    Using first h1 as title: "{title}"', file=sys.stderr)
            print(f"    This fallback will be deprecated in v2.0.", file=sys.stderr)
            print(f'    Add frontmatter: title: "{title}"', file=sys.stderr)
        else:
            title = "Untitled Document"
            print(
                f"⚠️  Warning: No 'title' in frontmatter and no h1 found.",
                file=sys.stderr,
            )
            print(f'    Using fallback: "{title}"', file=sys.stderr)
            print(f'    Add frontmatter: title: "{title}"', file=sys.stderr)

    # Extract description
    description = metadata.get("description", "")
    if description:
        print(f"   Description from frontmatter: {description}")
    elif strict:
        raise ValueError("--strict: 'description' field required in frontmatter")
    else:
        print(f"ℹ️  Info: No 'description' in frontmatter.", file=sys.stderr)
        print(
            f"    <meta name='description'> will be empty. SEO may be affected.",
            file=sys.stderr,
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
    assets_path: Path, output_path: Path, force: bool = False
) -> Path:
    """
    Copy the assets directory to the output file's parent directory.

    This function copies the entire assets directory (including all contents)
    to the same directory where the output file will live. This ensures that
    relative asset references (e.g., `assets/css/styles.css`) resolve correctly
    when the output file is opened in a browser.

    Args:
        assets_path: Path to the source assets directory.
        output_path: Path to the output directory. assets will be copied here.
        force: If True, overwrite existing assets directory; if False, raise
               error if destination already exists.

    Returns:
        Path to the copied assets directory within the output directory.

    Raises:
        FileNotFoundError: If assets_path or output_path do not exist.
        NotADirectoryError: If assets_path or output_path is not a directory.
        FileExistsError: If assets destination exists and force is False.
        OSError: For other file operation errors (permissions, disk full, etc.).

    Examples:
        >>> from pathlib import Path
        >>> assets = Path("/project/assets")
        >>> output = Path("/project/output")
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

    if not output_path.exists():
        raise FileNotFoundError(f"Output path does not exist: {output_path}")

    if not output_path.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {output_path}")

    # Determine destination: output directory + assets directory name
    assets_dest_dir = output_path / assets_path.name

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

    # return final assets path within output dir
    return assets_dest_dir


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
        f.write(content)


def create_output(
    content: str, output_dir: Path, assets_dir: Path, force: bool
) -> Path:
    """
    Writes final HTML file to dedicated output dir and copies assets
    to that directory to resolve <script> and <link> paths.

    Args:
        content: Final HTML string.
        output_dir: output directory to write index.html in and copy assets into
        assets_dir: path to assets directory
        force: Whether to overwrite existing file.

    Returns:
        Path to index.html file that is written, if successful
    """

    # path to final index.html
    index_path = output_dir / "index.html"

    # create index.html in output dir
    write_html_file(content, index_path, force)
    # copy assets directory to output dir so js and css paths will resolve in browser
    final_assets_dir = copy_assets_to_output(assets_dir, output_dir, force)

    # return path to index.html for final logging
    return index_path


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
        "--strict",
        action="store_true",
        help="Require 'title' and 'description' in frontmatter (exits with error if missing)",
    )

    args = parser.parse_args()

    # Resolve all paths to absolute (handles relative, symlinks, etc.)
    # rel paths will be evaluated rel callers cwd, NOT script dir
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    template_path = args.template.resolve()
    assets_path = args.assets.resolve()

    try:
        print(f"\n📖 Reading markdown file: {input_path}")
        raw_content = read_markdown_file(input_path)

        print("📦 Parsing YAML frontmatter")
        metadata, markdown_content = parse_frontmatter(raw_content)

        print("🔑 Extract title and description from metadata...")
        title, description = extract_data_from_frontmatter(
            metadata, markdown_content, args.strict
        )

        print("🔄 Converting markdown to HTML...")
        html_content, toc, top_anchor = convert_markdown_to_html(markdown_content)

        print(f"🔧 Template content")
        final_html = template_html(
            template_path, title, description, html_content, toc, top_anchor
        )

        print(f"📝 Writing output: {output_path}")
        index_path = create_output(final_html, output_path, assets_path, args.force)

        print(f"\n✅ Done! Generated: {index_path}")

    except FileNotFoundError as e:
        print(f"\n❌ Error:\n{e}\n")
        sys.exit(1)
    except FileExistsError as e:
        print(f"\n⚠️  Error:\n{e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
