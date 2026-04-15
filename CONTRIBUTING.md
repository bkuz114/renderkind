# Contributing to renderkind

Thank you for your interest in contributing.

## Development Setup

```bash
git clone https://github.com/bkuz114/md2html.git
cd renderkind
python -m venv venv
source venv/bin/activate
pip install -e .[dev]
```

## Vendored Dependencies

This project vendors certain internal libraries in `src/renderkind/vendor/`. 

**To update a vendored dependency**:
1. Update the source in its original repository
2. Copy the relevant file(s) to `src/renderkind/vendor/`
3. Update `VENDORED.txt` with the new version and commit hash
4. Run tests to ensure compatibility

**Do not edit vendored files directly** without updating the source and re-vendoring.

## Running Tests

```bash
pytest tests/
```

## Before Submitting a Pull Request

- Run tests locally
- Update CHANGELOG.md with your changes
- Ensure the package builds: `python -m build`
- Test installation in a fresh virtual environment

## Code Style

This project uses Black and Ruff. Run before committing:

```bash
black src/renderkind/
ruff check src/renderkind/
```

Thank you for building with kindness.
