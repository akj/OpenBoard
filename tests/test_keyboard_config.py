"""Tests for keyboard configuration module.

Covers KeyBinding.matches() modifier branch logic (8 branches via parametrize),
KeyboardCommandHandler routing, and JSON round-trip serialization. (ref: DL-001)

Uses wx integer key codes directly because wx is a project dependency and
imports successfully in the test environment. (ref: DL-003)
"""

import pytest

from openboard.config.keyboard_config import (
    KeyBinding,
    KeyAction,
    KeyModifier,
    GameKeyboardConfig,
    DialogKeyboardConfig,
    KeyboardCommandHandler,
    load_keyboard_config_from_json,
    save_keyboard_config_to_json,
)


class TestKeyBindingMatches:
    """Parametrized tests covering all 8 modifier combinations in KeyBinding.matches().

    Each parametrize case covers one modifier value across its four input states
    (matching, plus three rejects with extra modifiers). (ref: DL-003)
    """

    @pytest.mark.parametrize(
        "shift,ctrl,alt,expected",
        [
            (False, False, False, True),  # NONE matches no modifiers
            (True, False, False, False),  # NONE rejects shift
            (False, True, False, False),  # NONE rejects ctrl
            (False, False, True, False),  # NONE rejects alt
        ],
    )
    def test_none_modifier(self, shift, ctrl, alt, expected):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.NONE
        )
        assert binding.matches(65, shift=shift, ctrl=ctrl, alt=alt) == expected

    @pytest.mark.parametrize(
        "shift,ctrl,alt,expected",
        [
            (False, True, False, True),  # CTRL matches ctrl-only
            (True, True, False, False),  # CTRL rejects ctrl+shift
            (False, True, True, False),  # CTRL rejects ctrl+alt
            (False, False, False, False),  # CTRL rejects no modifier
        ],
    )
    def test_ctrl_modifier(self, shift, ctrl, alt, expected):
        binding = KeyBinding(
            key="65", action=KeyAction.UNDO, modifiers=KeyModifier.CTRL
        )
        assert binding.matches(65, shift=shift, ctrl=ctrl, alt=alt) == expected

    @pytest.mark.parametrize(
        "shift,ctrl,alt,expected",
        [
            (True, False, False, True),  # SHIFT matches shift-only
            (True, True, False, False),  # SHIFT rejects shift+ctrl
            (True, False, True, False),  # SHIFT rejects shift+alt
            (False, False, False, False),  # SHIFT rejects no modifier
        ],
    )
    def test_shift_modifier(self, shift, ctrl, alt, expected):
        binding = KeyBinding(
            key="65", action=KeyAction.DESELECT, modifiers=KeyModifier.SHIFT
        )
        assert binding.matches(65, shift=shift, ctrl=ctrl, alt=alt) == expected

    @pytest.mark.parametrize(
        "shift,ctrl,alt,expected",
        [
            (False, False, True, True),  # ALT matches alt-only
            (True, False, True, False),  # ALT rejects shift+alt
            (False, True, True, False),  # ALT rejects ctrl+alt
            (False, False, False, False),  # ALT rejects no modifier
        ],
    )
    def test_alt_modifier(self, shift, ctrl, alt, expected):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.ALT
        )
        assert binding.matches(65, shift=shift, ctrl=ctrl, alt=alt) == expected

    def test_ctrl_shift_modifier(self):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.CTRL_SHIFT
        )
        assert binding.matches(65, shift=True, ctrl=True, alt=False) is True
        assert binding.matches(65, shift=True, ctrl=True, alt=True) is False
        assert binding.matches(65, shift=False, ctrl=True, alt=False) is False

    def test_ctrl_alt_modifier(self):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.CTRL_ALT
        )
        assert binding.matches(65, shift=False, ctrl=True, alt=True) is True
        assert binding.matches(65, shift=True, ctrl=True, alt=True) is False
        assert binding.matches(65, shift=False, ctrl=True, alt=False) is False

    def test_shift_alt_modifier(self):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.SHIFT_ALT
        )
        assert binding.matches(65, shift=True, ctrl=False, alt=True) is True
        assert binding.matches(65, shift=True, ctrl=True, alt=True) is False
        assert binding.matches(65, shift=True, ctrl=False, alt=False) is False

    def test_ctrl_shift_alt_modifier(self):
        binding = KeyBinding(
            key="65", action=KeyAction.SELECT, modifiers=KeyModifier.CTRL_SHIFT_ALT
        )
        assert binding.matches(65, shift=True, ctrl=True, alt=True) is True
        assert binding.matches(65, shift=False, ctrl=True, alt=True) is False
        assert binding.matches(65, shift=True, ctrl=False, alt=True) is False

    def test_disabled_binding_never_matches(self):
        binding = KeyBinding(key="65", action=KeyAction.SELECT, enabled=False)
        assert binding.matches(65) is False

    def test_wx_key_string_resolves_correctly(self):
        import wx

        binding = KeyBinding(key="wx.WXK_UP", action=KeyAction.NAVIGATE_UP)
        assert binding.matches(wx.WXK_UP) is True
        assert binding.matches(wx.WXK_DOWN) is False

    def test_ord_key_string_resolves_correctly(self):
        binding = KeyBinding(key="ord('H')", action=KeyAction.REQUEST_HINT)
        assert binding.matches(ord("H")) is True
        assert binding.matches(ord("h")) is False

    def test_integer_string_key_resolves_correctly(self):
        binding = KeyBinding(key="65", action=KeyAction.SELECT)
        assert binding.matches(65) is True
        assert binding.matches(66) is False


class TestGameKeyboardConfig:
    """Tests for GameKeyboardConfig class."""

    def setup_method(self):
        self.config = GameKeyboardConfig()

    def test_default_bindings_include_all_expected_actions(self):
        actions = {b.action for b in self.config.bindings}
        expected = {
            KeyAction.NAVIGATE_UP,
            KeyAction.NAVIGATE_DOWN,
            KeyAction.NAVIGATE_LEFT,
            KeyAction.NAVIGATE_RIGHT,
            KeyAction.SELECT,
            KeyAction.DESELECT,
            KeyAction.UNDO,
            KeyAction.REQUEST_HINT,
            KeyAction.REPLAY_PREV,
            KeyAction.REPLAY_NEXT,
            KeyAction.TOGGLE_ANNOUNCE_MODE,
            KeyAction.ANNOUNCE_LAST_MOVE,
            KeyAction.ANNOUNCE_LEGAL_MOVES,
            KeyAction.ANNOUNCE_ATTACKING_PIECES,
        }
        assert expected.issubset(actions)

    def test_find_binding_returns_correct_binding(self):
        import wx

        binding = self.config.find_binding(wx.WXK_UP)
        assert binding is not None
        assert binding.action == KeyAction.NAVIGATE_UP

    def test_find_binding_returns_none_for_unbound_key(self):
        result = self.config.find_binding(9999)
        assert result is None

    def test_get_bindings_by_action_returns_matching_bindings(self):
        bindings = self.config.get_bindings_by_action(KeyAction.NAVIGATE_UP)
        assert len(bindings) >= 1
        assert all(b.action == KeyAction.NAVIGATE_UP for b in bindings)

    def test_add_binding_appends_to_list(self):
        initial_count = len(self.config.bindings)
        new_binding = KeyBinding(key="99", action=KeyAction.ANNOUNCE_LAST_MOVE)
        self.config.add_binding(new_binding)
        assert len(self.config.bindings) == initial_count + 1

    def test_remove_binding_removes_by_action_key_modifier(self):
        new_binding = KeyBinding(key="99", action=KeyAction.ANNOUNCE_LAST_MOVE)
        self.config.add_binding(new_binding)
        result = self.config.remove_binding(KeyAction.ANNOUNCE_LAST_MOVE, "99")
        assert result is True

    def test_remove_binding_returns_false_for_nonexistent(self):
        result = self.config.remove_binding(KeyAction.ANNOUNCE_LAST_MOVE, "99999")
        assert result is False

    def test_disable_binding_disables_all_bindings_for_action(self):
        self.config.disable_binding(KeyAction.NAVIGATE_UP)
        for b in self.config.bindings:
            if b.action == KeyAction.NAVIGATE_UP:
                assert b.enabled is False

    def test_enable_binding_re_enables_disabled_bindings(self):
        self.config.disable_binding(KeyAction.NAVIGATE_UP)
        self.config.enable_binding(KeyAction.NAVIGATE_UP)
        for b in self.config.bindings:
            if b.action == KeyAction.NAVIGATE_UP:
                assert b.enabled is True


class TestDialogKeyboardConfig:
    """Tests for DialogKeyboardConfig class."""

    def setup_method(self):
        self.config = DialogKeyboardConfig()

    def test_default_bindings_include_expected_dialog_actions(self):
        import wx

        # RETURN key should be present
        binding = self.config.find_binding(wx.WXK_RETURN)
        assert binding is not None
        assert binding.action == KeyAction.SELECT

    def test_find_binding_works_for_escape(self):
        import wx

        binding = self.config.find_binding(wx.WXK_ESCAPE)
        assert binding is not None
        assert binding.action == KeyAction.DESELECT


class TestKeyboardCommandHandler:
    """Tests for KeyboardCommandHandler dispatch logic."""

    def setup_method(self):
        self.config = GameKeyboardConfig()
        self.handled_actions = []
        import wx

        self.action_handlers = {
            KeyAction.NAVIGATE_UP: lambda: self.handled_actions.append(
                KeyAction.NAVIGATE_UP
            ),
            KeyAction.SELECT: lambda: self.handled_actions.append(KeyAction.SELECT),
            KeyAction.UNDO: lambda: self.handled_actions.append(KeyAction.UNDO),
        }
        self.handler = KeyboardCommandHandler(self.config, self.action_handlers)
        self.wx = wx

    def test_handle_key_event_dispatches_to_correct_action(self):
        result = self.handler.handle_key_event(self.wx.WXK_UP)
        assert result is True
        assert KeyAction.NAVIGATE_UP in self.handled_actions

    def test_handle_key_event_returns_false_for_unbound_key(self):
        result = self.handler.handle_key_event(9999)
        assert result is False
        assert len(self.handled_actions) == 0

    def test_handle_key_event_returns_false_when_no_handler_for_action(self):

        # REQUEST_HINT is bound but not in action_handlers
        result = self.handler.handle_key_event(ord("H"))
        assert result is False

    def test_get_description_for_action_returns_description(self):
        desc = self.handler.get_description_for_action(KeyAction.NAVIGATE_UP)
        assert desc is not None
        assert len(desc) > 0

    def test_list_all_bindings_returns_formatted_strings(self):
        descriptions = self.handler.list_all_bindings()
        assert len(descriptions) > 0
        assert all(isinstance(d, str) for d in descriptions)
        assert all(":" in d for d in descriptions)


class TestKeyboardConfigJsonRoundTrip:
    """Tests for JSON serialization of keyboard configuration."""

    def test_save_then_load_produces_equivalent_config(self):
        original = GameKeyboardConfig()
        json_str = save_keyboard_config_to_json(original)
        loaded = load_keyboard_config_from_json(json_str)
        assert len(loaded.bindings) == len(original.bindings)
        for orig, loaded_b in zip(original.bindings, loaded.bindings):
            assert orig.key == loaded_b.key
            assert orig.action == loaded_b.action
            assert orig.modifiers == loaded_b.modifiers

    def test_load_from_valid_json_string_creates_correct_config(self):
        config = GameKeyboardConfig()
        json_str = save_keyboard_config_to_json(config)
        loaded = load_keyboard_config_from_json(json_str)
        assert isinstance(loaded, GameKeyboardConfig)
        assert len(loaded.bindings) > 0

    def test_load_from_invalid_json_raises_error(self):
        with pytest.raises(Exception):
            load_keyboard_config_from_json("{invalid json}")
