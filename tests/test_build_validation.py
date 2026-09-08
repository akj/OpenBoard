"""Startup validation must exercise the application and reject broken builds."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT / ".build" / "validation" / "verify_build.py"
spec = importlib.util.spec_from_file_location("verify_build", VALIDATOR_PATH)
assert spec is not None and spec.loader is not None
verify_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_build)


def test_source_startup_smoke_check():
    report = verify_build.validate_startup(project_root=PROJECT_ROOT)
    assert report["status"] == "ok"
    assert report["legal_moves"] == 20
    assert report["move"] == "e2e4"


def test_source_check_from_another_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert verify_build.validate_startup(project_root=PROJECT_ROOT)["status"] == "ok"


def test_missing_executable_fails(tmp_path):
    with pytest.raises(verify_build.ValidationError, match="Executable not found"):
        verify_build.validate_startup(tmp_path / "missing")


@pytest.mark.parametrize("stdout", ["", "not JSON", "{}", "[]", '{"status": "ok"}'])
def test_exit_zero_without_smoke_result_fails(stdout):
    result = subprocess.CompletedProcess([], 0, stdout, "")
    with patch.object(verify_build.subprocess, "run", return_value=result):
        with pytest.raises(verify_build.ValidationError):
            verify_build.validate_startup()


def test_nonzero_exit_fails_with_stderr():
    result = subprocess.CompletedProcess([], 1, "", "Missing bundled dependency")
    with patch.object(verify_build.subprocess, "run", return_value=result):
        with pytest.raises(
            verify_build.ValidationError, match="Missing bundled dependency"
        ):
            verify_build.validate_startup()


def test_timeout_fails():
    with patch.object(
        verify_build.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired("OpenBoard", 1),
    ):
        with pytest.raises(verify_build.ValidationError, match="could not finish"):
            verify_build.validate_startup(timeout=1)


def test_packaged_check_uses_isolated_profile_and_working_directory(
    tmp_path, monkeypatch
):
    executable = tmp_path / "OpenBoard.exe"
    executable.touch()
    monkeypatch.setenv("PYTHONPATH", str(PROJECT_ROOT))
    original_profile = os.environ["OPENBOARD_PROFILE_DIR"]
    observed_profile = None

    def run(command, **kwargs):
        nonlocal observed_profile
        observed_profile = Path(kwargs["env"]["OPENBOARD_PROFILE_DIR"])
        assert observed_profile.is_dir()
        assert str(observed_profile) != original_profile
        assert kwargs["cwd"] == str(observed_profile)
        assert "PYTHONPATH" not in kwargs["env"]
        assert command == [str(executable.resolve()), "--self-test"]
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"check": "startup", "status": "ok"}), ""
        )

    with patch.object(verify_build.subprocess, "run", side_effect=run):
        verify_build.validate_startup(executable)
    assert observed_profile is not None and not observed_profile.exists()
    assert os.environ["OPENBOARD_PROFILE_DIR"] == original_profile


def test_validator_cli_checks_source():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--verbose"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Startup smoke check passed" in result.stdout


@pytest.fixture
def build_scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / ".build"))
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / ".build" / "installers" / "scripts"))
    modules = []
    for name, path in (
        ("build_openboard", PROJECT_ROOT / ".build" / "scripts" / "build.py"),
        (
            "build_installers",
            PROJECT_ROOT / ".build" / "installers" / "scripts" / "build_installer.py",
        ),
    ):
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def test_builder_rejects_missing_macos_binary_instead_of_checking_source(
    build_scripts, tmp_path
):
    build_module, _ = build_scripts
    with patch.object(
        build_module.OpenBoardBuilder, "_setup_logging", return_value=MagicMock()
    ):
        builder = build_module.OpenBoardBuilder(PROJECT_ROOT)
    builder.is_macos = True
    builder.is_windows = False
    builder.dist_dir = tmp_path
    assert (
        builder.executable_path
        == tmp_path / "OpenBoard.app" / "Contents" / "MacOS" / "OpenBoard"
    )
    with pytest.raises(build_module.BuildError, match="Command failed"):
        builder.run_build_validation()


def test_build_clean_preserves_wheels_and_unrelated_caches(build_scripts, tmp_path):
    build_module, _ = build_scripts
    builder = object.__new__(build_module.OpenBoardBuilder)
    builder.project_root = tmp_path
    builder.dist_dir = tmp_path / "dist"
    builder.build_dir = tmp_path / "build"
    builder.spec_file = tmp_path / "openboard.spec"
    builder.logger = MagicMock()
    executable_dir = builder.dist_dir / "OpenBoard"
    executable_dir.mkdir(parents=True)
    (executable_dir / "OpenBoard.exe").write_bytes(b"executable")
    wheel = builder.dist_dir / "package.whl"
    wheel.write_bytes(b"wheel")
    unrelated_cache = tmp_path / ".venv" / "__pycache__"
    unrelated_cache.mkdir(parents=True)
    builder._clean_build_artifacts()
    assert not executable_dir.exists()
    assert wheel.read_bytes() == b"wheel"
    assert unrelated_cache.is_dir()


def test_requested_rpm_failure_does_not_return_only_deb(build_scripts, tmp_path):
    _, installers = build_scripts
    with (
        patch.object(
            installers, "build_deb_package", return_value=tmp_path / "openboard.deb"
        ),
        patch.object(installers, "build_rpm_package", return_value=None),
    ):
        with pytest.raises(RuntimeError, match="Requested rpm installer"):
            installers.build_for_platform(
                "linux", ["deb", "rpm"], tmp_path, "0.1.0", tmp_path
            )
