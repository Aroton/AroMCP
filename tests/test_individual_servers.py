"""Tests for individual MCP servers."""

import subprocess
import sys
from pathlib import Path

import pytest


class TestIndividualServers:
    """Test that each server can run independently."""

    @pytest.fixture
    def server_configs(self):
        """Get server configurations from pyproject.toml."""
        import tomllib

        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        return config["tool"]["aromcp"]["servers"]

    def test_filesystem_server_imports(self):
        """Test that filesystem server can be imported."""
        from aromcp.filesystem_server.server import mcp

        assert mcp.name == "AroMCP FileSystem Server"
        assert hasattr(mcp, "run")

    def test_build_server_imports(self):
        """Test that build server can be imported."""
        from aromcp.build_server.server import mcp

        assert mcp.name == "AroMCP Build Server"
        assert hasattr(mcp, "run")

    def test_analysis_server_imports(self):
        """Test that analysis server can be imported."""
        from aromcp.analysis_server.server import mcp

        assert mcp.name == "AroMCP Analysis Server"
        assert hasattr(mcp, "run")

    def test_standards_server_imports(self):
        """Test that standards server can be imported."""
        from aromcp.standards_server.server import mcp

        assert mcp.name == "AroMCP Standards Server"
        assert hasattr(mcp, "run")

    def test_workflow_server_imports(self):
        """Test that workflow server can be imported."""
        from aromcp.workflow_server.server import mcp

        assert mcp.name == "AroMCP Workflow Server"
        assert hasattr(mcp, "run")

    def test_server_tools_registered(self):
        """Test that each server has its tools registered."""
        # Import servers and check that they have the tool decorator
        servers = [
            ("filesystem", "aromcp.filesystem_server.server"),
            ("build", "aromcp.build_server.server"),
            ("analysis", "aromcp.analysis_server.server"),
            ("standards", "aromcp.standards_server.server"),
            ("workflow", "aromcp.workflow_server.server"),
        ]

        for server_name, module_path in servers:
            # Dynamically import the server module
            module = __import__(module_path, fromlist=["mcp"])
            mcp = module.mcp

            # Check that the server has the tool decorator method
            assert hasattr(mcp, "tool"), f"{server_name} server missing tool decorator"
            assert callable(mcp.tool), f"{server_name} server tool decorator not callable"

    def test_entry_points_exist(self):
        """Test that all entry point files exist."""
        entry_points = [
            "servers/filesystem/main.py",
            "servers/build/main.py",
            "servers/analysis/main.py",
            "servers/standards/main.py",
            "servers/workflow/main.py",
        ]

        for entry_point in entry_points:
            path = Path(entry_point)
            assert path.exists(), f"Entry point {entry_point} does not exist"

    def test_server_configs_exist(self):
        """Test that all server configuration files exist."""
        config_files = [
            ".aromcp/servers/filesystem.yaml",
            ".aromcp/servers/build.yaml",
            ".aromcp/servers/analysis.yaml",
            ".aromcp/servers/standards.yaml",
            ".aromcp/servers/workflow.yaml",
        ]

        for config_file in config_files:
            path = Path(config_file)
            assert path.exists(), f"Config file {config_file} does not exist"

    @pytest.mark.parametrize(
        "server_name,entry_point",
        [
            ("filesystem", "servers/filesystem/main.py"),
            ("build", "servers/build/main.py"),
            ("analysis", "servers/analysis/main.py"),
            ("standards", "servers/standards/main.py"),
            ("workflow", "servers/workflow/main.py"),
        ],
    )
    def test_server_entry_point_syntax(self, server_name, entry_point):
        """Test that server entry points have valid Python syntax."""
        result = subprocess.run([sys.executable, "-m", "py_compile", entry_point], capture_output=True, text=True)
        assert result.returncode == 0, f"{entry_point} has syntax errors: {result.stderr}"

    def test_server_independence(self):
        """Test that servers don't have circular dependencies."""
        # Check that each server module can be imported independently
        server_modules = [
            "aromcp.filesystem_server.server",
            "aromcp.build_server.server",
            "aromcp.analysis_server.server",
            "aromcp.standards_server.server",
            "aromcp.workflow_server.server",
        ]

        for module_path in server_modules:
            # Clear any previously imported modules
            for key in list(sys.modules.keys()):
                if key.startswith("aromcp") and key != module_path:
                    del sys.modules[key]

            # Try to import the module
            try:
                __import__(module_path, fromlist=["mcp"])
            except ImportError as e:
                pytest.fail(f"Failed to import {module_path} independently: {e}")

    def test_server_versions(self):
        """Test that each server has a version defined."""
        servers = [
            ("filesystem", "aromcp.filesystem_server.server"),
            ("build", "aromcp.build_server.server"),
            ("analysis", "aromcp.analysis_server.server"),
            ("standards", "aromcp.standards_server.server"),
            ("workflow", "aromcp.workflow_server.server"),
        ]

        for server_name, module_path in servers:
            module = __import__(module_path, fromlist=["__version__"])
            assert hasattr(module, "__version__"), f"{server_name} server missing __version__"
            assert module.__version__ == "0.1.0", f"{server_name} server has wrong version"
