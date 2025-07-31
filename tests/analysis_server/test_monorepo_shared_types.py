"""
Test shared type optimization in monorepo.

This test focuses on the shared type context optimization feature.
"""

import json

import pytest

from aromcp.analysis_server.tools.monorepo_analyzer import MonorepoAnalyzer


@pytest.fixture
def shared_types_monorepo(tmp_path):
    """Create a monorepo where types are shared across projects."""
    # Project A defines types
    proj_a = tmp_path / "packages" / "project-a"
    proj_a.mkdir(parents=True)

    (proj_a / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"composite": True, "declaration": True}, "include": ["src/**/*"]})
    )

    (proj_a / "package.json").write_text(json.dumps({"name": "@test/project-a", "version": "1.0.0"}))

    (proj_a / "src").mkdir()
    (proj_a / "src" / "types.ts").write_text(
        """
export interface SharedType {
    id: string;
    data: any;
}

export type SharedAlias = string | number;
"""
    )

    # Project B uses types from A
    proj_b = tmp_path / "packages" / "project-b"
    proj_b.mkdir(parents=True)

    (proj_b / "tsconfig.json").write_text(
        json.dumps(
            {"compilerOptions": {"composite": True}, "references": [{"path": "../project-a"}], "include": ["src/**/*"]}
        )
    )

    (proj_b / "package.json").write_text(
        json.dumps({"name": "@test/project-b", "version": "1.0.0", "dependencies": {"@test/project-a": "workspace:*"}})
    )

    (proj_b / "src").mkdir()
    (proj_b / "src" / "usage.ts").write_text(
        """
import { SharedType, SharedAlias } from '@test/project-a';

export function processItem(item: SharedType): SharedAlias {
    return item.id;
}
"""
    )

    # Project C also uses types from A
    proj_c = tmp_path / "packages" / "project-c"
    proj_c.mkdir(parents=True)

    (proj_c / "tsconfig.json").write_text(
        json.dumps(
            {"compilerOptions": {"composite": True}, "references": [{"path": "../project-a"}], "include": ["src/**/*"]}
        )
    )

    (proj_c / "package.json").write_text(
        json.dumps({"name": "@test/project-c", "version": "1.0.0", "dependencies": {"@test/project-a": "workspace:*"}})
    )

    (proj_c / "src").mkdir()
    (proj_c / "src" / "consumer.ts").write_text(
        """
import { SharedType } from '@test/project-a';

export class Consumer {
    items: SharedType[] = [];
    
    addItem(item: SharedType): void {
        this.items.push(item);
    }
}
"""
    )

    return tmp_path


class TestSharedTypeOptimization:
    """Test shared type context optimization."""

    def test_shared_types_detected_after_analysis(self, shared_types_monorepo):
        """Test that shared types are detected after analyzing projects."""
        analyzer = MonorepoAnalyzer(str(shared_types_monorepo))
        context = analyzer.create_workspace_context(enable_type_sharing=True)

        # First, we need to analyze the projects to populate symbols
        # This is the key - we need to force symbol resolution
        for project_name in ["@test/project-a", "@test/project-b", "@test/project-c"]:
            # Get the project
            project = context.projects.get(project_name)
            if project:
                # Force symbol resolution for each file
                for file_path in project.source_files:
                    symbols = context.symbol_resolver.get_file_symbols(file_path)

        # Now check shared type stats
        stats = context.get_shared_type_stats()

        # SharedType should be detected as shared
        assert "SharedType" in stats.shared_types
        assert stats.reuse_count > 0
        assert stats.memory_savings_mb > 0

    def test_shared_types_require_multiple_projects(self, shared_types_monorepo):
        """Test that types are only considered shared if used in multiple projects."""
        analyzer = MonorepoAnalyzer(str(shared_types_monorepo))

        # Discover only project A by analyzing a subset
        project_a_path = shared_types_monorepo / "packages" / "project-a"
        analyzer_single = MonorepoAnalyzer(str(project_a_path))
        context_single = analyzer_single.create_workspace_context(enable_type_sharing=True)

        # Analyze the single project
        for project in context_single.projects.values():
            for file_path in project.source_files:
                context_single.symbol_resolver.get_file_symbols(file_path)

        # Check stats - should have no shared types with only one project
        stats = context_single.get_shared_type_stats()
        assert len(stats.shared_types) == 0
        assert stats.reuse_count == 0
