# Changelog

All notable changes to `renderkind` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (Placeholder for future changes)

## [0.4.0] - 2026-04-26

### Added

- **Arbitrary YAML frontmatter fields**
  - Any frontmatter field (e.g., `author:`, `date:`, `version:`) is now available as `{{ field }}` in templates
  - No code changes needed to support new frontmatter fields
  - `title:` and `description:` continue to work with fallback logic
  - Commit caca492 

- **Wiki mode support for multiple h1 documents**
  - Documents with multiple `#` headings now render correctly as wiki-style notes
  - Header title uses filename (or frontmatter `title:`) instead of first h1
  - TOC no longer displays up-arrow "Back to top" on every h1 (cleaner navigation)
  - Mode selection with priority: CLI `--mode` → frontmatter `type:` → auto-detection
  - Commit 30cc272

- **`--mode` CLI flag**
  - `--mode document` – Force document mode (single h1 as title, up-arrow on first h1)
  - `--mode wiki` – Force wiki mode (filename as title, no up-arrows)
  - `--mode auto` – Auto-detect based on h1 count (default)
  - Commit 30cc272

- **Frontmatter `type:` field**
  - Special YAML frontmatter param to force a particular document type when constructing TOC (github vs. wiki style)
  - `type: github` – Forces github-style mode (First h1 found links to #top in TOC; if no 'title' field in YAML to specify document title, will use first h1)
  - `type: wiki` – Forces wiki-style mode (General "Start" anchor to #top; if no 'title' field in YAML to specify document title, use filename)
  - Useful when frontmatter is preferred over auto-detection
  - Commit 30cc272

- **--version flag**
  - Prints current renderkind version and quits.
  - Commit 51d0e7b 

- **Favicon for generated HTML files**
  - Adds a favicon to generated HTML files to avoid browser default
  - Commit ff29a1d

### Changed

- `template_html()` now accepts a `frontmatter: Dict[str, str]` parameter instead of individual `title` and `description` arguments
- All frontmatter fields are merged into template substitutions (reserved keys: `content`, `toc`, `asset_path_prefix`)

### Fixed

- No new fixes in this release (existing v0.3.1 fixes preserved)

### Migration Notes

Upgrading from v0.3.1 to v0.4.0:
- build tool bin/build.sh must be updated else will fail due to rename of `examples/example.md` -> `examples/example_github.md`
- Existing single-h1 documents continue to work as before (document mode)
- Custom templates that relied on only `{{ title }}` and `{{ description }}` still work
- Templates with additional frontmatter fields will now receive those values

### Example: Wiki-style note with frontmatter

Input (`notes.md`):
```markdown
---
title: "My Personal Notes"
type: wiki
---

# Python Tips
## List comprehensions

# Git Commands
## Stashing changes
```

Output:

- Header title: "My Personal Notes" (from frontmatter)
- TOC: Python Tips, Git Commands (no up-arrows)

## [0.3.1] - 2026-04-20

### Fixed

- **Windows path escaping in template rendering**
  - Fixed crash when template values contained Windows filepaths (e.g., `C:\Users\Ivan\file.txt`)
  - Error manifested as: `re.error: bad escape \U at position x`
  - Root cause: `re.subn()` (from vendored `template_utils`) interpreted backslashes in replacement strings as regex escape sequences
  - Solution: Updated vendored `template_utils` to v0.3.0 (two-pass design: regex for pattern matching, `str.replace` for literal insertion)
    see:
	https://github.com/bkuz114/template_utils/releases/tag/v0.3.0
    https://github.com/bkuz114/template_utils/commit/1e21de59bd9ed8e769818dd2c8a40d1393f1f008
  - To support the updated vendored `template_utils`:
    - Removed `href_escaped` workaround from `_render_tree()` (no longer needed)
    - Removed obsolete comments about backslash escaping
  - Commit: 30ef4e7 

- **Typo in fallback title when there is no `title` variable in YAML frontmatter**
  - When no 'title' variable in YAML frontmatter (or frontmatter missing), and title can't be extracted from the first h1, falls back to a generic title.
  - That title had typo: "Untitle Document" vs. "Untitled Document"
  - Commit: 20f7d31 

- **TOC generation crash for documents with no headings**
  - Fixed crash when processing markdown files that contain no headings (no h1-h4)
  - Previously, processing a markdown file with no headings (e.g., plain text or lists only) would crash with:
    `ValueError: not enough values to unpack (expected 2, got 0)`
  - Root cause: `render_toc()` returned an empty string early when `toc_entries` was empty, but caller (`convert_markdown_to_html`) expected `Tuple[str, str]` (which is what is returned in the normal case).
  - Solution: removed the early return. The function now runs to completion, returning an empty TOC (`<ul class="toc-list"></ul>`) and the default `"#top"` anchor.
  - Documents with headings are unaffected; documents without headings now build successfully.
  - Commit: 4e7054e 

- **Header title link for documents with no headings**
  - Previously, the site title link in the fixed header used the first h1's ID as its anchor (e.g., `href="#cleaning-chemistry"`)
  - This caused broken links (no action on click) when processing markdown files without any headings
  - Fixed by replacing dynamic anchor with static `#top` anchor and adding `id="top"` to the `<html>` element
  - The header link now always scrolls to the top of the page, regardless of document structure
  - Commit: 0f3699f 

### Changed

- **Default log level changed from WARNING to ERROR**
  - Warnings (e.g., missing frontmatter description) are now suppressed by default
  - Use `--quiet` to suppress all non-error output
  - Use `--verbose` (if added in future) to see warnings
  - Commit: 7783eb8 

- **Remove redundant "Generated" message after index page generation**
  - Removes redundant "Generated index page" message after index page generation in batch mode (similar message already being printed any time a new file is written)
  - Adds instead a "Create index page" message before index page generation, to give user visual separation between regular file generation and index file generation
  - Commit: cd57695

### Dependencies

- Updated vendored `template_utils` from v0.2.0 → v0.3.0
  see:
  https://github.com/bkuz114/template_utils/releases/tag/v0.3.0
  https://github.com/bkuz114/template_utils/commit/1e21de59bd9ed8e769818dd2c8a40d1393f1f008

### Migration Notes

No breaking changes. Users experiencing Windows path crashes should upgrade to v0.3.1.

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
[0.4.0]: https://github.com/bkuz114/renderkind/releases/tag/v0.4.0
