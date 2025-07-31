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
        assert mcp.name == "AroMCP Development Tools Suite"

    @pytest.mark.asyncio
    async def test_all_tools_loaded(self):
        """Test that all expected tools are loaded."""
        tools = await mcp.get_tools()
        tool_names = list(tools)

        # Expected tool names from each module (based on actual registrations)
        filesystem_tools = ["list_files", "read_files", "write_files"]

        workflow_state_tools = [
            "workflow_state_read",
            "workflow_state_update",
            "workflow_state_dependencies",
            "workflow_state_init",
            "workflow_state_validate_path",
        ]

        workflow_execution_tools = [
            "workflow_get_info",
            "workflow_start",
            "workflow_list",
            "workflow_get_next_step",
            "workflow_get_status",
            "workflow_update_state",
            "workflow_list_active",
            "workflow_checkpoint",
            "workflow_resume",
        ]

        build_tools = ["check_typescript", "lint_project", "run_test_suite"]

        analysis_tools = ["find_references", "get_function_details", "analyze_call_graph"]  # TypeScript analysis tools

        standards_tools = [
            "check_updates",
            "register",
            "delete",
            "hints_for_file",
            "get_session_stats",
            "clear_session",
            "analyze_context",
            "add_hint",
            "add_rule",
            "list_rules",
        ]

        all_expected_tools = (
            filesystem_tools
            + workflow_state_tools
            + workflow_execution_tools
            + build_tools
            + analysis_tools
            + standards_tools
        )

        # Check that we have the expected number of tools
        assert len(tools) == len(all_expected_tools), f"Expected {len(all_expected_tools)} tools, got {len(tools)}"

        # Check that all expected tools are present
        for expected_tool in all_expected_tools:
            assert expected_tool in tool_names, f"Tool '{expected_tool}' not found in loaded tools"

    @pytest.mark.asyncio
    async def test_tool_categories_loaded(self):
        """Test that tools from each category are loaded."""
        tools = await mcp.get_tools()
        tool_names = list(tools)

        # Check each category has tools
        filesystem_present = any("files" in name or "imports" in name or "documents" in name for name in tool_names)
        workflow_present = any("workflow" in name for name in tool_names)
        build_present = any("typescript" in name or "lint" in name or "test" in name for name in tool_names)
        # Check for TypeScript analysis tools
        analysis_present = any(
            "references" in name or "function_details" in name or "call_graph" in name for name in tool_names
        )
        standards_present = any(
            "check_updates" in name
            or "register" in name
            or "delete" in name
            or "hints_for_file" in name
            or "session" in name
            or "add_hint" in name
            or "add_rule" in name
            or "list_rules" in name
            for name in tool_names
        )

        assert filesystem_present, "No filesystem tools found"
        assert workflow_present, "No workflow state management tools found"
        assert build_present, "No build tools found"
        assert analysis_present, "No analysis tools found"
        assert standards_present, "No standards tools found"

    @pytest.mark.asyncio
    async def test_individual_tool_callable(self):
        """Test that individual tools can be retrieved and have proper structure."""
        # Test a tool from each implemented category
        test_tools = [
            "list_files",  # filesystem
            "workflow_state_read",  # workflow state
            "workflow_start",  # workflow execution
            "check_typescript",  # build
            "find_references",  # analysis - TypeScript tools
            "check_updates",  # standards
            "get_session_stats",  # standards v2
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
