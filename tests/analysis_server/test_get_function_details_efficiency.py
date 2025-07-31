"""
Tests for get_function_details efficiency improvements.

Ensures the tool returns reasonable response sizes and doesn't generate
excessive errors for functions not found in every file.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from aromcp.analysis_server.tools.get_function_details import get_function_details_impl


class TestGetFunctionDetailsEfficiency:
    """Test efficiency improvements for get_function_details."""

    def test_no_excessive_errors_for_missing_functions(self):
        """Test that missing functions don't generate errors for every file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a project with many files, but function only in one
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            # File 1: Contains the target function
            target_file = src_dir / "target.ts"
            target_file.write_text(
                """
export function myFunction(): string {
    return "found";
}
"""
            )

            # Files 2-10: Don't contain the function
            for i in range(2, 11):
                other_file = src_dir / f"other{i}.ts"
                other_file.write_text(
                    f"""
export function someOtherFunction{i}(): number {{
    return {i};
}}
"""
                )

            # Test project-wide search
            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = get_function_details_impl(
                    functions="myFunction",
                    file_paths=None,  # Project-wide search
                    include_code=False,
                    include_types=False,
                    include_calls=False,
                )

                # Should find the function
                assert len(result.functions) == 1
                assert "myFunction" in result.functions

                # Should have minimal or no errors (not one per file searched)
                assert len(result.errors) <= 2  # Allow for minor analysis errors

                # Should be successful
                assert result.success is True

    def test_reasonable_response_size(self):
        """Test that response sizes are reasonable even with detailed analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            # Create a function with some complexity
            test_file = src_dir / "complex.ts"
            test_file.write_text(
                """
export function complexFunction(param: string): Promise<number> {
    console.log(param);
    const helper = () => parseInt(param);
    return Promise.resolve(helper());
}

function helperFunction(): void {
    console.log("helper");
}
"""
            )

            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = get_function_details_impl(
                    functions="complexFunction",
                    file_paths=None,
                    include_code=False,  # Don't include code to keep size reasonable
                    include_types=True,
                    include_calls=True,
                )

                # Convert to approximate token count (rough estimate: 4 chars = 1 token)
                import json

                json_str = json.dumps(result.__dict__, default=str)
                approx_tokens = len(json_str) // 4

                # Should be well under the 25k token limit
                assert approx_tokens < 5000, f"Response too large: ~{approx_tokens} tokens"

                # Should still find the function
                assert len(result.functions) >= 1
                assert result.success is True

    def test_targeted_file_search_efficiency(self):
        """Test that providing specific files is efficient."""
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()

            target_file = src_dir / "specific.ts"
            target_file.write_text(
                """
export function specificFunction(): boolean {
    return true;
}
"""
            )

            with patch.dict(os.environ, {"MCP_FILE_ROOT": str(temp_dir)}):
                result = get_function_details_impl(
                    functions="specificFunction",
                    file_paths="src/specific.ts",  # Specific file
                    include_code=False,
                    include_types=True,
                    include_calls=True,
                )

                # Should find the function with no errors
                assert len(result.functions) == 1
                assert len(result.errors) == 0
                assert result.success is True

                # Response should be very small
                import json

                json_str = json.dumps(result.__dict__, default=str)
                approx_tokens = len(json_str) // 4
                assert approx_tokens < 1000, f"Specific file search too large: ~{approx_tokens} tokens"
