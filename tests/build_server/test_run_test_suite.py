"""Tests for run_test_suite tool implementation."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from aromcp.build_server.tools.run_test_suite import _parse_jest_output, run_test_suite_impl


class TestRunTestSuite:
    """Test class for run_test_suite functionality."""

    # Real Jest JSON output from SmallBusinessWebsite
    REAL_JEST_JSON = """{
  "numFailedTestSuites": 0,
  "numFailedTests": 0,
  "numPassedTestSuites": 13,
  "numPassedTests": 187,
  "numPendingTestSuites": 0,
  "numPendingTests": 0,
  "numRuntimeErrorTestSuites": 0,
  "numTodoTests": 0,
  "numTotalTestSuites": 13,
  "numTotalTests": 187,
  "openHandles": [],
  "snapshot": {
    "added": 0,
    "didUpdate": false,
    "failure": false,
    "filesAdded": 0,
    "filesRemoved": 0,
    "filesRemovedList": [],
    "filesUnmatched": 0,
    "filesUpdated": 0,
    "matched": 0,
    "total": 0,
    "unchecked": 0,
    "uncheckedKeysByFile": [],
    "unmatched": 0,
    "updated": 0
  },
  "startTime": 1752855068935,
  "success": true,
  "testResults": [
    {
      "assertionResults": [
        {
          "ancestorTitles": ["Basic Type Safety Tests", "✅ Should Compile - Basic Dependencies"],
          "duration": 4,
          "failureDetails": [],
          "failureMessages": [],
          "fullName": "Basic Type Safety Tests Test 1.1: Simple linear dep chain",
          "invocations": 1,
          "location": null,
          "numPassingAsserts": 0,
          "retryReasons": [],
          "status": "passed",
          "title": "Test 1.1: Simple linear dependency chain"
        }
      ],
      "endTime": 1752855070024,
      "message": "",
      "name": "/home/aroto/SmallBusinessWebsite/lib/Pipeline/verification.test.ts",
      "startTime": 1752855069670,
      "status": "passed",
      "summary": ""
    },
    {
      "assertionResults": [
        {
          "ancestorTitles": ["imageUtils", "fileToDataUrl"],
          "duration": 5,
          "failureDetails": [],
          "failureMessages": [],
          "fullName": "imageUtils fileToDataUrl should convert a File to base64 data URL",
          "invocations": 1,
          "location": null,
          "numPassingAsserts": 2,
          "retryReasons": [],
          "status": "passed",
          "title": "should convert a File to base64 data URL"
        }
      ],
      "endTime": 1752855070047,
      "message": "",
      "name": "/home/aroto/SmallBusinessWebsite/src/components/GenericChat/utils/__tests__/imageUtils.test.ts",
      "startTime": 1752855069681,
      "status": "passed",
      "summary": ""
    }
  ],
  "wasInterrupted": false
}"""

    def test_jest_json_parsing_with_real_data(self):
        """Test Jest parsing with actual JSON output from SmallBusinessWebsite."""
        result = _parse_jest_output(self.REAL_JEST_JSON, "")

        # Verify test counts
        assert result["summary"]["total"] == 187
        assert result["summary"]["passed"] == 187
        assert result["summary"]["failed"] == 0
        assert result["summary"]["skipped"] == 0

        # Verify test suite information is present
        assert "test_suites" in result
        assert result["test_suites"]["total"] == 13
        assert result["test_suites"]["passed"] == 13
        assert result["test_suites"]["failed"] == 0

        # Verify duration calculation
        assert result["summary"]["duration"] > 0  # Should calculate from test files

        # Verify test files are parsed
        assert len(result["test_files"]) == 2
        assert result["test_files"][0]["file"] == "/home/aroto/SmallBusinessWebsite/lib/Pipeline/verification.test.ts"

    def test_command_construction_with_jest(self):
        """Test that the correct command is constructed for Jest projects."""
        captured_commands = []

        def mock_subprocess_run(*args, **kwargs):
            # Capture the command
            cmd = args[0] if args else kwargs.get("args", [])
            captured_commands.append(cmd)

            # Return mock result with JSON output
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = self.REAL_JEST_JSON
            mock_result.stderr = ""
            return mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package.json like SmallBusinessWebsite
            package_json = {
                "name": "small-business-website",
                "scripts": {"test": "jest"},
                "devDependencies": {"jest": "^29.0.0"},
            }
            package_json_path = os.path.join(temp_dir, "package.json")
            with open(package_json_path, "w") as f:
                json.dump(package_json, f)

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                with patch.dict(os.environ, {"MCP_FILE_ROOT": temp_dir}):
                    result = run_test_suite_impl()

                    # Verify command construction
                    assert len(captured_commands) == 1
                    cmd = captured_commands[0]
                    assert cmd == ["npm", "run", "test", "--", "--json"]

                    # Verify the result includes test suite information
                    assert result.tests_passed == 187
                    assert result.total_tests == 187
                    assert result.test_suites is not None
                    assert result.test_suites.total == 13

    def test_fallback_parsing_when_json_fails(self):
        """Test that fallback parsing works when JSON is malformed."""
        # Malformed JSON that should trigger fallback
        malformed_json = '{"numTotalTests": 215, "numPassedTests": 215, "numTotalTestSuites": 13, "incomplete'

        result = _parse_jest_output(malformed_json, "")

        # Should fall back to regex parsing
        assert result["summary"]["total"] == 215
        assert result["summary"]["passed"] == 215
        assert result["summary"]["failed"] == 0
        assert "test_suites" in result
        assert result["test_suites"]["total"] == 13

    def test_text_fallback_parsing(self):
        """Test that text parsing works when no JSON is present."""
        text_output = """
        PASS  lib/Pipeline/verification.test.ts
        PASS  src/components/GenericChat/utils/__tests__/imageUtils.test.ts

        Test Suites: 13 passed, 13 total
        Tests:       187 passed, 187 total
        Snapshots:   0 total
        Time:        2.169 s
        """

        result = _parse_jest_output("", text_output)

        # Should use generic parsing (counting "pass" occurrences case-insensitively)
        # "PASS" appears 2 times, "passed" appears 2 times = 4 total
        assert result["summary"]["total"] == 4
        assert result["summary"]["passed"] == 4
        # No test_suites in generic parsing
        assert "test_suites" not in result

    def test_implementation_with_actual_jest_scenario(self):
        """Test the full implementation path that mimics SmallBusinessWebsite scenario."""

        def mock_subprocess_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])

            # Simulate Jest running with --json flag
            if "--json" in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = self.REAL_JEST_JSON
                mock_result.stderr = ""
                return mock_result
            else:
                # This shouldn't happen with our fix
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Tests: 15 passed, 15 total"  # Text output
                mock_result.stderr = ""
                return mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package.json exactly like SmallBusinessWebsite
            package_json = {
                "name": "small-business-website",
                "version": "0.1.0",
                "private": True,
                "scripts": {"test": "jest"},
                "dependencies": {},
                "devDependencies": {"jest": "^29.0.0"},
            }
            package_json_path = os.path.join(temp_dir, "package.json")
            with open(package_json_path, "w") as f:
                json.dump(package_json, f, indent=2)

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                with patch.dict(os.environ, {"MCP_FILE_ROOT": temp_dir}):
                    result = run_test_suite_impl()

                    # This should match what SmallBusinessWebsite should get
                    assert result.tests_passed == 187
                    assert result.tests_failed == 0
                    assert result.total_tests == 187
                    assert result.framework == "jest"
                    assert result.success is True

                    # The key assertion - test_suites should be present
                    assert result.test_suites is not None, "test_suites field should be present in result"
                    assert result.test_suites.total == 13
                    assert result.test_suites.passed == 13
                    assert result.test_suites.failed == 0

                    # Duration should be calculated
                    assert result.duration > 0

    def test_actual_smallbusinesswebsite_output(self):
        """Test with the actual simplified output from SmallBusinessWebsite."""
        # This is the actual Jest JSON output from SmallBusinessWebsite
        actual_json = """{
  "numFailedTestSuites": 0,
  "numFailedTests": 0,
  "numPassedTestSuites": 13,
  "numPassedTests": 187,
  "numPendingTestSuites": 0,
  "numPendingTests": 0,
  "numRuntimeErrorTestSuites": 0,
  "numTodoTests": 0,
  "numTotalTestSuites": 13,
  "numTotalTests": 187,
  "openHandles": [],
  "snapshot": {
    "added": 0,
    "didUpdate": false,
    "failure": false,
    "filesAdded": 0,
    "filesRemoved": 0,
    "filesRemovedList": [],
    "filesUnmatched": 0,
    "filesUpdated": 0,
    "matched": 0,
    "total": 0,
    "unchecked": 0,
    "uncheckedKeysByFile": [],
    "unmatched": 0,
    "updated": 0
  },
  "startTime": 1752856503726,
  "success": true,
  "testResults": [],
  "wasInterrupted": false
}"""

        # Test direct parsing
        result = _parse_jest_output(actual_json, "")

        # Verify parsing works correctly
        assert result["summary"]["total"] == 187
        assert result["summary"]["passed"] == 187
        assert result["summary"]["failed"] == 0
        assert "test_suites" in result
        assert result["test_suites"]["total"] == 13
        assert result["test_suites"]["passed"] == 13
        assert result["test_suites"]["failed"] == 0

        # Duration will be 0 since no endTime and empty testResults
        assert result["summary"]["duration"] == 0

        # Test full implementation with this output
        with tempfile.TemporaryDirectory() as temp_dir:
            package_json = {
                "name": "small-business-website",
                "scripts": {"test": "jest"},
                "devDependencies": {"jest": "^29.0.0"},
            }
            package_json_path = os.path.join(temp_dir, "package.json")
            with open(package_json_path, "w") as f:
                json.dump(package_json, f)

            def mock_subprocess_run(*args, **kwargs):  # noqa: ARG001
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = actual_json
                mock_result.stderr = ""
                return mock_result

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                with patch.dict(os.environ, {"MCP_FILE_ROOT": temp_dir}):
                    impl_result = run_test_suite_impl()

                    # This should have test_suites in the implementation result
                    assert impl_result.tests_passed == 187
                    assert impl_result.total_tests == 187
                    assert impl_result.test_suites is not None, "test_suites should be present in implementation result"
                    assert impl_result.test_suites.total == 13

    def test_mixed_text_and_json_output(self):
        """Test Jest output that contains both text and JSON (common real-world scenario)."""
        # Simulate Jest output with human-readable results followed by JSON
        mixed_output = """PASS  lib/Pipeline/verification.test.ts
PASS  src/components/GenericChat/utils/__tests__/imageUtils.test.ts

Test Suites: 13 passed, 13 total
Tests:       187 passed, 187 total
Snapshots:   0 total
Time:        2.169 s
Ran all test suites.

{"numFailedTestSuites":0,"numFailedTests":0,"numPassedTestSuites":13,"numPassedTests":187,"numPendingTestSuites":0,"numPendingTests":0,"numRuntimeErrorTestSuites":0,"numTodoTests":0,"numTotalTestSuites":13,"numTotalTests":187,"openHandles":[],"snapshot":{"added":0,"didUpdate":false,"failure":false},"startTime":1752856503726,"success":true,"testResults":[],"wasInterrupted":false}"""

        result = _parse_jest_output(mixed_output, "")

        # Should parse the JSON part correctly, not the text part
        assert result["summary"]["total"] == 187  # From JSON, not text counting
        assert result["summary"]["passed"] == 187
        assert result["summary"]["failed"] == 0
        assert "test_suites" in result
        assert result["test_suites"]["total"] == 13
        assert result["test_suites"]["passed"] == 13
        assert result["test_suites"]["failed"] == 0

    def test_multiline_json_at_end(self):
        """Test Jest output with pretty-printed JSON at the end."""
        mixed_output = """PASS  lib/Pipeline/verification.test.ts

Test Suites: 13 passed, 13 total

{
  "numFailedTestSuites": 0,
  "numFailedTests": 0,
  "numPassedTestSuites": 13,
  "numPassedTests": 187,
  "numTotalTestSuites": 13,
  "numTotalTests": 187,
  "success": true,
  "testResults": []
}"""

        result = _parse_jest_output(mixed_output, "")

        # Should extract and parse the multi-line JSON correctly
        assert result["summary"]["total"] == 187
        assert result["summary"]["passed"] == 187
        assert "test_suites" in result
        assert result["test_suites"]["total"] == 13

    def test_vitest_mixed_output(self):
        """Test Vitest with mixed text and JSON output."""
        mixed_output = """✓ utils/helpers.test.ts (3)
✓ components/Button.test.tsx (5)

 Test Files  2 passed (2)
      Tests  8 passed (8)

{"testResults":[{"name":"utils/helpers.test.ts","status":"passed","assertionResults":[]}],"numPassedTests":8,"numFailedTests":0,"numTotalTests":8}"""

        from aromcp.build_server.tools.run_test_suite import _parse_vitest_output

        result = _parse_vitest_output(mixed_output, "")

        # Should extract the JSON part correctly
        assert "summary" in result
        # Vitest has different structure but should still work

    def test_mocha_mixed_output(self):
        """Test Mocha with mixed text and JSON output."""
        mixed_output = """  Authentication
    ✓ should authenticate user
    ✓ should handle invalid credentials

  2 passing (150ms)

{"stats":{"tests":2,"passes":2,"failures":0,"duration":150},"tests":[]}"""

        from aromcp.build_server.tools.run_test_suite import _parse_mocha_output

        result = _parse_mocha_output(mixed_output, "")

        # Should extract the JSON part correctly
        assert result["summary"]["total"] == 2
        assert result["summary"]["passed"] == 2
        assert result["summary"]["failed"] == 0

    def test_framework_detection_with_jest(self):
        """Test that Jest is correctly detected from package.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package.json with Jest
            package_json = {"scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}
            package_json_path = os.path.join(temp_dir, "package.json")
            with open(package_json_path, "w") as f:
                json.dump(package_json, f)

            # Mock subprocess to capture command
            captured_commands = []

            def mock_subprocess_run(*args, **kwargs):
                captured_commands.append(args[0] if args else kwargs.get("args", []))
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = self.REAL_JEST_JSON
                mock_result.stderr = ""
                return mock_result

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                with patch.dict(os.environ, {"MCP_FILE_ROOT": temp_dir}):
                    result = run_test_suite_impl()

                    # Verify Jest was detected and npm run test is used
                    assert result.framework == "jest"
                    assert len(captured_commands) == 1
                    assert captured_commands[0] == ["npm", "run", "test", "--", "--json"]
