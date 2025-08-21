"""Stockfish downloader utilities for managing engine installations."""

import hashlib
import json
import logging
import platform
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


class StockfishDownloader:
    """Handles downloading and extracting Stockfish engines."""
    
    # Stockfish GitHub releases API
    GITHUB_API_URL = "https://api.github.com/repos/official-stockfish/Stockfish/releases"
    LATEST_RELEASE_URL = f"{GITHUB_API_URL}/latest"
    
    # Windows binary patterns
    WINDOWS_BINARY_PATTERNS = [
        "stockfish-windows-x86-64-avx2.zip",
        "stockfish-windows-x86-64-sse41-popcnt.zip", 
        "stockfish-windows-x86-64-ssse3.zip",
        "stockfish-windows-x86-64.zip"
    ]
    
    def __init__(self, install_dir: Optional[Path] = None):
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
        
        # Ensure directories exist
        self.install_dir.mkdir(exist_ok=True)
        self.stockfish_dir.mkdir(exist_ok=True) 
        self.downloads_dir.mkdir(exist_ok=True)

    def get_latest_version(self) -> Optional[str]:
        """
        Get the latest Stockfish version from GitHub releases.
        
        Returns:
            Version string (e.g. "sf_17") or None if unable to fetch
        """
        try:
            request = Request(self.LATEST_RELEASE_URL)
            request.add_header('User-Agent', 'OpenBoard Chess GUI')
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('tag_name')
                
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Failed to fetch latest version: {e}")
            return None

    def get_installed_version(self) -> Optional[str]:
        """
        Get the currently installed Stockfish version.
        
        Returns:
            Version string or None if not installed/unknown
        """
        version_file = self.stockfish_dir / "version.txt"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except Exception as e:
                logger.warning(f"Could not read version file: {e}")
                
        return None

    def find_windows_binary_url(self, release_data: Dict[str, Any]) -> Optional[str]:
        """
        Find the best Windows binary download URL from release assets.
        
        Args:
            release_data: GitHub release data
            
        Returns:
            Download URL or None if not found
        """
        assets = release_data.get('assets', [])
        
        # Try to find the best binary in order of preference
        for pattern in self.WINDOWS_BINARY_PATTERNS:
            for asset in assets:
                if pattern in asset.get('name', '').lower():
                    return asset.get('browser_download_url')
                    
        return None

    def download_file(
        self, 
        url: str, 
        dest_path: Path, 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download a file with optional progress reporting.
        
        Args:
            url: URL to download from
            dest_path: Destination file path
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            request = Request(url)
            request.add_header('User-Agent', 'OpenBoard Chess GUI')
            
            with urlopen(request, timeout=30) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                            
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
                            
                logger.info(f"Downloaded {dest_path.name} ({downloaded} bytes)")
                return True
                
        except (URLError, HTTPError, OSError) as e:
            logger.error(f"Failed to download {url}: {e}")
            if dest_path.exists():
                dest_path.unlink()  # Clean up partial download
            return False

    def extract_zip(self, zip_path: Path, extract_to: Path) -> bool:
        """
        Extract a ZIP file to the specified directory.
        
        Args:
            zip_path: Path to ZIP file
            extract_to: Directory to extract to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(extract_to)
                
            logger.info(f"Extracted {zip_path.name} to {extract_to}")
            return True
            
        except (zipfile.BadZipFile, OSError) as e:
            logger.error(f"Failed to extract {zip_path}: {e}")
            return False

    def find_stockfish_executable(self, extract_dir: Path) -> Optional[Path]:
        """
        Find the Stockfish executable in the extracted directory.
        
        Args:
            extract_dir: Directory where files were extracted
            
        Returns:
            Path to executable or None if not found
        """
        # Common executable names
        exe_names = ["stockfish.exe", "stockfish"]
        
        # Search recursively for the executable
        for exe_name in exe_names:
            for exe_path in extract_dir.rglob(exe_name):
                if exe_path.is_file():
                    return exe_path
                    
        return None

    def download_and_install_latest(
        self, 
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """
        Download and install the latest Stockfish version.
        
        Args:
            progress_callback: Optional callback(status_message, progress, total)
            
        Returns:
            True if successful, False otherwise
        """
        if platform.system().lower() != 'windows':
            logger.error("Automatic installation only supported on Windows")
            return False
            
        def update_progress(message: str, current: int = 0, total: int = 100):
            if progress_callback:
                progress_callback(message, current, total)
                
        try:
            update_progress("Fetching latest version info...")
            
            # Get latest release info
            request = Request(self.LATEST_RELEASE_URL)
            request.add_header('User-Agent', 'OpenBoard Chess GUI')
            
            with urlopen(request, timeout=10) as response:
                release_data = json.loads(response.read().decode('utf-8'))
                
            version = release_data.get('tag_name')
            if not version:
                logger.error("Could not determine latest version")
                return False
                
            update_progress(f"Found version {version}")
            
            # Find Windows binary URL
            download_url = self.find_windows_binary_url(release_data)
            if not download_url:
                logger.error("No compatible Windows binary found")
                return False
                
            # Download the binary
            filename = download_url.split('/')[-1]
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
                logger.error("Could not find Stockfish executable in archive")
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
                "executable_path": str(final_exe_path)
            }
            
            metadata_file = self.stockfish_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2))
            
            # Cleanup
            try:
                import shutil
                shutil.rmtree(temp_extract)
                download_path.unlink()
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
                
            update_progress("Installation complete!", 100, 100)
            logger.info(f"Successfully installed Stockfish {version}")
            return True
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            update_progress(f"Installation failed: {e}")
            return False

    def get_installed_executable_path(self) -> Optional[Path]:
        """
        Get the path to the installed Stockfish executable.
        
        Returns:
            Path to executable or None if not installed
        """
        exe_path = self.stockfish_dir / "bin" / "stockfish.exe"
        return exe_path if exe_path.exists() else None