#!/usr/bin/env python3
"""
Cross-platform build automation script for OpenBoard.

This script automates the PyInstaller build process with proper error handling,
cross-platform support, and build verification.
"""

import argparse
import datetime
import json
import logging
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Dict, NoReturn

# Add parent directory to path to import build utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.version import get_version_from_pyproject


class BuildError(Exception):
    """Raised when a build operation fails."""

    pass


class OpenBoardBuilder:
    """Handles the build process for OpenBoard chess GUI."""

    def __init__(self, project_root: Path | None = None):
        """
        Initialize the builder.

        Args:
            project_root: Path to the project root directory
        """
        if project_root is None:
            # Assume script is in build/scripts/, so project root is two levels up
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root).resolve()

        self.build_dir = self.project_root / "build"  # PyInstaller build artifacts
        self.dist_dir = self.project_root / "dist"
        self.spec_file = self.project_root / "openboard.spec"
        self.pyproject_file = self.project_root / "pyproject.toml"
        self.log_file = self.project_root / "build.log"  # Log file in project root

        # Platform detection
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.is_macos = self.system == "Darwin"
        self.is_linux = self.system == "Linux"

        self.logger = self._setup_logging()
        self.project_metadata = self._load_project_metadata()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the build process."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.log_file, mode="w"),
            ],
        )
        return logging.getLogger(__name__)

    def _load_project_metadata(self) -> Dict[str, str]:
        """Load project metadata from pyproject.toml."""
        try:
            # Use shared version utility
            version = get_version_from_pyproject(self.pyproject_file)

            # Load other metadata
            with open(self.pyproject_file, "rb") as f:
                pyproject_data = tomllib.load(f)

            project_section = pyproject_data.get("project", {})

            return {
                "name": project_section.get("name", "openboard"),
                "version": version,
                "description": project_section.get("description", ""),
                "requires_python": project_section.get("requires-python", ""),
            }
        except Exception as e:
            self.logger.warning(f"Could not load project metadata: {e}")
            return {
                "name": "openboard",
                "version": "unknown",
                "description": "",
                "requires_python": "",
            }

    def _generate_build_metadata(self) -> Dict[str, str]:
        """Generate comprehensive build metadata."""
        git_commit = self._get_git_commit()
        git_branch = self._get_git_branch()
        build_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return {
            "build_time": build_time,
            "platform": self.system,
            "platform_version": platform.platform(),
            "python_version": platform.python_version(),
            "git_commit": git_commit,
            "git_branch": git_branch,
            "project_name": self.project_metadata["name"],
            "project_version": self.project_metadata["version"],
            "project_description": self.project_metadata["description"],
        }

    def _get_git_commit(self) -> str:
        """Get the current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    def _get_git_branch(self) -> str:
        """Get the current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    def _save_build_metadata(self) -> None:
        """Save build metadata to a JSON file in the dist directory."""
        metadata = self._generate_build_metadata()
        metadata_file = self.dist_dir / "build_metadata.json"

        try:
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            self.logger.info(f"Build metadata saved to {metadata_file}")
        except Exception as e:
            self.logger.warning(f"Could not save build metadata: {e}")

    def _run_command(self, command: list[str], cwd: Path | None = None) -> None:
        """
        Run a command with proper error handling.

        Args:
            command: Command to run as list of strings
            cwd: Working directory for the command

        Raises:
            BuildError: If the command fails
        """
        if cwd is None:
            cwd = self.project_root

        self.logger.info(f"Running command: {' '.join(command)}")
        self.logger.info(f"Working directory: {cwd}")

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout:
                self.logger.info(f"Command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with exit code {e.returncode}")
            self.logger.error(f"stdout: {e.stdout}")
            self.logger.error(f"stderr: {e.stderr}")
            raise BuildError(f"Command failed: {' '.join(command)}")
        except FileNotFoundError:
            raise BuildError(f"Command not found: {command[0]}")

    def _check_dependencies(self) -> None:
        """Check that all required build dependencies are available."""
        self.logger.info("Checking build dependencies...")

        # Check that we're in a UV environment
        try:
            self._run_command(["uv", "--version"])
        except BuildError:
            raise BuildError("UV package manager not found. Please install UV.")

        # Check that PyInstaller is available
        try:
            self._run_command([sys.executable, "-m", "PyInstaller", "--version"])
        except BuildError:
            raise BuildError(
                "PyInstaller not found. Please run 'uv sync --group dev' to install build dependencies."
            )

        # Check that the project dependencies are installed
        try:
            self._run_command([sys.executable, "-c", "import openboard"])
        except BuildError:
            raise BuildError(
                "OpenBoard package not found. Please run 'uv sync' to install dependencies."
            )

        self.logger.info("All dependencies are available.")

    def _check_spec_file(self) -> None:
        """Check that the PyInstaller spec file exists and is valid."""
        if not self.spec_file.exists():
            raise BuildError(f"Spec file not found: {self.spec_file}")

        self.logger.info(f"Using spec file: {self.spec_file}")

    def _clean_build_artifacts(self) -> None:
        """Remove only this app's generated executable and intermediate build files."""
        for target in (
            self.dist_dir / "OpenBoard",
            self.dist_dir / "OpenBoard.app",
            self.build_dir / self.spec_file.stem,
        ):
            resolved = target.resolve()
            if not resolved.is_relative_to(self.project_root.resolve()):
                raise BuildError(
                    f"Refusing to remove build path outside the project: {target}"
                )
            if target.exists():
                shutil.rmtree(target)
                self.logger.info(f"Removed {target}")

    def _run_pyinstaller(self) -> None:
        """Run PyInstaller with the spec file."""
        self.logger.info("Running PyInstaller...")

        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(self.spec_file),
        ]

        self._run_command(command)
        self.logger.info("PyInstaller completed successfully.")

    @property
    def executable_path(self) -> Path:
        """The executable inside the platform's distribution directory."""
        if self.is_macos:
            return self.dist_dir / "OpenBoard.app" / "Contents" / "MacOS" / "OpenBoard"
        filename = "OpenBoard.exe" if self.is_windows else "OpenBoard"
        return self.dist_dir / "OpenBoard" / filename

    def _verify_build(self) -> None:
        if not self.executable_path.is_file():
            raise BuildError(f"Executable not found: {self.executable_path}")
        self.logger.info(f"Build created executable: {self.executable_path}")

    def _get_build_info(self) -> Dict[str, str]:
        """Get build information for reporting."""
        build_metadata = self._generate_build_metadata()

        return {
            "Project Name": build_metadata["project_name"],
            "Project Version": build_metadata["project_version"],
            "Platform": build_metadata["platform"],
            "Platform Version": build_metadata["platform_version"],
            "Python Version": build_metadata["python_version"],
            "Git Branch": build_metadata["git_branch"],
            "Git Commit": build_metadata["git_commit"][:8]
            if build_metadata["git_commit"] != "unknown"
            else "unknown",
            "Build Time": build_metadata["build_time"],
            "Project Root": str(self.project_root),
            "Spec File": str(self.spec_file),
            "Distribution Directory": str(self.dist_dir),
        }

    def build(self, clean: bool = True) -> None:
        """
        Run the complete build process.

        Args:
            clean: Whether to clean build artifacts before building

        Raises:
            BuildError: If any step of the build process fails
        """
        self.logger.info("Starting OpenBoard build process...")

        # Log build information
        build_info = self._get_build_info()
        for key, value in build_info.items():
            self.logger.info(f"{key}: {value}")

        try:
            # Check dependencies
            self._check_dependencies()

            # Check spec file
            self._check_spec_file()

            # Clean previous builds
            if clean:
                self._clean_build_artifacts()

            # Run PyInstaller
            self._run_pyinstaller()

            # Save build metadata
            self._save_build_metadata()

            # Verify build
            self._verify_build()

            self.logger.info("Build process completed successfully!")

        except BuildError as e:
            self.logger.error(f"Build failed: {e}")
            raise

    def run_tests(self) -> None:
        """Run the source startup smoke check without opening the GUI."""
        self._run_command(
            [
                sys.executable,
                str(self.project_root / ".build" / "validation" / "verify_build.py"),
            ]
        )

    def run_build_validation(self, executable_path: Path | None = None) -> None:
        """Run the packaged startup smoke check without falling back to source."""
        self._run_command(
            [
                sys.executable,
                str(self.project_root / ".build" / "validation" / "verify_build.py"),
                "--executable",
                str(executable_path or self.executable_path),
            ]
        )

    def build_installer(self, installer_type: str | None = None) -> None:
        """
        Build platform-specific installer.

        Args:
            installer_type: Type of installer to build (auto-detected if None).
                           Supported: 'innosetup', 'dmg', 'deb', 'rpm'
        """
        self.logger.info("Building platform-specific installer...")

        # Path to installer build script
        installer_script = (
            self.project_root
            / ".build"
            / "installers"
            / "scripts"
            / "build_installer.py"
        )

        if not installer_script.exists():
            raise BuildError(f"Installer build script not found at {installer_script}")

        # Build command
        command = [sys.executable, str(installer_script)]

        # Add version from project metadata
        command.extend(["--version", self.project_metadata["version"]])

        # Add installer type if specified
        if installer_type:
            command.extend(["--type", installer_type])

        # Add verbose flag if debug logging
        if self.logger.level == logging.DEBUG:
            command.append("--verbose")

        try:
            self._run_command(command)
            self.logger.info("Installer build completed successfully!")
        except BuildError as e:
            self.logger.error(f"Installer build failed: {e}")
            raise


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build OpenBoard chess GUI with PyInstaller"
    )

    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean build artifacts before building",
    )

    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Only run tests, don't build",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run build validation, don't build",
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip build validation after building",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        help="Path to the project root directory",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--build-installer",
        action="store_true",
        help="Build platform-specific installer after executable build",
    )

    parser.add_argument(
        "--installer-type",
        type=str,
        help="Specify installer type (innosetup, dmg, deb, rpm). Auto-detected if not specified.",
    )

    return parser.parse_args()


def main() -> NoReturn:
    """Main entry point for the build script."""
    args = _parse_args()

    # Adjust logging level if verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        builder = OpenBoardBuilder(args.project_root)

        if args.test_only:
            builder.run_tests()
        elif args.validate_only:
            builder.run_build_validation()
        else:
            builder.run_tests()  # Run tests first
            builder.build(clean=not args.no_clean)

            # Run validation after build unless skipped
            if not args.skip_validation:
                builder.run_build_validation()

            # Build installer if requested
            if args.build_installer:
                builder.build_installer(args.installer_type)

        print("\nBuild completed successfully!")
        sys.exit(0)

    except BuildError as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
