# renderkind

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

- **YAML frontmatter** – Title, description, and extensible metadata
- **Build-time TOC** – Table of contents generated from headings (h1-h4)
- **Fully offline** – No CDNs, no external requests, no tracking. Works anywhere.
- **Self-contained output** – Generated HTML includes all assets; the output directory is portable
- **Responsive default template** – Fixed header, collapsible TOC panel, color theme support
- **Customizable** – Bring your own templates, CSS, and JavaScript
- **Strict mode** – Validate frontmatter requirements (CI/CD friendly)

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
renderkind INPUT_MD_FILE [--output OUTPUT_DIR] [--template TEMPLATE_FILE] [--force] [--strict]
```

### Basic usage

Generates `dist/index.html` in the current working directory from `input.md`:

```bash
renderkind input.md
```

### With output directory specified

```bash
renderkind input.md --output dist/
```

The `dist/` directory will contain `index.html` and a copy of the `assets/` directory.

### With force overwrite

```bash
renderkind input.md --force
```

### With strict validation (requires title and description in frontmatter)

```bash
renderkind input.md --strict
```

### With custom template

```bash
renderkind input.md --template path/to/custom.html
```

### Show version

```bash
renderkind --version
```

## Frontmatter

Add YAML frontmatter at the top of your markdown file:

```markdown
---
title: "My Document Title"
description: "A clear description of this document's content"
---

# Optional: Can match title or be different

Document content...
```

### Supported fields

| Field | Required? | Purpose | Fallback if missing |
|-------|-----------|---------|---------------------|
| `title` | No (but recommended) | Document title for `<title>` tag and header | First `# h1` in markdown (with warning) |
| `description` | No | Meta description for SEO | Empty string (with info message) |

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
