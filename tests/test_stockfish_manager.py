"""Tests for StockfishManager and related functionality."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from openboard.engine.stockfish_manager import StockfishManager
from openboard.engine.downloader import StockfishDownloader


class TestStockfishManager(unittest.TestCase):
    """Test cases for StockfishManager."""

    def setUp(self):
        """Set up test fixtures."""
        # Use temporary directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.install_dir = Path(self.temp_dir)
        self.manager = StockfishManager(self.install_dir)

    def test_manager_initialization(self):
        """Test manager initializes correctly."""
        self.assertIsNotNone(self.manager.downloader)
        self.assertIsNotNone(self.manager.detector)
        self.assertEqual(self.manager.downloader.install_dir, self.install_dir)

    def test_get_status_no_engines(self):
        """Test status when no engines are installed."""
        with patch.object(self.manager.detector, 'find_engine', return_value=None):
            status = self.manager.get_status()
            
            self.assertFalse(status["system_installed"])
            self.assertFalse(status["local_installed"])
            self.assertIsNone(status["system_path"])
            self.assertIsNone(status["local_path"])

    def test_get_status_system_engine_only(self):
        """Test status when only system engine is available."""
        mock_path = "/usr/bin/stockfish"
        
        with patch.object(self.manager.detector, 'find_engine', return_value=mock_path):
            with patch.object(self.manager.downloader, 'get_installed_executable_path', return_value=None):
                status = self.manager.get_status()
                
                self.assertTrue(status["system_installed"])
                self.assertFalse(status["local_installed"])
                self.assertEqual(status["system_path"], mock_path)

    def test_get_status_local_engine_only(self):
        """Test status when only local engine is available."""
        mock_local_path = self.install_dir / "stockfish" / "bin" / "stockfish.exe"
        mock_local_path.parent.mkdir(parents=True)
        mock_local_path.touch()
        
        # Create version file
        version_file = self.install_dir / "stockfish" / "version.txt"
        version_file.write_text("sf_17")
        
        with patch.object(self.manager.detector, 'find_engine', return_value=None):
            status = self.manager.get_status()
            
            self.assertFalse(status["system_installed"])
            self.assertTrue(status["local_installed"])
            self.assertEqual(status["local_version"], "sf_17")

    def test_get_best_engine_path_prefers_local(self):
        """Test that local installation is preferred over system."""
        system_path = "/usr/bin/stockfish"
        local_path = self.install_dir / "stockfish" / "bin" / "stockfish.exe"
        local_path.parent.mkdir(parents=True)
        local_path.touch()
        
        with patch.object(self.manager.detector, 'find_engine', return_value=system_path):
            best_path = self.manager.get_best_engine_path()
            self.assertEqual(best_path, str(local_path))

    def test_can_install_windows_only(self):
        """Test that installation is only supported on Windows."""
        with patch('platform.system', return_value='Windows'):
            self.assertTrue(self.manager.can_install())
            
        with patch('platform.system', return_value='Linux'):
            self.assertFalse(self.manager.can_install())
            
        with patch('platform.system', return_value='Darwin'):
            self.assertFalse(self.manager.can_install())


class TestStockfishDownloader(unittest.TestCase):
    """Test cases for StockfishDownloader."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.install_dir = Path(self.temp_dir)
        self.downloader = StockfishDownloader(self.install_dir)

    def test_downloader_initialization(self):
        """Test downloader initializes correctly and creates directories."""
        self.assertTrue(self.downloader.install_dir.exists())
        self.assertTrue(self.downloader.stockfish_dir.exists())
        self.assertTrue(self.downloader.downloads_dir.exists())

    def test_get_installed_version_no_file(self):
        """Test version detection when no version file exists."""
        version = self.downloader.get_installed_version()
        self.assertIsNone(version)

    def test_get_installed_version_with_file(self):
        """Test version detection when version file exists."""
        version_file = self.downloader.stockfish_dir / "version.txt"
        version_file.write_text("sf_17")
        
        version = self.downloader.get_installed_version()
        self.assertEqual(version, "sf_17")

    def test_get_installed_executable_path_not_exists(self):
        """Test executable path when not installed."""
        path = self.downloader.get_installed_executable_path()
        self.assertIsNone(path)

    def test_get_installed_executable_path_exists(self):
        """Test executable path when installed."""
        exe_path = self.downloader.stockfish_dir / "bin" / "stockfish.exe"
        exe_path.parent.mkdir(parents=True)
        exe_path.touch()
        
        path = self.downloader.get_installed_executable_path()
        self.assertEqual(path, exe_path)

    @patch('openboard.engine.downloader.urlopen')
    def test_get_latest_version_success(self, mock_urlopen):
        """Test successful version fetching."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"tag_name": "sf_17"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        version = self.downloader.get_latest_version()
        self.assertEqual(version, "sf_17")

    @patch('openboard.engine.downloader.urlopen')
    def test_get_latest_version_failure(self, mock_urlopen):
        """Test version fetching failure."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network error")
        
        version = self.downloader.get_latest_version()
        self.assertIsNone(version)

    def test_find_windows_binary_url(self):
        """Test finding Windows binary URL from release data."""
        release_data = {
            "assets": [
                {"name": "stockfish-linux-x86-64.tar.gz", "browser_download_url": "linux_url"},
                {"name": "stockfish-windows-x86-64-avx2.zip", "browser_download_url": "windows_url"},
                {"name": "stockfish-macos-arm64.tar.gz", "browser_download_url": "macos_url"}
            ]
        }
        
        url = self.downloader.find_windows_binary_url(release_data)
        self.assertEqual(url, "windows_url")

    def test_find_windows_binary_url_not_found(self):
        """Test when no Windows binary is found."""
        release_data = {
            "assets": [
                {"name": "stockfish-linux-x86-64.tar.gz", "browser_download_url": "linux_url"},
                {"name": "stockfish-macos-arm64.tar.gz", "browser_download_url": "macos_url"}
            ]
        }
        
        url = self.downloader.find_windows_binary_url(release_data)
        self.assertIsNone(url)


class TestEngineDetectionWithLocalInstallation(unittest.TestCase):
    """Test engine detection with local installation priority."""

    def setUp(self):
        """Set up test fixtures."""
        from openboard.engine.engine_detection import EngineDetector
        self.detector = EngineDetector()

    def test_local_installation_priority(self):
        """Test that local installation is checked first."""
        # Mock the _check_local_installation to return a local path
        mock_local_path = "/test/openboard/engines/stockfish/bin/stockfish.exe"
        
        with patch.object(self.detector, '_check_local_installation', return_value=mock_local_path):
            with patch.object(self.detector, '_check_in_path', return_value='/usr/bin/stockfish'):
                result = self.detector.find_engine("stockfish")
                
                # Should return local path, not system path
                self.assertEqual(result, mock_local_path)

    def test_fallback_to_system_path(self):
        """Test fallback to system PATH when local installation not found."""
        # Mock no local installation
        with patch('pathlib.Path.exists', return_value=False):
            with patch('shutil.which', return_value='/usr/bin/stockfish'):
                with patch.object(self.detector, '_is_valid_engine', return_value=True):
                    result = self.detector.find_engine("stockfish")
                    
                    self.assertEqual(result, '/usr/bin/stockfish')


if __name__ == '__main__':
    unittest.main()