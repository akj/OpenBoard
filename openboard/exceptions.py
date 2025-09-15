"""Exception hierarchy for OpenBoard application."""


class OpenBoardError(Exception):
    """Base exception for all OpenBoard application errors."""

    def __init__(self, message: str, details: str | None = None):
        """Initialize exception with message and optional details.

        Args:
            message: Human-readable error message
            details: Optional detailed error information
        """
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        """String representation of the exception."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(OpenBoardError):
    """Configuration-related errors."""

    pass


class GameModeError(ConfigurationError):
    """Game mode configuration errors."""

    pass


class EngineError(OpenBoardError):
    """Base class for engine-related errors."""

    pass


class EngineNotFoundError(EngineError):
    """Raised when no chess engine is available or cannot be found."""

    def __init__(
        self, engine_name: str = "chess engine", search_paths: list[str] | None = None
    ):
        """Initialize with engine name and optional search paths.

        Args:
            engine_name: Name of the engine that was not found
            search_paths: List of paths that were searched
        """
        message = f"{engine_name} not found"
        details = None
        if search_paths:
            details = f"Searched in: {', '.join(search_paths)}"
        super().__init__(message, details)
        self.engine_name = engine_name
        self.search_paths = search_paths or []


class EngineInitializationError(EngineError):
    """Raised when engine initialization fails."""

    pass


class EngineTimeoutError(EngineError):
    """Raised when engine operations timeout."""

    def __init__(self, operation: str, timeout_ms: int):
        """Initialize with operation and timeout information.

        Args:
            operation: The operation that timed out
            timeout_ms: Timeout value in milliseconds
        """
        message = f"Engine {operation} timed out after {timeout_ms}ms"
        super().__init__(message)
        self.operation = operation
        self.timeout_ms = timeout_ms


class EngineProcessError(EngineError):
    """Raised when engine process encounters an error."""

    def __init__(
        self, message: str, return_code: int | None = None, stderr: str | None = None
    ):
        """Initialize with process error details.

        Args:
            message: Error message
            return_code: Process return code if available
            stderr: Process stderr output if available
        """
        details = []
        if return_code is not None:
            details.append(f"exit code: {return_code}")
        if stderr:
            details.append(f"stderr: {stderr}")

        super().__init__(message, "; ".join(details) if details else None)
        self.return_code = return_code
        self.stderr = stderr


class GameError(OpenBoardError):
    """Base class for game-related errors."""

    pass


class IllegalMoveError(GameError):
    """Raised when an illegal chess move is attempted."""

    def __init__(self, move: str, position_fen: str | None = None):
        """Initialize with move and optional position.

        Args:
            move: The illegal move (e.g., "e2e5")
            position_fen: FEN string of the position where move was attempted
        """
        message = f"Illegal move: {move}"
        details = f"in position: {position_fen}" if position_fen else None
        super().__init__(message, details)
        self.move = move
        self.position_fen = position_fen


class GameStateError(GameError):
    """Raised when game is in an invalid state for the requested operation."""

    pass


class UIError(OpenBoardError):
    """Base class for user interface errors."""

    pass


class DialogError(UIError):
    """Raised when dialog operations fail."""

    pass


class AccessibilityError(UIError):
    """Raised when accessibility features encounter errors."""

    pass


class SettingsError(ConfigurationError):
    """Raised when settings validation or loading fails."""

    pass


class NetworkError(OpenBoardError):
    """Base class for network-related errors (for future engine downloads)."""

    pass


class DownloadError(NetworkError):
    """Raised when file downloads fail."""

    def __init__(self, url: str, reason: str | None = None):
        """Initialize with URL and optional reason.

        Args:
            url: The URL that failed to download
            reason: Optional reason for failure
        """
        message = f"Failed to download from {url}"
        super().__init__(message, reason)
        self.url = url
        self.reason = reason


class OpeningBookError(OpenBoardError):
    """Raised when opening book operations fail."""

    pass
