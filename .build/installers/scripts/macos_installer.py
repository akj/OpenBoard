"""
macOS DMG installer builder.

This module provides functionality to build macOS DMG installers for OpenBoard
using either create-dmg tool or hdiutil (built-in macOS tool).
"""

import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def verify_macos() -> None:
    """
    Verify that the script is running on macOS.

    Raises:
        OSError: If not running on macOS
    """
    if platform.system() != "Darwin":
        raise OSError(
            f"This script must be run on macOS, not {platform.system()}"
        )


def find_create_dmg() -> Path | None:
    """
    Find create-dmg command-line tool.

    Returns:
        Path to create-dmg if found, None otherwise
    """
    create_dmg_path = shutil.which("create-dmg")
    if create_dmg_path:
        logger.info(f"Found create-dmg in PATH: {create_dmg_path}")
        return Path(create_dmg_path)

    logger.info("create-dmg not found in PATH")
    return None


def create_dmg_with_create_dmg(
    app_bundle: Path,
    dmg_path: Path,
    version: str
) -> None:
    """
    Create DMG using create-dmg tool.

    Args:
        app_bundle: Path to .app bundle
        dmg_path: Output DMG path
        version: Version string for volume name

    Raises:
        RuntimeError: If DMG creation fails
    """
    logger.info("Creating DMG using create-dmg tool")

    volume_name = f"OpenBoard {version}"

    command = [
        "create-dmg",
        "--volname", volume_name,
        "--window-size", "600", "400",
        "--icon-size", "80",
        "--app-drop-link", "400", "200",
        str(dmg_path),
        str(app_bundle)
    ]

    logger.info(f"Running create-dmg: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        if result.stdout:
            logger.info(f"create-dmg output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"create-dmg warnings:\n{result.stderr}")

    except subprocess.CalledProcessError as e:
        logger.error(f"create-dmg failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise RuntimeError(
            f"create-dmg failed: {e.stderr}"
        ) from e


def create_dmg_with_hdiutil(
    app_bundle: Path,
    dmg_path: Path,
    version: str
) -> None:
    """
    Create DMG using hdiutil (macOS built-in tool).

    Args:
        app_bundle: Path to .app bundle
        dmg_path: Output DMG path
        version: Version string for volume name

    Raises:
        RuntimeError: If DMG creation fails
    """
    logger.info("Creating DMG using hdiutil")

    volume_name = f"OpenBoard {version}"
    temp_dir = None

    try:
        # Create temporary directory for DMG contents
        temp_dir = Path(tempfile.mkdtemp(prefix="openboard_dmg_"))
        logger.info(f"Created temporary directory: {temp_dir}")

        # Copy .app bundle to temp directory
        app_name = app_bundle.name
        dest_app = temp_dir / app_name
        logger.info(f"Copying {app_bundle} to {dest_app}")
        shutil.copytree(app_bundle, dest_app, symlinks=True)

        # Create Applications symlink
        applications_link = temp_dir / "Applications"
        logger.info(f"Creating Applications symlink: {applications_link}")
        os.symlink("/Applications", applications_link)

        # Create DMG using hdiutil
        command = [
            "hdiutil",
            "create",
            "-volname", volume_name,
            "-srcfolder", str(temp_dir),
            "-ov",  # Overwrite if exists
            "-format", "UDZO",  # Compressed
            str(dmg_path)
        ]

        logger.info(f"Running hdiutil: {' '.join(command)}")

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        if result.stdout:
            logger.info(f"hdiutil output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"hdiutil warnings:\n{result.stderr}")

    except subprocess.CalledProcessError as e:
        logger.error(f"hdiutil failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise RuntimeError(
            f"hdiutil failed: {e.stderr}"
        ) from e

    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)


def build_macos_installer(
    dist_dir: Path,
    version: str,
    output_dir: Path
) -> Path:
    """
    Build macOS DMG installer.

    Args:
        dist_dir: Path to PyInstaller dist/ directory containing .app bundle
        version: Version string for installer
        output_dir: Directory to place output DMG

    Returns:
        Path to created DMG file

    Raises:
        FileNotFoundError: If .app bundle not found
        RuntimeError: If DMG creation fails
        OSError: If not running on macOS
    """
    logger.info("Starting macOS DMG installer build")
    logger.info(f"Distribution directory: {dist_dir}")
    logger.info(f"Version: {version}")
    logger.info(f"Output directory: {output_dir}")

    # Validate version format to prevent command injection
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$', version):
        raise ValueError(
            f"Invalid version format: {version}. "
            "Expected format: X.Y.Z or X.Y.Z-suffix"
        )

    # Verify running on macOS
    verify_macos()

    # Verify .app bundle exists
    app_bundle = dist_dir / "OpenBoard.app"
    if not app_bundle.exists():
        raise FileNotFoundError(
            f".app bundle not found: {app_bundle}"
        )

    logger.info(f"Verified .app bundle: {app_bundle}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define output DMG path
    dmg_filename = f"OpenBoard-v{version}-macos-x64.dmg"
    dmg_path = output_dir / dmg_filename

    # Try create-dmg first, fallback to hdiutil
    create_dmg_tool = find_create_dmg()

    if create_dmg_tool:
        create_dmg_with_create_dmg(app_bundle, dmg_path, version)
    else:
        logger.info("create-dmg not available, using hdiutil fallback")
        create_dmg_with_hdiutil(app_bundle, dmg_path, version)

    # Verify DMG was created
    if not dmg_path.exists():
        raise RuntimeError(
            f"DMG was not created at expected location: {dmg_path}"
        )

    logger.info(f"Successfully created macOS DMG installer: {dmg_path}")
    return dmg_path


def main() -> None:
    """
    Main entry point for command-line usage.

    Example usage:
        python macos_installer.py
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example paths for testing
    dist_dir = Path(__file__).parent.parent.parent.parent / "dist"
    version = "1.0.0"
    output_dir = Path(__file__).parent.parent / "output"

    try:
        dmg_path = build_macos_installer(dist_dir, version, output_dir)
        print(f"DMG installer created: {dmg_path}")
    except Exception as e:
        logger.error(f"Failed to build DMG installer: {e}")
        raise


if __name__ == "__main__":
    main()
