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
            imports = result["data"]["imports"]
            assert "utils.py" in imports
            assert len(imports["utils.py"]["importers"]) == 1
            assert imports["utils.py"]["importers"][0]["file"] == "main.py"

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
            imports = result["data"]["imports"]
            assert "isolated.py" in imports
            assert len(imports["isolated.py"]["importers"]) == 0
    
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
            imports = result["data"]["imports"]
            assert "utils.js" in imports
            assert len(imports["utils.js"]["importers"]) == 1
            
            # Should find multiple import types
            import_types = imports["utils.js"]["importers"][0]["import_types"]
            assert len(import_types) >= 2  # Should find ES6 and require imports
    
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
            imports = result["data"]["imports"]
            assert len(imports["config.py"]["importers"]) == 2  # Only Python files
            
            # Search all files
            result = find_imports_for_files_impl(
                file_paths=["config.py"],
                project_root=temp_dir,
                search_patterns=["*.*"]
            )
            
            assert "data" in result
            imports = result["data"]["imports"]
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
            imports = result["data"]["imports"]
            
            # All target files should be found
            for target_file in files.keys():
                assert target_file in imports
                assert len(imports[target_file]["importers"]) == 1
                assert imports[target_file]["importers"][0]["file"] == "main.py"
    
    def test_nonexistent_target_files(self):
        """Test behavior with non-existent target files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = find_imports_for_files_impl(
                file_paths=["nonexistent.py"],
                project_root=temp_dir,
                search_patterns=["*.py"]
            )
            
            assert "data" in result
            imports = result["data"]["imports"]
            assert "nonexistent.py" in imports
            assert len(imports["nonexistent.py"]["importers"]) == 0
            assert len(imports["nonexistent.py"]["module_names"]) == 0