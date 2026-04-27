# renderkind

[![PyPI version](https://badge.fury.io/py/renderkind.svg)](https://pypi.org/project/renderkind/)
[![Python versions](https://img.shields.io/pypi/pyversions/renderkind.svg)](https://pypi.org/project/renderkind/)

> **Lightweight, offline-first markdown to HTML. Built with kindness.**

A markdown to HTML converter with YAML frontmatter, build-time table of contents, and customizable templates. The generated output is fully self-contained, works entirely offline, and is designed with the end user's experience in mind.

## Quickstart

```bash
# Install
pip install renderkind

# Convert a markdown file
renderkind input.md

# Output to a specific directory
renderkind input.md --output dist/

# See all options
renderkind --help
```

That's it. No submodules, no manual dependency installation, no external CDNs. Just your content, rendered well.

## Features

- **Single file or batch processing** – Convert individual files or entire directories
- **YAML frontmatter** – Title, description, and extensible metadata
- **Build-time TOC** – Table of contents generated from headings (h1-h4)
- **Automatic index page** – Navigable directory tree for batch output
- **Wiki mode support** – Perfect for personal notes and knowledge bases with multiple # headings
- **Arbitrary frontmatter** – Any YAML field becomes a {{ placeholder }} in templates
- **Responsive default template** – Fixed header, collapsible TOC panel, dark mode support
- **Smart asset handling** – Assets copied once, paths resolved at any depth
- **Customizable** – Bring your own templates, CSS, and JavaScript
- **No runtime dependencies** – Pure HTML output works offline
- **Strict mode** – Validate frontmatter requirements (CI/CD friendly)
- **Clean builds** – `--clean` flag for fresh output directories
- **Quiet mode** – Suppress output for scripting

## Installation

### Via pip (recommended)

```bash
pip install renderkind
```

Requirements: Python 3.9 or higher. All dependencies are installed automatically.

### From source (for development)

```bash
git clone https://github.com/bkuz114/renderkind.git
cd renderkind
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e .
```

## Usage

```bash
renderkind INPUT [--output OUTPUT_DIR] [--template TEMPLATE_FILE] [--force] [--strict] [--mode] [--quiet] [--clean] [--no-recursive] [--no-index] [--index-name NAME]
```

### Basic Usage

#### Single file mode

Process a single markdown file (outputs to `dist/index.html`):

```bash
renderkind docs/intro.md
```

#### Batch mode (directory)

Process all markdown files in a directory, preserving nested structure:

```bash
renderkind docs/
```

Output structure:
```
dist/
├── index.html              # Auto-generated index page
├── intro.html
├── getting-started/
│   ├── install.html
│   └── quickstart.html
└── assets/                 # Copied automatically
    ├── css/
    └── js/
```

### Output Directory

Specify a custom output directory (default: `dist/`):

```bash
renderkind docs/ --output site/
```

### Index Page Generation

In batch mode, an index page (`index.html`) is automatically generated with a navigable directory tree:

```bash
renderkind docs/
# Generates dist/index.html
```

Disable index generation:

```bash
renderkind docs/ --no-index
```

Use a custom index filename:

```bash
renderkind docs/ --index-name README.html
```

### Wiki mode for personal notes

```bash
# Auto-detect (multiple h1s → wiki mode)
renderkind notes/
```

```bash
# Force wiki mode for personal notes
renderkind notes/ --mode wiki
```

```bash
# Force github-style mode
renderkind notes/ --mode github
```

### File Discovery

Process only top-level files (no subdirectories):

```bash
renderkind docs/ --no-recursive
```

### Overwrite Behavior

Force overwrite of existing output files:

```bash
renderkind docs/ --force
```

Clean output directory before processing (requires `--force`):

```bash
renderkind docs/ --clean --force
```

### Output Verbosity

Suppress all non-error output (useful for scripting or CI/CD):

```bash
renderkind docs/ --quiet
```

### Frontmatter Validation

Require `title` and `description` in frontmatter (exits with error if missing):

```bash
renderkind docs/ --strict
```

### Custom Template

Use a custom HTML template:

```bash
renderkind docs/ --template path/to/custom.html
```

### Show version

```bash
renderkind --version
```

### Show Help

```bash
renderkind --help
```

## Examples

### Single file with custom output

```bash
renderkind docs/intro.md --output build/
# Creates build/index.html
```

### Complete documentation site

```bash
# Process entire docs folder
renderkind docs/ --output site/ --clean --force

# Output:
# site/
# ├── index.html (auto-generated navigation)
# ├── intro.html
# ├── advanced/
# │   └── config.html
# └── assets/
```

### Quiet build for CI/CD

```bash
renderkind docs/ --output site/ --quiet --force
# No output on success (only errors)
```

### Strict mode with custom index name

```bash
renderkind docs/ --strict --index-name README.html
# Requires frontmatter title/description in every file
# Generates site/README.html instead of index.html
```

## Frontmatter

Add YAML frontmatter at the top of your markdown file:

```markdown
---
title: "My Document Title"
description: "A clear description of this document's content"
type: github  # or "wiki"
author: "Your Name"
date: "2024-01-15"
version: "1.0.0"
---

# Optional: Can match title or be different

Document content...
```

### Supported fields

| Field | Required? | Purpose | Fallback if missing |
|-------|-----------|---------|---------------------|
| `title` | No (but recommended) | Document title for `<title>` tag and header | First `# h1` in markdown (with warning) |
| `description` | No | Meta description for SEO | Empty string (with info message) |
| `type` | Document mode (`document` or `wiki`) | Auto-detection (single h1 → document, multiple h1s → wiki) |

### Extending frontmatter

The tool passes all frontmatter fields to the template. Add custom fields as needed:

```markdown
---
title: "My Document"
description: "Document description"
author: "Your Name"
date: "2024-01-15"
version: "1.0.0"
---
```

Then access them in your template: `{{author}}`, `{{date}}`, etc.

## Document Modes

Each .md has a "document mode" indicating how TOC should styled, and how the document title is found -- either "github style" (one `h1` as the document title) or "wiki style" (mutliple `h1`s, none of them being the ttile). Document mode is determined based on how many `h1` headers are found in the markdown file, but can be forced by either YAML frontmatter (`type` field), or cli arg `--mode`.

### Overview

| Mode | Title source | TOC behavior | Best for |
|------|--------------|--------------|----------|
| **Github** | First `# h1` (or frontmatter) | Up-arrow on first h1 only | Blog posts, documentation, articles |
| **Wiki** | Filename (or frontmatter) | No up-arrows on any h1 | Personal notes, wikis, knowledge bases |

### Mode Selection (Priority Order)

1. CLI flag: `--mode github|wiki|auto`
2. Frontmatter `type:` field
3. Auto-detection based on h1 count

## Templates

Templates use `{{placeholder}}` syntax. The following placeholders are provided:

| Placeholder | Description |
|-------------|-------------|
| `{{title}}` | Document title (from frontmatter or fallback) |
| `{{description}}` | Document description (from frontmatter) |
| `{{content}}` | Converted markdown HTML |
| `{{toc}}` | Generated table of contents HTML |
| `{{anchor_top}}` | Anchor ID for "back to top" links (derived from h1) |

### Default template

The default template (`templates/default_template.html`) includes:
- Responsive fixed header
- Collapsible TOC panel (slides from left on desktop, from top on mobile)
- Theme picker dropdown
- Print stylesheet
- **Zero external dependencies** – everything is local and offline

You can override it with `--template` or replace the default file.

## Output Paths and Assets

When you run `renderkind`, the following happens automatically:

1. Output directory is created (default: `dist/`)
2. Assets (`css/`, `js/`, etc.) are copied to `dist/assets/`
3. HTML files are generated with correct relative paths to assets

### Single file mode

```bash
renderkind docs/intro.md --output site/
```

Output:
```
site/
├── index.html              # Generated HTML
└── assets/                 # Copied from source
    ├── css/
    └── js/
```

### Batch mode

```bash
renderkind docs/ --output site/
```

Output:
```
site/
├── index.html              # Auto-generated navigation
├── intro.html
├── getting-started/
│   └── install.html
└── assets/                 # Shared across all HTML files
    ├── css/
    └── js/
```

Asset paths are automatically calculated for nested files:
- `site/index.html` → `assets/css/styles.css`
- `site/getting-started/install.html` → `../assets/css/styles.css`

## CSS and JavaScript

The default template references `assets/css/styles.css` and `assets/js/scripts.js`.

When you run `renderkind`, it automatically copies the `assets/` directory to your output directory (e.g., `dist/assets/`). This makes the generated HTML **self-contained and portable**—you can move or share the output folder anywhere, and everything works. No network requests, no broken paths.

### Customizing assets

To use your own CSS or JavaScript:

1. Create your own `assets/css/` and `assets/js/` directories
2. Modify the template to point to your files, or
3. Replace the default assets in the output directory after generation

### Default CSS features

- 6 color themes via CSS variables
- Responsive grid for card layouts
- Table zebra striping
- Code block styling
- Print-friendly styles

### Default JavaScript features

- TOC panel toggle (open/close)
- Smooth scroll to anchors
- Responsive behavior for mobile
- Table wrapper for horizontal scroll

## Examples

```bash
# Basic markdown (no frontmatter)
renderkind examples/basic.md

# With frontmatter
renderkind examples/with-frontmatter.md

# With custom template
renderkind examples/with-frontmatter.md --template my-template.html

# Full build to dist directory
renderkind docs/index.md --output dist/ --strict

# Auto-detecting document type (multiple h1s → wiki mode)
renderkind notes/

# Force wiki mode
renderkind notes/ --mode wiki

# Force github mode
renderkind notes/ --mode github
```

See the `examples/` directory for complete working examples.

## Requirements

`renderkind` requires Python 3.9 or higher. Dependencies are installed automatically with pip:

- `markdown` – Markdown parsing
- `beautifulsoup4` – Heading ID generation
- `pyyaml` – YAML frontmatter parsing

## Project Structure

```
renderkind/
├── src/renderkind/
│   ├── __init__.py
│   ├── cli.py                 # Main CLI entry point
│   ├── templates/
│   │   └── default_template.html
│   ├── assets/                # Copied to output directory at build time
│   │   ├── css/
│   │   │   └── styles.css
│   │   └── js/
│   │       └── scripts.js
│   └── vendor/                # Vendored dependencies (internal)
├── examples/
│   ├── basic.md
│   ├── with-frontmatter.md
│   └── with-custom-template.md
├── tests/
├── pyproject.toml
└── README.md
```

## Customization Guide

### Using your own template

1. Copy `templates/default_template.html` to your project
2. Modify as needed (keep `{{placeholder}}` syntax)
3. Use `--template path/to/your-template.html`

### Using your own CSS/JS

Modify the template's `<link>` and `<script>` tags to point to your files, or replace the default assets in your output directory.

### Adding frontmatter fields

Add fields to your markdown frontmatter, then use `{{field_name}}` in your template.

## Development

### Running tests

```bash
python -m pytest tests/
```

### Adding features

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Submit a pull request

## Version History

See [CHANGELOG.md](CHANGELOG.md) for details.

## License

MIT License – see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [python-markdown](https://python-markdown.github.io/)
- Vendored utilities from [template_utils](https://github.com/bkuz114/template_utils) and [themePicker](https://github.com/bkuz114/themePicker) (kept offline and dependency-free)

---

**Created for developers who want clean, maintainable documentation. Built with kindness. Works offline. Always.**
