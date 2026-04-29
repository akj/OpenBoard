"""Security regression tests for openboard/engine/downloader.py — TD-13 / D-21 / D-22."""

import hashlib
import ssl
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openboard.exceptions import DownloadError


class TestSSLContext:
    """Verifies TD-13 / D-21 (Security #3): explicit ssl.create_default_context() on urlopen."""

    def test_download_uses_ssl_context(self, tmp_path: Path) -> None:
        """Verifies D-21 (Codex LOW one-line acceptance): urlopen receives context=ssl.create_default_context()."""
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.read.side_effect = [b"abc", b""]
        fake_response.headers = {}
        fake_response.getheader.return_value = "3"

        with patch("openboard.engine.downloader.urlopen", return_value=fake_response) as urlopen_mock:
            downloader.download_file(
                url="https://example.com/stockfish.zip",
                dest_path=tmp_path / "stockfish.zip",
            )

        assert urlopen_mock.called, "download_file must call urlopen"
        kwargs = urlopen_mock.call_args.kwargs
        ssl_context_arg = kwargs.get("context")
        assert ssl_context_arg is not None, "TD-13 / D-21: urlopen must receive context= kwarg"
        assert isinstance(ssl_context_arg, ssl.SSLContext)
        assert ssl_context_arg.verify_mode == ssl.CERT_REQUIRED


class TestSHA256Verification:
    """Verifies TD-13 / D-21 (Security #1): SHA-256 verification when checksum is provided."""

    def test_download_sha256_mismatch_raises(self, tmp_path: Path) -> None:
        """Verifies D-21: download_file raises DownloadError when expected_sha256 mismatches actual."""
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)
        payload = b"hello world"

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.read.side_effect = [payload, b""]
        fake_response.headers = {}
        fake_response.getheader.return_value = str(len(payload))

        wrong_hash = "0" * 64

        with patch("openboard.engine.downloader.urlopen", return_value=fake_response):
            with pytest.raises(DownloadError, match="sha256 mismatch"):
                downloader.download_file(
                    url="https://example.com/payload.bin",
                    dest_path=tmp_path / "payload.bin",
                    expected_sha256=wrong_hash,
                )

        # On mismatch, the partial file must be removed
        assert not (tmp_path / "payload.bin").exists()

    def test_download_sha256_match_succeeds(self, tmp_path: Path) -> None:
        """Verifies D-21: download_file accepts a correct expected_sha256 (no raise)."""
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)
        payload = b"hello world"
        correct_hash = hashlib.sha256(payload).hexdigest()

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.read.side_effect = [payload, b""]
        fake_response.headers = {}
        fake_response.getheader.return_value = str(len(payload))

        with patch("openboard.engine.downloader.urlopen", return_value=fake_response):
            result = downloader.download_file(
                url="https://example.com/payload.bin",
                dest_path=tmp_path / "payload.bin",
                expected_sha256=correct_hash,
            )

        assert result is True
        assert (tmp_path / "payload.bin").read_bytes() == payload

    def test_download_logs_debug_when_no_sha256(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies D-21 / Codex MEDIUM: log level is DEBUG (not WARN) when expected_sha256 is None.

        Codex MEDIUM: the original plan called WARNING per-download, which would be noisy if
        downloads are chunked or repeated. Revised: DEBUG per-download in download_file;
        a single INFO at startup in StockfishManager (covered by a separate test).
        """
        from openboard.engine.downloader import StockfishDownloader

        downloader = StockfishDownloader(install_dir=tmp_path)
        payload = b"hello"

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.read.side_effect = [payload, b""]
        fake_response.headers = {}
        fake_response.getheader.return_value = str(len(payload))

        with patch("openboard.engine.downloader.urlopen", return_value=fake_response):
            with caplog.at_level("DEBUG"):
                downloader.download_file(
                    url="https://example.com/payload.bin",
                    dest_path=tmp_path / "payload.bin",
                )

        debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert any(
            "SHA-256" in r.message or "integrity NOT verified" in r.message
            for r in debug_records
        ), (
            "TD-13 / D-21 / Codex MEDIUM: download_file must log a DEBUG (not WARN) message "
            f"when expected_sha256 is None. Got DEBUG records: {[r.message for r in debug_records]}"
        )

        # And explicitly: NO WARN-level log from this path.
        warn_records = [
            r for r in caplog.records
            if r.levelname == "WARNING" and ("SHA-256" in r.message or "integrity" in r.message)
        ]
        assert warn_records == [], (
            "Codex MEDIUM: per-download log must be DEBUG, not WARN. "
            f"Found WARN: {[r.message for r in warn_records]}"
        )

    def test_stockfish_manager_logs_single_startup_info_on_no_checksum_source(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies D-21 / Codex MEDIUM: StockfishManager logs ONE INFO at startup if no checksum source is configured.

        This satisfies the operator-visibility need without flooding logs on every download.
        """
        from openboard.engine.stockfish_manager import StockfishManager

        with caplog.at_level("INFO"):
            StockfishManager(Path(tmp_path))

        info_records = [
            r for r in caplog.records
            if r.levelname == "INFO" and "no upstream checksum source" in r.message.lower()
        ]
        assert len(info_records) == 1, (
            "Codex MEDIUM: StockfishManager must log exactly ONE INFO at startup if no "
            f"upstream checksum source is configured. Got {len(info_records)} INFO records."
        )


class TestZipPathTraversalGuard:
    """Verifies TD-13 / D-21 (Security #2): ZIP path-traversal protection in extract_zip."""

    def test_extract_zip_rejects_path_traversal(self, tmp_path: Path) -> None:
        """Verifies D-21: a ZIP member with `..` path components must be rejected with DownloadError."""
        from openboard.engine.downloader import StockfishDownloader

        install_dir = tmp_path / "install"
        install_dir.mkdir()
        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("../../etc/passwd", "compromised")

        downloader = StockfishDownloader(install_dir=install_dir)

        with pytest.raises(DownloadError, match="escapes extract dir"):
            downloader.extract_zip(bad_zip, install_dir)

        # The malicious path must NOT have been created anywhere outside install_dir
        assert not (tmp_path.parent / "etc" / "passwd").exists()

    def test_extract_zip_accepts_safe_archive(self, tmp_path: Path) -> None:
        """Verifies D-21: a normal archive without traversal extracts successfully."""
        from openboard.engine.downloader import StockfishDownloader

        install_dir = tmp_path / "install"
        install_dir.mkdir()
        ok_zip = tmp_path / "ok.zip"
        with zipfile.ZipFile(ok_zip, "w") as archive:
            archive.writestr("nested/file.txt", "safe content")

        downloader = StockfishDownloader(install_dir=install_dir)
        assert downloader.extract_zip(ok_zip, install_dir) is True
        assert (install_dir / "nested" / "file.txt").read_text() == "safe content"


class TestFilenameInvariant:
    """Verifies Codex HIGH: settings.json never appears in source — config.json is preserved."""

    def test_no_settings_json_filename_in_source_tree(self) -> None:
        """[guardrail] Verifies Codex HIGH: no `settings.json` filename anywhere in openboard/ or tests/.

        Phase 1 explicitly preserves the legacy `config.json` filename in the new platformdirs
        location. The rename to `settings.json` is DEFERRED. This grep guardrail catches any
        accidental drift toward the rename.

        See <filename_decision> in 01-04-PLAN.md.
        """
        result = subprocess.run(
            ["grep", "-rn", "settings.json", "openboard/", "tests/"],
            capture_output=True,
            text=True,
        )
        # Filter out the matches in this test file itself (which legitimately contain the token).
        offending_lines = [
            line for line in result.stdout.splitlines()
            if "test_downloader_security.py" not in line
            and "01-04-PLAN.md" not in line
        ]
        assert offending_lines == [], (
            "Codex HIGH: `settings.json` filename must NOT appear in openboard/ or tests/ "
            "(Phase 1 preserves legacy config.json). Found:\n"
            + "\n".join(offending_lines)
        )
