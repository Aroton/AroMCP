"""Tests for lint_project tool."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from aromcp.build_server.tools.lint_project import lint_project_impl
from aromcp.build_server.models.build_models import LintProjectResponse


class TestLintProject:
    """Test cases for lint_project functionality."""

    def test_target_files_string_input(self):
        """Test that target_files accepts a single string and converts to list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file
            test_file = Path(temp_dir) / "test.js"
            test_file.write_text("console.log('test');")

            # Mock the subprocess call
            mock_result = Mock()
            mock_result.stdout = json.dumps(
                [
                    {
                        "filePath": str(test_file),
                        "messages": [
                            {
                                "line": 1,
                                "column": 1,
                                "severity": 1,
                                "ruleId": "no-console",
                                "message": "Unexpected console statement.",
                                "fix": None,
                            }
                        ],
                    }
                ]
            )
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
                patch("pathlib.Path.exists", return_value=True),
            ):
                # Test with string input
                result = lint_project_impl(use_standards=False, target_files="test.js")

                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert len(result.issues) == 1
                    # Handle both dataclass and dict issues
                    issue = result.issues[0]
                    if hasattr(issue, 'rule'):
                        assert issue.rule == "no-console"
                    else:
                        assert issue['rule'] == "no-console"
                else:
                    assert "issues" in result
                    assert len(result["issues"]) == 1
                    assert result["issues"][0]["rule"] == "no-console"

    def test_target_files_list_input(self):
        """Test that target_files accepts a list of files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file1 = Path(temp_dir) / "test1.js"
            test_file2 = Path(temp_dir) / "test2.js"
            test_file1.write_text("console.log('test1');")
            test_file2.write_text("console.log('test2');")

            # Mock the subprocess call
            mock_result = Mock()
            mock_result.stdout = json.dumps(
                [
                    {
                        "filePath": str(test_file1),
                        "messages": [
                            {
                                "line": 1,
                                "column": 1,
                                "severity": 1,
                                "ruleId": "no-console",
                                "message": "Unexpected console statement.",
                                "fix": None,
                            }
                        ],
                    },
                    {
                        "filePath": str(test_file2),
                        "messages": [
                            {
                                "line": 1,
                                "column": 1,
                                "severity": 1,
                                "ruleId": "no-console",
                                "message": "Unexpected console statement.",
                                "fix": None,
                            }
                        ],
                    },
                ]
            )
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
                patch("pathlib.Path.exists", return_value=True),
            ):
                # Test with list input
                result = lint_project_impl(use_standards=False, target_files=["test1.js", "test2.js"])

                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert len(result.issues) == 1  # Only shows first file's issues
                    assert result.total_issues == 2  # Total across all files
                    assert not result.check_again  # No fixable issues
                    # Handle both dataclass and dict issues
                    issue = result.issues[0]
                    if hasattr(issue, 'rule'):
                        assert issue.rule == "no-console"
                    else:
                        assert issue['rule'] == "no-console"
                else:
                    assert "issues" in result
                    assert len(result["issues"]) == 1  # Only shows first file's issues
                    assert result["total_issues"] == 2  # Total across all files
                    assert not result["check_again"]  # No fixable issues
                    assert result["issues"][0]["rule"] == "no-console"

    def test_target_files_passed_to_subprocess(self):
        """Test that target_files are properly passed to subprocess command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config to avoid fallback logic
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Mock the subprocess call
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with specific target files
                result = lint_project_impl(use_standards=False, target_files=["src/app.js", "src/utils.js"])

                # Verify result structure (no issues case)
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert "issues" in result
                    assert "check_again" in result
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]

                # Verify target files are in the command
                assert "src/app.js" in call_args
                assert "src/utils.js" in call_args
                assert "npx" == call_args[0]
                assert "eslint" == call_args[1]

    def test_string_target_file_conversion(self):
        """Test that a single string target_file is converted to a list internally."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Mock the subprocess call
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with single string file
                result = lint_project_impl(use_standards=False, target_files="single-file.js")

                # Verify result structure (no issues case)
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert "issues" in result
                    assert "check_again" in result
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called with the file
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "single-file.js" in call_args

    def test_no_target_files_uses_default_src(self):
        """Test that when target_files is None, it defaults to src directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Mock the subprocess call
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with None target_files
                result = lint_project_impl(use_standards=False, target_files=None)

                # Verify result structure (no issues case)
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert "issues" in result
                    assert "check_again" in result
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called with src and extensions
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src" in call_args
                assert "--ext" in call_args

    def test_fixable_issues_suggest_check_again(self):
        """Test that fixable issues suggest checking again."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "test.js"
            test_file.write_text("console.log('test');")

            # Mock the subprocess call with fixable issue
            mock_result = Mock()
            mock_result.stdout = json.dumps(
                [
                    {
                        "filePath": str(test_file),
                        "messages": [
                            {
                                "line": 1,
                                "column": 1,
                                "severity": 1,
                                "ruleId": "no-console",
                                "message": "Unexpected console statement.",
                                "fix": {"range": [0, 20], "text": ""},  # Fixable issue
                            }
                        ],
                    }
                ]
            )
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
                patch("pathlib.Path.exists", return_value=True),
            ):
                # Test with fixable issue
                result = lint_project_impl(use_standards=False, target_files="test.js")

                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert len(result.issues) == 1
                    assert result.total_issues == 1
                    assert result.check_again  # Should suggest checking again
                    assert result.fixable_issues == 1  # Should include fixable count
                    # Handle both dataclass and dict issues
                    issue = result.issues[0]
                    if hasattr(issue, 'rule'):
                        assert issue.rule == "no-console"
                        assert issue.fixable
                    else:
                        assert issue['rule'] == "no-console"
                        assert issue['fixable']
                else:
                    assert "issues" in result
                    assert len(result["issues"]) == 1
                    assert result["total_issues"] == 1
                    assert result["check_again"]  # Should suggest checking again
                    assert result["fixable_issues"] == 1  # Should include fixable count
                    assert result["issues"][0]["rule"] == "no-console"
                    assert result["issues"][0]["fixable"]

    def test_directory_auto_globbing(self):
        """Test that directory paths are automatically globbed with /*."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Create a directory structure
            src_dir = Path(temp_dir) / "src" / "components"
            src_dir.mkdir(parents=True)

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with directory path
                result = lint_project_impl(use_standards=False, target_files="src/components")

                # Verify result
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called with globbed path
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src/components/*" in call_args
                assert "npx" == call_args[0]
                assert "eslint" == call_args[1]

    def test_glob_patterns_passed_through(self):
        """Test that glob patterns are passed directly to ESLint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with glob pattern
                result = lint_project_impl(use_standards=False, target_files="src/**/*.ts")

                # Verify result
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called with glob pattern
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src/**/*.ts" in call_args  # Glob pattern passed through unchanged
                assert "npx" == call_args[0]
                assert "eslint" == call_args[1]

    def test_no_target_files_parameter_uses_default_behavior(self):
        """Test that calling lint_project() with no target_files parameter uses default behavior."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ESLint config
            eslint_config = Path(temp_dir) / ".eslintrc.js"
            eslint_config.write_text("module.exports = {};")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with no target_files parameter (defaults to None)
                result = lint_project_impl(use_standards=True, target_files=None)

                # Verify result
                assert isinstance(result, (LintProjectResponse, dict))
                if isinstance(result, LintProjectResponse):
                    assert result.issues == []
                    assert not result.check_again
                else:
                    assert result["issues"] == []
                    assert not result["check_again"]

                # Verify subprocess was called with default src directory
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src" in call_args
                assert "--ext" in call_args
                assert "npx" == call_args[0]
                assert "eslint" == call_args[1]