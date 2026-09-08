"""Stockfish downloader utilities for managing engine installations."""

import hashlib
import json
import logging
import platform
import ssl
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config.paths import engines_dir
from ..exceptions import DownloadError, NetworkError

logger = logging.getLogger(__name__)

SSL_CONTEXT = ssl.create_default_context()


class StockfishDownloader:
    """Handles downloading and extracting Stockfish engines."""

    # Stockfish GitHub releases API
    GITHUB_API_URL = (
        "https://api.github.com/repos/official-stockfish/Stockfish/releases"
    )
    LATEST_RELEASE_URL = f"{GITHUB_API_URL}/latest"

    def __init__(self, install_dir: Path | None = None):
        """
        Initialize the downloader.

        Args:
            install_dir: Directory to install Stockfish. Defaults to the user data directory.
        """
        if install_dir is None:
            install_dir = engines_dir()

        self.install_dir = install_dir
        self.stockfish_dir = install_dir / "stockfish"
        self.downloads_dir = install_dir / "downloads"
        self._logger = logging.getLogger(__name__)

        # Ensure directories exist
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.stockfish_dir.mkdir(exist_ok=True)
        self.downloads_dir.mkdir(exist_ok=True)

    def get_latest_version(self) -> str | None:
        """
        Get the latest Stockfish version from GitHub releases.

        Returns:
            Version string (e.g. "sf_17") or None if unable to fetch
        """
        try:
            request = Request(self.LATEST_RELEASE_URL)
            request.add_header("User-Agent", "OpenBoard Chess GUI")

            with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("tag_name")

        except (URLError, HTTPError, json.JSONDecodeError) as error:
            self._logger.error(f"Failed to fetch latest version: {error}")
            return None

    def get_installed_version(self) -> str | None:
        """
        Get the currently installed Stockfish version.

        Returns:
            Version string or None if not installed/unknown
        """
        version_file = self.stockfish_dir / "version.txt"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except Exception as error:
                self._logger.warning(f"Could not read version file: {error}")

        return None

    def find_windows_asset(self, release_data: dict[str, Any]) -> dict[str, Any] | None:
        """Select the universal Windows binary for this machine's architecture."""
        assets = release_data.get("assets", [])
        machine = platform.machine().lower()
        if machine in {"arm64", "aarch64"}:
            names = ["stockfish-windows-arm64-universal.zip"]
        elif machine in {"amd64", "x86_64"}:
            names = [
                "stockfish-windows-x86-64-universal.zip",
                "stockfish-windows-x86-64.zip",
            ]
        else:
            return None
        for name in names:
            for asset in assets:
                if name == asset.get("name", "").lower():
                    return asset
        return None

    def download_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
        expected_sha256: str | None = None,
    ) -> bool:
        """Download to a temporary file, verify it, then replace the destination.

        Args:
            url: URL to download from
            dest_path: Destination file path
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            expected_sha256: Optional expected SHA-256 hex digest; raises DownloadError on mismatch

        Returns:
            True if successful

        Raises:
            DownloadError: On SHA-256 mismatch or OS-level write failure
            NetworkError: On network-level failure (URLError, HTTPError)
        """
        partial_path = None
        try:
            request = Request(url)
            request.add_header("User-Agent", "OpenBoard Chess GUI")

            sha = hashlib.sha256()
            with urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
                total_size = int(response.getheader("Content-Length", "0") or 0)
                downloaded_bytes = 0

                with tempfile.NamedTemporaryFile(
                    dir=dest_path.parent, prefix=f".{dest_path.name}.", delete=False
                ) as output_file:
                    partial_path = Path(output_file.name)
                    while True:
                        chunk = response.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        output_file.write(chunk)
                        sha.update(chunk)
                        downloaded_bytes += len(chunk)
                        if progress_callback is not None and total_size > 0:
                            progress_callback(downloaded_bytes, total_size)

            if total_size and downloaded_bytes != total_size:
                raise DownloadError(url, "Download ended before the full file arrived")

            if expected_sha256 is not None:
                actual_hash = sha.hexdigest()
                if actual_hash != expected_sha256.lower():
                    raise DownloadError(
                        url,
                        f"sha256 mismatch: expected {expected_sha256}, got {actual_hash}",
                    )
            else:
                self._logger.debug(
                    f"No SHA-256 provided for {url}; downloaded file integrity NOT verified for this download."
                )

            partial_path.replace(dest_path)
            self._logger.info(f"Downloaded {dest_path.name} ({downloaded_bytes} bytes)")
            return True

        except (URLError, HTTPError) as exc:
            raise NetworkError(f"Network failure downloading {url}", str(exc)) from exc
        except OSError as exc:
            raise DownloadError(url, str(exc)) from exc
        finally:
            if partial_path is not None:
                partial_path.unlink(missing_ok=True)

    def extract_zip(self, zip_path: Path, extract_to: Path) -> bool:
        """Validate every ZIP member before extracting any files.

        Args:
            zip_path: Path to ZIP file
            extract_to: Directory to extract to

        Returns:
            True if successful

        Raises:
            DownloadError: If a ZIP member escapes the extract directory, or on corrupt zip
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                extract_root = Path(extract_to).resolve()
                for member in archive.infolist():
                    target = (extract_root / member.filename).resolve()
                    if not target.is_relative_to(extract_root):
                        raise DownloadError(
                            str(zip_path),
                            f"refusing to extract: {member.filename!r} escapes extract dir",
                        )
                archive.extractall(extract_to)

            self._logger.info(f"Extracted {zip_path.name} to {extract_to}")
            return True

        except zipfile.BadZipFile as exc:
            raise DownloadError(str(zip_path), f"corrupt zip: {exc}") from exc

    def find_stockfish_executable(self, extract_dir: Path) -> Path | None:
        """
        Find the Stockfish executable in the extracted directory.

        Args:
            extract_dir: Directory where files were extracted

        Returns:
            Path to executable or None if not found
        """
        # Common executable names and patterns
        exe_patterns = [
            "stockfish.exe",
            "stockfish",
            "**/stockfish.exe",
            "**/stockfish",
            "**/*stockfish*.exe",
            "**/*stockfish*",
        ]

        # Search recursively for the executable using glob patterns
        for pattern in exe_patterns:
            for exe_path in extract_dir.glob(pattern):
                if exe_path.is_file() and exe_path.name.lower().startswith("stockfish"):
                    # Additional check to ensure it's likely an executable
                    if (
                        exe_path.suffix.lower() in [".exe", ""]
                        and exe_path.stat().st_size > 1000
                    ):
                        self._logger.info(f"Found Stockfish executable: {exe_path}")
                        return exe_path

        # If not found, list directory contents for debugging
        self._logger.error(f"Could not find Stockfish executable in {extract_dir}")
        self._logger.error("Directory contents:")
        for item in extract_dir.rglob("*"):
            if item.is_file():
                self._logger.error(f"  File: {item} (size: {item.stat().st_size})")
            else:
                self._logger.error(f"  Dir:  {item}/")

        return None

    def download_and_install_latest(
        self, progress_callback: Callable[[str, int, int], None] | None = None
    ) -> bool:
        """
        Download and install the latest Stockfish version.

        Args:
            progress_callback: Optional callback(status_message, progress, total)

        Returns:
            True if successful, False otherwise
        """
        if platform.system().lower() != "windows":
            self._logger.error("Automatic installation only supported on Windows")
            return False

        def update_progress(message: str, current: int = 0, total: int = 100):
            if progress_callback:
                progress_callback(message, current, total)

        temporary_install = None
        preserve_previous = False
        try:
            update_progress("Fetching latest version info...")

            # Get latest release info
            request = Request(self.LATEST_RELEASE_URL)
            request.add_header("User-Agent", "OpenBoard Chess GUI")

            with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
                release_data = json.loads(response.read().decode("utf-8"))

            version = release_data.get("tag_name")
            if not version:
                self._logger.error("Could not determine latest version")
                return False

            update_progress(f"Found version {version}")

            # Find Windows binary URL
            asset = self.find_windows_asset(release_data)
            if asset is None:
                self._logger.error("No compatible Windows binary found")
                return False

            download_url = asset["browser_download_url"]
            digest = asset.get("digest") or ""
            expected_sha256 = digest.removeprefix("sha256:")
            if not digest.startswith("sha256:") or len(expected_sha256) != 64:
                raise DownloadError(download_url, "Release asset has no SHA-256 digest")

            update_progress("Downloading Stockfish...", 0, 100)

            def download_progress(downloaded: int, total: int):
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    update_progress(f"Downloading... {percent}%", downloaded, total)

            temporary_install = tempfile.TemporaryDirectory(
                dir=self.downloads_dir, ignore_cleanup_errors=True, delete=False
            )
            with temporary_install as staging:
                staging_dir = Path(staging)
                download_path = staging_dir / "stockfish.zip"
                self.download_file(
                    download_url,
                    download_path,
                    download_progress,
                    expected_sha256=expected_sha256,
                )
                update_progress("Extracting files...")
                temp_extract = staging_dir / "extracted"
                self.extract_zip(download_path, temp_extract)
                update_progress("Locating executable...")
                exe_path = self.find_stockfish_executable(temp_extract)
                if exe_path is None:
                    raise DownloadError(
                        download_url, "No Stockfish executable in archive"
                    )

                candidate = staging_dir / "installation"
                (candidate / "bin").mkdir(parents=True)
                exe_path.replace(candidate / "bin" / "stockfish.exe")
                (candidate / "version.txt").write_text(version, encoding="utf-8")
                metadata = {
                    "version": version,
                    "download_url": download_url,
                    "executable_path": str(
                        self.stockfish_dir / "bin" / "stockfish.exe"
                    ),
                    "sha256": expected_sha256,
                }
                (candidate / "metadata.json").write_text(
                    json.dumps(metadata, indent=2), encoding="utf-8"
                )

                # Keep the prior installation until the binary and metadata are ready.
                previous = staging_dir / "previous"
                had_previous = self.stockfish_dir.exists()
                if had_previous:
                    self.stockfish_dir.replace(previous)
                try:
                    candidate.replace(self.stockfish_dir)
                except OSError:
                    if had_previous:
                        try:
                            previous.replace(self.stockfish_dir)
                        except OSError as error:
                            preserve_previous = True
                            raise DownloadError(
                                download_url,
                                f"Could not restore the previous installation. It is preserved at {previous}",
                            ) from error
                    raise

            update_progress("Installation complete!", 100, 100)
            self._logger.info(f"Successfully installed Stockfish {version}")
            return True

        except Exception as error:
            self._logger.error(f"Installation failed: {error}")
            update_progress(f"Installation failed: {error}")
            return False
        finally:
            if temporary_install is not None and not preserve_previous:
                temporary_install.cleanup()

    def get_installed_executable_path(self) -> Path | None:
        """
        Get the path to the installed Stockfish executable.

        Returns:
            Path to executable or None if not installed
        """
        exe_path = self.stockfish_dir / "bin" / "stockfish.exe"
        return exe_path if exe_path.exists() else None
