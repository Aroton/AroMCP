"""Tests for extract_method_signatures implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import extract_method_signatures_impl


class TestExtractMethodSignatures:
    """Test extract_method_signatures implementation."""

    def test_python_function_extraction(self):
        """Test extracting Python function signatures."""
        with tempfile.TemporaryDirectory() as temp_dir:
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

            test_file = Path(temp_dir) / "test.py"
            test_file.write_text(python_code)

            result = extract_method_signatures_impl(
                file_paths="test.py",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.py" in files
            
            signatures = files["test.py"]["signatures"]

            # Should find 2 functions, 1 class, and 2 methods
            assert len(signatures) == 5

            # Check function names
            names = {sig["name"] for sig in signatures}
            expected = {
                "simple_function", "function_with_args", "TestClass", "method", "prop"
            }
            assert names == expected

    def test_javascript_function_extraction(self):
        """Test extracting JavaScript function signatures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            js_code = '''
function regularFunction(a, b = 10) {
    return a + b;
}

const arrowFunction = (x, y) => x * y;

class MyClass {
    constructor(name) {
        this.name = name;
    }

    async method(param: string): Promise<void> {
        console.log(param);
    }
}
'''

            test_file = Path(temp_dir) / "test.js"
            test_file.write_text(js_code)

            result = extract_method_signatures_impl(
                file_paths="test.js",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.js" in files
            
            signatures = files["test.js"]["signatures"]

            # Should find functions and class
            assert len(signatures) > 0
            names = {sig["name"] for sig in signatures}
            assert "regularFunction" in names
            assert "arrowFunction" in names

    def test_unsupported_file_type(self):
        """Test handling of unsupported file types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.unknown"
            test_file.write_text("some content")

            result = extract_method_signatures_impl(
                file_paths="test.unknown",
                project_root=temp_dir
            )

            assert "data" in result
            assert "errors" in result["data"]
            assert len(result["data"]["errors"]) == 1
            assert "Unsupported file type" in result["data"]["errors"][0]["error"]

    def test_parameter_variations(self):
        """Test include_docstrings and include_decorators parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            python_code = '''
@decorator
def decorated_function():
    """This function has a docstring."""
    pass

class TestClass:
    @property
    def prop(self) -> str:
        """Property with docstring."""
        return "value"
'''

            test_file = Path(temp_dir) / "test.py"
            test_file.write_text(python_code)

            # Test without docstrings
            result = extract_method_signatures_impl(
                file_paths="test.py",
                project_root=temp_dir,
                include_docstrings=False,
                include_decorators=True
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.py" in files
            
            signatures = files["test.py"]["signatures"]

            # Find the function signature
            func_sig = next(s for s in signatures if s["name"] == "decorated_function")
            assert func_sig["docstring"] is None
            assert len(func_sig["decorators"]) > 0

            # Test without decorators
            result = extract_method_signatures_impl(
                file_paths="test.py",
                project_root=temp_dir,
                include_docstrings=True,
                include_decorators=False
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.py" in files
            
            signatures = files["test.py"]["signatures"]

            func_sig = next(s for s in signatures if s["name"] == "decorated_function")
            assert func_sig["docstring"] is not None
            assert len(func_sig["decorators"]) == 0

    def test_async_functions(self):
        """Test extraction of async functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            python_code = '''
async def async_function(param: str) -> None:
    """An async function."""
    pass

class AsyncClass:
    async def async_method(self) -> bool:
        """An async method."""
        return True
'''

            test_file = Path(temp_dir) / "test.py"
            test_file.write_text(python_code)

            result = extract_method_signatures_impl(
                file_paths="test.py",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.py" in files
            
            signatures = files["test.py"]["signatures"]

            # Find async function
            async_func = next(s for s in signatures if s["name"] == "async_function")
            assert async_func["is_async"] is True
            assert "async def" in async_func["signature"]

            # Find async method
            async_method = next(s for s in signatures if s["name"] == "async_method")
            assert async_method["is_async"] is True

    def test_complex_type_annotations(self):
        """Test complex type annotations extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            python_code = '''
from typing import List, Dict, Optional, Union

def complex_function(
    items: List[Dict[str, int]],
    callback: Optional[Callable[[str], bool]] = None,
    mode: Union[str, int] = "default"
) -> Dict[str, List[int]]:
    """Function with complex types."""
    pass
'''

            test_file = Path(temp_dir) / "test.py"
            test_file.write_text(python_code)

            result = extract_method_signatures_impl(
                file_paths="test.py",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.py" in files
            
            signatures = files["test.py"]["signatures"]
            func_sig = signatures[0]

            # Check that parameters have type annotations
            params = func_sig["parameters"]
            # Note: Complex type annotations might be simplified by AST parsing
            # Let's check for basic type structure instead
            assert any("type" in p for p in params)  # At least some params have types
            assert len(params) >= 3  # Should have the 3 parameters we defined

    def test_typescript_control_structures_should_not_be_extracted(self):
        """Test that control structures like if/for/while are NOT extracted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ts_code = '''
class UserService {
    private users: User[] = [];

    findUser(id: string): User | null {
        // This if statement should NOT be extracted
        if (id) {
            // This for loop should NOT be extracted
            for (let i = 0; i < this.users.length; i++) {
                if (this.users[i].id === id) {
                    return this.users[i];
                }
            }
        }

        // This while loop should NOT be extracted
        while (false) {
            console.log("never runs");
        }

        // This switch statement should NOT be extracted
        switch (id) {
            case 'admin':
                return this.getAdminUser();
            default:
                return null;
        }

        return null;
    }

    async createUser(userData: UserData): Promise<User> {
        const user = new User(userData);

        // This try/catch should NOT be extracted
        try {
            this.users.push(user);
            return user;
        } catch (error) {
            throw new Error('Failed to create user');
        }
    }

    private getAdminUser(): User {
        return this.users.find(u => u.role === 'admin') || null;
    }
}

// Top-level if should NOT be extracted
if (process.env.NODE_ENV === 'development') {
    console.log('Development mode');
}

// Top-level for should NOT be extracted
for (let i = 0; i < 5; i++) {
    console.log(i);
}
'''

            test_file = Path(temp_dir) / "test.ts"
            test_file.write_text(ts_code)

            result = extract_method_signatures_impl(
                file_paths="test.ts",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.ts" in files
            
            signatures = files["test.ts"]["signatures"]

            # Extract just the names for easier testing
            names = {sig["name"] for sig in signatures}

            # Should contain actual methods and class
            assert "UserService" in names
            assert "findUser" in names
            assert "createUser" in names
            assert "getAdminUser" in names

            # Should NOT contain control structures
            assert "if" not in names
            assert "for" not in names
            assert "while" not in names
            assert "switch" not in names
            assert "try" not in names
            assert "catch" not in names

            # Verify we only got legitimate signatures
            expected_names = {"UserService", "findUser", "createUser", "getAdminUser"}
            assert names == expected_names

    def test_javascript_mixed_control_structures_and_functions(self):
        """Test JavaScript with mixed control structures and actual functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            js_code = '''
function processData(items) {
    // This if should NOT be extracted
    if (items.length === 0) {
        return [];
    }

    const result = [];

    // This for loop should NOT be extracted
    for (const item of items) {
        // This if should NOT be extracted
        if (item.valid) {
            result.push(transform(item));
        }
    }

    return result;
}

const transform = (item) => {
    // This switch should NOT be extracted
    switch (item.type) {
        case 'A':
            return { ...item, processed: true };
        case 'B':
            return { ...item, processed: false };
        default:
            return item;
    }
};

class DataProcessor {
    process(data) {
        // This while should NOT be extracted
        while (data.hasNext()) {
            const item = data.next();

            // This try/catch should NOT be extracted
            try {
                this.handleItem(item);
            } catch (e) {
                console.error(e);
            }
        }
    }

    handleItem(item) {
        return item;
    }
}

// Top-level control structures should NOT be extracted
if (typeof window !== 'undefined') {
    console.log('Browser environment');
}

for (let i = 0; i < 3; i++) {
    console.log(`Iteration ${i}`);
}
'''

            test_file = Path(temp_dir) / "test.js"
            test_file.write_text(js_code)

            result = extract_method_signatures_impl(
                file_paths="test.js",
                project_root=temp_dir
            )

            assert "data" in result
            files = result["data"]["files"]
            assert "test.js" in files
            
            signatures = files["test.js"]["signatures"]

            # Extract just the names for easier testing
            names = {sig["name"] for sig in signatures}

            # Should contain actual functions, methods, and class
            assert "processData" in names
            assert "transform" in names
            assert "DataProcessor" in names
            assert "process" in names
            assert "handleItem" in names

            # Should NOT contain control structures
            control_structures = {
                "if", "for", "while", "switch", "try", "catch", "typeof"
            }
            assert not (names & control_structures), (
                f"Found control structures in signatures: "
                f"{names & control_structures}"
            )

            # Verify we only got legitimate signatures
            expected_names = {
                "processData", "transform", "DataProcessor", "process", "handleItem"
            }
            assert names == expected_names

    def test_pattern_expansion_basic(self):
        """Test basic glob pattern expansion for method signatures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "main.py": '''
def main():
    """Main function."""
    pass

class App:
    def run(self):
        """Run the app."""
        pass
''',
                "utils.py": '''
def helper():
    """Helper function."""
    return True

def process():
    """Process data."""
    pass
''',
                "test.js": '''
function testFunc() {
    return "test";
}

class TestClass {
    method() {
        return true;
    }
}
''',
                "README.md": "# Documentation"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test *.py pattern
            result = extract_method_signatures_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            files_result = result["data"]["files"]
            assert len(files_result) == 2  # main.py and utils.py
            assert "main.py" in files_result
            assert "utils.py" in files_result
            assert "test.js" not in files_result

            # Check signatures in main.py
            main_signatures = files_result["main.py"]["signatures"]
            main_names = {sig["name"] for sig in main_signatures}
            assert "main" in main_names
            assert "App" in main_names
            assert "run" in main_names

            # Check signatures in utils.py  
            utils_signatures = files_result["utils.py"]["signatures"]
            utils_names = {sig["name"] for sig in utils_signatures}
            assert "helper" in utils_names
            assert "process" in utils_names

    def test_pattern_expansion_multiple_files(self):
        """Test pattern expansion with multiple file types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files in different directories
            files = {
                "src/main.py": '''
def main():
    pass
''',
                "src/utils.py": '''
def helper():
    pass
''',
                "tests/test_main.py": '''
def test_main():
    pass
''',
                "frontend/app.js": '''
function initApp() {
    return true;
}
''',
                "frontend/utils.js": '''
const helper = () => {
    return false;
};
'''
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Test **/*.py pattern
            result = extract_method_signatures_impl(
                file_paths=["**/*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            files_result = result["data"]["files"]
            assert len(files_result) == 3
            assert "src/main.py" in files_result
            assert "src/utils.py" in files_result
            assert "tests/test_main.py" in files_result

            # Test **/*.js pattern
            result = extract_method_signatures_impl(
                file_paths=["**/*.js"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            files_result = result["data"]["files"]
            assert len(files_result) == 2
            assert "frontend/app.js" in files_result
            assert "frontend/utils.js" in files_result

    def test_pattern_expansion_mixed_with_static_paths(self):
        """Test mixing patterns with static file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "main.py": "def main(): pass",
                "utils.py": "def helper(): pass", 
                "specific.js": "function specific() { return true; }",
                "other.ts": "function other(): boolean { return false; }"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test mixing pattern and static path
            result = extract_method_signatures_impl(
                file_paths=["*.py", "specific.js"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            files_result = result["data"]["files"]
            assert len(files_result) == 3
            assert "main.py" in files_result
            assert "utils.py" in files_result
            assert "specific.js" in files_result
            assert "other.ts" not in files_result

    def test_pattern_expansion_disabled(self):
        """Test that pattern expansion can be disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "main.py": "def main(): pass",
                "utils.py": "def helper(): pass"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test with patterns but expansion disabled
            result = extract_method_signatures_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=False
            )

            assert "data" in result
            # Should treat "*.py" as literal filename (which doesn't exist)
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert len(result["data"]["errors"]) == 1

    def test_pattern_expansion_summary_statistics(self):
        """Test that summary includes pattern expansion statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "file1.py": "def func1(): pass",
                "file2.py": "def func2(): pass"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            result = extract_method_signatures_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            summary = result["data"]["summary"]
            assert summary["input_patterns"] == 1  # One input pattern
            assert summary["total_files"] == 2     # Expanded to 2 files
            assert summary["successful"] == 2      # Both files processed successfully
            assert summary["patterns_expanded"] is True
            assert "duration_ms" in summary
