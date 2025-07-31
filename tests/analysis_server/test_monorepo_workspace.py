"""
Test monorepo workspace analysis capabilities for TypeScript Analysis MCP Server.

Phase 5 tests that validate:
- Discovery of multiple tsconfig.json files across workspace
- Project dependency graph construction between TypeScript projects
- Cross-project symbol resolution in workspaces
- Isolated vs shared analysis contexts
"""

import json
from pathlib import Path

import pytest

# Import components expected in Phase 5
try:
    from aromcp.analysis_server.models.typescript_models import (
        AnalysisError,
        ReferenceInfo,
        SymbolInfo,
    )
    from aromcp.analysis_server.tools.monorepo_analyzer import (
        MonorepoAnalyzer,
        ProjectDependencyGraph,
        WorkspaceAnalysisResult,
        WorkspaceContext,
        WorkspaceProject,
    )
except ImportError:
    # Expected to fail initially - create placeholders
    class MonorepoAnalyzer:
        def __init__(self, workspace_root: str):
            self.workspace_root = workspace_root

    class WorkspaceProject:
        def __init__(self, name: str, root: str, tsconfig_path: str):
            self.name = name
            self.root = root
            self.tsconfig_path = tsconfig_path

    class ProjectDependencyGraph:
        pass

    class WorkspaceContext:
        pass

    class WorkspaceAnalysisResult:
        pass

    class AnalysisError:
        pass

    class SymbolInfo:
        pass

    class ReferenceInfo:
        pass


@pytest.fixture
def simple_monorepo(tmp_path):
    """Create a simple monorepo structure with multiple projects."""
    # Create root tsconfig
    root_tsconfig = {
        "compilerOptions": {"strict": True, "module": "commonjs", "target": "es2020"},
        "references": [{"path": "./packages/core"}, {"path": "./packages/ui"}, {"path": "./apps/web"}],
    }
    (tmp_path / "tsconfig.json").write_text(json.dumps(root_tsconfig, indent=2))

    # Create core package
    core_dir = tmp_path / "packages" / "core"
    core_dir.mkdir(parents=True)
    core_tsconfig = {
        "extends": "../../tsconfig.json",
        "compilerOptions": {"composite": True, "declaration": True, "outDir": "./dist"},
        "include": ["src/**/*"],
    }
    (core_dir / "tsconfig.json").write_text(json.dumps(core_tsconfig, indent=2))
    (core_dir / "package.json").write_text(json.dumps({"name": "@monorepo/core", "version": "1.0.0"}))

    # Create core source files
    (core_dir / "src").mkdir()
    (core_dir / "src" / "index.ts").write_text(
        """
export interface CoreConfig {
    apiUrl: string;
    version: string;
}

export class CoreService {
    constructor(private config: CoreConfig) {}
    
    getVersion(): string {
        return this.config.version;
    }
}
"""
    )

    # Create UI package that depends on core
    ui_dir = tmp_path / "packages" / "ui"
    ui_dir.mkdir(parents=True)
    ui_tsconfig = {
        "extends": "../../tsconfig.json",
        "compilerOptions": {"composite": True, "declaration": True, "jsx": "react", "outDir": "./dist"},
        "references": [{"path": "../core"}],
        "include": ["src/**/*"],
    }
    (ui_dir / "tsconfig.json").write_text(json.dumps(ui_tsconfig, indent=2))
    (ui_dir / "package.json").write_text(
        json.dumps({"name": "@monorepo/ui", "version": "1.0.0", "dependencies": {"@monorepo/core": "workspace:*"}})
    )

    # Create UI source files
    (ui_dir / "src").mkdir()
    (ui_dir / "src" / "Button.tsx").write_text(
        """
import { CoreConfig } from '@monorepo/core';

interface ButtonProps {
    config: CoreConfig;
    label: string;
    onClick: () => void;
}

export const Button: React.FC<ButtonProps> = ({ config, label, onClick }) => {
    return (
        <button onClick={onClick} data-version={config.version}>
            {label}
        </button>
    );
};
"""
    )

    # Create web app that depends on both
    web_dir = tmp_path / "apps" / "web"
    web_dir.mkdir(parents=True)
    web_tsconfig = {
        "extends": "../../tsconfig.json",
        "compilerOptions": {"jsx": "react"},
        "references": [{"path": "../../packages/core"}, {"path": "../../packages/ui"}],
        "include": ["src/**/*"],
    }
    (web_dir / "tsconfig.json").write_text(json.dumps(web_tsconfig, indent=2))
    (web_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "@monorepo/web",
                "version": "1.0.0",
                "dependencies": {"@monorepo/core": "workspace:*", "@monorepo/ui": "workspace:*"},
            }
        )
    )

    # Create web source files
    (web_dir / "src").mkdir()
    (web_dir / "src" / "App.tsx").write_text(
        """
import { CoreService, CoreConfig } from '@monorepo/core';
import { Button } from '@monorepo/ui';

const config: CoreConfig = {
    apiUrl: 'https://api.example.com',
    version: '1.0.0'
};

const service = new CoreService(config);

export const App = () => {
    return (
        <div>
            <h1>Version: {service.getVersion()}</h1>
            <Button 
                config={config} 
                label="Click me" 
                onClick={() => console.log('Clicked!')} 
            />
        </div>
    );
};
"""
    )

    return tmp_path


class TestMonorepoWorkspaceDiscovery:
    """Test discovery and analysis of monorepo workspaces."""

    def test_discover_workspace_projects(self, simple_monorepo):
        """Test discovery of all TypeScript projects in workspace."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Discover all projects
        projects = analyzer.discover_projects()

        # Should find 3 projects (root is excluded as it has no source files)
        assert len(projects) == 3, f"Expected 3 projects, found {len(projects)}"

        # Verify project names
        project_names = {p.name for p in projects}
        expected_names = {"@monorepo/core", "@monorepo/ui", "@monorepo/web"}
        assert project_names == expected_names, f"Project names mismatch: {project_names}"

        # Verify each project has correct tsconfig path
        for project in projects:
            assert project.tsconfig_path.endswith("tsconfig.json")
            assert Path(project.tsconfig_path).exists()

    def test_build_project_dependency_graph(self, simple_monorepo):
        """Test building dependency graph between projects."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Build dependency graph
        dep_graph = analyzer.build_project_dependency_graph()

        # Verify graph structure
        assert dep_graph.get_dependencies("@monorepo/web") == ["@monorepo/core", "@monorepo/ui"]
        assert dep_graph.get_dependencies("@monorepo/ui") == ["@monorepo/core"]
        assert dep_graph.get_dependencies("@monorepo/core") == []

        # Verify reverse dependencies
        assert dep_graph.get_dependents("@monorepo/core") == ["@monorepo/ui", "@monorepo/web"]
        assert dep_graph.get_dependents("@monorepo/ui") == ["@monorepo/web"]
        assert dep_graph.get_dependents("@monorepo/web") == []

        # Verify topological order for build
        build_order = dep_graph.get_build_order()
        assert build_order.index("@monorepo/core") < build_order.index("@monorepo/ui")
        assert build_order.index("@monorepo/ui") < build_order.index("@monorepo/web")

    def test_cross_project_symbol_resolution(self, simple_monorepo):
        """Test resolving symbols across project boundaries."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Initialize workspace context
        workspace_context = analyzer.create_workspace_context()

        # Resolve CoreService usage in web app
        references = workspace_context.find_references(symbol_name="CoreService", project="@monorepo/web")

        # Should find:
        # 1. Import in web/src/App.tsx
        # 2. Usage for instantiation
        assert len(references) >= 2

        # Should also find original definition in core
        definition_refs = [r for r in references if r.reference_type == "definition"]
        assert len(definition_refs) == 1
        assert "packages/core" in definition_refs[0].file_path

    def test_workspace_type_sharing(self, simple_monorepo):
        """Test type sharing across workspace projects."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))
        workspace_context = analyzer.create_workspace_context()

        # Resolve CoreConfig type usage across projects
        type_refs = workspace_context.find_type_references("CoreConfig")

        # Should find usage in:
        # 1. core/src/index.ts (definition)
        # 2. ui/src/Button.tsx (import and usage)
        # 3. web/src/App.tsx (import and usage)

        # Extract project names from paths more reliably
        project_names = set()
        for ref in type_refs:
            path_parts = Path(ref.file_path).parts
            # Find the package name (look for packages/xxx or apps/xxx)
            for i, part in enumerate(path_parts):
                if part in ("packages", "apps") and i + 1 < len(path_parts):
                    project_names.add(path_parts[i + 1])
                    break

        assert project_names >= {"core", "ui", "web"}

    def test_isolated_project_analysis(self, simple_monorepo):
        """Test analyzing single project in isolation."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Analyze core project in isolation
        core_result = analyzer.analyze_project(project_name="@monorepo/core", isolated=True)

        # Should only analyze files within core project
        assert all("/core/" in f for f in core_result.analyzed_files)

        # Should not resolve external references
        assert len(core_result.unresolved_imports) == 0  # No external imports in core

    def test_shared_context_analysis(self, simple_monorepo):
        """Test analyzing with shared workspace context."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Analyze UI project with shared context
        ui_result = analyzer.analyze_project(project_name="@monorepo/ui", isolated=False)

        # Should resolve imports from core
        assert len(ui_result.resolved_imports) > 0
        assert any("@monorepo/core" in imp for imp in ui_result.resolved_imports)

        # Should have no unresolved workspace imports
        workspace_unresolved = [imp for imp in ui_result.unresolved_imports if imp.startswith("@monorepo/")]
        assert len(workspace_unresolved) == 0


class TestMonorepoPerformance:
    """Test performance characteristics for monorepo analysis."""

    @pytest.fixture
    def large_monorepo(self, tmp_path):
        """Create a large monorepo structure for performance testing."""
        # Create 20 packages with interdependencies
        num_packages = 20

        # Root tsconfig
        root_tsconfig = {
            "compilerOptions": {"strict": True, "module": "commonjs", "target": "es2020"},
            "references": [{"path": f"./packages/pkg-{i}"} for i in range(num_packages)],
        }
        (tmp_path / "tsconfig.json").write_text(json.dumps(root_tsconfig, indent=2))

        # Create packages
        for i in range(num_packages):
            pkg_dir = tmp_path / "packages" / f"pkg-{i}"
            pkg_dir.mkdir(parents=True)

            # Package depends on previous packages (creates complex graph)
            dependencies = []
            if i > 0:
                dependencies.extend([{"path": f"../pkg-{j}"} for j in range(max(0, i - 3), i)])

            pkg_tsconfig = {
                "extends": "../../tsconfig.json",
                "compilerOptions": {"composite": True, "declaration": True, "outDir": "./dist"},
                "references": dependencies,
                "include": ["src/**/*"],
            }
            (pkg_dir / "tsconfig.json").write_text(json.dumps(pkg_tsconfig, indent=2))

            # Create source files
            (pkg_dir / "src").mkdir()
            for j in range(10):  # 10 files per package
                (pkg_dir / "src" / f"module{j}.ts").write_text(
                    f"""
export interface Interface{i}_{j} {{
    id: string;
    data: any;
}}

export class Service{i}_{j} {{
    process(item: Interface{i}_{j}): void {{
        console.log(`Processing ${{item.id}}`);
    }}
}}

export const constant{i}_{j} = {{
    name: 'Module {i}-{j}',
    version: '1.0.0'
}};
"""
                )

        return tmp_path

    def test_workspace_discovery_performance(self, large_monorepo):
        """Test performance of discovering projects in large workspace."""
        import time

        analyzer = MonorepoAnalyzer(str(large_monorepo))

        start_time = time.perf_counter()
        projects = analyzer.discover_projects()
        discovery_time = time.perf_counter() - start_time

        # Should discover all projects quickly
        assert len(projects) == 20  # 20 packages (root is excluded as it only has references)
        assert discovery_time < 1.0, f"Discovery took {discovery_time:.2f}s, expected <1s"

    def test_dependency_graph_construction_performance(self, large_monorepo):
        """Test performance of building dependency graph for complex workspace."""
        import time

        analyzer = MonorepoAnalyzer(str(large_monorepo))
        projects = analyzer.discover_projects()

        start_time = time.perf_counter()
        dep_graph = analyzer.build_project_dependency_graph()
        graph_time = time.perf_counter() - start_time

        # Should build graph efficiently
        assert graph_time < 2.0, f"Graph construction took {graph_time:.2f}s, expected <2s"

        # Verify graph has expected complexity
        total_edges = sum(len(dep_graph.get_dependencies(p.name)) for p in projects)
        assert total_edges > 30  # Complex interdependencies

    def test_parallel_project_analysis(self, large_monorepo):
        """Test parallel analysis of multiple projects."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        analyzer = MonorepoAnalyzer(str(large_monorepo))
        projects = analyzer.discover_projects()[:10]  # Analyze first 10 projects

        # Sequential analysis
        seq_start = time.perf_counter()
        seq_results = []
        for project in projects:
            result = analyzer.analyze_project(project.name, isolated=True)
            seq_results.append(result)
        seq_time = time.perf_counter() - seq_start

        # Parallel analysis
        par_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            par_results = list(executor.map(lambda p: analyzer.analyze_project(p.name, isolated=True), projects))
        par_time = time.perf_counter() - par_start

        # Parallel should be significantly faster
        speedup = seq_time / par_time
        assert speedup > 2.0, f"Parallel speedup only {speedup:.1f}x"

        # Results should be equivalent
        assert len(par_results) == len(seq_results)


class TestWorkspaceContextSharing:
    """Test context sharing and optimization in workspace analysis."""

    def test_shared_type_context_optimization(self, simple_monorepo):
        """Test that shared types are efficiently handled across projects."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))

        # Create workspace context with type sharing
        context = analyzer.create_workspace_context(enable_type_sharing=True)

        # Analyze multiple projects
        results = []
        for project in ["@monorepo/core", "@monorepo/ui", "@monorepo/web"]:
            result = context.analyze_project(project)
            results.append(result)

        # Verify shared type context
        shared_stats = context.get_shared_type_stats()

        # CoreConfig should be in shared context
        assert "CoreConfig" in shared_stats.shared_types

        # Should show reuse across projects
        assert shared_stats.reuse_count > 0
        assert shared_stats.memory_savings_mb > 0

    def test_incremental_workspace_updates(self, simple_monorepo):
        """Test incremental updates when files change in workspace."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))
        context = analyzer.create_workspace_context()

        # Initial analysis
        initial_result = context.analyze_all_projects()
        initial_symbols = initial_result.total_symbols

        # Modify a file in core
        core_index = simple_monorepo / "packages" / "core" / "src" / "index.ts"
        original_content = core_index.read_text()

        new_content = (
            original_content
            + """

export class NewService {
    getName(): string {
        return "New Service";
    }
}
"""
        )
        core_index.write_text(new_content)

        # Incremental update
        update_result = context.update_changed_files([str(core_index)])

        # Should detect new symbols (NewService class + getName method)
        assert update_result.symbols_added >= 1  # At least NewService
        assert update_result.files_reanalyzed == 1

        # Should identify affected projects
        assert "@monorepo/core" in update_result.affected_projects
        # UI and web depend on core, so they might be affected
        assert len(update_result.affected_projects) >= 1

    def test_workspace_cache_invalidation(self, simple_monorepo):
        """Test cache invalidation across project boundaries."""
        analyzer = MonorepoAnalyzer(str(simple_monorepo))
        context = analyzer.create_workspace_context()

        # Analyze and populate caches
        context.analyze_all_projects()

        # Get cache stats before change
        cache_stats_before = context.get_cache_stats()

        # Change a widely-used type
        core_index = simple_monorepo / "packages" / "core" / "src" / "index.ts"
        content = core_index.read_text()
        # Add a property to CoreConfig
        modified_content = content.replace("version: string;", "version: string;\n    environment: string;")
        core_index.write_text(modified_content)

        # Update and check invalidation
        context.update_changed_files([str(core_index)])
        cache_stats_after = context.get_cache_stats()

        # Should invalidate caches for dependent files
        assert cache_stats_after.invalidations > cache_stats_before.invalidations
        # At minimum, the changed file should be invalidated
        assert cache_stats_after.invalidations >= cache_stats_before.invalidations + 1


class TestMonorepoEdgeCases:
    """Test edge cases and error handling in monorepo analysis."""

    def test_circular_project_dependencies(self, tmp_path):
        """Test handling of circular dependencies between projects."""
        # Create projects with circular dependency
        for name in ["proj-a", "proj-b"]:
            proj_dir = tmp_path / name
            proj_dir.mkdir()

            other = "proj-b" if name == "proj-a" else "proj-a"
            tsconfig = {"compilerOptions": {"composite": True}, "references": [{"path": f"../{other}"}]}
            (proj_dir / "tsconfig.json").write_text(json.dumps(tsconfig))

        analyzer = MonorepoAnalyzer(str(tmp_path))

        # Should detect circular dependency
        with pytest.warns(UserWarning, match="Circular dependency detected"):
            dep_graph = analyzer.build_project_dependency_graph()

        # Should still create graph but mark circular dependencies
        assert dep_graph.has_circular_dependencies()
        circular_chains = dep_graph.get_circular_dependencies()
        assert len(circular_chains) > 0

    def test_missing_project_references(self, tmp_path):
        """Test handling of missing project references."""
        # Create project with reference to non-existent project
        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()

        tsconfig = {"compilerOptions": {"composite": True}, "references": [{"path": "../non-existent"}]}
        (proj_dir / "tsconfig.json").write_text(json.dumps(tsconfig))

        analyzer = MonorepoAnalyzer(str(tmp_path))
        projects = analyzer.discover_projects()

        # Should discover the project despite bad reference
        assert len(projects) == 1

        # Should report error about missing reference
        result = analyzer.analyze_project("my-project")
        assert any("non-existent" in error.message for error in result.errors)

    def test_deeply_nested_workspaces(self, tmp_path):
        """Test handling of deeply nested workspace structures."""
        # Create deeply nested structure
        current = tmp_path
        for i in range(5):  # 5 levels deep
            current = current / f"level-{i}"
            current.mkdir()

            tsconfig = {"compilerOptions": {"composite": True}, "include": ["src/**/*"]}
            (current / "tsconfig.json").write_text(json.dumps(tsconfig))

            (current / "src").mkdir()
            (current / "src" / "index.ts").write_text(f"export const level = {i};")

        analyzer = MonorepoAnalyzer(str(tmp_path))
        projects = analyzer.discover_projects()

        # Should find all nested projects
        assert len(projects) == 5

        # Should maintain correct paths
        for project in projects:
            assert Path(project.tsconfig_path).exists()
