"""Tests for find_import_cycles tool."""

from aromcp.analysis_server.tools.find_import_cycles import find_import_cycles_impl


class TestFindImportCycles:
    """Test cases for find_import_cycles functionality."""

    def test_basic_cycle_detection(self, tmp_path):
        """Test basic import cycle detection."""
        # Create files with circular imports
        file_a = tmp_path / "module_a.py"
        file_a.write_text("""
from module_b import function_b

def function_a():
    return function_b()
""")

        file_b = tmp_path / "module_b.py"
        file_b.write_text("""
from module_a import function_a

def function_b():
    return "result from b"
""")

        # Run cycle detection
        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        # Verify result structure
        assert "data" in result
        assert "cycles" in result["data"]
        assert "summary" in result["data"]
        assert "recommendations" in result["data"]

        # Should detect the cycle
        cycles = result["data"]["cycles"]
        assert len(cycles) >= 1

        # Check cycle structure
        for cycle in cycles:
            assert "files" in cycle
            assert "length" in cycle
            assert "severity" in cycle
            assert "type" in cycle
            assert "suggestions" in cycle
            assert len(cycle["files"]) >= 2

    def test_three_way_cycle(self, tmp_path):
        """Test detection of three-way import cycle."""
        # Create A -> B -> C -> A cycle
        file_a = tmp_path / "a.py"
        file_a.write_text("""
from b import b_function

def a_function():
    return b_function()
""")

        file_b = tmp_path / "b.py"
        file_b.write_text("""
from c import c_function

def b_function():
    return c_function()
""")

        file_c = tmp_path / "c.py"
        file_c.write_text("""
from a import a_function

def c_function():
    return "end of chain"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should detect the three-way cycle
        assert len(cycles) >= 1

        # Check that we have a cycle of length 3
        cycle_lengths = [cycle["length"] for cycle in cycles]
        assert 3 in cycle_lengths

    def test_no_cycles_detected(self, tmp_path):
        """Test when no import cycles exist."""
        # Create files with proper dependency hierarchy
        file_a = tmp_path / "base.py"
        file_a.write_text("""
def base_function():
    return "base"
""")

        file_b = tmp_path / "middle.py"
        file_b.write_text("""
from base import base_function

def middle_function():
    return base_function() + " middle"
""")

        file_c = tmp_path / "top.py"
        file_c.write_text("""
from middle import middle_function

def top_function():
    return middle_function() + " top"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should not detect any cycles
        assert len(cycles) == 0

        # Should have positive recommendations
        recommendations = result["data"]["recommendations"]
        assert any("no import cycles" in rec.lower() for rec in recommendations)

    def test_javascript_cycle_detection(self, tmp_path):
        """Test cycle detection in JavaScript files."""
        # Create JavaScript files with imports
        file_a = tmp_path / "moduleA.js"
        file_a.write_text("""
import { functionB } from './moduleB.js';

export function functionA() {
    return functionB();
}
""")

        file_b = tmp_path / "moduleB.js"
        file_b.write_text("""
import { functionA } from './moduleA.js';

export function functionB() {
    return "result";
}
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should detect JavaScript cycle
        assert len(cycles) >= 1

        # Check cycle type classification
        for cycle in cycles:
            if cycle["type"] == "javascript_module_cycle":
                assert len(cycle["files"]) >= 2

    def test_typescript_cycle_detection(self, tmp_path):
        """Test cycle detection in TypeScript files."""
        # Create TypeScript files with imports
        file_a = tmp_path / "serviceA.ts"
        file_a.write_text("""
import { ServiceB } from './serviceB';

export class ServiceA {
    private serviceB = new ServiceB();

    public doSomething(): string {
        return this.serviceB.process();
    }
}
""")

        file_b = tmp_path / "serviceB.ts"
        file_b.write_text("""
import { ServiceA } from './serviceA';

export class ServiceB {
    public process(): string {
        return "processed";
    }
}
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should detect TypeScript cycle
        assert len(cycles) >= 1

    def test_mixed_language_cycles(self, tmp_path):
        """Test cycle detection across different file types."""
        # Create mixed language project
        py_file = tmp_path / "python_module.py"
        py_file.write_text("""
# Python module that might interact with JS via subprocess or API
def python_function():
    return "python"
""")

        js_file = tmp_path / "javascript_module.js"
        js_file.write_text("""
// JavaScript module
function jsFunction() {
    return "javascript";
}

export { jsFunction };
""")

        ts_file = tmp_path / "typescript_module.ts"
        ts_file.write_text("""
import { jsFunction } from './javascript_module.js';

export function tsFunction(): string {
    return jsFunction() + " typescript";
}
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result

        # Should analyze all file types
        summary = result["data"]["summary"]
        assert summary["total_files_analyzed"] >= 3

    def test_max_depth_parameter(self, tmp_path):
        """Test max_depth parameter functionality."""
        # Create a deep import chain
        num_files = 6
        for i in range(num_files):
            current_file = tmp_path / f"module_{i}.py"
            if i == num_files - 1:
                # Last file imports the first to create a cycle
                content = f'from module_0 import function_0\n\ndef function_{i}():\n    return "module_{i}"'
            else:
                # Each file imports the next
                next_i = (i + 1) % num_files
                content = (
                    f'from module_{next_i} import function_{next_i}\n\ndef function_{i}():\n    return "module_{i}"'
                )
            current_file.write_text(content)

        # Test with shallow max_depth
        result_shallow = find_import_cycles_impl(project_root=str(tmp_path), max_depth=3)

        # Test with deep max_depth
        result_deep = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result_shallow
        assert "data" in result_deep

        # Deep search should find more or equal cycles
        cycles_shallow = result_shallow["data"]["cycles"]
        cycles_deep = result_deep["data"]["cycles"]

        assert len(cycles_deep) >= len(cycles_shallow)

    def test_include_node_modules_parameter(self, tmp_path):
        """Test include_node_modules parameter."""
        # Create node_modules structure
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()

        package_dir = node_modules / "some-package"
        package_dir.mkdir()

        package_file = package_dir / "index.js"
        package_file.write_text("""
export function packageFunction() {
    return "package";
}
""")

        # Create main project file
        main_file = tmp_path / "main.js"
        main_file.write_text("""
import { packageFunction } from './node_modules/some-package/index.js';

export function mainFunction() {
    return packageFunction();
}
""")

        # Test excluding node_modules
        result_exclude = find_import_cycles_impl(project_root=str(tmp_path), include_node_modules=False)

        # Test including node_modules
        result_include = find_import_cycles_impl(project_root=str(tmp_path), include_node_modules=True)

        assert "data" in result_exclude
        assert "data" in result_include

        # Including node_modules should analyze more files
        files_exclude = result_exclude["data"]["analysis_settings"]["files_analyzed"]
        files_include = result_include["data"]["analysis_settings"]["files_analyzed"]

        assert files_include >= files_exclude

    def test_relative_import_resolution(self, tmp_path):
        """Test resolution of relative imports."""
        # Create nested directory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # File in subdirectory
        sub_file = subdir / "sub_module.py"
        sub_file.write_text("""
from ..main_module import main_function

def sub_function():
    return main_function()
""")

        # Main file
        main_file = tmp_path / "main_module.py"
        main_file.write_text("""
from subdir.sub_module import sub_function

def main_function():
    return "main"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result

        # Should resolve relative imports and detect cycle
        cycles = result["data"]["cycles"]
        assert len(cycles) >= 1

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = find_import_cycles_impl(project_root="/nonexistent/path", max_depth=10)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_invalid_max_depth(self, tmp_path):
        """Test handling of invalid max_depth values."""
        # Test max_depth too low
        result1 = find_import_cycles_impl(project_root=str(tmp_path), max_depth=0)

        # Test max_depth too high
        result2 = find_import_cycles_impl(project_root=str(tmp_path), max_depth=100)

        assert "error" in result1
        assert result1["error"]["code"] == "INVALID_INPUT"

        assert "error" in result2
        assert result2["error"]["code"] == "INVALID_INPUT"

    def test_cycle_severity_calculation(self, tmp_path):
        """Test cycle severity calculation."""
        # Create a cycle involving important files
        main_file = tmp_path / "main.py"
        main_file.write_text("""
from core import core_function

def main():
    return core_function()
""")

        core_file = tmp_path / "core.py"
        core_file.write_text("""
from main import main

def core_function():
    return "core"
""")

        # Create another cycle with less important files
        util1_file = tmp_path / "util1.py"
        util1_file.write_text("""
from util2 import util2_function

def util1_function():
    return util2_function()
""")

        util2_file = tmp_path / "util2.py"
        util2_file.write_text("""
from util1 import util1_function

def util2_function():
    return "util"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should detect both cycles
        assert len(cycles) >= 2

        # Check that severity is calculated
        for cycle in cycles:
            assert "severity" in cycle
            assert isinstance(cycle["severity"], int)
            assert 1 <= cycle["severity"] <= 10

    def test_cycle_impact_analysis(self, tmp_path):
        """Test cycle impact analysis."""
        # Create a cycle that affects many other files
        cycle_a = tmp_path / "cycle_a.py"
        cycle_a.write_text("""
from cycle_b import cycle_b_function

def cycle_a_function():
    return cycle_b_function()
""")

        cycle_b = tmp_path / "cycle_b.py"
        cycle_b.write_text("""
from cycle_a import cycle_a_function

def cycle_b_function():
    return "cycle_b"
""")

        # Create files that depend on the cycle
        for i in range(5):
            dependent_file = tmp_path / f"dependent_{i}.py"
            dependent_file.write_text(f"""
from cycle_a import cycle_a_function

def dependent_{i}_function():
    return cycle_a_function()
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        # Should detect high impact cycle
        assert len(cycles) >= 1

        for cycle in cycles:
            assert "impact" in cycle
            assert cycle["impact"] in ["low", "medium", "high"]

    def test_cycle_suggestions_generation(self, tmp_path):
        """Test generation of cycle-breaking suggestions."""
        # Create Python cycle
        py_a = tmp_path / "python_a.py"
        py_a.write_text("""
from python_b import PythonB

class PythonA:
    def __init__(self):
        self.b = PythonB()
""")

        py_b = tmp_path / "python_b.py"
        py_b.write_text("""
from python_a import PythonA

class PythonB:
    def method(self):
        return "b"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        cycles = result["data"]["cycles"]

        if cycles:
            cycle = cycles[0]
            assert "suggestions" in cycle
            assert isinstance(cycle["suggestions"], list)
            assert len(cycle["suggestions"]) > 0

            # Should include TYPE_CHECKING suggestion for Python
            suggestions_text = " ".join(cycle["suggestions"])
            assert "TYPE_CHECKING" in suggestions_text or "dependency injection" in suggestions_text

    def test_complex_dependency_graph(self, tmp_path):
        """Test analysis of complex dependency graphs."""
        # Create a complex web of dependencies with multiple cycles
        files_config = {
            "auth.py": ["user", "permission"],
            "user.py": ["auth", "profile"],
            "profile.py": ["user", "settings"],
            "settings.py": ["auth"],
            "permission.py": ["user"],
            "api.py": ["auth", "user"],
            "utils.py": [],
            "main.py": ["api", "utils"],
        }

        for filename, imports in files_config.items():
            file_path = tmp_path / filename
            import_lines = [f"from {imp} import {imp}_function" for imp in imports]
            content = "\n".join(import_lines) + f"\n\ndef {filename[:-3]}_function():\n    return '{filename[:-3]}'"
            file_path.write_text(content)

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result

        # Should detect multiple cycles
        cycles = result["data"]["cycles"]
        assert len(cycles) >= 1

        # Check summary statistics
        summary = result["data"]["summary"]
        assert "total_cycles_found" in summary
        assert "files_involved_in_cycles" in summary
        assert "average_cycle_length" in summary

    def test_dependency_graph_output(self, tmp_path):
        """Test dependency graph simplification for output."""
        # Create files with various dependency patterns
        file_a = tmp_path / "heavy_deps.py"
        file_a.write_text("""
import os
import sys
import json
from pathlib import Path
from collections import defaultdict

def heavy_function():
    return "heavy"
""")

        file_b = tmp_path / "light_deps.py"
        file_b.write_text("""
from heavy_deps import heavy_function

def light_function():
    return heavy_function()
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result
        dependency_graph = result["data"]["dependency_graph"]

        # Check simplified graph structure
        assert "total_files" in dependency_graph
        assert "total_dependencies" in dependency_graph
        assert "avg_dependencies_per_file" in dependency_graph

        # Should not include the full graph (too large for output)
        assert "file_with_most_dependencies" in dependency_graph
        assert "most_depended_on_file" in dependency_graph

    def test_import_parsing_edge_cases(self, tmp_path):
        """Test handling of various import statement formats."""
        edge_cases_file = tmp_path / "edge_cases.py"
        edge_cases_file.write_text("""
# Various import formats
import os
import sys, json
from pathlib import Path
from collections import defaultdict, Counter
from typing import (
    Dict,
    List,
    Optional
)

# Relative imports
from . import sibling
from .submodule import function
from ..parent import parent_function

# Import with alias
import numpy as np
from pandas import DataFrame as df

# Dynamic import (should be ignored)
# importlib.import_module("dynamic")

def test_function():
    return "test"
""")

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        # Should handle all import formats without errors
        assert "data" in result or "error" in result
        if "data" in result:
            dependency_graph = result["data"]["dependency_graph"]
            assert "total_files" in dependency_graph

    def test_performance_with_many_files(self, tmp_path):
        """Test performance with a larger number of files."""
        # Create many files with some interconnections
        num_files = 50

        for i in range(num_files):
            file_path = tmp_path / f"module_{i}.py"

            # Create some import patterns
            imports = []
            if i > 0:
                imports.append(f"from module_{i - 1} import function_{i - 1}")
            if i < num_files - 1 and i % 5 == 0:
                imports.append(f"from module_{i + 1} import function_{i + 1}")

            content = "\n".join(imports) + f"\n\ndef function_{i}():\n    return 'module_{i}'"
            file_path.write_text(content)

        result = find_import_cycles_impl(project_root=str(tmp_path), max_depth=10)

        assert "data" in result

        # Should process all files efficiently
        summary = result["data"]["summary"]
        assert summary["total_files_analyzed"] == num_files

        # Should complete in reasonable time (test will timeout if too slow)
        assert "total_cycles_found" in summary
