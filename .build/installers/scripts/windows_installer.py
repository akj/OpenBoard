"""
Windows installer builder using Inno Setup.

This module provides functionality to build Windows installers for OpenBoard
using the Inno Setup compiler (iscc.exe).
"""

import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def find_inno_setup_compiler() -> Path | None:
    """
    Find Inno Setup compiler executable.

    Searches common installation locations and PATH for iscc.exe.

    Returns:
        Path to iscc.exe if found, None otherwise
    """
    # Check PATH first
    iscc_path = shutil.which("iscc")
    if iscc_path:
        logger.info(f"Found Inno Setup compiler in PATH: {iscc_path}")
        return Path(iscc_path)

    # Check common installation locations on Windows
    common_locations = [
        Path("C:/Program Files (x86)/Inno Setup 6/iscc.exe"),
        Path("C:/Program Files/Inno Setup 6/iscc.exe"),
        Path("C:/Program Files (x86)/Inno Setup/iscc.exe"),
        Path("C:/Program Files/Inno Setup/iscc.exe"),
    ]

    for location in common_locations:
        if location.exists():
            logger.info(f"Found Inno Setup compiler at: {location}")
            return location

    logger.error("Inno Setup compiler (iscc.exe) not found")
    return None


def build_windows_installer(dist_dir: Path, version: str, output_dir: Path) -> Path:
    """
    Build Windows installer using Inno Setup.

    Args:
        dist_dir: Path to PyInstaller dist/ directory
        version: Version string for installer
        output_dir: Directory to place output installer

    Returns:
        Path to created installer executable

    Raises:
        FileNotFoundError: If Inno Setup not found or dist directory missing
        RuntimeError: If installer build fails
    """
    logger.info("Starting Windows installer build")
    logger.info(f"Distribution directory: {dist_dir}")
    logger.info(f"Version: {version}")
    logger.info(f"Output directory: {output_dir}")

    # Validate version format to prevent command injection
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$", version):
        raise ValueError(
            f"Invalid version format: {version}. Expected format: X.Y.Z or X.Y.Z-suffix"
        )

    # Find Inno Setup compiler
    iscc_exe = find_inno_setup_compiler()
    if not iscc_exe:
        raise FileNotFoundError(
            "Inno Setup compiler (iscc.exe) not found. "
            "Please install Inno Setup from https://jrsoftware.org/isdl.php"
        )

    # Verify PyInstaller dist folder exists
    openboard_dist = dist_dir / "OpenBoard"
    if not openboard_dist.exists():
        raise FileNotFoundError(
            f"PyInstaller distribution directory not found: {openboard_dist}"
        )

    logger.info(f"Verified PyInstaller distribution: {openboard_dist}")

    # Locate Inno Setup script
    script_dir = Path(__file__).parent
    innosetup_script = script_dir.parent / "windows" / "innosetup.iss"

    if not innosetup_script.exists():
        raise FileNotFoundError(f"Inno Setup script not found: {innosetup_script}")

    logger.info(f"Using Inno Setup script: {innosetup_script}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    # iscc /DAppVersion={version} /O{output_dir} {script_path}
    command = [
        str(iscc_exe),
        f"/DAppVersion={version}",
        f"/O{output_dir}",
        str(innosetup_script),
    ]

    logger.info(f"Running Inno Setup compiler: {' '.join(command)}")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)

        # Log compiler output
        if result.stdout:
            logger.info(f"Inno Setup output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Inno Setup warnings:\n{result.stderr}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Inno Setup compilation failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise RuntimeError(f"Inno Setup compilation failed: {e.stderr}") from e

    # Verify output installer exists
    expected_installer = output_dir / f"OpenBoard-v{version}-windows-x64-setup.exe"

    if not expected_installer.exists():
        raise RuntimeError(
            f"Installer was not created at expected location: {expected_installer}"
        )

    logger.info(f"Successfully created Windows installer: {expected_installer}")
    return expected_installer


def main() -> None:
    """
    Main entry point for command-line usage.

    Example usage:
        python windows_installer.py
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Example paths for testing
    dist_dir = Path(__file__).parent.parent.parent.parent / "dist"
    version = "1.0.0"
    output_dir = Path(__file__).parent.parent / "output"

    try:
        installer_path = build_windows_installer(dist_dir, version, output_dir)
        print(f"Installer created: {installer_path}")
    except Exception as e:
        logger.error(f"Failed to build installer: {e}")
        raise


if __name__ == "__main__":
    main()
