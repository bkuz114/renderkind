# md2html

A markdown to HTML converter with YAML frontmatter, build-time table of contents, and customizable templates.

## Features

- **YAML frontmatter** – Title, description, and extensible metadata
- **Build-time TOC** – Table of contents generated from headings (h1-h4)
- **Responsive default template** – Fixed header, collapsible TOC panel, color theme support
- **Customizable** – Bring your own templates, CSS, and JavaScript
- **No runtime dependencies** – Pure HTML output works offline
- **Strict mode** – Validate frontmatter requirements (CI/CD friendly)

## Installation

### As a submodule (recommended for projects)

```bash
git submodule add https://github.com/bkuz114/md2html.git libs/md2html
```

### As a standalone script

```bash
git clone --recursive https://github.com/bkuz114/md2html.git
cd md2html
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Usage

```bash
python md2html.py INPUT_MD_FILE [--output output_file] [--template template_file] [--force] [--strict]
```

### Basic usage

Generates `index.html` in cwd from `input.md`, using template file `templates/default_template.html`

```bash
python md2html.py input.md
```

### With output file specified

```bash
python md2html.py input.md --output generated.html
```

### With force overwrite

```bash
python md2html.py input.md --force
```

### With strict validation (requires title and description in input.md frontmatter)

```bash
python md2html.py input.md --strict
```

### With custom template

```bash
python md2html.py input.md --template path/to/custom.html
```

### Show version

```bash
python md2html.py --version
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

The script passes all frontmatter fields to the template. Add custom fields as needed:

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
- Dark mode toggle (via external `darkMode.js` or your own implementation)
- Print stylesheet

You can override it with `--template` or replace the default file.

## CSS and JavaScript

The default template links to `css/styles.css` and `js/scripts.js`. These files are **not** required – you can provide your own or modify the template to link to different paths.

### Default CSS features

- Light/dark mode via CSS variables
- Responsive grid for card layouts
- Table zebra striping
- Code block styling
- Print-friendly styles

### Default JavaScript features

- TOC panel toggle (open/close)
- Smooth scroll to anchors
- Responsive behavior for mobile
- Table wrapper for horizontal scroll

## Output Path and Assets

The generated HTML assumes CSS/JS are in `css/styles.css` and `js/scripts.js`
relative to the HTML file's location.

**To avoid broken paths:**
- Write output to current directory (or use default): `md2html.py guide.md --output index.html`
- Or copy the `css/` and `js/` directories to your output location

**Example with custom output:**
```bash
md2html.py guide.md --output dist/index.html
cp -r css js dist/
```

## Examples

### Basic markdown (no frontmatter)

```bash
python md2html.py examples/basic.md
```

### With frontmatter and custom template

```bash
python md2html.py examples/with-frontmatter.md --template my-template.html
```

See the `examples/` directory for complete working examples.

## Requirements

- Python 3.8 or higher
- `markdown` – Markdown parsing
- `beautifulsoup4` – Heading ID generation
- `pyyaml` – YAML frontmatter parsing

Install all dependencies with:

```bash
pip install -r requirements.txt
```

## Project Structure

```
md2html/
├── md2html.py                    # Main script
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── LICENSE
├── CHANGELOG.md
├── assets/
│   ├── css/
│   │   └── styles.css            # Default styles (optionsl)
│   ├── js/
│   │   └── scripts.js            # Default JavaScript (optional)
├── libs/                         # Git submodules (to move to assets/libs/)
│   ├── themePicker/              # Theme selection submodule
│   └── template_utils/           # Submodule for template rendering
├── templates/
│   └── default_template.html    # Default HTML template
└── examples/
    ├── basic.md
    ├── with-frontmatter.md
    └── with-custom-template.md
```

## Customization Guide

### Using your own template

1. Copy `templates/default_template.html` to your project
2. Modify as needed (keep `{{placeholder}}` syntax)
3. Use `--template path/to/your-template.html`

### Using your own CSS/JS

Modify the template's `<link>` and `<script>` tags to point to your files.

### Adding frontmatter fields

Add fields to your markdown frontmatter, then use `{{field_name}}` in your template.

## Development

### Running tests

```bash
python -m pytest tests/  # (when tests are added)
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
- Template rendering via [template_utils](https://github.com/bkuz114/template_utils)
- Theme selection via [themePicker](https://github.com/bkuz114/themePicker)

---

**Created for developers who want clean, maintainable documentation.**
