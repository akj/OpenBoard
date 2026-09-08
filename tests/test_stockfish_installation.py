"""Exercise downloads, release selection, and installation using real ZIP files."""

import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from openboard.engine.downloader import StockfishDownloader
from openboard.engine.stockfish_manager import StockfishManager
from openboard.exceptions import DownloadError, NetworkError


def response(payload, length=None):
    result = MagicMock()
    result.__enter__.return_value = result
    result.read.side_effect = io.BytesIO(payload).read
    result.getheader.return_value = str(len(payload) if length is None else length)
    return result


@pytest.mark.parametrize("machine,arch", [("AMD64", "x86-64"), ("ARM64", "arm64")])
def test_selects_native_universal_asset(tmp_path, machine, arch):
    downloader = StockfishDownloader(tmp_path)
    assets = [
        {"name": f"stockfish-windows-{name}-universal.zip"}
        for name in ("arm64", "x86-64")
    ]
    with patch("platform.machine", return_value=machine):
        assert downloader.find_windows_asset({"assets": assets}) == {
            "name": f"stockfish-windows-{arch}-universal.zip"
        }


@pytest.mark.parametrize("failure", ["network", "truncated", "checksum"])
def test_failed_download_preserves_destination_and_cleans_partial(tmp_path, failure):
    downloader = StockfishDownloader(tmp_path)
    destination = tmp_path / "archive.zip"
    destination.write_bytes(b"previous download")
    incoming = response(b"new", length=10 if failure == "truncated" else 3)
    if failure == "network":
        incoming.read.side_effect = [b"new", URLError("disconnected")]
    with patch("openboard.engine.downloader.urlopen", return_value=incoming):
        with pytest.raises((DownloadError, NetworkError)):
            downloader.download_file(
                "https://example.com/archive.zip",
                destination,
                expected_sha256="0" * 64 if failure == "checksum" else None,
            )
    assert destination.read_bytes() == b"previous download"
    assert not list(tmp_path.glob(".archive.zip.*"))


@pytest.mark.parametrize(
    "failure", [None, "checksum", "missing_digest", "metadata", "replace", "rollback"]
)
def test_install_keeps_prior_version_on_failure(tmp_path, monkeypatch, caplog, failure):
    downloader = StockfishDownloader(tmp_path)
    executable = downloader.stockfish_dir / "bin" / "stockfish.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"old engine")
    version_file = downloader.stockfish_dir / "version.txt"
    version_file.write_text("sf_old")
    payload = b"MZ" + b"engine" * 1000
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("stockfish/stockfish-windows-x86-64.exe", payload)
    zipped_bytes = archive.getvalue()
    digest = (
        "0" * 64 if failure == "checksum" else hashlib.sha256(zipped_bytes).hexdigest()
    )
    release = {
        "tag_name": "sf_test",
        "assets": [
            {
                "name": "stockfish-windows-x86-64-universal.zip",
                "browser_download_url": "https://example.com/stockfish.zip",
                "digest": None if failure == "missing_digest" else f"sha256:{digest}",
            }
        ],
    }
    write_text = Path.write_text
    replace = Path.replace

    def write_metadata(path, *args, **kwargs):
        if failure == "metadata" and path.name == "metadata.json":
            raise OSError("metadata write failed")
        return write_text(path, *args, **kwargs)

    def replace_installation(path, target):
        if failure in {"replace", "rollback"} and path.name == "installation":
            raise PermissionError("cannot replace installation")
        if failure == "rollback" and path.name == "previous":
            raise PermissionError("cannot restore installation")
        return replace(path, target)

    monkeypatch.setattr(Path, "write_text", write_metadata)
    monkeypatch.setattr(Path, "replace", replace_installation)
    success = failure is None
    with (
        patch("platform.system", return_value="Windows"),
        patch("platform.machine", return_value="AMD64"),
        patch(
            "openboard.engine.downloader.urlopen",
            side_effect=[
                response(json.dumps(release).encode()),
                response(zipped_bytes),
            ],
        ),
    ):
        assert downloader.download_and_install_latest() is success
    if failure == "rollback":
        backups = list(downloader.downloads_dir.glob("*/previous"))
        assert len(backups) == 1
        assert (backups[0] / "bin" / "stockfish.exe").read_bytes() == b"old engine"
        assert (backups[0] / "version.txt").read_text() == "sf_old"
        assert str(backups[0]) in caplog.text
        return
    assert executable.read_bytes() == (payload if success else b"old engine")
    assert version_file.read_text() == ("sf_test" if success else "sf_old")
    assert list(downloader.downloads_dir.iterdir()) == []


def test_local_status_never_contacts_network(tmp_path):
    manager = StockfishManager(tmp_path)
    executable = manager.downloader.stockfish_dir / "bin" / "stockfish.exe"
    executable.parent.mkdir()
    executable.touch()
    with (
        patch.object(manager.detector, "find_engine", return_value=None),
        patch.object(manager.downloader, "get_latest_version") as latest,
    ):
        assert manager.get_status()["local_installed"]
        latest.assert_not_called()


def test_failed_update_check_does_not_report_up_to_date(tmp_path):
    manager = StockfishManager(tmp_path)
    events = []
    manager.installation_completed.connect(
        lambda sender, **event: events.append(event), weak=False
    )
    with (
        patch.object(manager, "get_status", return_value={"local_installed": True}),
        patch.object(manager.downloader, "get_latest_version", return_value=None),
    ):
        assert not manager.update_stockfish()
    assert events[0]["success"] is False


def test_manager_events_belong_to_one_instance(tmp_path):
    first = StockfishManager(tmp_path / "one")
    second = StockfishManager(tmp_path / "two")
    events = []
    first.installation_progress.connect(
        lambda sender, **event: events.append(event), weak=False
    )
    second.installation_progress.send(second, message="another installation")
    assert events == []
