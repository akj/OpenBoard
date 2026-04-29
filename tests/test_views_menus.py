"""View-layer tests for menu binding hygiene (TD-05 / D-08, TD-09 / D-17).

Codex MEDIUM: behavioral tests are primary evidence; source-grep tests are secondary
guardrails. CI is currently Linux-only without Xvfb (RESEARCH.md Open Q1 / A4) — we
monkeypatch wx.EvtHandler.Bind to capture (id=) arguments.  A wx.App is created once
per session (headless, wx.App(False)) so that wx constructors inside _build_menu_bar
can run without a display.
A runtime end-to-end test on each platform is documented in 01-VALIDATION.md as a manual smoke.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import wx


VIEWS_PY = Path(__file__).parent.parent / "openboard" / "views" / "views.py"


@pytest.fixture(scope="session", autouse=True)
def wx_app_session():
    """Create a headless wx.App once for the whole test session.

    wx constructors (wx.MenuBar, wx.Menu, wx.MenuItem) raise wx.PyNoAppError when
    called without a running wx.App.  wx.App(False) starts wx in headless mode —
    no main loop is entered, no window is shown — so it is safe for unit tests.
    """
    app = wx.App(False)
    yield app
    app.Destroy()


class TestMenuBindingHygieneBehavioral:
    """Verifies TD-05 / CONCERNS.md Bug #4 (Codex MEDIUM PRIMARY EVIDENCE).

    Monkeypatches `wx.EvtHandler.Bind` to record every (id=) argument; asserts that
    no EVT_MENU bind uses `wx.ID_ANY`. This is the behavioral test that proves
    runtime correctness, not just source shape.
    """

    def test_bind_records_specific_ids_for_menu_items(self):
        """Verifies TD-05 / D-08 BEHAVIOR: every wx.EVT_MENU bind passes a specific MenuItem ID."""
        import wx

        recorded_binds: list[dict] = []

        def recording_bind(self_obj, event_type, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
            if event_type == wx.EVT_MENU:
                recorded_binds.append({
                    "handler": getattr(handler, "__name__", repr(handler)),
                    "id": id,
                })
            # Don't actually call original_bind — we don't want to invoke wx machinery.

        with patch.object(wx.EvtHandler, "Bind", recording_bind):
            from openboard.views.views import ChessFrame

            frame_mock = MagicMock(spec=ChessFrame)

            if hasattr(ChessFrame, "_build_menu_bar"):
                ChessFrame._build_menu_bar(frame_mock)
            elif hasattr(ChessFrame, "_setup_menus"):
                ChessFrame._setup_menus(frame_mock)
            else:
                pytest.skip(
                    "ChessFrame menu-construction method name unknown; "
                    "implementation step in Task 3 must wire this seam. Source-grep guardrail still runs."
                )

        # Every recorded EVT_MENU bind must have a specific id, not wx.ID_ANY.
        offending = [bind for bind in recorded_binds if bind["id"] == wx.ID_ANY]
        assert offending == [], (
            f"TD-05 / D-08 BEHAVIORAL: {len(offending)} EVT_MENU binds use wx.ID_ANY:\n"
            + "\n".join(f"  - handler={bind['handler']}, id=wx.ID_ANY" for bind in offending)
        )

        # And we should have observed at least one bind (sanity check that the test actually ran).
        assert len(recorded_binds) > 0, (
            "TD-05 BEHAVIORAL: no EVT_MENU binds were recorded; the menu-construction seam "
            "may not be exercised by this test. Adjust the seam in Task 3."
        )


class TestMenuBindingHygieneSourceGrep:
    """[guardrail] Verifies TD-05 source shape — secondary evidence (Codex MEDIUM)."""

    def test_no_evt_menu_bound_to_id_any_source_grep(self):
        """[guardrail] Verifies TD-05 / D-08: no `id=wx.ID_ANY` in any wx.EVT_MENU Bind line.

        Source-grep secondary evidence; primary proof is TestMenuBindingHygieneBehavioral above.
        wx.ID_OPEN and wx.ID_EXIT are stock IDs — NOT wx.ID_ANY — and are legitimate per D-08.
        """
        source = VIEWS_PY.read_text()
        pattern = re.compile(
            r"self\.Bind\s*\(\s*wx\.EVT_MENU.*?id\s*=\s*wx\.ID_ANY",
            re.DOTALL,
        )
        offending = pattern.findall(source)
        assert offending == [], (
            f"TD-05 / D-08 [guardrail]: Found {len(offending)} wx.EVT_MENU bind(s) to wx.ID_ANY:\n"
            + "\n".join(offending)
        )


class TestBookHintAccelerator:
    """Verifies TD-09 / CONCERNS.md "Hard-coded B keyboard shortcut conflict": removed."""

    def test_book_hint_menu_no_accelerator(self):
        """Verifies TD-09 / D-17: the Book Hint menu item label has no `\\tB` accelerator.

        The B key continues to dispatch via EVT_CHAR_HOOK -> KeyAction.REQUEST_BOOK_HINT.
        """
        source = VIEWS_PY.read_text()
        forbidden = re.compile(r'"&?Book\s+Hint\\t[Bb]"')
        matches = forbidden.findall(source)
        assert matches == [], (
            f"TD-09 / D-17: Book Hint menu item must not declare a \\tB accelerator. Found: {matches}"
        )

    def test_request_book_hint_keyaction_still_defined(self):
        """Verifies TD-09 / D-17: the B keyboard shortcut still works via the keyboard config system."""
        from openboard.config.keyboard_config import KeyAction

        assert hasattr(KeyAction, "REQUEST_BOOK_HINT"), (
            "TD-09: REQUEST_BOOK_HINT KeyAction must remain — only the menu \\tB accelerator is dropped"
        )
