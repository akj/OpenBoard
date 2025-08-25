"""
Logging configuration for OpenBoard.

This module provides centralized logging setup for the OpenBoard chess application.
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    console_output: bool = True,
) -> None:
    """
    Configure logging for the OpenBoard application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, creates openboard.log in user's home
        console_output: Whether to output logs to console
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file is None:
        log_file = str(Path.home() / "openboard.log")

    try:
        # Create directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use RotatingFileHandler to prevent log files from growing too large
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't create the log file, just log to console
        if console_output:
            logging.warning(f"Could not create log file {log_file}: {e}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def configure_for_development() -> None:
    """Configure logging for development with more verbose output."""
    setup_logging(log_level="DEBUG", console_output=True)


def configure_for_production() -> None:
    """Configure logging for production with less verbose output."""
    setup_logging(log_level="INFO", console_output=False)
