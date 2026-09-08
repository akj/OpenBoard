"""Hidden native wx controls with speech replaced by the shared test fixture."""

import ctypes
import sys
import uuid
import threading
import time
from unittest.mock import Mock

import chess
import pytest
import wx

from openboard.controllers.chess_controller import ChessController
from openboard.models.game import Game
from openboard.views.game_dialogs import MoveListDialog
from openboard.views.views import BoardPanel, ChessFrame
from openboard.views import views
from openboard.views.engine_dialogs import EngineInstallationRunner


@pytest.fixture(scope="module")
def app():
    existing = wx.GetApp()
    app = existing or wx.App(False)
    yield app
    if existing is None:
        app.Destroy()


@pytest.fixture
def frame(app, monkeypatch):
    monkeypatch.setattr(ChessFrame, "Show", lambda self: None)
    frame = ChessFrame(ChessController(Game()))
    app.ProcessPendingEvents()
    yield frame
    frame.controller.game.close()
    frame.Destroy()
    app.ProcessPendingEvents()


def test_frame_publishes_startup_only_after_speech_is_connected(frame, speech_output):
    messages = [call.args[0] for call in speech_output.speak.call_args_list]
    assert "Human vs Human" in messages
    assert frame.board_panel.AcceptsFocus()


def test_native_key_events_play_and_undo_a_move(frame, app):
    for code in [
        wx.WXK_UP,
        *([wx.WXK_RIGHT] * 4),
        wx.WXK_SPACE,
        wx.WXK_UP,
        wx.WXK_UP,
        wx.WXK_SPACE,
    ]:
        event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        event.SetKeyCode(code)
        wx.PostEvent(frame.board_panel, event)
        app.ProcessPendingEvents()
    assert frame.controller.game.board_state.board.peek() == chess.Move.from_uci("e2e4")
    assert frame.board_panel.focus == chess.E4
    assert frame.board_panel.selected is None
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetKeyCode(ord("Z"))
    event.SetControlDown(True)
    wx.PostEvent(frame.board_panel, event)
    app.ProcessPendingEvents()
    assert frame.board_panel.board.fen() == chess.STARTING_FEN


def test_engine_startup_leaves_gui_event_loop_responsive(frame, app, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    threads = []

    def start():
        threads.append(threading.get_ident())
        started.set()
        assert release.wait(2)

    engine = Mock(start=start, stop=stopped.set)
    monkeypatch.setattr(views, "EngineAdapter", lambda **kwargs: engine)
    frame.start_engine()
    try:
        assert started.wait(1)
        callbacks = []
        wx.CallAfter(callbacks.append, "responsive")
        app.ProcessPendingEvents()
        assert callbacks == ["responsive"]
        frame.controller.navigate("up")
        assert frame.controller.current_square == chess.A2
    finally:
        release.set()
    deadline = time.monotonic() + 2
    while frame.controller.game.engine_adapter is None and time.monotonic() < deadline:
        app.ProcessPendingEvents()
        time.sleep(0.01)
    assert frame.controller.game.engine_adapter is engine
    assert threads != [threading.get_ident()]
    frame.on_close(Mock())
    assert stopped.wait(1)


def test_close_during_engine_startup_stops_unattached_engine(frame, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    stopped = threading.Event()

    def start():
        started.set()
        assert release.wait(2)

    engine = Mock(start=start, stop=stopped.set)
    monkeypatch.setattr(views, "EngineAdapter", lambda **kwargs: engine)
    frame.start_engine()
    try:
        assert started.wait(1)
        frame.on_close(Mock())
    finally:
        release.set()
    assert stopped.wait(1)
    assert frame.controller.game.engine_adapter is None


def test_installation_worker_stops_loaded_engine_before_replacing_it():
    actions = []
    engine = Mock(stop=lambda: actions.append("stop"))
    manager = Mock(update_stockfish=lambda: actions.append("update"))
    runner = EngineInstallationRunner(None, manager, engine)
    worker = threading.Thread(target=runner._run_installation, args=(True,))
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert actions == ["stop", "update"]


def test_computer_game_continues_after_synchronous_book_move(frame, app):
    from openboard.models.game_mode import GameConfig, GameMode, DifficultyLevel

    book = Mock(is_loaded=True)
    book.get_move.side_effect = [
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
        None,
    ]
    frame.controller.game.opening_book = book
    frame.controller.new_game(
        GameConfig(
            mode=GameMode.COMPUTER_VS_COMPUTER,
            white_difficulty=DifficultyLevel.BEGINNER,
            black_difficulty=DifficultyLevel.BEGINNER,
        )
    )
    app.ProcessPendingEvents()
    app.ProcessPendingEvents()
    assert frame.controller.game.board_state.board.move_stack == [
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
    ]
    assert not frame.controller.is_computer_thinking()


def test_move_list_keeps_start_selection_and_fen_move_numbers(app):
    start = chess.Board("4k3/8/8/8/8/8/4P3/4K3 b - - 0 12")
    moves = [chess.Move.from_uci("e8d7"), chess.Move.from_uci("e2e4")]
    with MoveListDialog(None, moves, -1, start_board=start) as dialog:
        assert dialog.get_selected_position() == -1
        assert dialog.list_ctrl.GetItemText(0, 0) == "12"
        assert dialog.list_ctrl.GetItemText(0, 1) == "Black"
        assert dialog.list_ctrl.GetItemText(0, 2) == "Kd7"
        assert dialog.list_ctrl.GetItemText(1, 0) == "13"
        dialog._on_goto_end(None)
        assert dialog.list_ctrl.GetFocusedItem() == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows MSAA events")
def test_native_focus_and_selection_events_follow_controller(frame, monkeypatch):
    events = []
    monkeypatch.setattr(wx.Accessible, "NotifyEvent", lambda *args: events.append(args))
    monkeypatch.setattr(BoardPanel, "IsShownOnScreen", lambda self: True)
    monkeypatch.setattr(BoardPanel, "HasFocus", lambda self: True)
    frame.controller.focus_square(chess.E2)
    assert events[-1] == (
        wx.ACC_EVENT_OBJECT_FOCUS,
        frame.board_panel,
        wx.OBJID_CLIENT,
        chess.E2 + 1,
    )
    frame.controller.select()
    assert events[-1][0] == wx.ACC_EVENT_OBJECT_STATECHANGE
    frame.controller.focus_square(chess.E4)
    frame.controller.select()
    assert any(event[0] == wx.ACC_EVENT_OBJECT_NAMECHANGE for event in events)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows MSAA interface")
def test_windows_accessibility_exposes_live_squares_and_selection(frame, monkeypatch):
    pythoncom = pytest.importorskip("pythoncom")
    panel = frame.board_panel
    pointer = ctypes.c_void_p()
    iid = (ctypes.c_byte * 16).from_buffer_copy(
        uuid.UUID("618736e0-3c3d-11cf-810c-00aa00389b71").bytes_le
    )
    get_accessible = ctypes.windll.oleacc.AccessibleObjectFromWindow
    get_accessible.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_accessible.restype = ctypes.c_long
    assert (
        get_accessible(
            panel.GetHandle(), 0xFFFFFFFC, ctypes.byref(iid), ctypes.byref(pointer)
        )
        == 0
    )
    native = pythoncom.ObjectFromAddress(pointer.value, pythoncom.IID_IDispatch)

    def query(object, dispatch_id, *args):
        return object.Invoke(
            dispatch_id, 0, pythoncom.DISPATCH_PROPERTYGET, True, *args
        )

    assert query(native, -5001) == 64
    for square in chess.SQUARES:
        assert chess.square_name(square) in query(native, -5003, square + 1)
    rook = query(native, -5002, chess.A1 + 1)
    assert query(rook, -5003, 0) == "White rook on a1"
    assert query(rook, -5006, 0) == 0x1D  # Native MSAA ROLE_SYSTEM_CELL.
    assert query(rook, -5007, 0) & 0x10000  # Native STATE_SYSTEM_OFFSCREEN.
    assert query(native, -5011) is None

    frame.controller.focus_square(chess.E2)
    frame.controller.select()
    pawn = query(native, -5002, chess.E2 + 1)
    assert query(pawn, -5007, 0) & 0x2  # Native STATE_SYSTEM_SELECTED.
    assert query(native, -5012) == chess.E2 + 1

    # Exercise MSAA focus marshaling without focusing a window on the user's desktop.
    monkeypatch.setattr(BoardPanel, "HasFocus", lambda self: True)
    monkeypatch.setattr(BoardPanel, "IsShownOnScreen", lambda self: True)
    focused = query(native, -5011)
    assert query(focused, -5003, 0) == "White pawn on e2"
    monkeypatch.setattr(BoardPanel, "HasFocus", lambda self: False)
    monkeypatch.setattr(BoardPanel, "IsShownOnScreen", lambda self: False)
    frame.controller.focus_square(chess.E4)
    frame.controller.select()
    assert query(native, -5003, chess.E2 + 1) == "e2"
    assert query(native, -5003, chess.E4 + 1) == "White pawn on e4"
    assert query(native, -5012) is None
