#!/usr/bin/env python3
"""
Tests for the build validation framework.

This module provides comprehensive tests for the build validation system,
ensuring that the validation framework itself works correctly across
different platforms and scenarios.
"""

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the parent directories to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from .build directory (with dot prefix it needs special handling)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "verify_build",
    Path(__file__).parent.parent / ".build" / "validation" / "verify_build.py"
)
verify_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_build)
BuildValidator = verify_build.BuildValidator
ValidationError = verify_build.ValidationError


class TestBuildValidator:
    """Test the BuildValidator class functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.test_project_root = Path(__file__).parent.parent.parent
        self.validator = BuildValidator(project_root=self.test_project_root)

    def test_validator_initialization(self):
        """Test that the validator initializes correctly."""
        assert self.validator.project_root == self.test_project_root
        assert self.validator.system in ["Linux", "Windows", "Darwin"]
        assert isinstance(self.validator.results, dict)

    def test_add_result(self):
        """Test the _add_result method."""
        test_name = "test_validation"
        self.validator._add_result(
            test_name=test_name,
            passed=True,
            message="Test passed",
            duration=0.5,
            details={"extra": "info"}
        )

        assert test_name in self.validator.results
        result = self.validator.results[test_name]
        assert result["passed"] is True
        assert result["message"] == "Test passed"
        assert result["duration"] == 0.5
        assert result["details"]["extra"] == "info"

    def test_run_subprocess_test_success(self):
        """Test _run_subprocess_test with a successful command."""
        success, message, details = self.validator._run_subprocess_test(
            command=["python", "-c", "print('test')"],
            test_name="test_command",
            timeout=5
        )

        assert success is True
        assert "test_command completed successfully" in message
        assert details["returncode"] == 0
        assert "test" in details["stdout"]

    def test_run_subprocess_test_failure(self):
        """Test _run_subprocess_test with a failing command."""
        success, message, details = self.validator._run_subprocess_test(
            command=["python", "-c", "import sys; sys.exit(1)"],
            test_name="test_failing_command",
            timeout=5
        )

        assert success is False
        assert "failed with exit code 1" in message
        assert details["returncode"] == 1

    def test_run_subprocess_test_not_found(self):
        """Test _run_subprocess_test with a command that doesn't exist."""
        success, message, details = self.validator._run_subprocess_test(
            command=["nonexistent_command_12345"],
            test_name="test_missing_command",
            timeout=5
        )

        assert success is False
        assert "command not found" in message

    def test_validate_dependencies(self):
        """Test the validate_dependencies method."""
        self.validator.validate_dependencies()

        assert "dependencies" in self.validator.results
        result = self.validator.results["dependencies"]

        # Should pass if we're in a properly set up environment
        if result["passed"]:
            assert "required dependencies are available" in result["message"]
            # Details should contain the individual package results
            assert "details" in result
            assert "chess" in result["details"]
        else:
            assert "Missing or broken dependencies" in result["message"]

    def test_validate_package_imports(self):
        """Test the validate_package_imports method."""
        self.validator.validate_package_imports()

        assert "package_imports" in self.validator.results
        result = self.validator.results["package_imports"]

        # Check that the result has the expected structure
        assert "passed" in result
        assert "message" in result
        assert "details" in result

        # The details should contain information about each module
        if result["passed"]:
            assert "Successfully imported" in result["message"]

    def test_validate_accessibility_modules(self):
        """Test the validate_accessibility_modules method."""
        self.validator.validate_accessibility_modules()

        assert "accessibility_modules" in self.validator.results
        result = self.validator.results["accessibility_modules"]

        assert "passed" in result
        assert "message" in result

        # Should contain information about available outputs
        if result["passed"]:
            assert "available_outputs" in result["details"]

    def test_validate_chess_engine_detection(self):
        """Test the validate_chess_engine_detection method."""
        self.validator.validate_chess_engine_detection()

        assert "engine_detection" in self.validator.results
        result = self.validator.results["engine_detection"]

        assert "passed" in result
        assert "message" in result
        assert "details" in result

        # Check that engine detection details are present
        details = result["details"]
        assert "stockfish_path" in details
        assert "engines_found" in details
        assert "engine_names" in details

    def test_validate_game_logic(self):
        """Test the validate_game_logic method."""
        self.validator.validate_game_logic()

        assert "game_logic" in self.validator.results
        result = self.validator.results["game_logic"]

        assert "passed" in result
        assert "message" in result

        if result["passed"]:
            assert "details" in result
            details = result["details"]
            assert "initial_legal_moves" in details
            assert "move_made_correctly" in details
            assert "game_config_valid" in details

    def test_validate_signal_system(self):
        """Test the validate_signal_system method."""
        self.validator.validate_signal_system()

        assert "signal_system" in self.validator.results
        result = self.validator.results["signal_system"]

        assert "passed" in result
        assert "message" in result

        if result["passed"]:
            assert "details" in result
            details = result["details"]
            assert "basic_signal_received" in details
            assert "board_signals_working" in details

    def test_performance_baseline(self):
        """Test the performance_baseline method."""
        self.validator.performance_baseline()

        assert "performance_baseline" in self.validator.results
        result = self.validator.results["performance_baseline"]

        assert "passed" in result
        assert "message" in result
        assert "details" in result

        # Check benchmark details
        details = result["details"]
        if "benchmarks" in details:
            benchmarks = details["benchmarks"]
            expected_metrics = ["import_time", "game_init_time", "move_generation_time"]
            for metric in expected_metrics:
                if metric in benchmarks:
                    assert isinstance(benchmarks[metric], (int, float))
                    assert benchmarks[metric] >= 0

    def test_validate_executable_functionality_no_executable(self):
        """Test validate_executable_functionality with no executable provided."""
        validator = BuildValidator(executable_path=None)
        validator.validate_executable_functionality()

        assert "executable_functionality" in validator.results
        result = validator.results["executable_functionality"]
        assert result["passed"] is False
        assert "No executable path provided" in result["message"]

    def test_validate_executable_functionality_nonexistent_executable(self):
        """Test validate_executable_functionality with a nonexistent executable."""
        fake_executable = Path("/nonexistent/fake/executable")
        validator = BuildValidator(executable_path=fake_executable)
        validator.validate_executable_functionality()

        assert "executable_functionality" in validator.results
        result = validator.results["executable_functionality"]
        assert result["passed"] is False
        assert "executable not found" in result["message"]

    def test_run_all_validations(self):
        """Test that run_all_validations executes all validation methods."""
        results = self.validator.run_all_validations()

        # Check that all expected validation tests were run
        expected_tests = [
            "dependencies",
            "package_imports",
            "accessibility_modules",
            "engine_detection",
            "game_logic",
            "signal_system",
            "performance_baseline"
        ]

        for test_name in expected_tests:
            assert test_name in results
            assert "passed" in results[test_name]
            assert "message" in results[test_name]

    def test_print_results(self):
        """Test the print_results method."""
        # Add some test results
        self.validator._add_result("test_pass", True, "Test passed", 0.1)
        self.validator._add_result("test_fail", False, "Test failed", 0.2)

        # Capture the result
        all_passed = self.validator.print_results()

        # Should return False since we have a failing test
        assert all_passed is False

        # Test with all passing results
        validator2 = BuildValidator()
        validator2._add_result("test_pass1", True, "Test 1 passed", 0.1)
        validator2._add_result("test_pass2", True, "Test 2 passed", 0.2)

        all_passed = validator2.print_results()
        assert all_passed is True


class TestBuildValidationIntegration:
    """Integration tests for the build validation system."""

    def test_validation_script_execution(self):
        """Test that the validation script can be executed."""
        validation_script = Path(__file__).parent.parent / ".build" / "validation" / "verify_build.py"
        assert validation_script.exists(), "Validation script should exist"

        # Test that the script can be imported and run
        result = subprocess.run(
            [sys.executable, str(validation_script), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        assert "Validate OpenBoard build functionality" in result.stdout

    def test_validation_with_verbose_flag(self):
        """Test validation script with verbose flag."""
        validation_script = Path(__file__).parent.parent / ".build" / "validation" / "verify_build.py"

        # Run a quick validation with verbose flag
        result = subprocess.run(
            [sys.executable, str(validation_script), "--verbose"],
            capture_output=True,
            text=True,
            timeout=60  # Allow more time for full validation
        )

        # Should complete (pass or fail) but not crash
        assert result.returncode in [0, 1]  # 0 for success, 1 for validation failures
        assert "Starting comprehensive build validation" in result.stdout

    def test_validation_project_root_parameter(self):
        """Test validation script with custom project root."""
        validation_script = Path(__file__).parent.parent / ".build" / "validation" / "verify_build.py"
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [
                sys.executable,
                str(validation_script),
                "--project-root",
                str(project_root),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should complete without crashing
        assert result.returncode in [0, 1]


class TestBuildValidationError:
    """Test the ValidationError exception."""

    def test_validation_error_creation(self):
        """Test that ValidationError can be created and raised."""
        error_message = "Test validation error"

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(error_message)

        assert str(exc_info.value) == error_message


class TestBuildValidationMocking:
    """Test build validation with mocked dependencies."""

    def test_validate_dependencies_with_missing_imports(self):
        """Test dependency validation when imports fail."""
        validator = BuildValidator()

        # Mock importlib.import_module to simulate missing dependencies
        with patch('importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            validator.validate_dependencies()

            result = validator.results["dependencies"]
            assert result["passed"] is False
            assert "Missing or broken dependencies" in result["message"]

    def test_validate_package_imports_with_failures(self):
        """Test package import validation with some failures."""
        validator = BuildValidator()

        # Mock importlib.import_module to simulate some import failures
        def mock_import_side_effect(module_name):
            if "engine" in module_name:
                raise ImportError(f"Cannot import {module_name}")
            return MagicMock()

        with patch('importlib.import_module', side_effect=mock_import_side_effect):
            validator.validate_package_imports()

            result = validator.results["package_imports"]
            assert result["passed"] is False
            assert "Failed to import" in result["message"]

    def test_performance_baseline_with_slow_operations(self):
        """Test performance baseline with artificially slow operations."""
        validator = BuildValidator()

        # Mock time.time to simulate slow operations
        original_time = time.time
        call_count = 0

        def mock_time():
            nonlocal call_count
            call_count += 1
            # Make every other call return a time 2 seconds later
            if call_count % 2 == 0:
                return original_time() + 2.0
            return original_time()

        with patch('time.time', side_effect=mock_time):
            with patch('openboard.models.game.Game'):  # Mock to avoid actual slow operations
                validator.performance_baseline()

                result = validator.results["performance_baseline"]
                # The test might pass or fail depending on the mocked timings
                assert "passed" in result


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])