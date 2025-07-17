"""
Test file for Phase 1: Core State Engine - Transformation Engine

Tests the JavaScript transformation engine, dependency resolution, and error handling.
"""

import pytest

# Import implemented transformer components
from aromcp.workflow_server.state.transformer import CircularDependencyError, DependencyResolver, TransformationEngine


class TestTransformationEngine:
    """Test JavaScript transformation execution"""

    def test_simple_transformation(self):
        """Test basic JavaScript transformation"""
        # Given
        transformer = TransformationEngine()
        transform = "input * 2"

        # When
        result = transformer.execute(transform, 5)

        # Then
        assert result == 10

    def test_transformation_with_dependencies(self):
        """Test transformation with multiple dependencies"""
        # Given
        transformer = TransformationEngine()
        transform = "input[0] + input[1]"
        inputs = [5, 3]

        # When
        result = transformer.execute(transform, inputs)

        # Then
        assert result == 8

    def test_string_transformation(self):
        """Test string manipulation transformations"""
        # Given
        transformer = TransformationEngine()
        transform = "input.toUpperCase()"

        # When
        result = transformer.execute(transform, "hello")

        # Then
        assert result == "HELLO"

    def test_array_transformation(self):
        """Test array manipulation transformations"""
        # Given
        transformer = TransformationEngine()
        transform = "input.filter(x => x > 5)"

        # When
        result = transformer.execute(transform, [1, 5, 10, 3, 8])

        # Then
        assert result == [10, 8]

    def test_object_transformation(self):
        """Test object manipulation transformations"""
        # Given
        transformer = TransformationEngine()
        transform = "({ name: input.name.toUpperCase(), age: input.age + 1 })"

        # When
        result = transformer.execute(transform, {"name": "alice", "age": 30})

        # Then
        assert result == {"name": "ALICE", "age": 31}

    def test_template_literal_transformation(self):
        """Test template literal transformations"""
        # Given
        transformer = TransformationEngine()
        transform = "`Hello ${input.name}, you are ${input.age} years old`"

        # When
        result = transformer.execute(transform, {"name": "Alice", "age": 30})

        # Then
        assert result == "Hello Alice, you are 30 years old"

    def test_transformation_error_handling(self):
        """Test transformation handles JavaScript errors"""
        # Given
        transformer = TransformationEngine()
        transform = "input.nonexistent.property"

        # When/Then
        with pytest.raises((AttributeError, TypeError)):
            transformer.execute(transform, {"valid": "data"})

    def test_transformation_with_math(self):
        """Test transformations using Math functions"""
        # Given
        transformer = TransformationEngine()
        transform = "Math.round(input * 1.7)"

        # When
        result = transformer.execute(transform, 5)

        # Then
        assert result == 9  # Math.round(5 * 1.7) = Math.round(8.5) = 9

    def test_transformation_with_json(self):
        """Test transformations using JSON functions"""
        # Given
        transformer = TransformationEngine()
        transform = "JSON.parse(input)"

        # When
        result = transformer.execute(transform, '{"key": "value"}')

        # Then
        assert result == {"key": "value"}


class TestDependencyResolver:
    """Test dependency graph building and resolution"""

    def test_simple_dependency_resolution(self):
        """Test resolving simple dependency chain"""
        # Given
        schema = {"computed": {"double": {"from": "raw.value", "transform": "input * 2"}}}
        resolver = DependencyResolver(schema)

        # When
        resolved = resolver.resolve()

        # Then
        assert "double" in resolved
        assert resolved["double"]["dependencies"] == ["raw.value"]

    def test_multiple_dependency_resolution(self):
        """Test resolving multiple dependencies"""
        # Given
        schema = {"computed": {"sum": {"from": ["raw.a", "raw.b"], "transform": "input[0] + input[1]"}}}
        resolver = DependencyResolver(schema)

        # When
        resolved = resolver.resolve()

        # Then
        assert resolved["sum"]["dependencies"] == ["raw.a", "raw.b"]

    def test_cascading_dependency_resolution(self):
        """Test resolving cascading dependencies"""
        # Given
        schema = {
            "computed": {
                "double": {"from": "raw.value", "transform": "input * 2"},
                "quadruple": {"from": "computed.double", "transform": "input * 2"},
            }
        }
        resolver = DependencyResolver(schema)

        # When
        resolved = resolver.resolve()

        # Then
        # Should resolve in correct order: double first, then quadruple
        execution_order = list(resolved.keys())
        assert execution_order.index("double") < execution_order.index("quadruple")

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected"""
        # Given
        schema = {
            "computed": {
                "a": {"from": "computed.b", "transform": "input"},
                "b": {"from": "computed.a", "transform": "input"},
            }
        }

        # When/Then
        with pytest.raises(CircularDependencyError):
            DependencyResolver(schema).resolve()

    def test_self_circular_dependency_detection(self):
        """Test that self-referential dependencies are detected"""
        # Given
        schema = {"computed": {"self_ref": {"from": "computed.self_ref", "transform": "input + 1"}}}

        # When/Then
        with pytest.raises(CircularDependencyError):
            DependencyResolver(schema).resolve()

    def test_complex_dependency_resolution(self):
        """Test resolving complex dependency graph"""
        # Given
        schema = {
            "computed": {
                "a": {"from": "raw.value", "transform": "input * 2"},
                "b": {"from": "raw.value", "transform": "input + 1"},
                "c": {"from": ["computed.a", "computed.b"], "transform": "input[0] + input[1]"},
                "d": {"from": "computed.c", "transform": "input * 3"},
            }
        }
        resolver = DependencyResolver(schema)

        # When
        resolved = resolver.resolve()

        # Then
        execution_order = list(resolved.keys())
        # a and b should come before c, c should come before d
        assert execution_order.index("a") < execution_order.index("c")
        assert execution_order.index("b") < execution_order.index("c")
        assert execution_order.index("c") < execution_order.index("d")

    def test_no_dependencies(self):
        """Test resolving schema with no computed fields"""
        # Given
        schema = {"computed": {}}
        resolver = DependencyResolver(schema)

        # When
        resolved = resolver.resolve()

        # Then
        assert resolved == {}


class TestTransformationIntegration:
    """Integration tests for transformation engine with dependency resolution"""

    def test_cascading_transformation_execution(self):
        """Test executing cascading transformations in correct order"""
        # Given
        transformer = TransformationEngine()
        schema = {
            "computed": {
                "double": {"from": "raw.value", "transform": "input * 2"},
                "quadruple": {"from": "computed.double", "transform": "input * 2"},
            }
        }
        state = {"raw": {"value": 5}, "computed": {}}

        # When
        resolver = DependencyResolver(schema)
        resolved = resolver.resolve()

        # Execute in dependency order
        for field_name, field_info in resolved.items():
            dependencies = field_info["dependencies"]
            inputs = []
            for dep in dependencies:
                parts = dep.split(".")
                if parts[0] == "raw":
                    inputs.append(state["raw"][parts[1]])
                elif parts[0] == "computed":
                    inputs.append(state["computed"][parts[1]])

            if len(inputs) == 1:
                result = transformer.execute(field_info["transform"], inputs[0])
            else:
                result = transformer.execute(field_info["transform"], inputs)

            state["computed"][field_name] = result

        # Then
        assert state["computed"]["double"] == 10
        assert state["computed"]["quadruple"] == 20
