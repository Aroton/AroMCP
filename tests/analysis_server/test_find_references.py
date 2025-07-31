"""
Tests for find_references tool implementation.

Tests both the string literal filtering functionality and MCP_FILE_ROOT
project-wide search capabilities.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from aromcp.analysis_server.tools.find_references import find_references_impl
from aromcp.analysis_server.tools.get_call_trace import get_call_trace_impl
from aromcp.analysis_server.tools.get_function_details import get_function_details_impl


class TestFindReferences:
    """Test find_references implementation."""

    def test_string_literal_filtering(self):
        """Test that symbols inside string literals are correctly filtered out."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file with both valid references and string literals
            test_file = Path(temp_dir) / "test.ts"
            test_content = """
// Valid function definition
export function useSubscription(): any {
    // Valid function call
    const result = useSubscription();
    
    // String literals that should be filtered out
    throw new Error('useSubscription must be used within a provider');
    console.log("useSubscription is not available");
    const message = `useSubscription error occurred`;
    
    // Valid usage in code
    return useSubscription;
}
"""
            test_file.write_text(test_content)

            # Test with string filtering (default behavior)
            result = find_references_impl(
                symbol="useSubscription", file_paths=[str(test_file)], include_declarations=True, include_usages=True
            )

            # Should find: function definition, function call, and return statement
            # Should NOT find: error message strings, console.log string, template literal
            assert len(result.references) == 3  # definition, call, return

            # Verify none of the references are from string literals
            for ref in result.references:
                assert "Error(" not in ref.context
                assert "console.log(" not in ref.context
                assert "message = `" not in ref.context

            # Verify we got the valid references
            contexts = [ref.context.strip() for ref in result.references]
            assert any("export function useSubscription()" in ctx for ctx in contexts)
            assert any("const result = useSubscription()" in ctx for ctx in contexts)

    def test_mcp_file_root_project_wide_search(self):
        """Test that project-wide search uses MCP_FILE_ROOT when file_paths=None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a project structure with multiple files
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            # File 1: Contains function definition
            file1 = src_dir / "hooks.ts"
            file1.write_text(
                """
export function useSubscription(): any {
    return null;
}
"""
            )

            # File 2: Contains function usage
            file2 = src_dir / "component.tsx"
            file2.write_text(
                """
import { useSubscription } from './hooks';

export function MyComponent() {
    const sub = useSubscription();
    return null;
}
"""
            )

            # File 3: Contains string literal (should be filtered)
            file3 = src_dir / "test.ts"
            file3.write_text(
                """
describe('useSubscription tests', () => {
    // This should be filtered out
    console.log('useSubscription is being tested');
});
"""
            )

            # Test project-wide search with MCP_FILE_ROOT
            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = find_references_impl(
                    symbol="useSubscription",
                    file_paths=None,  # This should trigger project-wide search
                    include_declarations=True,
                    include_usages=True,
                    resolve_imports=True,
                )

                # Should find references across multiple files
                assert len(result.references) >= 3  # definition, import, usage
                assert result.searched_files >= 3  # Should have searched multiple files

                # Verify we found references in different files
                file_paths = {ref.file_path for ref in result.references}
                assert len(file_paths) >= 2  # References from at least 2 different files

                # Verify string literal was filtered out
                for ref in result.references:
                    assert "console.log(" not in ref.context
                    assert "'useSubscription is being tested'" not in ref.context

    def test_specific_file_search(self):
        """Test that providing specific file_paths works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "specific.ts"
            test_file.write_text(
                """
export function useSubscription(): any {
    return useSubscription();
}
"""
            )

            result = find_references_impl(
                symbol="useSubscription", file_paths=[str(test_file)], include_declarations=True, include_usages=True
            )

            # Should find definition and usage
            assert len(result.references) == 2
            assert result.searched_files == 1

            # All references should be from the specified file
            for ref in result.references:
                assert ref.file_path == str(test_file)

    def test_empty_results_for_nonexistent_symbol(self):
        """Test that searching for non-existent symbol returns empty results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "empty.ts"
            test_file.write_text(
                """
export function someFunction(): any {
    return null;
}
"""
            )

            result = find_references_impl(
                symbol="nonExistentSymbol", file_paths=[str(test_file)], include_declarations=True, include_usages=True
            )

            assert len(result.references) == 0
            assert result.total_references == 0
            assert result.success is True
            assert len(result.errors) == 0

    def test_error_handling_for_nonexistent_file(self):
        """Test error handling when file doesn't exist."""
        result = find_references_impl(
            symbol="anySymbol", file_paths=["/nonexistent/file.ts"], include_declarations=True, include_usages=True
        )

        # Should handle error gracefully
        assert len(result.references) == 0
        assert len(result.errors) == 1
        assert result.errors[0].code == "NOT_FOUND"
        assert "File not found" in result.errors[0].message
        assert result.success is False


class TestMCPFileRootIntegration:
    """Test MCP_FILE_ROOT integration across analysis tools."""

    def test_get_function_details_relative_path_resolution(self):
        """Test that get_function_details resolves relative paths using MCP_FILE_ROOT."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            test_file = src_dir / "test.ts"
            test_file.write_text(
                """
export function testFunction(): string {
    return "hello";
}
"""
            )

            # Test with relative path
            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = get_function_details_impl(
                    functions="testFunction", file_paths="src/test.ts", include_code=True  # Relative path
                )

                assert result.success is True
                assert len(result.errors) == 0
                assert "testFunction" in result.functions

    def test_get_call_trace_relative_path_resolution(self):
        """Test that get_call_trace resolves relative paths using MCP_FILE_ROOT."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            test_file = src_dir / "trace.ts"
            test_file.write_text(
                """
export function entryFunction(): void {
    helperFunction();
}

function helperFunction(): void {
    console.log("helper");
}
"""
            )

            # Test with relative path
            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = get_call_trace_impl(
                    entry_point="entryFunction", file_paths="src/trace.ts", max_depth=3  # Relative path
                )

                assert len(result.errors) == 0
                assert result.entry_point == "entryFunction"
