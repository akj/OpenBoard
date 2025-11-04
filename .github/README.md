# GitHub Actions CI/CD

This directory contains the CI/CD pipeline configuration for OpenBoard.

## Workflows

### `workflows/ci.yml`
Main continuous integration workflow that runs on push and pull requests to main/master branches.

**Jobs:**
- **test**: Runs pytest with coverage on Python 3.12 and 3.13
- **lint**: Runs ruff linter to check code quality
- **type-check**: Runs pyright for static type checking
- **format-check**: Verifies code formatting with ruff

All jobs run in parallel for fast feedback.

## Composite Actions

### `actions/setup-python-uv`
Reusable composite action that sets up Python, installs UV package manager, and installs project dependencies.

**Inputs:**
- `python-version`: Python version to install (default: "3.12")
- `uv-version`: UV version to install (default: "0.5.11")

This action is used across all CI jobs to ensure consistent environment setup and reduce duplication (DRY principle).

## Configuration

The UV version is centralized in the `UV_VERSION` environment variable in `ci.yml` for easy updates.

## Local Testing

You can run the same checks locally:

```bash
# Run tests
uv run python -m pytest -v

# Run linting
uv run ruff check .

# Run type checking
uv run python -m pyright

# Run format check
uv run ruff format --check .
```
