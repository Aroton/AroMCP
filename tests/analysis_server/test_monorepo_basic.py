"""
Basic tests for monorepo functionality to drive TDD implementation.

These tests focus on the core monorepo features needed:
1. Cross-project symbol resolution
2. Type sharing across projects
3. Workspace-wide analysis
"""

import json

import pytest

from aromcp.analysis_server.tools.monorepo_analyzer import (
    MonorepoAnalyzer,
)


@pytest.fixture
def basic_monorepo(tmp_path):
    """Create a basic monorepo with two projects."""
    # Create shared package
    shared_dir = tmp_path / "packages" / "shared"
    shared_dir.mkdir(parents=True)

    (shared_dir / "tsconfig.json").write_text(
        json.dumps(
            {"compilerOptions": {"composite": True, "declaration": True, "outDir": "./dist"}, "include": ["src/**/*"]}
        )
    )

    (shared_dir / "package.json").write_text(json.dumps({"name": "@test/shared", "version": "1.0.0"}))

    # Create shared source
    (shared_dir / "src").mkdir()
    (shared_dir / "src" / "types.ts").write_text(
        """
export interface User {
    id: string;
    name: string;
    email: string;
}

export class UserService {
    getUser(id: string): User {
        return { id, name: 'Test', email: 'test@example.com' };
    }
}
"""
    )

    # Create app package that uses shared
    app_dir = tmp_path / "packages" / "app"
    app_dir.mkdir(parents=True)

    (app_dir / "tsconfig.json").write_text(
        json.dumps(
            {"compilerOptions": {"composite": True}, "references": [{"path": "../shared"}], "include": ["src/**/*"]}
        )
    )

    (app_dir / "package.json").write_text(
        json.dumps({"name": "@test/app", "version": "1.0.0", "dependencies": {"@test/shared": "workspace:*"}})
    )

    # Create app source
    (app_dir / "src").mkdir()
    (app_dir / "src" / "main.ts").write_text(
        """
import { User, UserService } from '@test/shared';

const service = new UserService();
const user: User = service.getUser('123');
console.log(user.name);
"""
    )

    return tmp_path


class TestBasicMonorepoFunctionality:
    """Test basic monorepo functionality needed for cross-project analysis."""

    def test_discover_projects_with_workspace_dependencies(self, basic_monorepo):
        """Test that workspace dependencies are properly discovered."""
        analyzer = MonorepoAnalyzer(str(basic_monorepo))
        projects = analyzer.discover_projects()

        # Should find both projects
        assert len(projects) == 2
        project_names = {p.name for p in projects}
        assert project_names == {"@test/shared", "@test/app"}

        # App should have workspace dependency on shared
        app_project = next(p for p in projects if p.name == "@test/app")
        assert "@test/shared" in app_project.workspace_dependencies

    def test_symbol_resolution_finds_cross_project_definitions(self, basic_monorepo):
        """Test that symbols can be resolved across project boundaries."""
        analyzer = MonorepoAnalyzer(str(basic_monorepo))
        context = analyzer.create_workspace_context()

        # Find references to UserService in app project
        refs = context.find_references("UserService", project="@test/app")

        # Should find at least:
        # 1. Import in app/src/main.ts
        # 2. Usage for instantiation in app/src/main.ts
        # 3. Definition in shared/src/types.ts
        assert len(refs) >= 3

        # Check we found the definition
        definition_refs = [r for r in refs if r.reference_type == "definition"]
        assert len(definition_refs) == 1
        assert "shared/src/types.ts" in definition_refs[0].file_path

    def test_type_references_across_projects(self, basic_monorepo):
        """Test finding type references across project boundaries."""
        analyzer = MonorepoAnalyzer(str(basic_monorepo))
        context = analyzer.create_workspace_context()

        # Find all references to User interface
        refs = context.find_type_references("User")

        # Should find references in both projects
        file_paths = {r.file_path for r in refs}
        assert any("shared/src/types.ts" in path for path in file_paths)
        assert any("app/src/main.ts" in path for path in file_paths)

    def test_workspace_context_includes_dependencies(self, basic_monorepo):
        """Test that workspace context properly includes project dependencies."""
        analyzer = MonorepoAnalyzer(str(basic_monorepo))

        # Analyze app project with shared context
        result = analyzer.analyze_project("@test/app", isolated=False)

        # Should resolve imports from shared project
        assert len(result.resolved_imports) > 0
        assert any("@test/shared" in imp for imp in result.resolved_imports)

        # Should have no unresolved workspace imports
        workspace_unresolved = [imp for imp in result.unresolved_imports if imp.startswith("@test/")]
        assert len(workspace_unresolved) == 0

    def test_isolated_analysis_does_not_resolve_cross_project(self, basic_monorepo):
        """Test that isolated analysis doesn't resolve cross-project imports."""
        analyzer = MonorepoAnalyzer(str(basic_monorepo))

        # Analyze app project in isolation
        result = analyzer.analyze_project("@test/app", isolated=True)

        # Should only analyze files within app project
        assert all("/app/" in f for f in result.analyzed_files)

        # Should not resolve cross-project imports
        assert len(result.resolved_imports) == 0
