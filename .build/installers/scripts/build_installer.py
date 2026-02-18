#!/usr/bin/env python3
"""
Main installer orchestration script.

Detects platform and builds appropriate installer packages.
"""

import argparse
import logging
import platform
import sys
from pathlib import Path

# Add parent directory to path to import build utilities
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.version import get_version_from_pyproject

# Import platform-specific builders
from linux_installer import build_deb_package, build_rpm_package
from macos_installer import build_macos_installer
from windows_installer import build_windows_installer

logger = logging.getLogger(__name__)


def detect_platform() -> str:
    """
    Detect current platform.

    Returns:
        Platform name: "windows", "macos", or "linux"

    Raises:
        RuntimeError: If platform is not supported
    """
    system = platform.system()

    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def build_for_platform(
    platform_name: str,
    installer_types: list[str] | None,
    dist_dir: Path,
    version: str,
    output_dir: Path,
) -> list[Path]:
    """
    Build installers for specified platform.

    Args:
        platform_name: Platform to build for ("windows", "macos", "linux")
        installer_types: Specific installer types to build, or None for all
        dist_dir: Path to PyInstaller dist/ directory
        version: Version string for installers
        output_dir: Directory to place output installers

    Returns:
        List of paths to created installer files

    Raises:
        ValueError: If invalid installer type specified
        RuntimeError: If installer build fails
    """
    created_installers = []

    if platform_name == "windows":
        # Windows: build Inno Setup installer
        valid_types = ["innosetup"]

        if installer_types and not all(t in valid_types for t in installer_types):
            raise ValueError(
                f"Invalid installer type for Windows. Valid types: {valid_types}"
            )

        logger.info("Building Windows Inno Setup installer")
        try:
            installer_path = build_windows_installer(dist_dir, version, output_dir)
            created_installers.append(installer_path)
            logger.info(f"Created: {installer_path}")
        except Exception as e:
            logger.error(f"Windows installer build failed: {e}", exc_info=True)
            raise RuntimeError(f"Windows installer build failed: {e}") from e

    elif platform_name == "macos":
        # macOS: build DMG installer
        valid_types = ["dmg"]

        if installer_types and not all(t in valid_types for t in installer_types):
            raise ValueError(
                f"Invalid installer type for macOS. Valid types: {valid_types}"
            )

        logger.info("Building macOS DMG installer")
        try:
            installer_path = build_macos_installer(dist_dir, version, output_dir)
            created_installers.append(installer_path)
            logger.info(f"Created: {installer_path}")
        except Exception as e:
            logger.error(f"macOS installer build failed: {e}", exc_info=True)
            raise RuntimeError(f"macOS installer build failed: {e}") from e

    elif platform_name == "linux":
        # Linux: build DEB and/or RPM packages
        valid_types = ["deb", "rpm"]

        if installer_types:
            if not all(t in valid_types for t in installer_types):
                raise ValueError(
                    f"Invalid installer type for Linux. Valid types: {valid_types}"
                )
            build_types = installer_types
        else:
            # Build both by default
            build_types = valid_types

        # Build DEB if requested
        if "deb" in build_types:
            logger.info("Building DEB package")
            try:
                deb_path = build_deb_package(dist_dir, version, output_dir)
                created_installers.append(deb_path)
                logger.info(f"Created: {deb_path}")
            except Exception as e:
                logger.error(f"DEB package build failed: {e}", exc_info=True)
                # Don't raise - continue with RPM if requested
                if len(build_types) == 1:
                    # Only DEB requested, so fail
                    raise RuntimeError(f"DEB package build failed: {e}") from e

        # Build RPM if requested
        if "rpm" in build_types:
            logger.info("Building RPM package")
            try:
                rpm_path = build_rpm_package(dist_dir, version, output_dir)
                if rpm_path:
                    created_installers.append(rpm_path)
                    logger.info(f"Created: {rpm_path}")
                else:
                    logger.warning("RPM package skipped (rpmbuild not available)")
            except Exception as e:
                logger.error(f"RPM package build failed: {e}", exc_info=True)
                # Don't raise if DEB was successful
                if len(build_types) == 1:
                    # Only RPM requested, so fail
                    raise RuntimeError(f"RPM package build failed: {e}") from e

    else:
        raise ValueError(f"Unknown platform: {platform_name}")

    return created_installers


def main() -> int:
    """
    Main entry point for installer building.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Build platform-specific installers for OpenBoard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_installer.py
  python build_installer.py --version 1.0.0
  python build_installer.py --type deb
  python build_installer.py --type deb,rpm
        """,
    )

    parser.add_argument(
        "--version",
        help="Version string for installer (default: read from pyproject.toml)",
    )

    parser.add_argument(
        "--type",
        help=(
            "Installer type(s) to build (comma-separated). "
            "Valid: innosetup (Windows), dmg (macOS), deb/rpm (Linux). "
            "Default: all types for current platform"
        ),
    )

    parser.add_argument(
        "--dist-dir",
        type=Path,
        help="Path to PyInstaller dist/ directory (default: ../../dist from script)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for output installers "
            "(default: ../../dist/installers from script)"
        ),
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("=" * 60)
    logger.info("OpenBoard Installer Builder")
    logger.info("=" * 60)

    try:
        # Detect platform
        platform_name = detect_platform()
        logger.info(f"Detected platform: {platform_name}")

        # Get version
        if args.version:
            version = args.version
            logger.info(f"Using specified version: {version}")
        else:
            version = get_version_from_pyproject()
            logger.info(f"Using version from pyproject.toml: {version}")

        # Set up directories
        script_dir = Path(__file__).parent

        if args.dist_dir:
            dist_dir = args.dist_dir.resolve()
        else:
            dist_dir = (script_dir.parent.parent.parent / "dist").resolve()

        if args.output_dir:
            output_dir = args.output_dir.resolve()
        else:
            output_dir = (dist_dir / "installers").resolve()

        logger.info(f"Distribution directory: {dist_dir}")
        logger.info(f"Output directory: {output_dir}")

        # Verify dist directory exists
        if not dist_dir.exists():
            logger.error(f"Distribution directory does not exist: {dist_dir}")
            logger.error("Run PyInstaller build first!")
            return 1

        # Parse installer types
        installer_types = None
        if args.type:
            installer_types = [t.strip() for t in args.type.split(",")]
            logger.info(f"Building installer types: {installer_types}")
        else:
            logger.info("Building all installer types for platform")

        # Build installers
        logger.info("-" * 60)
        logger.info("Starting installer build")
        logger.info("-" * 60)

        created_installers = build_for_platform(
            platform_name, installer_types, dist_dir, version, output_dir
        )

        # Report results
        logger.info("=" * 60)
        logger.info("Build Complete!")
        logger.info("=" * 60)

        if created_installers:
            logger.info(f"Created {len(created_installers)} installer(s):")
            for installer in created_installers:
                logger.info(f"  - {installer}")
        else:
            logger.warning("No installers were created")
            return 1

        return 0

    except KeyboardInterrupt:
        logger.error("Build interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
