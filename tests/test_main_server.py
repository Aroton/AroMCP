"""Test main_server to ensure all tools load correctly."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aromcp.main_server import mcp


class TestMainServer:
    """Test suite for the unified main server."""

    def test_server_initialization(self):
        """Test that the server initializes correctly."""
        assert mcp is not None
        assert mcp.name == "AroMCP Server Suite"

    @pytest.mark.asyncio
    async def test_all_tools_loaded(self):
        """Test that all expected tools are loaded."""
        tools = await mcp.get_tools()
        tool_names = [tool for tool in tools]

        # Expected tool names from each module (based on actual registrations)
        filesystem_tools = [
            "get_target_files",
            "read_files_batch",
            "write_files_batch",
            "extract_method_signatures",
            "find_imports_for_files",
            "load_documents_by_pattern",
            "apply_file_diffs",
            "preview_file_changes",
            "validate_diffs"
        ]

        state_tools = [
            "initialize_process",
            "get_process_state",
            "update_process_state",
            "get_next_work_item",
            "complete_work_item",
            "cleanup_process"
        ]

        build_tools = [
            "run_command",
            "get_build_config",
            "check_dependencies",
            "parse_typescript_errors",
            "parse_lint_results",
            "run_test_suite",
            "run_nextjs_build"
        ]

        analysis_tools = [
            "find_dead_code",
            "find_import_cycles",
            "extract_api_endpoints"
        ]

        all_expected_tools = filesystem_tools + state_tools + build_tools + analysis_tools

        # Check that we have the expected number of tools
        assert len(tools) == len(all_expected_tools), f"Expected {len(all_expected_tools)} tools, got {len(tools)}"

        # Check that all expected tools are present
        for expected_tool in all_expected_tools:
            assert expected_tool in tool_names, f"Tool '{expected_tool}' not found in loaded tools"

    @pytest.mark.asyncio
    async def test_tool_categories_loaded(self):
        """Test that tools from each category are loaded."""
        tools = await mcp.get_tools()
        tool_names = [tool for tool in tools]

        # Check each category has tools
        filesystem_present = any("files" in name or "imports" in name or "documents" in name or "diffs" in name for name in tool_names)
        state_present = any("process" in name for name in tool_names)
        build_present = any("command" in name or "test" in name or "dependencies" in name for name in tool_names)
        analysis_present = any("dead_code" in name or "import_cycles" in name or "api_endpoints" in name for name in tool_names)

        assert filesystem_present, "No filesystem tools found"
        assert state_present, "No state management tools found"
        assert build_present, "No build tools found"
        assert analysis_present, "No analysis tools found"

    @pytest.mark.asyncio
    async def test_individual_tool_callable(self):
        """Test that individual tools can be retrieved and have proper structure."""
        # Test a tool from each category
        test_tools = [
            "get_target_files",
            "initialize_process",
            "run_command",
            "find_dead_code"
        ]

        for tool_name in test_tools:
            tool = await mcp.get_tool(tool_name)
            assert tool is not None, f"Tool '{tool_name}' not found"
            # Note: Actual tool execution would require proper MCP client setup
            # This just verifies the tool exists and is retrievable


def test_server_can_be_imported():
    """Test that the server can be imported without errors."""
    from aromcp.main_server import mcp
    assert mcp is not None


if __name__ == "__main__":
    pytest.main([__file__])
