"""Startup-ordering regression tests for openboard/views/views.py — Codex HIGH.

Verifies the architectural invariant that importing openboard.views (without invoking
main() and without instantiating wx.App) does NOT initialize the settings singleton
or trigger migration. This catches the Pitfall 3 regression where a module-top
`settings = get_settings()` line would silently force settings init at import time
AND make migration a no-op for users with legacy cwd files.
"""

import importlib
import sys
from pathlib import Path

import pytest


def _clear_openboard_modules() -> dict:
    """Remove all openboard.* modules from sys.modules and return the removed snapshot."""
    snapshot = {
        module_name: module_obj
        for module_name, module_obj in sys.modules.items()
        if module_name.startswith("openboard")
    }
    for module_name in snapshot:
        sys.modules.pop(module_name, None)
    return snapshot


def _restore_openboard_modules(snapshot: dict) -> None:
    """Restore previously removed openboard.* modules to sys.modules."""
    # Remove any fresh imports that happened after the snapshot was taken.
    for module_name in list(sys.modules):
        if module_name.startswith("openboard"):
            sys.modules.pop(module_name, None)
    # Restore the original snapshot.
    sys.modules.update(snapshot)


class TestStartupOrdering:
    """Verifies Codex HIGH: import-time side effects are absent."""

    def test_import_views_does_not_initialize_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies Codex HIGH: `import openboard.views.views` does NOT initialize the _settings singleton.

        Approach: force a fresh import of openboard.views.views with _settings reset to None.
        If views.views runs `settings = get_settings()` at module top, get_settings() will
        set _settings to a real Settings() object (since it's None). After the import, we
        assert _settings is still None — confirming no module-top initialization occurred.

        Pre-fix: views.py has `settings = get_settings()` at module top, which initializes
        _settings from None to a real Settings instance — the assertion fails.
        Post-fix: that line is removed; _settings stays None after import.

        NOTE: the views package has no __init__.py, so `openboard.views` alone does not
        execute views.py. We must import `openboard.views.views` to reach views.py.
        """
        # Save a snapshot of sys.modules so we can restore test isolation.
        snapshot = _clear_openboard_modules()

        try:
            # Import settings module first so we have a reference, then reset _settings to None.
            import openboard.config.settings as settings_module
            settings_module._settings = None  # Start with None so get_settings() would initialize it.

            # Import views.views — if it calls get_settings() at module top, _settings will become
            # a real Settings() object. We detect this by asserting it stays None.
            importlib.import_module("openboard.views.views")

            assert settings_module._settings is None, (
                "Codex HIGH startup ordering: importing openboard.views.views must NOT call "
                "get_settings() at module top. _settings was initialized (became non-None), which "
                "means module-top code ran get_settings() — this defeats migrate_legacy_paths(), "
                "which must run BEFORE the first get_settings() call (Pitfall 3)."
            )
        finally:
            _restore_openboard_modules(snapshot)

    def test_import_views_does_not_trigger_migration(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies Codex HIGH: `import openboard.views.views` does NOT call migrate_legacy_paths().

        Migration is an explicit `main()` step, NOT an import side effect. If migration
        ran at import time, then test imports of openboard.views would scrabble around in
        the developer's actual cwd looking for legacy files — a real bug.
        """
        snapshot = _clear_openboard_modules()

        try:
            # Redirect any potential migration to tmp_path so a real cwd-relative lookup
            # would not pollute the developer's machine if the test ever fails.
            monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
            monkeypatch.chdir(tmp_path)

            with caplog.at_level("INFO"):
                # Import openboard.views.views to reach the actual views.py module
                # (the views package has no __init__.py so `openboard.views` alone
                # does not execute views.py).
                importlib.import_module("openboard.views.views")

            migrated_lines = [r for r in caplog.records if "Migrated" in r.message]
            assert migrated_lines == [], (
                "Codex HIGH startup ordering: importing openboard.views.views must NOT trigger "
                f"migrate_legacy_paths(). Got Migrated INFO lines: {[r.message for r in migrated_lines]}"
            )
        finally:
            _restore_openboard_modules(snapshot)
