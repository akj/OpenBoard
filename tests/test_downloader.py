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
        with patch("openboard.engine.downloader.urlopen", side_effect=URLError("DNS failure")):
            with pytest.raises(NetworkError):
                downloader.download_file(url="https://example.com/x", dest_path=tmp_path / "x")

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
            with patch("builtins.open", side_effect=OSError("disk full")):
                with pytest.raises(DownloadError):
                    downloader.download_file(
                        url="https://example.com/x",
                        dest_path=tmp_path / "x",
                    )


class TestConcernsTraceability:
    """Verifies TD-14 / D-26 Plan 5 deliverable: tests/CONCERNS_TRACEABILITY.md exists and is complete."""

    def test_concerns_traceability_doc_exists_and_lists_all_td(self):
        """Verifies TD-14: every TD-01..TD-14 appears in tests/CONCERNS_TRACEABILITY.md."""
        from pathlib import Path

        # Resolve the audit doc relative to this test file rather than the cwd. Pytest
        # may be invoked from any directory and the relative form silently degrades to
        # FileNotFoundError instead of a clear assertion failure.
        doc_path = Path(__file__).parent / "CONCERNS_TRACEABILITY.md"
        assert doc_path.exists(), (
            f"TD-14: {doc_path} must be created (Plan 5 deliverable)"
        )

        content = doc_path.read_text()
        for td_index in range(1, 15):
            token = f"TD-{td_index:02d}"
            assert token in content, (
                f"TD-14: {token} must be referenced in {doc_path}"
            )

    def test_concerns_traceability_references_canonical_td04_fixture(self):
        """Verifies TD-14 / Codex MEDIUM cross-plan: traceability doc references the canonical TD-04 fixture by exact name.

        Plan 01 added `pinned_attacker_fen` to tests/conftest.py (FEN
        `4r3/8/8/8/8/8/8/4K3 w - - 0 1`). Plan 03 added the regression test
        `tests/test_chess_controller.py::TestAnnounceAttackingPieces::test_announce_attacking_pieces_includes_pinned_attacker`.
        Codex MEDIUM cross-plan: Plan 05's traceability doc MUST reference these by EXACT NAME.
        """
        from pathlib import Path

        doc_path = Path(__file__).parent / "CONCERNS_TRACEABILITY.md"
        content = doc_path.read_text()

        # Exact fixture name (Codex MEDIUM cross-plan).
        assert "pinned_attacker_fen" in content, (
            "TD-14 / Codex MEDIUM cross-plan: tests/CONCERNS_TRACEABILITY.md must reference "
            "the canonical TD-04 fixture by exact name `pinned_attacker_fen`."
        )
        # Exact FEN string.
        assert "4r3/8/8/8/8/8/8/4K3 w - - 0 1" in content, (
            "TD-14 / Codex MEDIUM cross-plan: tests/CONCERNS_TRACEABILITY.md must include "
            "the canonical TD-04 FEN literal `4r3/8/8/8/8/8/8/4K3 w - - 0 1`."
        )
        # Exact test name (per Plan 03).
        assert "test_announce_attacking_pieces_includes_pinned_attacker" in content, (
            "TD-14 / Codex MEDIUM cross-plan: tests/CONCERNS_TRACEABILITY.md must reference "
            "the canonical TD-04 test name `test_announce_attacking_pieces_includes_pinned_attacker`."
        )
