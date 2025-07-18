"""Run test suite tool implementation for Build Tools."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path


def run_test_suite_impl(
    test_command: str | None = None,
    test_framework: str = "auto",
    pattern: str | None = None,
    coverage: bool = False,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute tests with parsed results.

    Args:
        test_command: Custom test command (auto-detected if None)
        test_framework: Test framework ("jest", "vitest", "mocha", "pytest", "auto")
        pattern: Test file pattern to run specific tests
        coverage: Whether to generate coverage report
        timeout: Maximum execution time in seconds

    Returns:
        Dictionary with test results
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)

        # Validate project root path
        validation_result = validate_file_path(project_root, project_root)
        if not validation_result.get("valid", False):
            raise ValueError(validation_result.get("error", "Invalid project root path"))

        # Auto-detect test framework and command if needed
        if test_framework == "auto" or test_command is None:
            detected_framework, detected_command = _detect_test_setup(project_root)

            if test_framework == "auto":
                test_framework = detected_framework
            if test_command is None:
                test_command = detected_command

        if not test_command:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": (
                        "No test command found. Please specify test_command or ensure test framework is configured."
                    ),
                }
            }

        # Build test command
        cmd = test_command.split()

        # Add framework-specific options
        if test_framework == "jest":
            cmd = _add_jest_options(cmd, pattern, coverage)
        elif test_framework == "vitest":
            cmd = _add_vitest_options(cmd, pattern, coverage)
        elif test_framework == "mocha":
            cmd = _add_mocha_options(cmd, pattern)
        elif test_framework == "pytest":
            cmd = _add_pytest_options(cmd, pattern, coverage)

        try:
            result = subprocess.run(  # noqa: S603 # Safe: cmd built from internal functions with predetermined commands
                cmd, cwd=project_root, capture_output=True, text=True, timeout=timeout
            )

            # Parse test results based on framework
            if test_framework == "jest":
                parsed_results = _parse_jest_output(result.stdout, result.stderr)
            elif test_framework == "vitest":
                parsed_results = _parse_vitest_output(result.stdout, result.stderr)
            elif test_framework == "mocha":
                parsed_results = _parse_mocha_output(result.stdout, result.stderr)
            elif test_framework == "pytest":
                parsed_results = _parse_pytest_output(result.stdout, result.stderr)
            else:
                # Generic parsing for unknown frameworks
                parsed_results = _parse_generic_output(result.stdout, result.stderr)

            # Extract standard fields from parsed results
            summary = parsed_results.get("summary", {})

            # Build standardized response
            standardized_result = {
                "tests_passed": summary.get("passed", 0),
                "tests_failed": summary.get("failed", 0),
                "tests_skipped": summary.get("skipped", 0),
                "total_tests": summary.get("total", 0),
                "framework": test_framework,
                "duration": summary.get("duration", 0),
                "success": result.returncode == 0,
                "coverage": parsed_results.get("coverage", None),
                "test_results": parsed_results.get("test_files", []),
            }

            return standardized_result

        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Test execution timed out after {timeout} seconds") from e
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to run tests: {str(e)}") from e

    except Exception as e:
        raise ValueError(f"Failed to execute test suite: {str(e)}") from e


def _detect_test_setup(project_root: str) -> tuple[str, str | None]:
    """Auto-detect test framework and command."""
    project_path = Path(project_root)

    # Check package.json for test scripts and dependencies
    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            package_json = json.loads(package_json_path.read_text(encoding="utf-8"))

            # Check scripts
            scripts = package_json.get("scripts", {})
            test_script = scripts.get("test")

            # Check dependencies for frameworks
            all_deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}

            if "jest" in all_deps:
                return "jest", test_script or "npm test"
            elif "vitest" in all_deps:
                return "vitest", test_script or "npm test"
            elif "mocha" in all_deps:
                return "mocha", test_script or "npm test"

            # Fallback to script content analysis
            if test_script:
                if "jest" in test_script:
                    return "jest", test_script
                elif "vitest" in test_script:
                    return "vitest", test_script
                elif "mocha" in test_script:
                    return "mocha", test_script

        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Check for Python test setup
    if (project_path / "pytest.ini").exists() or (project_path / "pyproject.toml").exists():
        return "pytest", "pytest"

    # Check for test directories
    if (project_path / "__tests__").exists():
        return "jest", "npm test"
    elif (project_path / "test").exists():
        return "mocha", "npm test"

    return "unknown", None


def _add_jest_options(cmd: list[str], pattern: str | None, coverage: bool) -> list[str]:
    """Add Jest-specific options."""
    if pattern:
        cmd.extend(["--testPathPattern", pattern])
    if coverage:
        cmd.append("--coverage")
    cmd.append("--json")  # For structured output
    return cmd


def _add_vitest_options(cmd: list[str], pattern: str | None, coverage: bool) -> list[str]:
    """Add Vitest-specific options."""
    if pattern:
        cmd.append(pattern)
    if coverage:
        cmd.append("--coverage")
    cmd.append("--reporter=json")  # For structured output
    return cmd


def _add_mocha_options(cmd: list[str], pattern: str | None) -> list[str]:
    """Add Mocha-specific options."""
    if pattern:
        cmd.append(pattern)
    cmd.extend(["--reporter", "json"])  # For structured output
    return cmd


def _add_pytest_options(cmd: list[str], pattern: str | None, coverage: bool) -> list[str]:
    """Add pytest-specific options."""
    if pattern:
        cmd.extend(["-k", pattern])
    if coverage:
        cmd.extend(["--cov", "."])
    cmd.extend(["--tb=short", "-v"])  # Verbose output
    return cmd


def _parse_jest_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse Jest JSON output."""
    try:
        # Jest outputs JSON to stdout when --json flag is used
        if stdout.strip():
            jest_result = json.loads(stdout)

            summary = jest_result.get("testResults", [])
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0
            test_files = []

            for test_file in summary:
                file_path = test_file.get("name", "")
                test_results = test_file.get("assertionResults", [])

                file_passed = 0
                file_failed = 0
                file_skipped = 0

                for test in test_results:
                    status = test.get("status")
                    if status == "passed":
                        file_passed += 1
                        passed_tests += 1
                    elif status == "failed":
                        file_failed += 1
                        failed_tests += 1
                    elif status == "skipped":
                        file_skipped += 1
                        skipped_tests += 1

                total_tests += len(test_results)

                test_files.append(
                    {
                        "file": file_path,
                        "passed": file_passed,
                        "failed": file_failed,
                        "skipped": file_skipped,
                        "duration": test_file.get("endTime", 0) - test_file.get("startTime", 0),
                    }
                )

            return {
                "summary": {
                    "total": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "skipped": skipped_tests,
                    "duration": jest_result.get("testResults", [{}])[0].get("perfStats", {}).get("runtime", 0),
                },
                "test_files": test_files,
                "coverage": jest_result.get("coverageMap", {}),
            }

    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    # Fallback to text parsing
    return _parse_generic_output(stdout, stderr)


def _parse_vitest_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse Vitest JSON output."""
    try:
        # Vitest outputs JSON when --reporter=json is used
        if stdout.strip():
            vitest_result = json.loads(stdout)

            # Parse Vitest structure (may vary by version)
            test_results = vitest_result.get("testResults", [])
            total_tests = sum(len(tr.get("assertionResults", [])) for tr in test_results)

            summary = {
                "total": total_tests,
                "passed": vitest_result.get("numPassedTests", 0),
                "failed": vitest_result.get("numFailedTests", 0),
                "skipped": vitest_result.get("numSkippedTests", 0),
                "duration": vitest_result.get("testExecTime", 0),
            }

            return {"summary": summary, "test_files": test_results, "coverage": vitest_result.get("coverageMap", {})}

    except (json.JSONDecodeError, KeyError):
        pass

    return _parse_generic_output(stdout, stderr)


def _parse_mocha_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse Mocha JSON output."""
    try:
        if stdout.strip():
            mocha_result = json.loads(stdout)

            stats = mocha_result.get("stats", {})

            return {
                "summary": {
                    "total": stats.get("tests", 0),
                    "passed": stats.get("passes", 0),
                    "failed": stats.get("failures", 0),
                    "skipped": stats.get("pending", 0),
                    "duration": stats.get("duration", 0),
                },
                "test_files": mocha_result.get("tests", []),
                "failures": mocha_result.get("failures", []),
            }

    except (json.JSONDecodeError, KeyError):
        pass

    return _parse_generic_output(stdout, stderr)


def _parse_pytest_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse pytest output."""
    # pytest doesn't have built-in JSON output, so we parse text
    output = stdout + "\n" + stderr

    # Look for pytest summary line
    summary_pattern = re.compile(r"=+ (.+) in ([\d.]+)s =+")
    match = summary_pattern.search(output)

    passed = failed = skipped = 0
    duration = 0

    if match:
        summary_text = match.group(1)
        duration = float(match.group(2))

        # Parse summary components
        if "passed" in summary_text:
            passed_match = re.search(r"(\d+) passed", summary_text)
            if passed_match:
                passed = int(passed_match.group(1))

        if "failed" in summary_text:
            failed_match = re.search(r"(\d+) failed", summary_text)
            if failed_match:
                failed = int(failed_match.group(1))

        if "skipped" in summary_text:
            skipped_match = re.search(r"(\d+) skipped", summary_text)
            if skipped_match:
                skipped = int(skipped_match.group(1))

    return {
        "summary": {
            "total": passed + failed + skipped,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": duration,
        },
        "test_files": [],  # pytest text output doesn't easily give per-file breakdown
        "raw_output": output[:1000],  # Include first 1000 chars for debugging
    }


def _parse_generic_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Generic parser for unknown test frameworks."""
    output = stdout + "\n" + stderr

    # Try to extract basic pass/fail information
    passed = len(re.findall(r"\bpass(ed)?\b", output, re.IGNORECASE))
    failed = len(re.findall(r"\bfail(ed)?\b", output, re.IGNORECASE))

    return {
        "summary": {"total": passed + failed, "passed": passed, "failed": failed, "skipped": 0, "duration": 0},
        "test_files": [],
        "raw_output": output[:1000],
    }
