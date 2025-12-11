"""Linux installer builder for OpenBoard.

This script builds both DEB and RPM packages for Linux distribution.
"""

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def build_deb_package(
    dist_dir: Path,
    version: str,
    output_dir: Path
) -> Path:
    """
    Build Debian package.

    Args:
        dist_dir: Path to PyInstaller dist/ directory
        version: Version string for package
        output_dir: Directory to place output .deb file

    Returns:
        Path to created .deb file

    Raises:
        FileNotFoundError: If dist directory or dpkg-deb not found
        RuntimeError: If package build fails
    """
    logger.info(f"Building DEB package version {version}")

    # Validate version format to prevent command injection
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$', version):
        raise ValueError(
            f"Invalid version format: {version}. "
            "Expected format: X.Y.Z or X.Y.Z-suffix"
        )

    # Verify dpkg-deb is available
    if not shutil.which("dpkg-deb"):
        raise FileNotFoundError("dpkg-deb not found. Install dpkg on your system.")

    # Verify executable exists
    executable_dir = dist_dir / "OpenBoard"
    executable_path = executable_dir / "OpenBoard"
    if not executable_path.exists():
        raise FileNotFoundError(
            f"Executable not found at {executable_path}. "
            f"Run PyInstaller build first."
        )

    logger.info(f"Found executable at {executable_path}")

    # Get template directory
    templates_dir = Path(__file__).parent.parent / "linux" / "debian"
    if not templates_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {templates_dir}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary directory for package structure
    temp_dir = Path(tempfile.mkdtemp(prefix="openboard-deb-"))
    logger.info(f"Using temporary directory: {temp_dir}")

    try:
        # Create directory structure
        debian_dir = temp_dir / "DEBIAN"
        opt_dir = temp_dir / "opt" / "openboard"
        desktop_dir = temp_dir / "usr" / "share" / "applications"

        debian_dir.mkdir(parents=True)
        opt_dir.mkdir(parents=True)
        desktop_dir.mkdir(parents=True)

        logger.info("Created package directory structure")

        # Copy executable and all files
        logger.info(f"Copying files from {executable_dir} to {opt_dir}")
        for item in executable_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, opt_dir / item.name)
            else:
                shutil.copy2(item, opt_dir / item.name)

        # Copy DEBIAN control files
        control_src = templates_dir / "DEBIAN" / "control"
        postinst_src = templates_dir / "DEBIAN" / "postinst"

        if not control_src.exists():
            raise FileNotFoundError(f"Control file not found: {control_src}")
        if not postinst_src.exists():
            raise FileNotFoundError(f"Postinst file not found: {postinst_src}")

        # Copy and replace version in control file
        control_content = control_src.read_text()
        control_content = control_content.replace("{VERSION}", version)
        (debian_dir / "control").write_text(control_content)
        logger.info("Wrote control file with version replaced")

        # Copy postinst script
        shutil.copy2(postinst_src, debian_dir / "postinst")
        logger.info("Copied postinst script")

        # Copy desktop file
        desktop_src = templates_dir / "openboard.desktop"
        if not desktop_src.exists():
            raise FileNotFoundError(f"Desktop file not found: {desktop_src}")
        shutil.copy2(desktop_src, desktop_dir / "openboard.desktop")
        logger.info("Copied desktop file")

        # Set proper permissions
        (debian_dir / "postinst").chmod(0o755)
        (opt_dir / "OpenBoard").chmod(0o755)
        logger.info("Set executable permissions")

        # Build the package
        output_filename = f"openboard_{version}_amd64.deb"
        output_path = output_dir / output_filename

        logger.info(f"Building DEB package: {output_filename}")
        subprocess.run(
            ["dpkg-deb", "--build", str(temp_dir), str(output_path)],
            check=True,
            capture_output=True,
            text=True
        )

        if not output_path.exists():
            raise RuntimeError(f"DEB package was not created at {output_path}")

        logger.info(f"Successfully built DEB package: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"dpkg-deb failed: {e.stderr}")
        raise RuntimeError(f"Failed to build DEB package: {e.stderr}") from e
    finally:
        # Clean up temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")


def build_rpm_package(
    dist_dir: Path,
    version: str,
    output_dir: Path
) -> Path | None:
    """
    Build RPM package.

    Args:
        dist_dir: Path to PyInstaller dist/ directory
        version: Version string for package
        output_dir: Directory to place output .rpm file

    Returns:
        Path to created .rpm file, or None if rpmbuild not available

    Raises:
        FileNotFoundError: If dist directory not found
        RuntimeError: If package build fails
    """
    logger.info(f"Building RPM package version {version}")

    # Validate version format to prevent command injection
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$', version):
        raise ValueError(
            f"Invalid version format: {version}. "
            "Expected format: X.Y.Z or X.Y.Z-suffix"
        )

    # Check if rpmbuild is available
    if not shutil.which("rpmbuild"):
        logger.warning(
            "rpmbuild not found. Skipping RPM package build. "
            "Install rpm-build package to enable RPM creation."
        )
        return None

    # Verify executable exists
    executable_dir = dist_dir / "OpenBoard"
    executable_path = executable_dir / "OpenBoard"
    if not executable_path.exists():
        raise FileNotFoundError(
            f"Executable not found at {executable_path}. "
            f"Run PyInstaller build first."
        )

    logger.info(f"Found executable at {executable_path}")

    # Get template directory
    templates_dir = Path(__file__).parent.parent / "linux" / "rpm"
    spec_template = templates_dir / "openboard.spec"
    if not spec_template.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_template}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary build directory
    build_root = Path(tempfile.mkdtemp(prefix="openboard-rpm-"))
    logger.info(f"Using temporary build directory: {build_root}")

    try:
        # Create RPM build directory structure
        for subdir in ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS", "BUILDROOT"]:
            (build_root / subdir).mkdir(parents=True)

        logger.info("Created RPM build directory structure")

        # Create buildroot directory structure for %install section
        install_root = build_root / "BUILDROOT" / f"openboard-{version}-1.x86_64"
        opt_dir = install_root / "opt" / "openboard"
        desktop_dir = install_root / "usr" / "share" / "applications"

        opt_dir.mkdir(parents=True)
        desktop_dir.mkdir(parents=True)

        # Copy executable and all files to buildroot
        logger.info(f"Copying files from {executable_dir} to {opt_dir}")
        for item in executable_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, opt_dir / item.name)
            else:
                shutil.copy2(item, opt_dir / item.name)

        # Set executable permissions
        (opt_dir / "OpenBoard").chmod(0o755)
        logger.info("Set executable permissions")

        # Copy desktop file to SOURCES for spec file reference
        desktop_src = Path(__file__).parent.parent / "linux" / "debian" / "openboard.desktop"
        if desktop_src.exists():
            shutil.copy2(desktop_src, build_root / "SOURCES" / "openboard.desktop")
            # Also copy to buildroot for %files section
            shutil.copy2(desktop_src, desktop_dir / "openboard.desktop")
            logger.info("Copied desktop file")

        # Read and replace version in spec file
        spec_content = spec_template.read_text()
        spec_content = spec_content.replace("{VERSION}", version)

        # Write spec file to SPECS directory
        spec_file = build_root / "SPECS" / "openboard.spec"
        spec_file.write_text(spec_content)
        logger.info("Wrote spec file with version replaced")

        # Build the RPM package
        logger.info("Running rpmbuild...")
        subprocess.run(
            [
                "rpmbuild",
                "-bb",
                "--define", f"_topdir {build_root}",
                "--buildroot", str(install_root),
                str(spec_file)
            ],
            check=True,
            capture_output=True,
            text=True
        )

        # Find the built RPM
        rpm_dir = build_root / "RPMS" / "x86_64"
        rpm_files = list(rpm_dir.glob("*.rpm"))

        if not rpm_files:
            raise RuntimeError(f"No RPM file found in {rpm_dir}")

        # Copy to output directory
        built_rpm = rpm_files[0]
        output_filename = f"openboard-{version}-1.x86_64.rpm"
        output_path = output_dir / output_filename

        shutil.copy2(built_rpm, output_path)
        logger.info(f"Successfully built RPM package: {output_path}")

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"rpmbuild failed: {e.stderr}")
        raise RuntimeError(f"Failed to build RPM package: {e.stderr}") from e
    finally:
        # Clean up temporary directory
        if build_root.exists():
            shutil.rmtree(build_root)
            logger.info(f"Cleaned up temporary directory: {build_root}")


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example usage
    import sys

    if len(sys.argv) != 4:
        print("Usage: python linux_installer.py <dist_dir> <version> <output_dir>")
        print("Example: python linux_installer.py dist 1.0.0 installers")
        sys.exit(1)

    dist_dir = Path(sys.argv[1])
    version = sys.argv[2]
    output_dir = Path(sys.argv[3])

    # Build both packages
    try:
        deb_path = build_deb_package(dist_dir, version, output_dir)
        print(f"DEB package created: {deb_path}")
    except Exception as e:
        logger.error(f"DEB build failed: {e}")
        sys.exit(1)

    try:
        rpm_path = build_rpm_package(dist_dir, version, output_dir)
        if rpm_path:
            print(f"RPM package created: {rpm_path}")
        else:
            print("RPM package skipped (rpmbuild not available)")
    except Exception as e:
        logger.error(f"RPM build failed: {e}")
        sys.exit(1)
