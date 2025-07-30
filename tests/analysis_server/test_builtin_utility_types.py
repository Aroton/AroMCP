"""Test extraction of built-in TypeScript utility types."""

import tempfile
from pathlib import Path
import pytest

try:
    from aromcp.analysis_server.tools.function_analyzer import FunctionAnalyzer
    from aromcp.analysis_server.tools.type_resolver import TypeResolver
    from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser
    from aromcp.analysis_server.tools.symbol_resolver import SymbolResolver
    from aromcp.analysis_server.models.typescript_models import TypeDefinition
except ImportError:
    pytest.skip("Analysis server not fully implemented", allow_module_level=True)


class TestBuiltinUtilityTypes:
    """Test extraction of built-in TypeScript utility types."""

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

    def test_extract_partial_utility_type(self, temp_project):
        """Test that Partial<T> utility type is extracted."""
        test_file = temp_project / "utility_types.ts"
        test_file.write_text("""
        export function makePartial<T>(obj: T): Partial<T> {
            return { ...obj };
        }
        """)
        
        # Initialize components
        parser = TypeScriptParser()
        symbol_resolver = SymbolResolver(parser)
        type_resolver = TypeResolver(parser, symbol_resolver)
        function_analyzer = FunctionAnalyzer(parser, type_resolver)
        
        # Analyze function
        result, errors = function_analyzer.analyze_function(
            "makePartial", str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert result is not None
        assert result.types is not None
        
        # Should include Partial as a utility type
        assert "Partial" in result.types
        assert result.types["Partial"].kind == "utility_type"
        
    def test_extract_multiple_utility_types(self, temp_project):
        """Test extraction of multiple utility types."""
        test_file = temp_project / "multiple_utils.ts"
        test_file.write_text("""
        export function transformObject<T, K extends keyof T>(
            obj: T,
            keys: K[]
        ): Pick<T, K> & Partial<Omit<T, K>> {
            const picked = {} as Pick<T, K>;
            const rest = {} as Partial<Omit<T, K>>;
            
            for (const key in obj) {
                if (keys.includes(key as any)) {
                    (picked as any)[key] = obj[key];
                } else {
                    (rest as any)[key] = obj[key];
                }
            }
            
            return { ...picked, ...rest };
        }
        """)
        
        # Initialize components
        parser = TypeScriptParser()
        symbol_resolver = SymbolResolver(parser)
        type_resolver = TypeResolver(parser, symbol_resolver)
        function_analyzer = FunctionAnalyzer(parser, type_resolver)
        
        # Analyze function
        result, errors = function_analyzer.analyze_function(
            "transformObject", str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert result is not None
        assert result.types is not None
        
        # Should include all utility types
        utility_types = ["Pick", "Partial", "Omit"]
        for util_type in utility_types:
            assert util_type in result.types
            assert result.types[util_type].kind == "utility_type"