"""Tests for analyze_component_usage tool."""

import pytest
import tempfile
from pathlib import Path

from aromcp.analysis_server.tools.analyze_component_usage import analyze_component_usage_impl


class TestAnalyzeComponentUsage:
    """Test cases for component usage analysis."""

    def test_basic_functionality(self):
        """Test basic component usage analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample component files
            component_file = Path(temp_dir) / "components" / "Button.tsx"
            component_file.parent.mkdir(parents=True)
            component_file.write_text("""
import React from 'react';

export const Button = ({ children, onClick }) => {
  return <button onClick={onClick}>{children}</button>;
};

export default Button;
            """)
            
            usage_file = Path(temp_dir) / "pages" / "Home.tsx"
            usage_file.parent.mkdir(parents=True)
            usage_file.write_text("""
import { Button } from '../components/Button';
import React from 'react';

export const Home = () => {
  return (
    <div>
      <Button onClick={() => console.log('clicked')}>
        Click me
      </Button>
    </div>
  );
};
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx", "**/*.ts"],
                include_imports=True
            )

            assert "data" in result
            data = result["data"]
            
            # Should find Button component
            button_components = [c for c in data["components"] if c["name"] == "Button"]
            assert len(button_components) == 1
            
            button = button_components[0]
            assert button["type"] == "component"
            assert button["is_exported"] == True
            assert button["total_usage"] > 0
            assert button["import_count"] > 0

    def test_python_component_analysis(self):
        """Test Python function/class analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create Python module
            utils_file = Path(temp_dir) / "utils.py"
            utils_file.write_text("""
def helper_function(data):
    '''A helper function.'''
    return data.upper()

class DataProcessor:
    '''A data processing class.'''
    def process(self, data):
        return helper_function(data)

def _private_function():
    '''Private function.'''
    pass
            """)
            
            main_file = Path(temp_dir) / "main.py"
            main_file.write_text("""
from utils import helper_function, DataProcessor

def main():
    processor = DataProcessor()
    result = processor.process("hello")
    return helper_function(result)
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.py"],
                include_imports=True
            )

            assert "data" in result
            data = result["data"]
            
            # Should find functions and classes
            components = data["components"]
            names = [c["name"] for c in components]
            
            assert "helper_function" in names
            assert "DataProcessor" in names
            assert "_private_function" in names  # Private functions are still detected
            
            # Check usage tracking
            helper_usage = next(c for c in components if c["name"] == "helper_function")
            assert helper_usage["total_usage"] > 0

    def test_unused_components_detection(self):
        """Test detection of unused components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create unused component
            unused_file = Path(temp_dir) / "UnusedComponent.tsx"
            unused_file.write_text("""
export const UnusedComponent = () => {
  return <div>Never used</div>;
};
            """)
            
            # Create used component
            used_file = Path(temp_dir) / "UsedComponent.tsx"
            used_file.write_text("""
export const UsedComponent = () => {
  return <div>I am used</div>;
};
            """)
            
            # Create file that uses only one component
            consumer_file = Path(temp_dir) / "Consumer.tsx"
            consumer_file.write_text("""
import { UsedComponent } from './UsedComponent';

export const Consumer = () => {
  return <UsedComponent />;
};
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )

            assert "data" in result
            data = result["data"]
            
            # Check unused components
            unused_components = data["unused_components"]
            unused_names = [c["name"] for c in unused_components]
            
            assert "UnusedComponent" in unused_names
            assert "UsedComponent" not in unused_names

    def test_component_type_classification(self):
        """Test correct classification of component types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.tsx"
            test_file.write_text("""
// Function component
export const FunctionComponent = () => <div></div>;

// Class component  
export class ClassComponent extends React.Component {
  render() {
    return <div></div>;
  }
}

// Regular function
export function regularFunction() {
  return "not a component";
}

// Arrow function
export const arrowFunction = () => {
  return "also not a component";
};
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )

            assert "data" in result
            components = result["data"]["components"]
            
            # Check component type classification
            function_comp = next(c for c in components if c["name"] == "FunctionComponent")
            assert function_comp["type"] == "component"
            
            class_comp = next(c for c in components if c["name"] == "ClassComponent")
            assert class_comp["type"] == "class"
            
            regular_func = next(c for c in components if c["name"] == "regularFunction")
            assert regular_func["type"] == "function"

    def test_usage_statistics(self):
        """Test usage statistics generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create components with varying usage
            for i in range(3):
                comp_file = Path(temp_dir) / f"Component{i}.tsx"
                comp_file.write_text(f"""
export const Component{i} = () => <div>Component {i}</div>;
                """)
            
            # Create usage patterns
            usage_file = Path(temp_dir) / "Usage.tsx"
            usage_file.write_text("""
import { Component0 } from './Component0';
import { Component1 } from './Component1';
// Component2 is imported but not used

export const Usage = () => {
  return (
    <div>
      <Component0 />
      <Component0 />
      <Component1 />
    </div>
  );
};
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )

            assert "data" in result
            data = result["data"]
            
            # Check summary statistics
            summary = data["summary"]
            assert summary["total_components"] >= 3
            assert summary["total_usages"] > 0
            assert summary["files_analyzed"] > 0
            
            # Check usage stats
            usage_stats = data["usage_stats"]
            assert isinstance(usage_stats, dict)

    def test_empty_project(self):
        """Test handling of empty project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )

            assert "data" in result
            data = result["data"]
            
            assert data["components"] == []
            assert data["unused_components"] == []
            assert data["summary"]["total_components"] == 0

    def test_custom_patterns(self):
        """Test custom component patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create component in non-standard location
            comp_file = Path(temp_dir) / "widgets" / "CustomWidget.js"
            comp_file.parent.mkdir(parents=True)
            comp_file.write_text("""
export const CustomWidget = () => {
  return 'custom widget';
};
            """)

            # Test with default patterns (should not find it)
            result1 = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx", "**/*.jsx"],
                include_imports=True
            )
            
            assert result1["data"]["summary"]["total_components"] == 0

            # Test with custom patterns (should find it)
            result2 = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/widgets/**/*.js"],
                include_imports=True
            )
            
            assert result2["data"]["summary"]["total_components"] == 1

    def test_jsx_usage_tracking(self):
        """Test JSX usage tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            component_file = Path(temp_dir) / "Component.jsx"
            component_file.write_text("""
export const MyComponent = ({ title }) => {
  return <h1>{title}</h1>;
};
            """)
            
            usage_file = Path(temp_dir) / "Usage.jsx"
            usage_file.write_text("""
import { MyComponent } from './Component';

export const Usage = () => {
  return (
    <div>
      <MyComponent title="First" />
      <MyComponent title="Second" />
      <MyComponent title="Third" />
    </div>
  );
};
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.jsx"],
                include_imports=True
            )

            assert "data" in result
            components = result["data"]["components"]
            
            my_component = next(c for c in components if c["name"] == "MyComponent")
            # Should have 1 import + 3 JSX usages = 4 total
            assert my_component["total_usage"] >= 4
            assert my_component["import_count"] >= 1
            assert my_component["call_count"] >= 3

    def test_import_without_usage(self):
        """Test tracking imports that are never used."""
        with tempfile.TemporaryDirectory() as temp_dir:
            component_file = Path(temp_dir) / "Component.tsx"
            component_file.write_text("""
export const ImportedButNotUsed = () => <div>Hello</div>;
            """)
            
            usage_file = Path(temp_dir) / "Usage.tsx"
            usage_file.write_text("""
import { ImportedButNotUsed } from './Component';
// Imported but never actually used in JSX
            """)

            result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )

            assert "data" in result
            components = result["data"]["components"]
            
            component = next(c for c in components if c["name"] == "ImportedButNotUsed")
            assert component["import_count"] >= 1
            assert component["call_count"] == 0
            assert component["total_usage"] >= 1  # Has import but no usage

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Test with non-existent directory
        result = analyze_component_usage_impl(
            project_root="/non/existent/path",
            component_patterns=["**/*.tsx"],
            include_imports=True
        )

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"