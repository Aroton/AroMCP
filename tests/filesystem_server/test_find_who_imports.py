"""Tests for find_who_imports implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import find_who_imports_impl


class TestFindWhoImports:
    """Test find_who_imports implementation."""

    def test_basic_python_import(self):
        """Test finding Python imports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "utils.py"
            target_file.write_text("def helper_func(): pass")

            # Create importing file
            main_file = Path(temp_dir) / "main.py"
            main_file.write_text("from utils import helper_func")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("utils.py")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 1
            assert result.dependents[0]["file"] == "main.py"
            assert len(result.dependents[0]["imports"]) > 0
            assert result.safe_to_delete is False
            assert result.impact_analysis["risk_level"] == "low"

    def test_javascript_import(self):
        """Test finding JavaScript imports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "utils.js"
            target_file.write_text("export function helper() {}")

            # Create importing file
            main_file = Path(temp_dir) / "main.js"
            main_file.write_text("import { helper } from './utils'")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("utils.js")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 1
            assert result.dependents[0]["file"] == "main.js"
            assert result.safe_to_delete is False

    def test_no_imports_found(self):
        """Test when no files import the target."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file with no importers
            target_file = Path(temp_dir) / "unused.py"
            target_file.write_text("def unused_func(): pass")

            # Create unrelated file
            other_file = Path(temp_dir) / "other.py"
            other_file.write_text("def other_func(): pass")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("unused.py")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 0
            assert result.safe_to_delete is True
            assert result.impact_analysis["risk_level"] == "low"

    def test_multiple_importers(self):
        """Test file with multiple importers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "common.py"
            target_file.write_text("def shared_func(): pass")

            # Create multiple importing files
            for i in range(5):
                import_file = Path(temp_dir) / f"module{i}.py"
                import_file.write_text("from common import shared_func")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("common.py")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 5
            assert result.safe_to_delete is False
            assert result.impact_analysis["risk_level"] == "medium"

    def test_high_risk_many_importers(self):
        """Test file with many importers (high risk)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "core.py"
            target_file.write_text("def core_func(): pass")

            # Create many importing files
            for i in range(15):
                import_file = Path(temp_dir) / f"client{i}.py"
                import_file.write_text("from core import core_func")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("core.py")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 15
            assert result.safe_to_delete is False
            assert result.impact_analysis["risk_level"] == "high"

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            try:
                find_who_imports_impl("nonexistent.py")
                raise AssertionError("Should have raised an error")
            except ValueError as e:
                assert "File not found" in str(e)

    def test_typescript_import(self):
        """Test finding TypeScript imports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "types.ts"
            target_file.write_text("export interface User { name: string }")

            # Create importing file
            main_file = Path(temp_dir) / "main.ts"
            main_file.write_text("import { User } from './types'")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = find_who_imports_impl("types.ts")

            assert hasattr(result, "dependents")
            assert len(result.dependents) == 1
            assert result.dependents[0]["file"] == "main.ts"
