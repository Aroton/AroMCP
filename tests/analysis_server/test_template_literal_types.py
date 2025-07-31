"""Test for template literal type resolution - focused test for TDD."""

import tempfile
from pathlib import Path

import pytest

# Import the expected implementations
try:
    from aromcp.analysis_server.models.typescript_models import TypeDefinition
    from aromcp.analysis_server.tools.symbol_resolver import SymbolResolver
    from aromcp.analysis_server.tools.type_resolver import TypeResolver
    from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser
except ImportError:
    pytest.skip("Analysis server not fully implemented", allow_module_level=True)


class TestTemplateLiteralTypes:
    """Test template literal type resolution."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set MCP_FILE_ROOT for testing
            import os

            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)

            try:
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def test_template_literal_type_resolution(self, temp_project):
        """Test that template literal types are resolved correctly."""
        test_file = temp_project / "template_literals.ts"
        test_file.write_text(
            """
        export type EventName<T extends string> = `on${Capitalize<T>}`;
        export type ApiEndpoint<Method extends string, Path extends string> = `${Method} ${Path}`;
        
        function createEventHandler<T extends string>(
            eventType: T
        ): EventName<T> {
            return `on${eventType.charAt(0).toUpperCase()}${eventType.slice(1)}` as EventName<T>;
        }
        """
        )

        # Initialize components
        parser = TypeScriptParser()
        symbol_resolver = SymbolResolver(parser)
        type_resolver = TypeResolver(parser, symbol_resolver)

        # Test resolving EventName<T>
        result = type_resolver.resolve_type("EventName<T>", str(test_file), "full_inference")

        assert result is not None
        assert result.kind != "error"
        assert result.kind != "unknown"

        # The type should be recognized as a template literal type
        assert "template" in result.kind.lower() or "literal" in result.definition.lower()

    def test_find_template_literal_type_definition(self, temp_project):
        """Test finding template literal type definitions."""
        test_file = temp_project / "template_literals.ts"
        test_file.write_text(
            """
        export type EventName<T extends string> = `on${Capitalize<T>}`;
        export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
        export type ApiEndpoint<Method extends HttpMethod, Path extends string> = 
            `${Method} ${Path}`;
        """
        )

        # Initialize components
        parser = TypeScriptParser()
        symbol_resolver = SymbolResolver(parser)
        type_resolver = TypeResolver(parser, symbol_resolver)

        # Test finding EventName type alias
        result = type_resolver._find_type_alias_definition("EventName", None, str(test_file))

        assert result is not None
        assert result.kind == "template_literal"  # Template literal types have their own kind
        assert "`on${Capitalize<T>}`" in result.definition

        # Test finding ApiEndpoint type alias
        result2 = type_resolver._find_type_alias_definition("ApiEndpoint", None, str(test_file))

        assert result2 is not None
        assert result2.kind == "template_literal"  # Also a template literal type
        assert "`${Method} ${Path}`" in result2.definition

    def test_extract_template_literal_from_function_body(self, temp_project):
        """Test extracting template literal types referenced in function bodies."""
        test_file = temp_project / "function_with_template.ts"
        test_file.write_text(
            """
        export type EventName<T extends string> = `on${Capitalize<T>}`;
        
        function createEventHandler<T extends string>(
            eventType: T
        ): (handler: (event: { type: EventName<T>; data: any }) => void) => void {
            const eventName = `on${eventType.charAt(0).toUpperCase()}${eventType.slice(1)}` as EventName<T>;
            
            return (handler) => {
                console.log(`Registering handler for ${eventName}`);
            };
        }
        """
        )

        # Initialize components
        parser = TypeScriptParser()
        symbol_resolver = SymbolResolver(parser)
        type_resolver = TypeResolver(parser, symbol_resolver)

        # The function analyzer should extract EventName<T> from the return type
        # For now, let's test that we can at least resolve it
        result = type_resolver.resolve_type("EventName<T>", str(test_file), "full_inference")

        assert result is not None
        assert result.kind != "error"

        # Also test extracting from complex return type
        return_type = "(handler: (event: { type: EventName<T>; data: any }) => void) => void"
        # Extract type references from this complex type
        type_refs = type_resolver._extract_type_references(return_type)

        assert "EventName<T>" in type_refs or "EventName" in type_refs
