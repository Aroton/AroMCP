"""Tests for find_imports_for_files implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import find_imports_for_files_impl


class TestFindImportsForFiles:
    """Test find_imports_for_files implementation."""

    def test_python_imports(self):
        """Test finding Python imports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target module
            target_file = Path(temp_dir) / "utils.py"
            target_file.write_text("def helper(): pass")

            # Create importing file
            importer_file = Path(temp_dir) / "main.py"
            importer_file.write_text("from utils import helper\nimport utils")

            result = find_imports_for_files_impl(
                file_paths=["utils.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]
            assert "utils.py" in imports
            assert len(imports["utils.py"]["importers"]) == 1
            assert imports["utils.py"]["importers"][0]["file"] == "main.py"

            # Verify paginated items structure
            items = result["data"]["items"]
            assert len(items) == 1
            assert items[0]["target_file"] == "utils.py"
            assert items[0]["file"] == "main.py"

    def test_no_imports_found(self):
        """Test when no imports are found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "isolated.py"
            target_file.write_text("def lonely(): pass")

            result = find_imports_for_files_impl(
                file_paths=["isolated.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]
            assert "isolated.py" in imports
            assert len(imports["isolated.py"]["importers"]) == 0

            # Verify paginated items structure (should be empty)
            items = result["data"]["items"]
            assert len(items) == 0

    def test_javascript_imports(self):
        """Test finding JavaScript/TypeScript imports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target module
            target_file = Path(temp_dir) / "utils.js"
            target_file.write_text("export function helper() { return true; }")

            # Create importing file with different import styles
            importer_file = Path(temp_dir) / "main.js"
            importer_file.write_text("""
import { helper } from './utils.js';
const utils = require('./utils');
import('./utils.js').then(module => {});
""")

            result = find_imports_for_files_impl(
                file_paths=["utils.js"],
                project_root=temp_dir,
                search_patterns=["*.js"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]
            assert "utils.js" in imports
            assert len(imports["utils.js"]["importers"]) == 1

            # Should find multiple import types
            import_types = imports["utils.js"]["importers"][0]["import_types"]
            assert len(import_types) >= 2  # Should find ES6 and require imports

            # Verify paginated items structure
            items = result["data"]["items"]
            assert len(items) == 1
            assert items[0]["target_file"] == "utils.js"
            assert items[0]["file"] == "main.js"

    def test_custom_search_patterns(self):
        """Test custom search patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target file
            target_file = Path(temp_dir) / "config.py"
            target_file.write_text("CONFIG = {'key': 'value'}")

            # Create files with different extensions
            files = {
                "main.py": "from config import CONFIG",
                "test.py": "import config",
                "script.js": "// No imports",
                "readme.md": "See config.py for configuration"
            }

            for path, content in files.items():
                (Path(temp_dir) / path).write_text(content)

            # Search only Python files
            result = find_imports_for_files_impl(
                file_paths=["config.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]
            assert len(imports["config.py"]["importers"]) == 2  # Only Python files

            # Search all files
            result = find_imports_for_files_impl(
                file_paths=["config.py"],
                project_root=temp_dir,
                search_patterns=["*.*"]
            )

            assert "data" in result
            # Get imports from the data structure for the second test
            imports = result["data"]["imports_by_file"]
            # Should find more references including text references
            assert len(imports["config.py"]["importers"]) >= 2

    def test_multiple_target_files(self):
        """Test analyzing multiple target files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple target files
            files = {
                "utils.py": "def helper(): pass",
                "config.py": "CONFIG = {}",
                "models.py": "class Model: pass"
            }

            for path, content in files.items():
                (Path(temp_dir) / path).write_text(content)

            # Create importer
            main_file = Path(temp_dir) / "main.py"
            main_file.write_text("""
from utils import helper
import config
from models import Model
""")

            result = find_imports_for_files_impl(
                file_paths=list(files.keys()),
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]

            # All target files should be found
            for target_file in files.keys():
                assert target_file in imports
                assert len(imports[target_file]["importers"]) == 1
                assert imports[target_file]["importers"][0]["file"] == "main.py"

            # Verify paginated items structure
            items = result["data"]["items"]
            assert len(items) == 3  # Three target files, each with one importer
            target_files_in_items = {item["target_file"] for item in items}
            assert target_files_in_items == set(files.keys())

    def test_nonexistent_target_files(self):
        """Test behavior with non-existent target files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = find_imports_for_files_impl(
                file_paths=["nonexistent.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            # Check paginated structure
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]

            # Get imports from the data structure
            imports = result["data"]["imports_by_file"]
            assert "nonexistent.py" in imports
            assert len(imports["nonexistent.py"]["importers"]) == 0
            assert len(imports["nonexistent.py"]["module_names"]) == 0

            # Verify paginated items structure (should be empty)
            items = result["data"]["items"]
            assert len(items) == 0

    def test_pagination_parameters(self):
        """Test pagination parameters work correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple target files
            for i in range(5):
                target_file = Path(temp_dir) / f"module_{i}.py"
                target_file.write_text(f"def func_{i}(): pass")

            # Create an importer that imports all modules
            importer_file = Path(temp_dir) / "main.py"
            imports = [f"import module_{i}" for i in range(5)]
            importer_file.write_text("\n".join(imports))

            # Test with default pagination
            result = find_imports_for_files_impl(
                file_paths=[f"module_{i}.py" for i in range(5)],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result
            assert "items" in result["data"]
            assert "imports_by_file" in result["data"]
            assert "pagination" in result["data"]

            # Should have 5 importers (one per target file)
            items = result["data"]["items"]
            assert len(items) == 5

            # Verify pagination info
            pagination = result["data"]["pagination"]
            assert pagination["page"] == 1  # Current page is called "page", not "current_page"
            assert pagination["total_items"] == 5

    def test_metadata_structure(self):
        """Test metadata structure in paginated response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create target module
            target_file = Path(temp_dir) / "utils.py"
            target_file.write_text("def helper(): pass")

            # Create importing file
            importer_file = Path(temp_dir) / "main.py"
            importer_file.write_text("from utils import helper")

            result = find_imports_for_files_impl(
                file_paths=["utils.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )

            assert "data" in result

            # Check summary information
            assert "summary" in result["data"]
            summary = result["data"]["summary"]
            assert summary["target_files"] == 1
            assert summary["total_importers"] == 1
            assert summary["total_imports"] >= 1
            assert "duration_ms" in summary

            # Check imports_by_file structure (backward compatibility)
            assert "imports_by_file" in result["data"]
            imports_by_file = result["data"]["imports_by_file"]
            assert "utils.py" in imports_by_file
            assert len(imports_by_file["utils.py"]["importers"]) == 1

    def test_expand_patterns_parameter(self):
        """Test expand_patterns parameter works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple target files matching a pattern
            for i in range(3):
                target_file = Path(temp_dir) / f"util_{i}.py"
                target_file.write_text(f"def func_{i}(): pass")

            # Create importing files
            for i in range(3):
                importer_file = Path(temp_dir) / f"main_{i}.py"
                importer_file.write_text(f"import util_{i}")

            # Test with pattern expansion enabled (default)
            result = find_imports_for_files_impl(
                file_paths=["util_*.py"],
                project_root=temp_dir,
                search_patterns=["*.py"],
                expand_patterns=True
            )

            assert "data" in result
            imports_by_file = result["data"]["imports_by_file"]
            # Should find all 3 files matching the pattern
            assert len(imports_by_file) == 3
            for i in range(3):
                assert f"util_{i}.py" in imports_by_file

            # Test with pattern expansion disabled
            result = find_imports_for_files_impl(
                file_paths=["util_*.py"],
                project_root=temp_dir,
                search_patterns=["*.py"],
                expand_patterns=False
            )

            assert "data" in result
            imports_by_file = result["data"]["imports_by_file"]
            # Should treat the pattern as a literal filename (won't find anything)
            assert "util_*.py" in imports_by_file
            assert len(imports_by_file["util_*.py"]["importers"]) == 0
