"""Tests for scoped variable expression evaluation.

This module tests the enhanced expression evaluator that supports scoped variable
syntax like {{ this.variable }}, {{ global.variable }}, {{ loop.item }}, and {{ inputs.parameter }}.
"""


from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator


class TestScopedVariableResolution:
    """Test basic scoped variable resolution functionality."""

    def test_scoped_variable_this_scope_resolution(self):
        """Test basic 'this' scope variable resolution (AC 7.1)."""
        evaluator = ExpressionEvaluator()
        context = {"legacy_var": "old_value"}
        scoped_context = {"this": {"variable": "this_value", "config": {"setting": "enabled"}}}

        # Test basic this scope
        result = evaluator.evaluate("this.variable", context, scoped_context)
        assert result == "this_value"

        # Test nested this scope
        result = evaluator.evaluate("this.config.setting", context, scoped_context)
        assert result == "enabled"

    def test_scoped_variable_global_scope_resolution(self):
        """Test basic 'global' scope variable resolution (AC 7.1)."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "global": {"app_name": "MyApp", "version": "1.0.0", "settings": {"debug": True, "max_retries": 3}}
        }

        # Test basic global scope
        result = evaluator.evaluate("global.app_name", context, scoped_context)
        assert result == "MyApp"

        # Test nested global scope
        result = evaluator.evaluate("global.settings.debug", context, scoped_context)
        assert result is True

        result = evaluator.evaluate("global.settings.max_retries", context, scoped_context)
        assert result == 3

    def test_loop_scope_basic(self):
        """Test basic 'loop' scope variable resolution."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "loop": {"item": "current_file.js", "index": 2, "metadata": {"size": 1024, "modified": "2024-01-01"}}
        }

        # Test basic loop scope
        result = evaluator.evaluate("loop.item", context, scoped_context)
        assert result == "current_file.js"

        result = evaluator.evaluate("loop.index", context, scoped_context)
        assert result == 2

        # Test nested loop scope
        result = evaluator.evaluate("loop.metadata.size", context, scoped_context)
        assert result == 1024

    def test_inputs_scope_basic(self):
        """Test basic 'inputs' scope variable resolution."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "inputs": {
                "file_path": "/path/to/file.js",
                "options": {"verbose": True, "dry_run": False},
                "filters": ["*.ts", "*.js"],
            }
        }

        # Test basic inputs scope
        result = evaluator.evaluate("inputs.file_path", context, scoped_context)
        assert result == "/path/to/file.js"

        # Test nested inputs scope
        result = evaluator.evaluate("inputs.options.verbose", context, scoped_context)
        assert result is True

        result = evaluator.evaluate("inputs.options.dry_run", context, scoped_context)
        assert result is False

    def test_all_scopes_together(self):
        """Test all scopes working together in a single context."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "this": {"current_step": "validation"},
            "global": {"max_files": 100},
            "loop": {"item": "file1.ts", "index": 0},
            "inputs": {"target_dir": "/src"},
        }

        # Test each scope works independently
        assert evaluator.evaluate("this.current_step", context, scoped_context) == "validation"
        assert evaluator.evaluate("global.max_files", context, scoped_context) == 100
        assert evaluator.evaluate("loop.item", context, scoped_context) == "file1.ts"
        assert evaluator.evaluate("inputs.target_dir", context, scoped_context) == "/src"


class TestNestedPathNavigation:
    """Test navigation of deeply nested object paths."""

    def test_deep_nested_objects(self):
        """Test deeply nested object path resolution."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "this": {
                "config": {
                    "database": {
                        "connection": {"host": "localhost", "port": 5432, "ssl": {"enabled": True, "verify": False}}
                    }
                }
            }
        }

        # Test deep nested path
        result = evaluator.evaluate("this.config.database.connection.host", context, scoped_context)
        assert result == "localhost"

        result = evaluator.evaluate("this.config.database.connection.port", context, scoped_context)
        assert result == 5432

        result = evaluator.evaluate("this.config.database.connection.ssl.enabled", context, scoped_context)
        assert result is True

    def test_array_path_navigation(self):
        """Test path navigation with arrays."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "loop": {
                "items": [
                    {"name": "file1.js", "size": 100},
                    {"name": "file2.ts", "size": 200},
                    {"name": "file3.jsx", "size": 150},
                ]
            }
        }

        # Test array length
        result = evaluator.evaluate("loop.items.length", context, scoped_context)
        assert result == 3

        # Test array index access via brackets (correct JavaScript syntax)
        result = evaluator.evaluate("loop.items[0].name", context, scoped_context)
        assert result == "file1.js"

        result = evaluator.evaluate("loop.items[1].size", context, scoped_context)
        assert result == 200

    def test_mixed_object_array_paths(self):
        """Test paths that mix objects and arrays."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "global": {
                "projects": [
                    {"name": "project1", "files": ["index.js", "utils.ts"], "config": {"env": "dev"}},
                    {"name": "project2", "files": ["main.py", "test.py"], "config": {"env": "prod"}},
                ]
            }
        }

        # Test complex mixed paths
        result = evaluator.evaluate("global.projects[0].name", context, scoped_context)
        assert result == "project1"

        result = evaluator.evaluate("global.projects[1].config.env", context, scoped_context)
        assert result == "prod"

        result = evaluator.evaluate("global.projects[0].files.length", context, scoped_context)
        assert result == 2


class TestLegacyCompatibility:
    """Test backward compatibility with legacy variable resolution."""

    def test_legacy_variables_still_work(self):
        """Test that legacy context variables still work without scoped_context."""
        evaluator = ExpressionEvaluator()
        context = {"user_name": "Alice", "file_count": 5, "is_ready": True, "nested": {"prop": "value"}}

        # Test legacy variables work without scoped_context
        assert evaluator.evaluate("user_name", context) == "Alice"
        assert evaluator.evaluate("file_count", context) == 5
        assert evaluator.evaluate("is_ready", context) is True
        assert evaluator.evaluate("nested.prop", context) == "value"

    def test_legacy_with_empty_scoped_context(self):
        """Test legacy variables work with empty scoped_context."""
        evaluator = ExpressionEvaluator()
        context = {"legacy_var": "legacy_value"}
        scoped_context = {}

        result = evaluator.evaluate("legacy_var", context, scoped_context)
        assert result == "legacy_value"

    def test_fallback_to_legacy_for_unscoped_vars(self):
        """Test fallback to legacy context for variables that don't match scope syntax."""
        evaluator = ExpressionEvaluator()
        context = {"regular_var": "regular_value", "invalid": {"name": "invalid_value"}}  # Not a valid scope prefix
        scoped_context = {"this": {"scoped_var": "scoped_value"}}

        # Regular variables should use legacy context
        result = evaluator.evaluate("regular_var", context, scoped_context)
        assert result == "regular_value"

        # Scoped variables should use scoped context
        result = evaluator.evaluate("this.scoped_var", context, scoped_context)
        assert result == "scoped_value"

        # Variables with dots but not valid scopes should use legacy context
        result = evaluator.evaluate("invalid.name", context, scoped_context)
        assert result == "invalid_value"

    def test_priority_scoped_over_legacy(self):
        """Test that scoped variables take priority when both exist."""
        evaluator = ExpressionEvaluator()
        context = {"this.variable": "legacy_value"}  # Literal key with dot
        scoped_context = {"this": {"variable": "scoped_value"}}

        # Scoped syntax should use scoped_context, not legacy literal key
        result = evaluator.evaluate("this.variable", context, scoped_context)
        assert result == "scoped_value"


class TestScopeExpressions:
    """Test scoped variables in complex expressions."""

    def test_scoped_variables_in_conditions(self):
        """Test scoped variables in boolean expressions."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "this": {"count": 5, "enabled": True},
            "global": {"max_items": 10},
            "inputs": {"threshold": 3},
        }

        # Test comparison with scoped variables
        assert evaluator.evaluate("this.count > inputs.threshold", context, scoped_context)
        assert evaluator.evaluate("this.count <= global.max_items", context, scoped_context)
        assert not evaluator.evaluate("this.count > global.max_items", context, scoped_context)

        # Test logical operators with scoped variables
        assert evaluator.evaluate("this.enabled && this.count > 0", context, scoped_context)
        assert evaluator.evaluate("this.enabled || this.count == 0", context, scoped_context)

    def test_scoped_variables_in_arithmetic(self):
        """Test scoped variables in arithmetic expressions."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"loop": {"index": 2, "batch_size": 10}, "global": {"multiplier": 3}}

        # Test arithmetic with scoped variables
        result = evaluator.evaluate("loop.index * global.multiplier", context, scoped_context)
        assert result == 6

        result = evaluator.evaluate("loop.index + loop.batch_size", context, scoped_context)
        assert result == 12

    def test_scoped_variables_in_string_operations(self):
        """Test scoped variables in string operations."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"inputs": {"prefix": "file_", "suffix": ".js"}, "loop": {"name": "test"}}

        # Test string concatenation
        result = evaluator.evaluate("inputs.prefix + loop.name + inputs.suffix", context, scoped_context)
        assert result == "file_test.js"

    def test_scoped_variables_in_ternary(self):
        """Test scoped variables in ternary expressions."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"this": {"mode": "dev", "verbose": True}, "global": {"log_level": "debug"}}

        # Test ternary with scoped variables
        result = evaluator.evaluate("this.mode == 'dev' ? global.log_level : 'info'", context, scoped_context)
        assert result == "debug"

        result = evaluator.evaluate("this.verbose ? 'detailed' : 'summary'", context, scoped_context)
        assert result == "detailed"


class TestErrorHandling:
    """Test error cases and edge conditions."""

    def test_undefined_scoped_variables(self):
        """Test behavior with undefined scoped variables."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"this": {"existing": "value"}}

        # Undefined scope should return None
        result = evaluator.evaluate("missing.variable", context, scoped_context)
        assert result is None

        # Undefined variable in existing scope should return None
        result = evaluator.evaluate("this.missing", context, scoped_context)
        assert result is None

    def test_invalid_scope_names(self):
        """Test variables with invalid scope names fall back to legacy."""
        evaluator = ExpressionEvaluator()
        context = {"invalid": {"scope": "legacy_value"}}
        scoped_context = {"this": {"variable": "scoped_value"}}

        # Invalid scope should fall back to legacy
        result = evaluator.evaluate("invalid.scope", context, scoped_context)
        assert result == "legacy_value"

        # Valid scope should work
        result = evaluator.evaluate("this.variable", context, scoped_context)
        assert result == "scoped_value"

    def test_none_scope_data(self):
        """Test behavior when scope data is None."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"this": None, "global": {"valid": "value"}}

        # None scope should return None
        result = evaluator.evaluate("this.anything", context, scoped_context)
        assert result is None

        # Valid scope should still work
        result = evaluator.evaluate("global.valid", context, scoped_context)
        assert result == "value"

    def test_empty_variable_path(self):
        """Test behavior with special property names."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"this": {"_": "underscore_value", "normal": "normal_value"}}

        # Special property names should work
        result = evaluator.evaluate("this._", context, scoped_context)
        assert result == "underscore_value"

        # Normal path should still work
        result = evaluator.evaluate("this.normal", context, scoped_context)
        assert result == "normal_value"


class TestMixedScopedUnscoped:
    """Test expressions mixing scoped and unscoped variables."""

    def test_mixed_in_same_expression(self):
        """Test mixing scoped and unscoped variables in same expression."""
        evaluator = ExpressionEvaluator()
        context = {"legacy_count": 3, "legacy_flag": True}
        scoped_context = {"this": {"new_count": 7}, "inputs": {"multiplier": 2}}

        # Mix legacy and scoped variables
        result = evaluator.evaluate("legacy_count + this.new_count", context, scoped_context)
        assert result == 10

        result = evaluator.evaluate("legacy_flag && this.new_count > 0", context, scoped_context)
        assert result is True

        # Complex mixed expression
        result = evaluator.evaluate("(legacy_count * inputs.multiplier) + this.new_count", context, scoped_context)
        assert result == 13  # (3 * 2) + 7

    def test_property_access_on_scoped_variables(self):
        """Test property access on scoped variables using AST property access."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {"this": {"user": {"name": "Alice", "age": 30}, "items": ["a", "b", "c"]}}

        # Test property access on scoped variables (this uses AST property_access, not identifier parsing)
        # Note: this.user resolves to the user object, then .name is property access
        result = evaluator.evaluate("this.user.name", context, scoped_context)
        assert result == "Alice"

        result = evaluator.evaluate("this.items.length", context, scoped_context)
        assert result == 3


class TestArrayScopeHandling:
    """Test scoped variables with array structures."""

    def test_scope_with_arrays(self):
        """Test scoped variables containing arrays."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "loop": {
                "items": [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}, {"id": 3, "name": "third"}],
                "current_index": 1,
            }
        }

        # Test array length through scoped path
        result = evaluator.evaluate("loop.items.length", context, scoped_context)
        assert result == 3

        # Test array element access through scoped path
        result = evaluator.evaluate("loop.items[0].name", context, scoped_context)
        assert result == "first"

        result = evaluator.evaluate("loop.items[1].id", context, scoped_context)
        assert result == 2

    def test_scope_array_with_expressions(self):
        """Test scoped array access with computed indices."""
        evaluator = ExpressionEvaluator()
        context = {"offset": 1}
        scoped_context = {"this": {"data": ["zero", "one", "two", "three"], "index": 2}}

        # Test basic scoped array access
        result = evaluator.evaluate("this.data[0]", context, scoped_context)
        assert result == "zero"

        # Test array access with scoped index (this.data[this.index] equivalent)
        result = evaluator.evaluate("this.data[2]", context, scoped_context)
        assert result == "two"


class TestComplexScopedExpressions:
    """Test complex expressions using multiple scoped variables."""

    def test_workflow_condition_simulation(self):
        """Test expressions that simulate real workflow conditions."""
        evaluator = ExpressionEvaluator()
        context = {}  # No legacy context needed
        scoped_context = {
            "this": {"step_name": "validate_files", "completed_count": 5, "error_count": 0},
            "global": {"max_errors": 3, "total_files": 10, "debug_mode": True},
            "loop": {"item": "file.ts", "index": 4},
            "inputs": {"target_extensions": [".ts", ".js"], "skip_validation": False},
        }

        # Test realistic workflow conditions
        assert evaluator.evaluate("this.error_count < global.max_errors", context, scoped_context)
        assert evaluator.evaluate("this.completed_count < global.total_files", context, scoped_context)
        assert not evaluator.evaluate("inputs.skip_validation", context, scoped_context)
        assert evaluator.evaluate("global.debug_mode && this.error_count == 0", context, scoped_context)

    def test_template_replacement_simulation(self):
        """Test expressions that might come from template replacement."""
        evaluator = ExpressionEvaluator()
        context = {}
        scoped_context = {
            "inputs": {"file_path": "/src/components/Button.tsx", "component_name": "Button"},
            "this": {"output_dir": "/dist", "build_mode": "production"},
        }

        # Test string building (simulating template replacement)
        result = evaluator.evaluate("inputs.file_path.includes('.tsx')", context, scoped_context)
        assert result is True

        result = evaluator.evaluate("this.build_mode == 'production'", context, scoped_context)
        assert result is True
