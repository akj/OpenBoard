"""Version extraction utilities."""

from pathlib import Path


def get_version_from_pyproject(pyproject_path: Path | None = None) -> str:
    """
    Read version from pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml file. If None, searches from current file.

    Returns:
        Version string

    Raises:
        FileNotFoundError: If pyproject.toml not found
        RuntimeError: If version cannot be extracted
    """
    if pyproject_path is None:
        # Navigate up to project root from utils directory
        utils_dir = Path(__file__).parent
        project_root = utils_dir.parent.parent
        pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    # Try using tomllib (Python 3.11+) first, fallback to manual parsing
    try:
        import tomllib
    except ModuleNotFoundError:
        # Python < 3.11, use manual parsing
        content = pyproject_path.read_text()
        for line in content.splitlines():
            if line.strip().startswith("version"):
                # Parse line like: version = "0.1.0"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    version = parts[1].strip().strip('"').strip("'")
                    return version
        raise RuntimeError("Could not find version in pyproject.toml")
    else:
        # Use tomllib
        with open(pyproject_path, "rb") as f:
            import tomllib

            data = tomllib.load(f)

        if "project" not in data or "version" not in data["project"]:
            raise RuntimeError("Version not found in pyproject.toml [project] section")

        return data["project"]["version"]
