# Changelog

All notable changes to `renderkind` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (Placeholder for future changes)

## [0.3.0] - 2026-04-19

### Added

#### Batch Processing (Phase 2)
- Process entire directories of markdown files with preserved structure
- `--no-recursive` flag for top-level only processing
- Intelligent file discovery: excludes symlinks (with warning) and hidden directories (`.git/`, `.venv/`)
- Preserves nested directory hierarchy in output (e.g., `docs/getting-started/install.md` → `dist/getting-started/install.html`)

#### Index Page Generation (Phase 5)
- Automatic `index.html` generation in batch mode (creates navigable directory tree)
- `--no-index` flag to disable index generation
- `--index-name` flag for custom filename (e.g., `--index-name README.html`)
- Link text from frontmatter `title` field (falls back to filename stem)
- Directory tree rendered as nested HTML `<ul>` lists
- Windows path backslash escaping for `re.sub()` safety

#### Asset Path Resolution (Phase 1)
- Proper relative path calculation for HTML files at any directory depth
- `get_asset_path_prefix()` handles cousin paths using `os.path.relpath()`
- Assets copied once to output directory, referenced correctly at all depths (e.g., `dist/getting-started/install.html` → `../assets/css/styles.css`)

#### CLI Enhancements
- `--clean` flag: deletes entire output directory before processing (requires `--force`)
- `--quiet` flag: suppresses all non-error output using Python's logging module
- `--no-index` flag: skip index page generation in batch mode
- `--index-name` flag: custom index filename (default: `index.html`)

#### Logging Infrastructure
- Replaced `print()` statements with Python's `logging` module
- Centralized verbosity control via `--quiet`
- Errors and warnings always visible regardless of quiet mode
- Extensible for future `--verbose` flag (DEBUG level)

### Changed

- `INPUT` Can now be **either a single file or a directory**.
- Output filename based on input file: `test.md` -> `dist/test.html` (in previous single-mode only release, output was always `index.html`)
- Output specs:
  - Single file mode: output is `dist/input_filename.html` (use `--output` to change directory)
  - Batch mode: output preserves input directory structure under `--output`
- Console output reduced (one line per file in normal mode); python logging now used (default loglevel = `logging.WARNING`); use `--quiet` to suppress all stdout (warning and error will be printed)

### Fixed

- Windows path backslash escaping in index page hrefs (prevents `re.error: bad escape sequence`)
- Cousin path resolution for assets (e.g., `dist/getting-started/` to `dist/assets/`)
- Symlink handling: skipped with warning (no longer causes errors)
- Hidden directory traversal: files inside `.git/`, `.venv/`, etc., are now excluded

### Deprecated

- None in this release

### Security

- No security-related changes in this release

### Performance

- Batch mode: linear time complexity (files × processing time)
- Asset copying: once per batch (not per file)
- Index generation: reads each markdown file once for title extraction (acceptable for documentation-scale projects)

### Compatibility

- Python 3.9+
- Windows, macOS, Linux
- Offline operation (no external network requests)
- `file://` protocol support (no web server required)

### Migration Notes

**Upgrading from v0.2.0 to v0.3.0:**

1. Output files now based on input filename (previously, always `index.html`)
   ```bash
   # v0.2.0
   renderkind test.md
   # Output written to dist/index.html

   # v0.3.0
   renderkind test.md
   # Output written to dist/test.html
   ```

2. For batch processing, use directory input:
   ```bash
   renderkind docs/
   ```

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

### Planned
- Favicon.ico support
- Additional template options
- Watch mode for automatic rebuilds
- User-defined output filename (beyond `index.html`)

---

[0.1.0]: https://github.com/bkuz114/md2html/releases/tag/v0.1.0
