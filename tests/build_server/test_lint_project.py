"""Tests for lint_project tool."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from aromcp.build_server.tools.lint_project import lint_project_impl


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
            mock_result.stdout = json.dumps([{
                "filePath": str(test_file),
                "messages": [{
                    "line": 1,
                    "column": 1,
                    "severity": 1,
                    "ruleId": "no-console",
                    "message": "Unexpected console statement.",
                    "fix": None
                }]
            }])
            mock_result.returncode = 0

            with patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir), \
                 patch("subprocess.run", return_value=mock_result), \
                 patch("pathlib.Path.exists", return_value=True):

                # Test with string input
                result = lint_project_impl(use_standards=False, target_files="test.js")

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
            mock_result.stdout = json.dumps([
                {
                    "filePath": str(test_file1),
                    "messages": [{
                        "line": 1,
                        "column": 1,
                        "severity": 1,
                        "ruleId": "no-console",
                        "message": "Unexpected console statement.",
                        "fix": None
                    }]
                },
                {
                    "filePath": str(test_file2),
                    "messages": [{
                        "line": 1,
                        "column": 1,
                        "severity": 1,
                        "ruleId": "no-console",
                        "message": "Unexpected console statement.",
                        "fix": None
                    }]
                }
            ])
            mock_result.returncode = 0

            with patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir), \
                 patch("subprocess.run", return_value=mock_result), \
                 patch("pathlib.Path.exists", return_value=True):

                # Test with list input
                result = lint_project_impl(use_standards=False, target_files=["test1.js", "test2.js"])

                assert "issues" in result
                assert len(result["issues"]) == 2
                assert all(issue["rule"] == "no-console" for issue in result["issues"])

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

            with patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir), \
                 patch("subprocess.run", return_value=mock_result) as mock_subprocess:

                # Test with specific target files
                result = lint_project_impl(
                    use_standards=False,
                    target_files=["src/app.js", "src/utils.js"]
                )

                # Verify result structure
                assert "issues" in result
                assert "fixable" in result
                assert "total_issues" in result

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

            with patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir), \
                 patch("subprocess.run", return_value=mock_result) as mock_subprocess:

                # Test with single string file
                result = lint_project_impl(use_standards=False, target_files="single-file.js")

                # Verify result structure
                assert "issues" in result
                assert "fixable" in result

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

            with patch("aromcp.build_server.tools.lint_project.get_project_root", return_value=temp_dir), \
                 patch("subprocess.run", return_value=mock_result) as mock_subprocess:

                # Test with None target_files
                result = lint_project_impl(use_standards=False, target_files=None)

                # Verify result structure
                assert "issues" in result
                assert "fixable" in result

                # Verify subprocess was called with src and extensions
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src" in call_args
                assert "--ext" in call_args
