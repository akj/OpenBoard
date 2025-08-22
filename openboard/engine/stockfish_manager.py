"""Stockfish engine management service with signal-based updates."""

import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any

from blinker import signal

from .downloader import StockfishDownloader
from .engine_detection import EngineDetector

logger = logging.getLogger(__name__)


class StockfishManager:
    """
    High-level service for managing Stockfish installation and updates.

    Emits signals for UI updates:
    - installation_started(sender, version)
    - installation_progress(sender, message, current, total)
    - installation_completed(sender, success, message)
    - update_available(sender, current_version, latest_version)
    """

    # Signals for UI communication
    installation_started = signal("installation_started")
    installation_progress = signal("installation_progress")
    installation_completed = signal("installation_completed")
    update_available = signal("update_available")

    def __init__(self, install_dir: Optional[Path] = None):
        """
        Initialize the manager.

        Args:
            install_dir: Directory for engine installations. Defaults to <cwd>/engines
        """
        self.downloader = StockfishDownloader(install_dir)
        self.detector = EngineDetector()
        self._logger = logging.getLogger(__name__)

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive Stockfish status information.

        Returns:
            Dictionary with status details
        """
        status = {
            "system_installed": False,
            "system_path": None,
            "local_installed": False,
            "local_path": None,
            "local_version": None,
            "latest_version": None,
            "update_available": False,
            "platform_supported": platform.system().lower() == "windows",
        }

        # Check system installation
        system_path = self.detector.find_engine("stockfish")
        if system_path:
            status["system_installed"] = True
            status["system_path"] = system_path

        # Check local installation
        local_path = self.downloader.get_installed_executable_path()
        if local_path and local_path.exists():
            status["local_installed"] = True
            status["local_path"] = str(local_path)
            status["local_version"] = self.downloader.get_installed_version()

        # Check for updates (if locally installed)
        if status["local_installed"]:
            latest_version = self.downloader.get_latest_version()
            status["latest_version"] = latest_version

            if latest_version and status["local_version"]:
                status["update_available"] = latest_version != status["local_version"]

        return status

    def get_best_engine_path(self) -> Optional[str]:
        """
        Get the best available Stockfish executable path.
        Prefers local installation over system installation.

        Returns:
            Path to executable or None if not found
        """
        # Check local installation first
        local_path = self.downloader.get_installed_executable_path()
        if local_path and local_path.exists():
            return str(local_path)

        # Fall back to system installation
        return self.detector.find_engine("stockfish")

    def can_install(self) -> bool:
        """
        Check if automatic installation is supported on this platform.

        Returns:
            True if installation is supported
        """
        return platform.system().lower() == "windows"

    def install_stockfish(self) -> bool:
        """
        Install the latest Stockfish version.
        Emits signals to update UI during the process.

        Returns:
            True if successful, False otherwise
        """
        if not self.can_install():
            self._logger.error("Automatic installation not supported on this platform")
            self.installation_completed.send(
                self,
                success=False,
                message="Automatic installation not supported on this platform",
            )
            return False

        try:
            # Get latest version info first
            latest_version = self.downloader.get_latest_version()
            if not latest_version:
                self.installation_completed.send(
                    self,
                    success=False,
                    message="Could not determine latest Stockfish version",
                )
                return False

            self.installation_started.send(self, version=latest_version)

            def progress_callback(message: str, current: int, total: int):
                self.installation_progress.send(
                    self, message=message, current=current, total=total
                )

            success = self.downloader.download_and_install_latest(progress_callback)

            if success:
                self.installation_completed.send(
                    self,
                    success=True,
                    message=f"Successfully installed Stockfish {latest_version}",
                )
            else:
                self.installation_completed.send(
                    self,
                    success=False,
                    message="Installation failed. Check logs for details.",
                )

            return success

        except Exception as e:
            self._logger.error(f"Installation error: {e}")
            self.installation_completed.send(
                self, success=False, message=f"Installation failed: {str(e)}"
            )
            return False

    def update_stockfish(self) -> bool:
        """
        Update Stockfish to the latest version.

        Returns:
            True if successful, False otherwise
        """
        status = self.get_status()

        if not status["local_installed"]:
            self._logger.info("No local installation found, performing fresh install")
            return self.install_stockfish()

        if not status["update_available"]:
            self.installation_completed.send(
                self, success=True, message="Stockfish is already up to date"
            )
            return True

        self._logger.info(
            f"Updating from {status['local_version']} to {status['latest_version']}"
        )
        return self.install_stockfish()  # Same process as installation

    def check_for_updates(self) -> Optional[str]:
        """
        Check if updates are available.
        Emits update_available signal if an update is found.

        Returns:
            Latest version if update available, None otherwise
        """
        status = self.get_status()

        if status["update_available"]:
            self.update_available.send(
                self,
                current_version=status["local_version"],
                latest_version=status["latest_version"],
            )
            return status["latest_version"]

        return None

    def get_installation_instructions(self) -> str:
        """
        Get platform-specific installation instructions.

        Returns:
            Installation instructions string
        """
        if self.can_install():
            return "Use Engine > Install Stockfish to automatically download and install the latest version."
        else:
            instructions = self.detector.get_installation_instructions("stockfish")
            system_instructions = instructions.get(
                self.detector.system, instructions.get("generic", "")
            )
            return system_instructions

    def uninstall_local_stockfish(self) -> bool:
        """
        Remove locally installed Stockfish.

        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil

            if self.downloader.stockfish_dir.exists():
                shutil.rmtree(self.downloader.stockfish_dir)
                self._logger.info("Local Stockfish installation removed")
                return True
            else:
                self._logger.info("No local installation found")
                return True

        except Exception as e:
            self._logger.error(f"Failed to uninstall: {e}")
            return False
