"""Tests for check_typescript tool."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from aromcp.build_server.tools.check_typescript import check_typescript_impl


class TestCheckTypeScript:
    """Test cases for check_typescript functionality."""

    def test_no_errors_returns_simple_format(self):
        """Test that when no errors exist, only errors array is returned."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess to return no errors
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
            ):
                result = check_typescript_impl()

                # Should contain errors array and check_again flag when no errors
                assert result.errors == []
                assert not result.check_again
                assert hasattr(result, "total_errors")
                assert hasattr(result, "success")

    def test_errors_capped_to_first_file(self):
        """Test that errors are capped to first file only, with total count."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess to return errors from multiple files
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = """src/file1.ts(5,10): error TS2304: Cannot find name 'foo'.
src/file1.ts(8,15): error TS2304: Cannot find name 'bar'.
src/file2.ts(3,5): error TS2304: Cannot find name 'baz'.
src/file2.ts(7,12): error TS2304: Cannot find name 'qux'."""
            mock_result.returncode = 1

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
            ):
                result = check_typescript_impl()

                # Should cap errors to first file only
                assert len(result.errors) == 2  # Only errors from file1.ts
                assert result.total_errors == 4  # Total across all files
                assert result.check_again  # Should suggest checking again
                assert all(err.file == "src/file1.ts" for err in result.errors)
                assert result.errors[0].message == "Cannot find name 'foo'."
                assert result.errors[1].message == "Cannot find name 'bar'."

    def test_directory_auto_globbing(self):
        """Test that directory paths are automatically globbed with /*."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create a directory structure
            src_dir = Path(temp_dir) / "src" / "components"
            src_dir.mkdir(parents=True)

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with directory path
                check_typescript_impl(files="src/components")

                # Verify subprocess was called with globbed path
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src/components/*" in call_args
                assert "npx" == call_args[0]
                assert "tsc" == call_args[1]
                assert "--noEmit" == call_args[2]

    def test_file_paths_not_globbed(self):
        """Test that regular file paths are not modified."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create a test file
            test_file = Path(temp_dir) / "src" / "test.ts"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("const x: string = 'test';")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with file path
                check_typescript_impl(files="src/test.ts")

                # Verify subprocess was called with original file path
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src/test.ts" in call_args
                assert "src/test.ts/*" not in call_args

    def test_string_files_input(self):
        """Test that files parameter accepts a single string."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create a test file
            test_file = Path(temp_dir) / "test.ts"
            test_file.write_text("const x: string = 'test';")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with string input
                result = check_typescript_impl(files="test.ts")

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()

    def test_list_files_input(self):
        """Test that files parameter accepts a list of strings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create test files
            test_file1 = Path(temp_dir) / "test1.ts"
            test_file2 = Path(temp_dir) / "test2.ts"
            test_file1.write_text("const x: string = 'test1';")
            test_file2.write_text("const y: string = 'test2';")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with list input
                result = check_typescript_impl(files=["test1.ts", "test2.ts"])

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "test1.ts" in call_args
                assert "test2.ts" in call_args

    def test_json_string_files_input(self):
        """Test that files parameter handles JSON string input."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create test files
            test_file1 = Path(temp_dir) / "test1.ts"
            test_file2 = Path(temp_dir) / "test2.ts"
            test_file1.write_text("const x: string = 'test1';")
            test_file2.write_text("const y: string = 'test2';")

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with JSON string input
                result = check_typescript_impl(files='["test1.ts", "test2.ts"]')

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "test1.ts" in call_args
                assert "test2.ts" in call_args

    def test_mixed_files_and_directories(self):
        """Test handling of mixed files and directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Create test structure
            test_file = Path(temp_dir) / "test.ts"
            test_dir = Path(temp_dir) / "src"
            test_file.write_text("const x: string = 'test';")
            test_dir.mkdir()

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with mixed input
                result = check_typescript_impl(files=["test.ts", "src"])

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "test.ts" in call_args  # File unchanged
                assert "src/*" in call_args  # Directory globbed

    def test_nonexistent_file_raises_error(self):
        """Test that nonexistent files raise appropriate error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            with patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir):
                try:
                    check_typescript_impl(files="nonexistent.ts")
                    raise AssertionError("Should have raised ValueError")
                except ValueError as e:
                    assert "File or directory not found: nonexistent.ts" in str(e)

    def test_no_tsconfig_raises_error(self):
        """Test that missing tsconfig.json raises appropriate error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir):
                try:
                    check_typescript_impl()
                    raise AssertionError("Should have raised ValueError")
                except ValueError as e:
                    assert "No tsconfig.json found in project root" in str(e)

    def test_error_parsing(self):
        """Test parsing of TypeScript error output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess to return error
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = "src/test.ts(10,5): error TS2304: Cannot find name 'undefinedVar'."
            mock_result.returncode = 1

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
            ):
                result = check_typescript_impl()

                assert len(result.errors) == 1
                assert result.total_errors == 1
                assert result.check_again
                error = result.errors[0]
                assert error.file == "src/test.ts"
                assert error.line == 10
                assert error.column == 5
                assert error.severity == "error"
                assert error.code == "TS2304"
                assert error.message == "Cannot find name 'undefinedVar'."

    def test_glob_patterns_passed_through(self):
        """Test that glob patterns are passed directly to TypeScript compiler."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with glob pattern
                result = check_typescript_impl(files="src/**/*.ts")

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "src/**/*.ts" in call_args  # Glob pattern passed through unchanged
                assert "npx" == call_args[0]
                assert "tsc" == call_args[1]

    def test_errors_from_stdout_parsed(self):
        """Test that errors from stdout are properly parsed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess to return errors in stdout (common with exit code 2)
            mock_result = Mock()
            mock_result.stdout = "src/test.ts(10,5): error TS2304: Cannot find name 'undefinedVar'."
            mock_result.stderr = ""
            mock_result.returncode = 2

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result),
            ):
                result = check_typescript_impl()

                assert len(result.errors) == 1
                assert result.total_errors == 1
                assert result.check_again

                error = result.errors[0]
                assert error.file == "src/test.ts"
                assert error.line == 10
                assert error.message == "Cannot find name 'undefinedVar'."

    def test_no_files_parameter_checks_entire_project(self):
        """Test that calling check_typescript() with no files parameter checks the entire project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json
            tsconfig = Path(temp_dir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {"strict": true}}')

            # Mock subprocess
            mock_result = Mock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0

            with (
                patch("aromcp.build_server.tools.check_typescript.get_project_root", return_value=temp_dir),
                patch("subprocess.run", return_value=mock_result) as mock_subprocess,
            ):
                # Test with no files parameter (None)
                result = check_typescript_impl(files=None)

                assert result.errors == []
                assert not result.check_again
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                # Should contain more comprehensive TypeScript check
                assert "npx" == call_args[0]
                assert "tsc" == call_args[1]
                assert "--noEmit" in call_args
                # Should include either --skipLibCheck or --project depending on config
                assert "--skipLibCheck" in call_args or "--project" in call_args
