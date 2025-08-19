"""Test individual server tool registration and validation."""

import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aromcp.analysis_server.tools import register_analysis_tools
from aromcp.build_server.tools import register_build_tools
from aromcp.filesystem_server.tools import register_filesystem_tools
from aromcp.standards_server.tools import register_standards_tools
from aromcp.workflow_server.tools import register_workflow_tools


class TestServerRegistration:
    """Test suite for individual server tool registration."""

    @pytest.mark.asyncio 
    async def test_filesystem_server_registration(self):
        """Test that filesystem server tools register correctly."""
        mcp = FastMCP(name="Test Filesystem Server")
        register_filesystem_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
        expected_tools = ["list_files", "read_files", "write_files"]
        
        assert len(tool_names) == 3, f"Expected 3 filesystem tools, got {len(tool_names)}"
        for tool in expected_tools:
            assert tool in tool_names, f"Filesystem tool '{tool}' not registered"

    @pytest.mark.asyncio
    async def test_build_server_registration(self):
        """Test that build server tools register correctly."""
        mcp = FastMCP(name="Test Build Server")
        register_build_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
        expected_tools = ["check_typescript", "lint_project", "run_test_suite"]
        
        assert len(tool_names) == 3, f"Expected 3 build tools, got {len(tool_names)}"
        for tool in expected_tools:
            assert tool in tool_names, f"Build tool '{tool}' not registered"

    @pytest.mark.asyncio
    async def test_analysis_server_registration(self):
        """Test that analysis server tools register correctly."""
        mcp = FastMCP(name="Test Analysis Server")
        register_analysis_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
        expected_tools = ["find_references", "get_function_details", "analyze_call_graph", "find_unused_code"]
        
        assert len(tool_names) == 4, f"Expected 4 analysis tools, got {len(tool_names)}"
        for tool in expected_tools:
            assert tool in tool_names, f"Analysis tool '{tool}' not registered"

    @pytest.mark.asyncio
    async def test_standards_server_registration(self):
        """Test that standards server tools register correctly."""
        mcp = FastMCP(name="Test Standards Server")
        register_standards_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
        expected_tools = [
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
        
        assert len(tool_names) == 10, f"Expected 10 standards tools, got {len(tool_names)}"
        for tool in expected_tools:
            assert tool in tool_names, f"Standards tool '{tool}' not registered"

    @pytest.mark.asyncio
    async def test_workflow_server_registration(self):
        """Test that workflow server tools register correctly."""
        mcp = FastMCP(name="Test Workflow Server")
        register_workflow_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
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
        
        expected_tools = workflow_state_tools + workflow_execution_tools
        
        assert len(tool_names) == 14, f"Expected 14 workflow tools, got {len(tool_names)}" 
        for tool in expected_tools:
            assert tool in tool_names, f"Workflow tool '{tool}' not registered"

    @pytest.mark.asyncio
    async def test_all_servers_combined_registration(self):
        """Test that all servers can be registered together without conflicts."""
        mcp = FastMCP(name="Test All Servers Combined")
        
        # Register all servers
        register_filesystem_tools(mcp)
        register_build_tools(mcp)
        register_analysis_tools(mcp)
        register_standards_tools(mcp)
        register_workflow_tools(mcp)
        
        tools = await mcp.get_tools()
        tool_names = list(tools)
        
        # Expected total: 3 + 3 + 4 + 10 + 14 = 34 tools
        expected_total = 34
        
        assert len(tool_names) == expected_total, f"Expected {expected_total} total tools, got {len(tool_names)}"
        
        # Verify no duplicate tool names
        assert len(tool_names) == len(set(tool_names)), "Duplicate tool names found"

    @pytest.mark.asyncio
    async def test_tool_count_matches_inventory(self):
        """Test that actual tool counts match the documented inventory."""
        # This test ensures TOOL_INVENTORY.md stays accurate
        
        # Test individual server counts
        filesystem_mcp = FastMCP(name="Test FS")
        register_filesystem_tools(filesystem_mcp)
        fs_tools = await filesystem_mcp.get_tools()
        assert len(fs_tools) == 3, "Filesystem server should have 3 tools"
        
        build_mcp = FastMCP(name="Test Build")  
        register_build_tools(build_mcp)
        build_tools = await build_mcp.get_tools()
        assert len(build_tools) == 3, "Build server should have 3 tools"
        
        analysis_mcp = FastMCP(name="Test Analysis")
        register_analysis_tools(analysis_mcp)
        analysis_tools = await analysis_mcp.get_tools() 
        assert len(analysis_tools) == 4, "Analysis server should have 4 tools"
        
        standards_mcp = FastMCP(name="Test Standards")
        register_standards_tools(standards_mcp)
        standards_tools = await standards_mcp.get_tools()
        assert len(standards_tools) == 10, "Standards server should have 10 tools"
        
        workflow_mcp = FastMCP(name="Test Workflow")
        register_workflow_tools(workflow_mcp)
        workflow_tools = await workflow_mcp.get_tools()
        assert len(workflow_tools) == 14, "Workflow server should have 14 tools"
        
        # Total should be 34 tools (3+3+4+10+14)
        total_expected = 34
        actual_total = len(fs_tools) + len(build_tools) + len(analysis_tools) + len(standards_tools) + len(workflow_tools)
        assert actual_total == total_expected, f"Total tools should be {total_expected}, got {actual_total}"