"""Engine detection utilities for finding UCI chess engines on the system."""

import os
import shutil
import platform
from pathlib import Path
from typing import Optional, List, Dict


class EngineDetector:
    """Utility class for detecting UCI chess engines on the system."""

    # Common engine names and their typical executable names
    ENGINE_NAMES = {
        "stockfish": [
            "stockfish",
            "stockfish.exe",
            "stockfish-windows-x86-64-avx2.exe",
        ],
        "leela": ["lc0", "lc0.exe", "leela", "leela.exe"],
        "komodo": ["komodo", "komodo.exe"],
        "dragon": ["dragon", "dragon.exe"],
    }

    # Common installation paths by platform
    COMMON_PATHS = {
        "linux": [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/stockfish/bin",
            "~/.local/bin",
        ],
        "darwin": [  # macOS
            "/usr/local/bin",
            "/opt/homebrew/bin",
            "/usr/bin",
            "~/Applications/Stockfish",
        ],
        "windows": [
            r"C:\Program Files\Stockfish",
            r"C:\Program Files (x86)\Stockfish",
            r"C:\stockfish",
            os.path.expanduser(r"~\AppData\Local\Stockfish"),
        ],
    }

    def __init__(self):
        self.system = platform.system().lower()

    def find_engine(self, engine_name: str = "stockfish") -> Optional[str]:
        """
        Find a chess engine executable on the system.

        Args:
            engine_name: Name of the engine to find (default: "stockfish")

        Returns:
            Path to the engine executable, or None if not found
        """
        # First check local OpenBoard installation
        local_result = self._check_local_installation(engine_name)
        if local_result:
            return local_result

        # Then check if it's in PATH
        path_result = self._check_in_path(engine_name)
        if path_result:
            return path_result

        # Finally check common installation locations
        return self._check_common_paths(engine_name)

    def _check_local_installation(
        self, engine_name: str = "stockfish"
    ) -> Optional[str]:
        """
        Check for locally installed engines in OpenBoard's engines directory.

        Args:
            engine_name: Name of the engine to find

        Returns:
            Path to the engine executable, or None if not found
        """
        if engine_name != "stockfish":
            return None  # Currently only support Stockfish

        # Check OpenBoard's local installation directory
        local_engines_dir = Path.cwd() / "engines" / "stockfish" / "bin"

        if not local_engines_dir.exists():
            return None

        # Look for Stockfish executable
        possible_names = ["stockfish.exe", "stockfish"]

        for name in possible_names:
            exe_path = local_engines_dir / name
            if exe_path.exists() and self._is_valid_engine(str(exe_path)):
                return str(exe_path)

        return None

    def _check_in_path(self, engine_name: str) -> Optional[str]:
        """Check if the engine is available in system PATH."""
        possible_names = self.ENGINE_NAMES.get(engine_name, [engine_name])

        for name in possible_names:
            path = shutil.which(name)
            if path and self._is_valid_engine(path):
                return path
        return None

    def _check_common_paths(self, engine_name: str) -> Optional[str]:
        """Check common installation paths for the engine."""
        possible_names = self.ENGINE_NAMES.get(engine_name, [engine_name])
        common_paths = self.COMMON_PATHS.get(self.system, [])

        for base_path in common_paths:
            expanded_path = Path(os.path.expanduser(base_path))
            if not expanded_path.exists():
                continue

            for name in possible_names:
                engine_path = expanded_path / name
                if engine_path.exists() and self._is_valid_engine(str(engine_path)):
                    return str(engine_path)
        return None

    def _is_valid_engine(self, path: str) -> bool:
        """
        Verify that the path points to a valid executable.

        Args:
            path: Path to check

        Returns:
            True if path is executable, False otherwise
        """
        try:
            path_obj = Path(path)
            return path_obj.exists() and path_obj.is_file() and os.access(path, os.X_OK)
        except (OSError, PermissionError):
            return False

    def get_installation_instructions(
        self, engine_name: str = "stockfish"
    ) -> Dict[str, str]:
        """
        Get platform-specific installation instructions for an engine.

        Args:
            engine_name: Name of the engine

        Returns:
            Dict with installation instructions for different platforms
        """
        if engine_name == "stockfish":
            return {
                "linux": """Install Stockfish using your package manager:
    Ubuntu/Debian: sudo apt install stockfish
    Fedora: sudo dnf install stockfish
    Arch: sudo pacman -S stockfish
    Or download from: https://stockfishchess.org/download/""",
                "darwin": """Install Stockfish using Homebrew:
    brew install stockfish
    Or download from: https://stockfishchess.org/download/""",
                "windows": """Download and install Stockfish from:
    https://stockfishchess.org/download/
    Make sure to add it to your PATH or place it in a standard location.""",
            }

        return {
            "generic": f"Please install {engine_name} and ensure it's available in your system PATH."
        }

    def list_available_engines(self) -> List[str]:
        """
        List all available UCI engines found on the system.

        Returns:
            List of paths to available engines
        """
        found_engines = []

        for engine_name in self.ENGINE_NAMES.keys():
            path = self.find_engine(engine_name)
            if path:
                found_engines.append(path)

        return found_engines
