import logging
from typing import Union, Dict, Any, Optional

import chess
import chess.engine

from .engine_detection import EngineDetector


class EngineAdapter:
    """
    Thin synchronous wrapper around a UCI engine (e.g. Stockfish).

    Usage:
        adapter = EngineAdapter("/path/to/stockfish", {"Threads": 2})
        adapter.start()
        move1 = adapter.get_best_move("r1bqkbnr/pppppppp/2n5/8/8/2N5/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
        # or
        board = chess.Board()
        move2 = adapter.get_best_move(board, time_ms=500)
        adapter.stop()
    """

    def __init__(
        self,
        engine_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        :param engine_path: path to the UCI engine executable. If None, will auto-detect.
        :param options: dictionary of UCI options, e.g. {"Threads": 2, "Hash": 128}
        """
        if engine_path is None:
            detector = EngineDetector()
            engine_path = detector.find_engine("stockfish")
            if engine_path is None:
                instructions = detector.get_installation_instructions("stockfish")
                system = detector.system
                instruction_text = instructions.get(
                    system, instructions.get("generic", "")
                )
                raise RuntimeError(
                    f"No Stockfish engine found on system. Please install Stockfish:\n\n{instruction_text}"
                )

        self.engine_path = engine_path
        self.options = options or {}
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._logger = logging.getLogger(__name__)

    def start(self) -> None:
        """
        Launches the engine process if not already running.
        Raises RuntimeError on failure.
        """
        if self._engine is not None:
            return

        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        except Exception as e:
            msg = f"Failed to launch engine at '{self.engine_path}': {e}"
            self._logger.error(msg)
            raise RuntimeError(msg) from e

        # configure UCI options
        for name, val in self.options.items():
            try:
                self._engine.configure({name: val})
            except Exception as e:
                self._logger.warning(f"Could not set engine option {name}={val}: {e}")

    def stop(self) -> None:
        """
        Quits the engine process if running.
        Safe to call multiple times.
        """
        if not self._engine:
            return

        try:
            self._engine.quit()
        except Exception as e:
            self._logger.warning(f"Error while quitting engine: {e}")
        finally:
            self._engine = None

    def is_running(self) -> bool:
        """Returns True if the engine is currently running."""
        return self._engine is not None

    def get_best_move(
        self, position: Union[str, chess.Board], time_ms: int = 1000
    ) -> chess.Move | None:
        """
        Synchronously get the engine's best move for the given position.

        :param position: either a FEN string or a chess.Board instance.
        :param time_ms: think time in milliseconds.
        :return: a chess.Move instance.
        :raises RuntimeError: if engine isn't started.
        :raises ValueError: if the FEN is invalid.
        :raises chess.engine.EngineTerminatedError: on engine failure.
        """
        if self._engine is None:
            raise RuntimeError("Engine is not running; call start() first.")

        if isinstance(position, chess.Board):
            board = position
        elif isinstance(position, str):
            try:
                board = chess.Board(position)
            except Exception as e:
                raise ValueError(f"Invalid FEN string: {e}") from e
        else:
            raise TypeError("position must be a FEN string or chess.Board")

        limit = chess.engine.Limit(time=time_ms / 1000.0)
        try:
            result = self._engine.play(board, limit)
            return result.move
        except Exception as e:
            msg = f"Engine failed to compute best move: {e}"
            self._logger.error(msg)
            raise RuntimeError(msg) from e

    # Optional context‐manager support
    def __enter__(self) -> "EngineAdapter":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    @classmethod
    def create_with_auto_detection(
        cls, engine_name: str = "stockfish", options: Optional[Dict[str, Any]] = None
    ) -> "EngineAdapter":
        """
        Create an EngineAdapter with automatic engine detection.

        :param engine_name: Name of the engine to detect (default: "stockfish")
        :param options: Dictionary of UCI options
        :return: EngineAdapter instance
        :raises RuntimeError: If the engine cannot be found
        """
        detector = EngineDetector()
        engine_path = detector.find_engine(engine_name)

        if engine_path is None:
            instructions = detector.get_installation_instructions(engine_name)
            system = detector.system
            instruction_text = instructions.get(system, instructions.get("generic", ""))
            raise RuntimeError(
                f"No {engine_name} engine found on system. Please install {engine_name}:\n\n{instruction_text}"
            )

        return cls(engine_path, options)
