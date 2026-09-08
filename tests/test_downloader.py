"""Tests for openboard/engine/downloader.py — TD-11 / D-19 (non-security raise paths) + TD-14 audit."""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from openboard.exceptions import DownloadError, NetworkError


class TestDownloadFileExceptionWiring:
    """Verifies TD-11 / D-19: download_file raises NetworkError on URL failure, DownloadError on OS failure."""

    def test_network_error_on_url_failure(self, tmp_path):
        """Verifies D-19: a URLError during urlopen is wrapped as NetworkError."""
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)
        with patch(
            "openboard.engine.downloader.urlopen", side_effect=URLError("DNS failure")
        ):
            with pytest.raises(NetworkError):
                downloader.download_file(
                    url="https://example.com/x", dest_path=tmp_path / "x"
                )

    def test_download_error_on_os_error(self, tmp_path):
        """Verifies D-19: an OSError during file write is wrapped as DownloadError."""
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.read.side_effect = [b"abc", b""]
        fake_response.headers = {}
        fake_response.getheader.return_value = "3"

        # Patch urlopen to succeed but the open() to fail
        with patch("openboard.engine.downloader.urlopen", return_value=fake_response):
            with patch("tempfile.NamedTemporaryFile", side_effect=OSError("disk full")):
                with pytest.raises(DownloadError):
                    downloader.download_file(
                        url="https://example.com/x",
                        dest_path=tmp_path / "x",
                    )
