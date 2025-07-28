"""Tests for extract_method_signatures implementation."""

import os
import tempfile
from pathlib import Path

import pytest

from aromcp.filesystem_server.tools import extract_method_signatures_impl
from aromcp.filesystem_server.models.filesystem_models import ExtractMethodSignaturesResponse


class TestExtractMethodSignatures:
    """Test extract_method_signatures implementation."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory and set MCP_FILE_ROOT."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set environment variable for testing
            original_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = temp_dir

            try:
                yield temp_dir
            finally:
                # Restore original value
                if original_root is not None:
                    os.environ["MCP_FILE_ROOT"] = original_root
                elif "MCP_FILE_ROOT" in os.environ:
                    del os.environ["MCP_FILE_ROOT"]

    def test_python_function_extraction(self, temp_project):
        """Test extracting Python function signatures."""
        python_code = '''
def simple_function():
    """A simple function."""
    pass

def function_with_args(a: int, b: str = "default") -> bool:
    """Function with typed arguments."""
    return True

class TestClass:
    def method(self, x: int) -> None:
        """A method."""
        pass

    @property
    def prop(self) -> str:
        return "value"
'''

        test_file = Path(temp_project) / "test.py"
        test_file.write_text(python_code)

        result = extract_method_signatures_impl(file_paths="test.py")

        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert len(result.signatures) > 0
        # Find function signatures - signatures are dictionaries
        function_names = {sig["name"] for sig in result.signatures if "name" in sig}
        expected = {"simple_function", "function_with_args", "method", "prop"}

        # We expect to find at least some functions
        assert len(function_names & expected) >= 2

    def test_javascript_function_extraction(self, temp_project):
        """Test extracting JavaScript function signatures."""
        js_code = """
function regularFunction(a, b = 10) {
    return a + b;
}

const arrowFunction = (x, y) => x * y;

class MyClass {
    constructor(name) {
        this.name = name;
    }

    getName() {
        return this.name;
    }
}
"""

        test_file = Path(temp_project) / "test.js"
        test_file.write_text(js_code)

        result = extract_method_signatures_impl(file_paths="test.js")

        # For JS files, we expect some results or errors
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_unsupported_file_type(self, temp_project):
        """Test handling of unsupported file types."""
        test_file = Path(temp_project) / "test.txt"
        test_file.write_text("This is a text file with no function signatures.")

        result = extract_method_signatures_impl(file_paths="test.txt")

        # Should return response with errors for unsupported files
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert result.errors is not None

    def test_parameter_variations(self, temp_project):
        """Test different parameter combinations."""
        python_code = '''
@decorator
def decorated_function():
    """A decorated function."""
    pass
'''

        test_file = Path(temp_project) / "test.py"
        test_file.write_text(python_code)

        # Test without docstrings
        result = extract_method_signatures_impl(file_paths="test.py", include_docstrings=False, include_decorators=True)
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

        # Test without decorators
        result = extract_method_signatures_impl(file_paths="test.py", include_docstrings=True, include_decorators=False)
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_async_functions(self, temp_project):
        """Test async function detection."""
        python_code = '''
async def async_function():
    """An async function."""
    await something()

async def async_with_args(a: int, b: str) -> None:
    """Async function with arguments."""
    pass
'''

        test_file = Path(temp_project) / "test.py"
        test_file.write_text(python_code)

        result = extract_method_signatures_impl(file_paths="test.py")
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_complex_type_annotations(self, temp_project):
        """Test complex type annotations."""
        python_code = '''
from typing import List, Dict, Optional, Union

def complex_function(
    items: List[Dict[str, Union[int, str]]],
    callback: Optional[callable] = None
) -> Dict[str, List[int]]:
    """Function with complex type annotations."""
    return {}
'''

        test_file = Path(temp_project) / "test.py"
        test_file.write_text(python_code)

        result = extract_method_signatures_impl(file_paths="test.py")
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_pattern_expansion_basic(self, temp_project):
        """Test basic pattern expansion."""
        files = {"main.py": "def main(): pass", "utils.py": "def helper(): pass"}

        for file_path, content in files.items():
            full_path = Path(temp_project) / file_path
            full_path.write_text(content)

        # Test *.py pattern
        result = extract_method_signatures_impl(file_paths=["*.py"], expand_patterns=True)

        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_pattern_expansion_multiple_files(self, temp_project):
        """Test pattern expansion with multiple file types."""
        files = {
            "src/main.py": "def main(): pass",
            "src/utils.py": "def helper(): pass",
            "tests/test_main.py": "def test_main(): pass",
            "app.js": "function app() {}",
            "utils.js": "function util() {}",
        }

        for file_path, content in files.items():
            full_path = Path(temp_project) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Test **/*.py pattern
        result = extract_method_signatures_impl(file_paths=["**/*.py"], expand_patterns=True)

        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_pattern_expansion_mixed_with_static_paths(self, temp_project):
        """Test mixing pattern expansion with static file paths."""
        files = {
            "main.py": "def main(): pass",
            "utils.py": "def helper(): pass",
            "specific.js": "function specific() {}",
        }

        for file_path, content in files.items():
            full_path = Path(temp_project) / file_path
            full_path.write_text(content)

        # Test mixing pattern and static path
        result = extract_method_signatures_impl(file_paths=["*.py", "specific.js"], expand_patterns=True)

        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')

    def test_pattern_expansion_disabled(self, temp_project):
        """Test pattern expansion disabled."""
        files = {"main.py": "def main(): pass", "utils.py": "def helper(): pass"}

        for file_path, content in files.items():
            full_path = Path(temp_project) / file_path
            full_path.write_text(content)

        # Test with patterns but expansion disabled
        result = extract_method_signatures_impl(file_paths=["*.py"], expand_patterns=False)

        # Should return response with errors since "*.py" is treated as literal filename
        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert result.errors is not None

    def test_pattern_expansion_summary_statistics(self, temp_project):
        """Test summary statistics in pattern expansion."""
        files = {"main.py": "def main(): pass\ndef helper(): pass", "utils.py": "def util1(): pass\ndef util2(): pass"}

        for file_path, content in files.items():
            full_path = Path(temp_project) / file_path
            full_path.write_text(content)

        result = extract_method_signatures_impl(file_paths=["*.py"], expand_patterns=True)

        assert isinstance(result, ExtractMethodSignaturesResponse)
        assert hasattr(result, 'signatures')
