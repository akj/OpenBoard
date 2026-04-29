"""Stockfish downloader utilities for managing engine installations."""

import hashlib
import json
import logging
import os
import platform
import ssl
import zipfile
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import DownloadError, NetworkError

logger = logging.getLogger(__name__)

# Module-level SSL context: explicit CERT_REQUIRED for all HTTPS downloads.
# Codex LOW one-line acceptance: all urlopen calls pass context=SSL_CONTEXT (TD-13 / D-21 / Security #3).
SSL_CONTEXT = ssl.create_default_context()


class StockfishDownloader:
    """Handles downloading and extracting Stockfish engines."""

    # Stockfish GitHub releases API
    GITHUB_API_URL = (
        "https://api.github.com/repos/official-stockfish/Stockfish/releases"
    )
    LATEST_RELEASE_URL = f"{GITHUB_API_URL}/latest"

    # Windows binary patterns
    WINDOWS_BINARY_PATTERNS = [
        "stockfish-windows-x86-64-avx2.zip",
        "stockfish-windows-x86-64-sse41-popcnt.zip",
        "stockfish-windows-x86-64-ssse3.zip",
        "stockfish-windows-x86-64.zip",
    ]

    def __init__(self, install_dir: Path | None = None):
        """
        Initialize the downloader.

        Args:
            install_dir: Directory to install Stockfish. Defaults to <cwd>/engines
        """
        if install_dir is None:
            install_dir = Path.cwd() / "engines"

        self.install_dir = install_dir
        self.stockfish_dir = install_dir / "stockfish"
        self.downloads_dir = install_dir / "downloads"
        self._logger = logging.getLogger(__name__)

        # Ensure directories exist
        self.install_dir.mkdir(exist_ok=True)
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

    def find_windows_binary_url(self, release_data: dict[str, Any]) -> str | None:
        """
        Find the best Windows binary download URL from release assets.

        Args:
            release_data: GitHub release data

        Returns:
            Download URL or None if not found
        """
        assets = release_data.get("assets", [])

        # Try to find the best binary in order of preference
        for pattern in self.WINDOWS_BINARY_PATTERNS:
            for asset in assets:
                if pattern in asset.get("name", "").lower():
                    return asset.get("browser_download_url")

        return None

    def download_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
        expected_sha256: str | None = None,
    ) -> bool:
        """Download a file over HTTPS with explicit SSL context and optional SHA-256 verification.

        If expected_sha256 is provided, the downloaded archive's hash is verified after the
        write completes; on mismatch, the partial file is deleted and DownloadError is raised.
        If expected_sha256 is None, a DEBUG log records the integrity gap (Codex MEDIUM — not WARN
        per Plan revision; the operator-visible announcement is a single startup INFO from
        StockfishManager). Stockfish releases publish no per-asset checksums, so callers
        currently always pass None — this is the documented v1 baseline per RESEARCH.md Pitfall 5.
        (TD-13 / D-21)

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
        try:
            request = Request(url)
            request.add_header("User-Agent", "OpenBoard Chess GUI")

            sha = hashlib.sha256()
            with urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
                total_size = int(response.getheader("Content-Length", "0") or 0)
                downloaded_bytes = 0

                with open(dest_path, "wb") as output_file:
                    while True:
                        chunk = response.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        output_file.write(chunk)
                        sha.update(chunk)
                        downloaded_bytes += len(chunk)
                        if progress_callback is not None and total_size > 0:
                            progress_callback(downloaded_bytes, total_size)

            if expected_sha256 is not None:
                actual_hash = sha.hexdigest()
                if actual_hash != expected_sha256.lower():
                    dest_path.unlink(missing_ok=True)
                    raise DownloadError(
                        url,
                        f"sha256 mismatch: expected {expected_sha256}, got {actual_hash}",
                    )
            else:
                # Codex MEDIUM: DEBUG per-download (not WARN). The operator-visible signal is
                # a single INFO at StockfishManager startup (see stockfish_manager.py __init__).
                # Stockfish releases publish no per-asset checksums (RESEARCH.md Pitfall 5).
                self._logger.debug(
                    f"No SHA-256 provided for {url}; downloaded file integrity NOT verified for this download."
                )

            self._logger.info(f"Downloaded {dest_path.name} ({downloaded_bytes} bytes)")
            return True

        except (URLError, HTTPError) as exc:
            raise NetworkError(f"Network failure downloading {url}", str(exc)) from exc
        except OSError as exc:
            raise DownloadError(url, str(exc)) from exc

    def extract_zip(self, zip_path: Path, extract_to: Path) -> bool:
        """Extract a ZIP with per-member path-traversal validation.

        Per CPython docs (RESEARCH.md / D-21), zipfile.extractall does NOT sanitise
        filenames against the extract dir — `..` path components can escape. This guard
        resolves each member path and rejects any that lie outside extract_to.
        (TD-13 / D-21 / Security #2)

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
                    common_root = os.path.commonpath([str(extract_root), str(target)])
                    if common_root != str(extract_root):
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
            download_url = self.find_windows_binary_url(release_data)
            if not download_url:
                self._logger.error("No compatible Windows binary found")
                return False

            # Download the binary
            filename = download_url.split("/")[-1]
            download_path = self.downloads_dir / filename

            update_progress("Downloading Stockfish...", 0, 100)

            def download_progress(downloaded: int, total: int):
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    update_progress(f"Downloading... {percent}%", downloaded, total)

            if not self.download_file(download_url, download_path, download_progress):
                return False

            # Extract the archive
            update_progress("Extracting files...")
            temp_extract = self.downloads_dir / "temp_extract"
            temp_extract.mkdir(exist_ok=True)

            if not self.extract_zip(download_path, temp_extract):
                return False

            # Find the executable
            update_progress("Locating executable...")
            exe_path = self.find_stockfish_executable(temp_extract)
            if not exe_path:
                self._logger.error("Could not find Stockfish executable in archive")
                return False

            # Move executable to final location
            final_exe_path = self.stockfish_dir / "bin" / "stockfish.exe"
            final_exe_path.parent.mkdir(exist_ok=True)

            if final_exe_path.exists():
                final_exe_path.unlink()  # Remove old version

            exe_path.replace(final_exe_path)

            # Save version info
            version_file = self.stockfish_dir / "version.txt"
            version_file.write_text(version)

            # Save metadata
            metadata = {
                "version": version,
                "download_url": download_url,
                "installed_at": str(Path.cwd()),
                "executable_path": str(final_exe_path),
            }

            metadata_file = self.stockfish_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2))

            # Cleanup
            try:
                import shutil

                shutil.rmtree(temp_extract)
                download_path.unlink()
            except Exception as error:
                self._logger.warning(f"Cleanup failed: {error}")

            update_progress("Installation complete!", 100, 100)
            self._logger.info(f"Successfully installed Stockfish {version}")
            return True

        except Exception as error:
            self._logger.error(f"Installation failed: {error}")
            update_progress(f"Installation failed: {error}")
            return False

    def get_installed_executable_path(self) -> Path | None:
        """
        Get the path to the installed Stockfish executable.

        Returns:
            Path to executable or None if not installed
        """
        exe_path = self.stockfish_dir / "bin" / "stockfish.exe"
        return exe_path if exe_path.exists() else None
