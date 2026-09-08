#!/usr/bin/env python3
"""Run a startup smoke check against source or a packaged executable."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class ValidationError(Exception):
    """The application could not complete its startup smoke check."""


def validate_startup(
    executable: Path | None = None,
    project_root: Path | None = None,
    timeout: float = 30,
) -> dict:
    """Load the app in another process without a GUI, speech or a real profile."""
    project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    if executable is not None:
        executable = executable.resolve()
        if not executable.is_file():
            raise ValidationError(f"Executable not found: {executable}")
        command = [str(executable), "--self-test"]
    else:
        command = [sys.executable, "-m", "openboard", "--self-test"]

    with tempfile.TemporaryDirectory(prefix="openboard-smoke-") as temporary_dir:
        env = os.environ.copy()
        env["OPENBOARD_PROFILE_DIR"] = temporary_dir
        # A packaged build must work without the source checkout on its import path.
        if executable is not None:
            env.pop("PYTHONPATH", None)
        started = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=temporary_dir if executable is not None else project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValidationError(
                f"Startup smoke check could not finish: {error}"
            ) from error
        duration = time.perf_counter() - started
        if result.returncode != 0:
            raise ValidationError(
                f"Startup smoke check exited with {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        try:
            report = json.loads(result.stdout.strip())
        except (ValueError, TypeError) as error:
            raise ValidationError(
                f"Startup smoke check returned invalid output: {result.stdout!r}"
            ) from error
        if (
            not isinstance(report, dict)
            or report.get("check") != "startup"
            or report.get("status") != "ok"
        ):
            raise ValidationError(
                f"Startup smoke check did not report success: {report!r}"
            )
        return {**report, "duration_seconds": duration}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the OpenBoard startup smoke check"
    )
    parser.add_argument("--executable", type=Path, help="Packaged executable to check")
    parser.add_argument("--project-root", type=Path, help="Source checkout to check")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_startup(args.executable, args.project_root)
    except ValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Startup smoke check passed in {report['duration_seconds']:.3f}s")
    if args.verbose:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
