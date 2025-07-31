"""
Test symbol resolution in monorepo context.

This test file focuses on diagnosing symbol resolution issues.
"""

import json

import pytest

from aromcp.analysis_server.tools.monorepo_analyzer import MonorepoAnalyzer
from aromcp.analysis_server.tools.symbol_resolver import SymbolResolver
from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser


@pytest.fixture
def simple_project(tmp_path):
    """Create a simple TypeScript project."""
    # Create tsconfig
    (tmp_path / "tsconfig.json").write_text(json.dumps({"compilerOptions": {"strict": True}, "include": ["src/**/*"]}))

    # Create source file
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text(
        """
export interface Config {
    apiUrl: string;
    version: string;
}

export class Service {
    constructor(private config: Config) {}
    
    getVersion(): string {
        return this.config.version;
    }
}

export const DEFAULT_CONFIG: Config = {
    apiUrl: 'https://api.example.com',
    version: '1.0.0'
};
"""
    )

    return tmp_path


class TestSymbolResolution:
    """Test symbol resolution functionality."""

    def test_symbol_resolver_finds_symbols(self, simple_project):
        """Test that symbol resolver can find symbols in a file."""
        resolver = SymbolResolver()

        # Get symbols from the file
        file_path = str(simple_project / "src" / "index.ts")
        symbols = resolver.get_file_symbols(file_path)

        # Should find interface, class, and const
        assert len(symbols) > 0, "No symbols found"

        symbol_names = {s.name for s in symbols}
        assert "Config" in symbol_names
        assert "Service" in symbol_names
        assert "DEFAULT_CONFIG" in symbol_names

    def test_parser_parses_typescript(self, simple_project):
        """Test that TypeScript parser works correctly."""
        parser = TypeScriptParser()

        file_path = str(simple_project / "src" / "index.ts")
        result = parser.parse_file(file_path)

        assert result.success, f"Parser failed: {result.errors}"
        assert result.tree is not None
        assert result.parse_time_ms > 0

    def test_monorepo_workspace_context_populates_symbols(self, simple_project):
        """Test that workspace context properly populates symbols."""
        # Add package.json to make it a proper project
        (simple_project / "package.json").write_text(json.dumps({"name": "test-project", "version": "1.0.0"}))

        analyzer = MonorepoAnalyzer(str(simple_project))
        projects = analyzer.discover_projects()

        assert len(projects) == 1, f"Expected 1 project, found {len(projects)}"

        # Create workspace context
        context = analyzer.create_workspace_context()

        # Analyze the project
        result = context.analyze_project("test-project")
        assert result.success
        assert result.total_symbols > 0, "No symbols found in analysis"

        # Check shared type stats
        stats = context.get_shared_type_stats()
        # Since we only have one project, no types should be shared
        assert len(stats.shared_types) == 0
