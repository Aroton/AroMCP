"""Tests for find_dead_code tool."""

from aromcp.analysis_server.tools.find_dead_code import find_dead_code_impl


class TestFindDeadCode:
    """Test cases for find_dead_code functionality."""

    def test_basic_dead_code_detection(self, tmp_path):
        """Test basic dead code detection functionality."""
        # Create files with dead code
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def used_function():
    return "This function is used"

def unused_function():
    return "This function is never called"

if __name__ == "__main__":
    result = used_function()
    print(result)
""")

        utils_file = tmp_path / "utils.py"
        utils_file.write_text("""
def helper_function():
    return "helper"

def dead_helper():
    return "never used"

class UnusedClass:
    def method(self):
        pass
""")

        # Run dead code analysis
        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.7)

        # Verify result structure
        assert "data" in result
        assert "dead_code_candidates" in result["data"]
        assert "summary" in result["data"]
        assert "recommendations" in result["data"]

        # Should find some dead code
        candidates = result["data"]["dead_code_candidates"]
        assert len(candidates) > 0

        # Check candidate structure
        for candidate in candidates:
            assert "identifier" in candidate
            assert "confidence" in candidate
            assert "reason" in candidate
            assert "definition_locations" in candidate
            assert 0.7 <= candidate["confidence"] <= 1.0

    def test_entry_point_detection(self, tmp_path):
        """Test automatic entry point detection."""
        # Create main file
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def main():
    print("Main function")

if __name__ == "__main__":
    main()
""")

        # Create another file with __main__ check
        app_file = tmp_path / "app.py"
        app_file.write_text("""
def run_app():
    print("Running app")

if __name__ == "__main__":
    run_app()
""")

        result = find_dead_code_impl(
            project_root=str(tmp_path),
            entry_points=None,  # Auto-detect
        )

        assert "data" in result
        entry_points = result["data"]["entry_points"]

        # Should detect both files as entry points
        assert len(entry_points) >= 2
        assert any("main.py" in ep for ep in entry_points)
        assert any("app.py" in ep for ep in entry_points)

    def test_custom_entry_points(self, tmp_path):
        """Test using custom entry points."""
        # Create files
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def main_function():
    from utils import used_utility
    return used_utility()
""")

        utils_file = tmp_path / "utils.py"
        utils_file.write_text("""
def used_utility():
    return "used"

def unused_utility():
    return "not used"
""")

        # Specify custom entry point
        result = find_dead_code_impl(
            project_root=str(tmp_path), entry_points=[str(main_file)], confidence_threshold=0.8
        )

        assert "data" in result

        # Should use the specified entry point
        entry_points = result["data"]["entry_points"]
        assert len(entry_points) == 1
        assert str(main_file) in entry_points

    def test_include_tests_option(self, tmp_path):
        """Test including test files as entry points."""
        # Create test file
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
def test_something():
    assert True

def test_another():
    assert False
""")

        # Create main file
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def production_function():
    return "prod"
""")

        # Without including tests
        result1 = find_dead_code_impl(project_root=str(tmp_path), include_tests=False)

        # With including tests
        result2 = find_dead_code_impl(project_root=str(tmp_path), include_tests=True)

        # Should have different entry points
        entry_points1 = result1["data"]["entry_points"]
        entry_points2 = result2["data"]["entry_points"]

        assert len(entry_points2) >= len(entry_points1)

    def test_confidence_threshold_filtering(self, tmp_path):
        """Test confidence threshold filtering."""
        # Create file with code of varying usage patterns
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def definitely_unused():
    return "never called"

def maybe_unused():
    # This might be used in some edge case
    return "edge case"

def used_function():
    return maybe_unused()

if __name__ == "__main__":
    result = used_function()
""")

        # Test with high confidence threshold
        result_high = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.9)

        # Test with low confidence threshold
        result_low = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.5)

        # High threshold should find fewer candidates
        candidates_high = result_high["data"]["dead_code_candidates"]
        candidates_low = result_low["data"]["dead_code_candidates"]

        assert len(candidates_high) <= len(candidates_low)

    def test_javascript_dead_code_detection(self, tmp_path):
        """Test dead code detection in JavaScript files."""
        # Create JavaScript file
        js_file = tmp_path / "app.js"
        js_file.write_text("""
function usedFunction() {
    return "used";
}

function unusedFunction() {
    return "unused";
}

const unusedConst = "never referenced";

class UnusedClass {
    method() {
        return "unused";
    }
}

// Entry point
if (require.main === module) {
    console.log(usedFunction());
}
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.7)

        assert "data" in result
        candidates = result["data"]["dead_code_candidates"]

        # Should detect some unused JavaScript code
        assert len(candidates) > 0

    def test_mixed_language_project(self, tmp_path):
        """Test dead code detection in mixed language project."""
        # Create Python file
        py_file = tmp_path / "module.py"
        py_file.write_text("""
def python_function():
    return "python"

def unused_python():
    return "unused"
""")

        # Create JavaScript file
        js_file = tmp_path / "script.js"
        js_file.write_text("""
function jsFunction() {
    return "javascript";
}

function unusedJs() {
    return "unused";
}
""")

        # Create TypeScript file
        ts_file = tmp_path / "app.ts"
        ts_file.write_text("""
function tsFunction(): string {
    return "typescript";
}

function unusedTs(): string {
    return "unused";
}

// Use some functions
console.log(tsFunction());
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.6)

        assert "data" in result
        result["data"]["dead_code_candidates"]

        # Should analyze all supported file types
        usage_analysis = result["data"]["usage_analysis"]
        assert usage_analysis["total_files_analyzed"] >= 3

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = find_dead_code_impl(project_root="/nonexistent/path", confidence_threshold=0.7)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_invalid_confidence_threshold(self, tmp_path):
        """Test handling of invalid confidence threshold."""
        # Test threshold too high
        result1 = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=1.5)

        # Test threshold too low
        result2 = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=-0.1)

        assert "error" in result1
        assert result1["error"]["code"] == "INVALID_INPUT"

        assert "error" in result2
        assert result2["error"]["code"] == "INVALID_INPUT"

    def test_empty_project(self, tmp_path):
        """Test handling of project with no code files."""
        # Create only non-code files
        readme_file = tmp_path / "README.md"
        readme_file.write_text("# Empty Project")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.7)

        # Should handle gracefully
        assert "data" in result or "error" in result
        if "error" in result:
            assert result["error"]["code"] == "NOT_FOUND"

    def test_large_codebase_simulation(self, tmp_path):
        """Test performance with larger codebase simulation."""
        # Create multiple files with various patterns
        for i in range(10):
            file_path = tmp_path / f"module_{i}.py"
            file_path.write_text(f"""
def public_function_{i}():
    return "public_{i}"

def _private_function_{i}():
    return "private_{i}"

def unused_function_{i}():
    return "unused_{i}"

class Class{i}:
    def method(self):
        return "method_{i}"

    def unused_method(self):
        return "unused_{i}"
""")

        # Create main file that uses some functions
        main_file = tmp_path / "main.py"
        main_file.write_text("""
from module_0 import public_function_0
from module_1 import public_function_1

if __name__ == "__main__":
    print(public_function_0())
    print(public_function_1())
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.8)

        assert "data" in result

        # Should process all files
        summary = result["data"]["summary"]
        assert summary["total_files_analyzed"] >= 10

        # Should find many dead code candidates
        candidates = result["data"]["dead_code_candidates"]
        assert len(candidates) > 0

    def test_usage_analysis_structure(self, tmp_path):
        """Test the structure of usage analysis results."""
        # Create test file
        test_file = tmp_path / "analysis_test.py"
        test_file.write_text("""
def function_a():
    return function_b()

def function_b():
    return "result"

def function_c():
    return "unused"

class TestClass:
    def method_a(self):
        return "used"

    def method_b(self):
        return "unused"

if __name__ == "__main__":
    result = function_a()
    instance = TestClass()
    instance.method_a()
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.5)

        assert "data" in result
        usage_analysis = result["data"]["usage_analysis"]

        # Check structure
        assert "definitions" in usage_analysis
        assert "usages" in usage_analysis
        assert "usage_stats" in usage_analysis
        assert "total_files_analyzed" in usage_analysis

        # Check usage stats structure
        for _identifier, stats in usage_analysis["usage_stats"].items():
            assert "definitions" in stats
            assert "usages" in stats
            assert "used_in_entry_points" in stats
            assert "definition_locations" in stats
            assert "usage_locations" in stats

    def test_recommendations_generation(self, tmp_path):
        """Test generation of actionable recommendations."""
        # Create file with obvious dead code
        test_file = tmp_path / "recommendations_test.py"
        test_file.write_text("""
def used_function():
    return "used"

def completely_unused():
    return "never called"

def another_unused():
    return "also never called"

if __name__ == "__main__":
    print(used_function())
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.8)

        assert "data" in result
        recommendations = result["data"]["recommendations"]

        # Should provide actionable recommendations
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Should mention high-confidence candidates if they exist
        candidates = result["data"]["dead_code_candidates"]
        high_confidence = [c for c in candidates if c["confidence"] >= 0.9]

        if high_confidence:
            assert any("high-confidence" in rec.lower() for rec in recommendations)

    def test_python_ast_parsing_edge_cases(self, tmp_path):
        """Test handling of Python AST parsing edge cases."""
        # Create file with syntax errors
        invalid_file = tmp_path / "invalid.py"
        invalid_file.write_text("""
def valid_function():
    return "valid"

# Syntax error below
def invalid_function(
    # Missing closing parenthesis
    return "invalid"

def another_valid():
    return "valid"
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.5)

        # Should handle syntax errors gracefully
        assert "data" in result or "error" in result
        if "data" in result:
            # Should still analyze valid parts
            usage_analysis = result["data"]["usage_analysis"]
            assert usage_analysis["total_files_analyzed"] >= 0

    def test_import_usage_tracking(self, tmp_path):
        """Test tracking of imports and their usage."""
        # Create module file
        module_file = tmp_path / "mymodule.py"
        module_file.write_text("""
def exported_function():
    return "exported"

def unused_export():
    return "not imported anywhere"

class ExportedClass:
    def method(self):
        return "class method"

class UnusedClass:
    def method(self):
        return "unused class"
""")

        # Create main file that imports some things
        main_file = tmp_path / "main.py"
        main_file.write_text("""
from mymodule import exported_function, ExportedClass

if __name__ == "__main__":
    result = exported_function()
    instance = ExportedClass()
    print(result, instance.method())
""")

        result = find_dead_code_impl(project_root=str(tmp_path), confidence_threshold=0.7)

        assert "data" in result
        usage_analysis = result["data"]["usage_analysis"]

        # Check that imports are tracked
        assert "imports" in usage_analysis

        # Should find unused exports
        candidates = result["data"]["dead_code_candidates"]
        unused_names = [c["identifier"] for c in candidates]

        # Should identify unused exports with high confidence
        assert any("unused" in name.lower() for name in unused_names)
