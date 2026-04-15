# Changelog

All notable changes to `renderkind` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-14

### Added
- Initial release as a pip-installable package
- CLI command `renderkind` (replaces direct script execution)
- Automatic copying of `assets/` directory to output location
- Full offline support – no CDNs or external dependencies
- Windows, macOS, and Linux support via cross-platform path handling

### Changed
- **Breaking**: Package renamed from `md2html` to `renderkind`
- **Breaking**: Command changed from `python md2html.py` to `renderkind`
- Installation now via `pip install renderkind` (no submodules or manual setup)
- Vendored internal dependencies instead of git submodules
- Project restructured to `src/` layout for packaging compliance
- Resource access now uses `importlib.resources` with `__file__` fallback for Windows

### Removed
- Direct script execution (`python md2html.py`) – use `renderkind` command instead
- Git submodule dependencies – now vendored internally
- `requirements.txt` – dependencies declared in `pyproject.toml`

### Fixed
- Windows path handling for template and asset discovery
- `MultiplexedPath` conversion issues on Windows

### Security
- No changes – package has no external network dependencies

## [0.1.0] - 2026-04-12

### Added
- Initial release of `md2html` as standalone tool
- YAML frontmatter parsing with `title` and `description` fields
- Build-time table of contents generation (h1-h4 headings)
- Template rendering with `{{ placeholder }}` syntax
- Responsive default template with:
  - Fixed header with TOC toggle
  - Collapsible TOC panel (slide from left on desktop, from top on mobile)
  - Dark mode support (via external `darkMode.js` or custom implementation)
  - Print stylesheet
- CLI flags:
  - `--output` - Specify custom output path (defaults to `./index.html`)
  - `--force` – Overwrite existing output file
  - `--strict` – Require `title` and `description` in frontmatter
  - `--template` – Specify custom HTML template (defaults to `templates/default_template.html`)
- Markdown extensions:
  - Tables (`tables`)
  - Fenced code blocks (`fenced_code`)
  - Smart quotes and dashes (`smarty`)
  - Markdown inside HTML blocks (`md_in_html`)
- Graceful fallbacks:
  - Title from first `# h1` if no frontmatter `title` (with deprecation warning)
  - Empty description if no frontmatter `description` (with info message)
- Submodule support for `themePicker` (theme rendering library)
- Submodule support for `template-utils` (template rendering library)
- Example markdown files in `examples/` directory
- Documentation:
  - README with installation, usage, and customization guide
  - CHANGELOG (this file)
  - MIT License

### Deprecated
- Title fallback to first `# h1` – will be removed in v2.0. Use frontmatter `title:` instead.

### Known Issues
- None for this release

## [Unreleased]

### Planned
- Favicon.ico support
- Additional template options
- Watch mode for automatic rebuilds
- User-defined output filename (beyond `index.html`)

---

[0.1.0]: https://github.com/bkuz114/md2html/releases/tag/v0.1.0
