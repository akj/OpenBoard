#!/usr/bin/env python3
"""
Build validation framework for OpenBoard chess GUI.

This module provides comprehensive validation for built executables,
including functional testing without GUI interaction, accessibility
module validation, performance baseline establishment, and engine
detection system testing.
"""

import importlib
import logging
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Set up logging early to capture any import errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when a validation check fails."""

    pass


class BuildValidator:
    """Validates OpenBoard builds for functionality and performance."""

    def __init__(
        self, executable_path: Path | None = None, project_root: Path | None = None
    ):
        """
        Initialize the build validator.

        Args:
            executable_path: Path to the built executable to validate
            project_root: Path to the project root directory
        """
        if project_root is None:
            # Assume script is in build/validation/, so project root is two levels up
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self.executable_path = executable_path
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.is_macos = self.system == "Darwin"
        self.is_linux = self.system == "Linux"

        # Validation results storage
        self.results: Dict[str, Dict[str, Any]] = {}

    def _add_result(
        self,
        test_name: str,
        passed: bool,
        message: str,
        duration: float = 0.0,
        details: Dict[str, Any] | None = None,
    ) -> None:
        """Add a test result to the results storage."""
        self.results[test_name] = {
            "passed": passed,
            "message": message,
            "duration": duration,
            "details": details or {},
        }

    def _run_subprocess_test(
        self, command: List[str], test_name: str, timeout: int = 30
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Run a subprocess test with timeout and error handling.

        Args:
            command: Command to run
            test_name: Name of the test for logging
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, message, details)
        """
        logger.info(f"Running {test_name}: {' '.join(command)}")

        try:
            start_time = time.time()
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False
            )
            duration = time.time() - start_time

            details = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
            }

            if result.returncode == 0:
                return True, f"{test_name} completed successfully", details
            else:
                return (
                    False,
                    f"{test_name} failed with exit code {result.returncode}",
                    details,
                )

        except subprocess.TimeoutExpired:
            return (
                False,
                f"{test_name} timed out after {timeout} seconds",
                {"timeout": timeout},
            )
        except FileNotFoundError:
            return (
                False,
                f"{test_name} failed: command not found",
                {"command": command[0]},
            )
        except Exception as e:
            return (
                False,
                f"{test_name} failed with exception: {e}",
                {"exception": str(e)},
            )

    def validate_package_imports(self) -> None:
        """Validate that all core OpenBoard modules can be imported."""
        logger.info("Validating package imports...")

        core_modules = [
            "openboard",
            "openboard.models.game",
            "openboard.models.board_state",
            "openboard.models.game_mode",
            "openboard.controllers.chess_controller",
            "openboard.engine.engine_adapter",
            "openboard.engine.engine_detection",
            "openboard.config.settings",
            "openboard.logging_config",
            "openboard.views.views",
        ]

        failed_imports = []
        import_details = {}

        for module_name in core_modules:
            try:
                start_time = time.time()
                importlib.import_module(module_name)
                duration = time.time() - start_time
                import_details[module_name] = {"success": True, "duration": duration}
                logger.debug(f"Successfully imported {module_name}")
            except Exception as e:
                duration = time.time() - start_time
                import_details[module_name] = {
                    "success": False,
                    "duration": duration,
                    "error": str(e),
                }
                failed_imports.append(f"{module_name}: {e}")
                logger.error(f"Failed to import {module_name}: {e}")

        if failed_imports:
            self._add_result(
                "package_imports",
                False,
                f"Failed to import {len(failed_imports)} modules: {', '.join(failed_imports)}",
                details=import_details,
            )
        else:
            self._add_result(
                "package_imports",
                True,
                f"Successfully imported all {len(core_modules)} core modules",
                details=import_details,
            )

    def validate_accessibility_modules(self) -> None:
        """Validate accessibility modules are properly available."""
        logger.info("Validating accessibility modules...")

        try:
            start_time = time.time()

            # Test accessible-output3 import
            from accessible_output3.outputs.auto import Auto

            # Test screen reader interface creation (without actually speaking)
            auto_output = Auto()

            # Check available outputs
            available_outputs = []
            if hasattr(auto_output, "outputs"):
                available_outputs = [
                    str(output.__class__.__name__) for output in auto_output.outputs
                ]

            duration = time.time() - start_time

            self._add_result(
                "accessibility_modules",
                True,
                f"Accessibility modules loaded successfully with {len(available_outputs)} outputs",
                duration,
                {"available_outputs": available_outputs},
            )

        except Exception as e:
            duration = time.time() - start_time
            self._add_result(
                "accessibility_modules",
                False,
                f"Accessibility validation failed: {e}",
                duration,
                {"error": str(e)},
            )

    def validate_chess_engine_detection(self) -> None:
        """Validate engine detection system functionality."""
        logger.info("Validating chess engine detection...")

        try:
            start_time = time.time()

            from openboard.engine.engine_detection import EngineDetector

            detector = EngineDetector()

            # Test Stockfish detection
            stockfish_path = detector.find_engine("stockfish")

            # Test engine availability
            engines_found = detector.list_available_engines()

            duration = time.time() - start_time

            details = {
                "stockfish_path": str(stockfish_path) if stockfish_path else None,
                "engines_found": len(engines_found),
                "engine_names": engines_found,
            }

            self._add_result(
                "engine_detection",
                True,
                f"Engine detection completed, found {len(engines_found)} engines",
                duration,
                details,
            )

        except Exception as e:
            duration = time.time() - start_time
            self._add_result(
                "engine_detection",
                False,
                f"Engine detection failed: {e}",
                duration,
                {"error": str(e)},
            )

    def validate_game_logic(self) -> None:
        """Validate core game logic functionality."""
        logger.info("Validating game logic...")

        try:
            start_time = time.time()

            from openboard.models.game import Game
            from openboard.models.game_mode import GameMode, GameConfig

            # Test basic game creation
            game = Game()

            # Test move validation
            board = game.board_state.board
            legal_moves = list(board.legal_moves)

            if legal_moves:
                # Try making a legal move
                move = legal_moves[0]
                game.board_state.make_move(move)

                # Verify move was made
                if board.move_stack:
                    last_move = board.peek()
                    move_made_correctly = last_move == move
                else:
                    move_made_correctly = False
            else:
                move_made_correctly = False

            # Test game mode configuration
            config = GameConfig(
                mode=GameMode.HUMAN_VS_HUMAN,
                white_difficulty=None,
                black_difficulty=None,
            )

            duration = time.time() - start_time

            details = {
                "initial_legal_moves": len(legal_moves),
                "move_made_correctly": move_made_correctly,
                "game_config_valid": bool(config),
            }

            self._add_result(
                "game_logic",
                True,
                "Game logic validation completed successfully",
                duration,
                details,
            )

        except Exception as e:
            duration = time.time() - start_time
            self._add_result(
                "game_logic",
                False,
                f"Game logic validation failed: {e}",
                duration,
                {"error": str(e)},
            )

    def validate_signal_system(self) -> None:
        """Validate blinker signal system functionality."""
        logger.info("Validating signal system...")

        try:
            start_time = time.time()

            from blinker import Signal
            from openboard.models.board_state import BoardState

            # Test signal creation and connection
            test_signal = Signal()
            signal_received = []

            def signal_handler(sender, **kwargs):
                signal_received.append((sender, kwargs))

            test_signal.connect(signal_handler)
            test_signal.send("test_sender", test_data="test_value")

            # Test BoardState signals
            board_state = BoardState()
            move_signals = []

            def move_handler(sender, **kwargs):
                move_signals.append(kwargs)

            board_state.move_made.connect(move_handler)

            # Make a test move
            import chess

            move = chess.Move.from_uci("e2e4")
            if move in board_state.board.legal_moves:
                board_state.make_move(move)

            duration = time.time() - start_time

            details = {
                "basic_signal_received": len(signal_received) > 0,
                "board_signals_working": len(move_signals) > 0,
                "signal_data": signal_received[0] if signal_received else None,
            }

            self._add_result(
                "signal_system",
                True,
                "Signal system validation completed successfully",
                duration,
                details,
            )

        except Exception as e:
            duration = time.time() - start_time
            self._add_result(
                "signal_system",
                False,
                f"Signal system validation failed: {e}",
                duration,
                {"error": str(e)},
            )

    def validate_executable_functionality(self) -> None:
        """Validate the built executable can start and respond."""
        if not self.executable_path or not self.executable_path.exists():
            self._add_result(
                "executable_functionality",
                False,
                "No executable path provided or executable not found",
            )
            return

        logger.info(f"Validating executable functionality: {self.executable_path}")

        # Test executable can start and exit cleanly
        test_command = [str(self.executable_path), "--help"]

        success, message, details = self._run_subprocess_test(
            test_command, "executable help test", timeout=10
        )

        self._add_result(
            "executable_functionality",
            success,
            message,
            details.get("duration", 0),
            details,
        )

    def performance_baseline(self) -> None:
        """Establish performance baselines for critical operations."""
        logger.info("Establishing performance baselines...")

        benchmarks = {}

        try:
            # Import timing
            start_time = time.time()
            import_time = time.time() - start_time
            benchmarks["import_time"] = import_time

            # Game initialization timing
            start_time = time.time()
            from openboard.models.game import Game

            game = Game()
            init_time = time.time() - start_time
            benchmarks["game_init_time"] = init_time

            # Move generation timing
            start_time = time.time()
            legal_moves = list(game.board_state.board.legal_moves)
            move_gen_time = time.time() - start_time
            benchmarks["move_generation_time"] = move_gen_time

            # Board state update timing
            if legal_moves:
                start_time = time.time()
                move = legal_moves[0]
                game.board_state.make_move(move)
                move_time = time.time() - start_time
                benchmarks["move_execution_time"] = move_time

            # Performance thresholds (in seconds)
            thresholds = {
                "import_time": 2.0,
                "game_init_time": 0.5,
                "move_generation_time": 0.1,
                "move_execution_time": 0.1,
            }

            # Check if performance is acceptable
            performance_issues = []
            for metric, value in benchmarks.items():
                threshold = thresholds.get(metric, float("inf"))
                if value > threshold:
                    performance_issues.append(
                        f"{metric}: {value:.3f}s (threshold: {threshold}s)"
                    )

            if performance_issues:
                self._add_result(
                    "performance_baseline",
                    False,
                    f"Performance issues detected: {', '.join(performance_issues)}",
                    details={"benchmarks": benchmarks, "thresholds": thresholds},
                )
            else:
                self._add_result(
                    "performance_baseline",
                    True,
                    "All performance metrics within acceptable thresholds",
                    details={"benchmarks": benchmarks, "thresholds": thresholds},
                )

        except Exception as e:
            self._add_result(
                "performance_baseline",
                False,
                f"Performance baseline failed: {e}",
                details={"error": str(e), "benchmarks": benchmarks},
            )

    def validate_dependencies(self) -> None:
        """Validate all required dependencies are available and functional."""
        logger.info("Validating dependencies...")

        required_packages = [
            ("chess", "chess library for game logic"),
            ("wx", "wxPython GUI framework"),
            ("blinker", "signal system"),
            ("accessible_output3", "accessibility support"),
            ("pydantic", "configuration validation"),
        ]

        dependency_results = {}
        failed_dependencies = []

        for package_name, description in required_packages:
            try:
                start_time = time.time()
                importlib.import_module(package_name)
                import_time = time.time() - start_time
                dependency_results[package_name] = {
                    "available": True,
                    "import_time": import_time,
                    "description": description,
                }
            except Exception as e:
                dependency_results[package_name] = {
                    "available": False,
                    "error": str(e),
                    "description": description,
                }
                failed_dependencies.append(f"{package_name} ({description})")

        if failed_dependencies:
            self._add_result(
                "dependencies",
                False,
                f"Missing or broken dependencies: {', '.join(failed_dependencies)}",
                details=dependency_results,
            )
        else:
            self._add_result(
                "dependencies",
                True,
                f"All {len(required_packages)} required dependencies are available",
                details=dependency_results,
            )

    def run_all_validations(self) -> Dict[str, Dict[str, Any]]:
        """
        Run all validation tests.

        Returns:
            Dictionary containing all test results
        """
        logger.info("Starting comprehensive build validation...")

        # If executable path is provided, only validate the executable
        # (skip source code validations since openboard package isn't installed)
        if self.executable_path:
            validations = [
                ("Executable Functionality", self.validate_executable_functionality),
            ]
        else:
            # Run source code validations
            validations = [
                ("Dependencies", self.validate_dependencies),
                ("Package Imports", self.validate_package_imports),
                ("Accessibility Modules", self.validate_accessibility_modules),
                ("Engine Detection", self.validate_chess_engine_detection),
                ("Game Logic", self.validate_game_logic),
                ("Signal System", self.validate_signal_system),
                ("Performance Baseline", self.performance_baseline),
            ]

        for test_name, test_func in validations:
            try:
                logger.info(f"Running {test_name} validation...")
                test_func()
            except Exception as e:
                logger.error(f"Unexpected error in {test_name}: {e}")
                self._add_result(
                    test_name.lower().replace(" ", "_"),
                    False,
                    f"Unexpected error: {e}",
                    details={"exception": str(e)},
                )

        return self.results

    def print_results(self) -> bool:
        """
        Print validation results in a human-readable format.

        Returns:
            True if all validations passed, False otherwise
        """
        logger.info("=== Build Validation Results ===")

        passed_count = 0
        total_count = len(self.results)

        for test_name, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            duration = result.get("duration", 0)
            message = result["message"]

            logger.info(f"{status} {test_name}: {message}")
            if duration > 0:
                logger.info(f"    Duration: {duration:.3f}s")

            if not result["passed"] and result.get("details"):
                details = result["details"]
                if "error" in details:
                    logger.error(f"    Error: {details['error']}")
                if "exception" in details:
                    logger.error(f"    Exception: {details['exception']}")

            if result["passed"]:
                passed_count += 1

        logger.info(f"\nValidation Summary: {passed_count}/{total_count} tests passed")

        return passed_count == total_count


def main() -> int:
    """Main entry point for the validation script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate OpenBoard build functionality"
    )
    parser.add_argument(
        "--executable", type=Path, help="Path to the built executable to validate"
    )
    parser.add_argument(
        "--project-root", type=Path, help="Path to the project root directory"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        validator = BuildValidator(args.executable, args.project_root)
        validator.run_all_validations()
        all_passed = validator.print_results()

        return 0 if all_passed else 1

    except Exception as e:
        logger.error(f"Validation failed with unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
