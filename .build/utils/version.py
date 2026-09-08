"""Read package metadata used by executable and installer builds."""

import tomllib
from pathlib import Path


def get_version_from_pyproject(pyproject_path: Path | None = None) -> str:
    """Read the project version from pyproject.toml."""
    if pyproject_path is None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as stream:
        return tomllib.load(stream)["project"]["version"]
