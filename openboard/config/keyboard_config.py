"""Keyboard command configuration system using Pydantic dataclasses."""

from typing import Dict, List, Optional, Callable, Protocol
from enum import Enum
from dataclasses import field
from pydantic import Field
from pydantic.dataclasses import dataclass
import wx


class KeyModifier(str, Enum):
    """Keyboard modifier keys."""

    NONE = "none"
    CTRL = "ctrl"
    SHIFT = "shift"
    ALT = "alt"
    CTRL_SHIFT = "ctrl+shift"
    CTRL_ALT = "ctrl+alt"
    SHIFT_ALT = "shift+alt"
    CTRL_SHIFT_ALT = "ctrl+shift+alt"


class KeyAction(str, Enum):
    """Available keyboard actions."""

    NAVIGATE_UP = "navigate_up"
    NAVIGATE_DOWN = "navigate_down"
    NAVIGATE_LEFT = "navigate_left"
    NAVIGATE_RIGHT = "navigate_right"
    SELECT = "select"
    DESELECT = "deselect"
    UNDO = "undo"
    REQUEST_HINT = "request_hint"
    REPLAY_PREV = "replay_prev"
    REPLAY_NEXT = "replay_next"
    TOGGLE_ANNOUNCE_MODE = "toggle_announce_mode"
    SHOW_MOVE_LIST = "show_move_list"
    ANNOUNCE_LAST_MOVE = "announce_last_move"


class KeyboardConfigProtocol(Protocol):
    """Protocol for keyboard configuration classes."""

    bindings: List["KeyBinding"]

    def find_binding(
        self, key_code: int, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> Optional["KeyBinding"]:
        """Find the first matching key binding for the given key event."""
        ...

    def get_bindings_by_action(self, action: KeyAction) -> List["KeyBinding"]:
        """Get all bindings for a specific action."""
        ...


@dataclass
class KeyBinding:
    """A single key binding configuration."""

    key: str = Field(description="Key name or code")
    action: KeyAction = Field(description="Action to perform")
    modifiers: KeyModifier = Field(
        default=KeyModifier.NONE, description="Required modifier keys"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable description"
    )
    enabled: bool = Field(default=True, description="Whether this binding is enabled")

    def matches(
        self, key_code: int, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> bool:
        """Check if this binding matches the given key event."""
        if not self.enabled:
            return False

        # Check key match
        if isinstance(self.key, str):
            if self.key.startswith("wx."):
                # Handle wx constants like "wx.WXK_UP"
                wx_key = getattr(wx, self.key.split(".", 1)[1], None)
                if wx_key != key_code:
                    return False
            elif self.key.startswith("ord(") and self.key.endswith(")"):
                # Handle ord('H') syntax
                char = self.key[5:-2]  # Extract character from ord('X')
                if ord(char) != key_code:
                    return False
            else:
                # Direct integer comparison
                if int(self.key) != key_code:
                    return False
        else:
            if self.key != key_code:
                return False

        # Check modifiers
        match self.modifiers:
            case KeyModifier.NONE:
                return not (shift or ctrl or alt)
            case KeyModifier.CTRL:
                return ctrl and not shift and not alt
            case KeyModifier.SHIFT:
                return shift and not ctrl and not alt
            case KeyModifier.ALT:
                return alt and not ctrl and not shift
            case KeyModifier.CTRL_SHIFT:
                return ctrl and shift and not alt
            case KeyModifier.CTRL_ALT:
                return ctrl and alt and not shift
            case KeyModifier.SHIFT_ALT:
                return shift and alt and not ctrl
            case KeyModifier.CTRL_SHIFT_ALT:
                return ctrl and shift and alt
            case _:
                return False


@dataclass
class GameKeyboardConfig:
    """Keyboard configuration for the game board."""

    bindings: List[KeyBinding] = field(
        default_factory=lambda: [
            # Navigation
            KeyBinding(
                key="wx.WXK_UP", action=KeyAction.NAVIGATE_UP, description="Navigate up"
            ),
            KeyBinding(
                key="wx.WXK_DOWN",
                action=KeyAction.NAVIGATE_DOWN,
                description="Navigate down",
            ),
            KeyBinding(
                key="wx.WXK_LEFT",
                action=KeyAction.NAVIGATE_LEFT,
                description="Navigate left",
            ),
            KeyBinding(
                key="wx.WXK_RIGHT",
                action=KeyAction.NAVIGATE_RIGHT,
                description="Navigate right",
            ),
            # Selection
            KeyBinding(
                key="ord(' ')", action=KeyAction.SELECT, description="Select square"
            ),
            KeyBinding(
                key="ord(' ')",
                modifiers=KeyModifier.SHIFT,
                action=KeyAction.DESELECT,
                description="Deselect square",
            ),
            # Game actions
            KeyBinding(
                key="ord('Z')",
                modifiers=KeyModifier.CTRL,
                action=KeyAction.UNDO,
                description="Undo last move",
            ),
            KeyBinding(
                key="ord('H')",
                action=KeyAction.REQUEST_HINT,
                description="Request hint",
            ),
            # Replay
            KeyBinding(
                key="wx.WXK_F5",
                action=KeyAction.REPLAY_PREV,
                description="Previous move",
            ),
            KeyBinding(
                key="wx.WXK_F6", action=KeyAction.REPLAY_NEXT, description="Next move"
            ),
            # Accessibility
            KeyBinding(
                key="ord('T')",
                modifiers=KeyModifier.CTRL,
                action=KeyAction.TOGGLE_ANNOUNCE_MODE,
                description="Toggle announce mode",
            ),
            KeyBinding(
                key="ord('L')",
                modifiers=KeyModifier.CTRL,
                action=KeyAction.SHOW_MOVE_LIST,
                description="Show move list",
            ),
            KeyBinding(
                key="ord(']')",
                action=KeyAction.ANNOUNCE_LAST_MOVE,
                description="Announce last move",
            ),
        ]
    )

    def find_binding(
        self, key_code: int, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> Optional[KeyBinding]:
        """Find the first matching key binding for the given key event."""
        for binding in self.bindings:
            if binding.matches(key_code, shift, ctrl, alt):
                return binding
        return None

    def get_bindings_by_action(self, action: KeyAction) -> List[KeyBinding]:
        """Get all bindings for a specific action."""
        return [binding for binding in self.bindings if binding.action == action]

    def add_binding(self, binding: KeyBinding) -> None:
        """Add a new key binding."""
        self.bindings.append(binding)

    def remove_binding(
        self, action: KeyAction, key: str, modifiers: KeyModifier = KeyModifier.NONE
    ) -> bool:
        """Remove a key binding. Returns True if binding was found and removed."""
        for i, binding in enumerate(self.bindings):
            if (
                binding.action == action
                and binding.key == key
                and binding.modifiers == modifiers
            ):
                del self.bindings[i]
                return True
        return False

    def disable_binding(self, action: KeyAction) -> None:
        """Disable all bindings for a specific action."""
        for binding in self.bindings:
            if binding.action == action:
                binding.enabled = False

    def enable_binding(self, action: KeyAction) -> None:
        """Enable all bindings for a specific action."""
        for binding in self.bindings:
            if binding.action == action:
                binding.enabled = True


@dataclass
class DialogKeyboardConfig:
    """Keyboard configuration for dialogs."""

    bindings: List[KeyBinding] = field(
        default_factory=lambda: [
            KeyBinding(
                key="wx.WXK_RETURN", action=KeyAction.SELECT, description="Accept/Apply"
            ),
            KeyBinding(
                key="wx.WXK_SPACE", action=KeyAction.SELECT, description="Accept/Apply"
            ),
            KeyBinding(
                key="wx.WXK_HOME",
                action=KeyAction.NAVIGATE_UP,
                description="Go to start",
            ),
            KeyBinding(
                key="wx.WXK_END",
                action=KeyAction.NAVIGATE_DOWN,
                description="Go to end",
            ),
            KeyBinding(
                key="wx.WXK_ESCAPE",
                action=KeyAction.DESELECT,
                description="Cancel/Close",
            ),
        ]
    )

    def find_binding(
        self, key_code: int, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> Optional[KeyBinding]:
        """Find the first matching key binding for the given key event."""
        for binding in self.bindings:
            if binding.matches(key_code, shift, ctrl, alt):
                return binding
        return None

    def get_bindings_by_action(self, action: KeyAction) -> List[KeyBinding]:
        """Get all bindings for a specific action."""
        return [binding for binding in self.bindings if binding.action == action]


class KeyboardCommandHandler:
    """Handles keyboard commands using configuration."""

    def __init__(
        self,
        config: KeyboardConfigProtocol,
        action_handlers: Dict[KeyAction, Callable[[], None]],
    ):
        """
        Initialize the keyboard command handler.

        Args:
            config: The keyboard configuration
            action_handlers: Dictionary mapping actions to handler functions
        """
        self.config = config
        self.action_handlers = action_handlers

    def handle_key_event(
        self, key_code: int, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> bool:
        """
        Handle a keyboard event.

        Args:
            key_code: The key code from the event
            shift: Whether shift is pressed
            ctrl: Whether ctrl is pressed
            alt: Whether alt is pressed

        Returns:
            True if the event was handled, False otherwise
        """
        binding = self.config.find_binding(key_code, shift, ctrl, alt)
        if binding and binding.action in self.action_handlers:
            self.action_handlers[binding.action]()
            return True
        return False

    def get_description_for_action(self, action: KeyAction) -> Optional[str]:
        """Get a human-readable description for an action's key binding."""
        bindings = self.config.get_bindings_by_action(action)
        if bindings:
            return bindings[0].description
        return None

    def list_all_bindings(self) -> List[str]:
        """Get a list of all key bindings as human-readable strings."""
        descriptions = []
        for binding in self.config.bindings:
            if binding.enabled:
                key_desc = self._format_key_description(binding)
                desc = binding.description or binding.action.value
                descriptions.append(f"{key_desc}: {desc}")
        return descriptions

    def _format_key_description(self, binding: KeyBinding) -> str:
        """Format a key binding as a human-readable string."""
        parts = []

        if binding.modifiers != KeyModifier.NONE:
            parts.append(binding.modifiers.value.replace("+", " + ").title())

        # Format key name
        if binding.key.startswith("wx.WXK_"):
            key_name = binding.key[7:].replace("_", " ").title()
        elif binding.key.startswith("ord("):
            key_name = binding.key[5:-2]  # Extract character from ord('X')
        else:
            key_name = str(binding.key)

        parts.append(key_name)
        return " + ".join(parts)


def load_keyboard_config_from_json(json_data: str) -> GameKeyboardConfig:
    """Load keyboard configuration from JSON string."""
    import json
    from pydantic import TypeAdapter

    adapter = TypeAdapter(GameKeyboardConfig)
    data = json.loads(json_data)
    return adapter.validate_python(data)


def save_keyboard_config_to_json(config: GameKeyboardConfig) -> str:
    """Save keyboard configuration to JSON string."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(GameKeyboardConfig)
    return adapter.dump_json(config, indent=2).decode("utf-8")
