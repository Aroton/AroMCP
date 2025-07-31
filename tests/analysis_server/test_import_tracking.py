"""
Comprehensive tests for TypeScript import/export dependency tracking.

These tests define the expected behavior for Phase 2 import analysis,
including dependency graph construction, module resolution, and cross-file
symbol tracking. Tests will initially fail (RED phase) until implementation.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Import the expected import tracking components (will fail initially)
try:
    from aromcp.analysis_server.models.typescript_models import (
        AnalysisError,
        CircularDependency,
        DependencyGraph,
        ExportInfo,
        ImportAnalysisResult,
        ImportInfo,
        ModuleInfo,
    )
    from aromcp.analysis_server.tools.import_tracker import (
        ExportType,
        ImportTracker,
        ImportType,
        ModuleResolver,
    )
except ImportError as e:
    print(f"Import error: {e}")

    # Expected to fail initially - create placeholder classes for type hints
    class ImportTracker:
        pass

    class ModuleResolver:
        pass

    class ImportType:
        NAMED = "named"
        DEFAULT = "default"
        NAMESPACE = "namespace"
        SIDE_EFFECT = "side_effect"
        DYNAMIC = "dynamic"

    class ExportType:
        NAMED = "named"
        DEFAULT = "default"
        NAMESPACE = "namespace"
        RE_EXPORT = "re_export"

    class ImportInfo:
        pass

    class ExportInfo:
        pass

    class DependencyGraph:
        pass

    class ModuleInfo:
        pass

    class CircularDependency:
        pass

    class ImportAnalysisResult:
        pass

    class AnalysisError:
        pass


class TestImportTracker:
    """Test the import/export dependency tracking system."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the path to test fixtures directory."""
        return Path(__file__).parent / "fixtures"

    @pytest.fixture
    def tracker(self):
        """Create an import tracker instance."""
        # This will fail initially until implementation exists
        from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser

        parser = TypeScriptParser()
        return ImportTracker(
            parser=parser,
            resolve_node_modules=False,  # Focus on local imports for testing
            cache_enabled=True,
            max_cache_size_mb=50,
        )

    @pytest.fixture
    def dependency_project(self):
        """Create realistic project structure for dependency testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set MCP_FILE_ROOT for testing
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)

            try:
                # Create comprehensive project structure
                self._create_dependency_fixtures(temp_path)
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def _create_dependency_fixtures(self, temp_path: Path):
        """Create realistic TypeScript project for import tracking testing."""
        # Package.json for module resolution context
        (temp_path / "package.json").write_text(
            """
{
  "name": "test-project",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "react": "^18.0.0",
    "typescript": "^5.0.0"
  }
}
        """
        )

        # Base types (foundation layer)
        (temp_path / "src" / "types").mkdir(parents=True)
        (temp_path / "src" / "types" / "base.ts").write_text(
            """
export interface Entity {
    id: string;
    createdAt: Date;
    updatedAt: Date;
}

export type Status = 'active' | 'inactive' | 'pending';

export enum Priority {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high'
}
        """
        )

        (temp_path / "src" / "types" / "user.ts").write_text(
            """
import { Entity, Status } from './base';

export interface User extends Entity {
    name: string;
    email: string;
    status: Status;
}

export interface UserProfile {
    userId: string;
    avatar?: string;
    bio?: string;
}

export type UserWithProfile = User & {
    profile: UserProfile;
};
        """
        )

        (temp_path / "src" / "types" / "index.ts").write_text(
            """
// Re-export all types from base and user modules
export * from './base';
export * from './user';

// Default export for convenience
export { User as DefaultUser } from './user';
        """
        )

        # Core business logic (depends on types)
        (temp_path / "src" / "core").mkdir()
        (temp_path / "src" / "core" / "user-repository.ts").write_text(
            """
import { User, UserProfile, Status } from '../types';
import type { Entity } from '../types/base';

export class UserRepository {
    private users: Map<string, User> = new Map();
    private profiles: Map<string, UserProfile> = new Map();

    async findById(id: string): Promise<User | null> {
        return this.users.get(id) || null;
    }

    async create(userData: Omit<User, keyof Entity>): Promise<User> {
        const user: User = {
            ...userData,
            id: Date.now().toString(),
            createdAt: new Date(),
            updatedAt: new Date()
        };
        
        this.users.set(user.id, user);
        return user;
    }

    async updateStatus(id: string, status: Status): Promise<User | null> {
        const user = this.users.get(id);
        if (user) {
            user.status = status;
            user.updatedAt = new Date();
            return user;
        }
        return null;
    }

    async getProfile(userId: string): Promise<UserProfile | null> {
        return this.profiles.get(userId) || null;
    }
}
        """
        )

        (temp_path / "src" / "core" / "user-service.ts").write_text(
            """
import { UserRepository } from './user-repository';
import { User, UserProfile, UserWithProfile, Status } from '../types';
import { validateEmail } from '../utils/validation';
import { logger } from '../utils/logger';

export class UserService {
    constructor(private repository: UserRepository) {}

    async createUser(name: string, email: string): Promise<User> {
        if (!validateEmail(email)) {
            throw new Error('Invalid email format');
        }

        logger.info(`Creating user: ${name} (${email})`);
        
        return this.repository.create({
            name,
            email,
            status: 'pending' as Status
        });
    }

    async getUserWithProfile(id: string): Promise<UserWithProfile | null> {
        const user = await this.repository.findById(id);
        if (!user) return null;

        const profile = await this.repository.getProfile(id);
        if (!profile) return null;

        return { ...user, profile };
    }

    async activateUser(id: string): Promise<User | null> {
        const user = await this.repository.updateStatus(id, 'active');
        if (user) {
            logger.info(`User activated: ${user.name}`);
        }
        return user;
    }
}
        """
        )

        # Utilities (leaf dependencies)
        (temp_path / "src" / "utils").mkdir()
        (temp_path / "src" / "utils" / "validation.ts").write_text(
            r"""
export function validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

export function validateRequired(value: any, fieldName: string): void {
    if (value === null || value === undefined || value === '') {
        throw new Error(`${fieldName} is required`);
    }
}

export const validators = {
    email: validateEmail,
    required: validateRequired
};
        """
        )

        (temp_path / "src" / "utils" / "logger.ts").write_text(
            """
export interface Logger {
    info(message: string): void;
    warn(message: string): void;
    error(message: string): void;
}

class ConsoleLogger implements Logger {
    info(message: string): void {
        console.log(`[INFO] ${message}`);
    }

    warn(message: string): void {
        console.warn(`[WARN] ${message}`);
    }

    error(message: string): void {
        console.error(`[ERROR] ${message}`);
    }
}

export const logger: Logger = new ConsoleLogger();
export default logger;
        """
        )

        # API layer (depends on core and utils)
        (temp_path / "src" / "api").mkdir()
        (temp_path / "src" / "api" / "user-controller.ts").write_text(
            """
import { UserService } from '../core/user-service';
import { UserRepository } from '../core/user-repository';
import { User, UserWithProfile } from '../types';
import { logger } from '../utils/logger';

export class UserController {
    private userService: UserService;

    constructor() {
        const repository = new UserRepository();
        this.userService = new UserService(repository);
    }

    async handleCreateUser(name: string, email: string): Promise<{ user: User }> {
        try {
            const user = await this.userService.createUser(name, email);
            return { user };
        } catch (error) {
            logger.error(`Failed to create user: ${error.message}`);
            throw error;
        }
    }

    async handleGetUser(id: string): Promise<{ user: UserWithProfile | null }> {
        const user = await this.userService.getUserWithProfile(id);
        return { user };
    }

    async handleActivateUser(id: string): Promise<{ success: boolean }> {
        const user = await this.userService.activateUser(id);
        return { success: user !== null };
    }
}
        """
        )

        # Main application entry point
        (temp_path / "src" / "main.ts").write_text(
            """
import { UserController } from './api/user-controller';
import { logger } from './utils/logger';
import type { User } from './types';

// Dynamic import example
async function loadConfig(): Promise<any> {
    const config = await import('./config/app-config.json');
    return config.default;
}

class Application {
    private userController: UserController;

    constructor() {
        this.userController = new UserController();
    }

    async start(): Promise<void> {
        logger.info('Starting application...');
        
        try {
            const config = await loadConfig();
            logger.info(`Loaded config: ${JSON.stringify(config)}`);
        } catch (error) {
            logger.warn('Failed to load config, using defaults');
        }

        logger.info('Application started successfully');
    }

    getUserController(): UserController {
        return this.userController;
    }
}

export { Application };
export default Application;
        """
        )

        # Configuration file (JSON import)
        (temp_path / "src" / "config").mkdir()
        (temp_path / "src" / "config" / "app-config.json").write_text(
            """
{
    "appName": "Test Application",
    "version": "1.0.0",
    "environment": "development"
}
        """
        )

        # Circular dependency example
        (temp_path / "src" / "circular").mkdir()
        (temp_path / "src" / "circular" / "module-a.ts").write_text(
            """
import { ModuleB } from './module-b';

export class ModuleA {
    private moduleB: ModuleB;

    constructor() {
        this.moduleB = new ModuleB();
    }

    callB(): string {
        return this.moduleB.fromB();
    }

    fromA(): string {
        return 'Hello from A';
    }
}
        """
        )

        (temp_path / "src" / "circular" / "module-b.ts").write_text(
            """
import { ModuleA } from './module-a';

export class ModuleB {
    callA(): string {
        const moduleA = new ModuleA();
        return moduleA.fromA();
    }

    fromB(): string {
        return 'Hello from B';
    }
}
        """
        )

        # External library usage
        (temp_path / "src" / "components").mkdir()
        (temp_path / "src" / "components" / "user-list.tsx").write_text(
            """
import React, { useState, useEffect } from 'react';
import { User } from '../types';
import { UserController } from '../api/user-controller';

interface UserListProps {
    controller: UserController;
}

export const UserList: React.FC<UserListProps> = ({ controller }) => {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async (): Promise<void> => {
        setLoading(true);
        // Mock loading users
        setLoading(false);
    };

    return (
        <div>
            {loading ? (
                <div>Loading...</div>
            ) : (
                <ul>
                    {users.map(user => (
                        <li key={user.id}>{user.name}</li>
                    ))}
                </ul>
            )}
        </div>
    );
};
        """
        )

    def test_basic_import_detection(self, tracker, dependency_project):
        """Test detection of basic import statements."""
        user_service_file = dependency_project / "src" / "core" / "user-service.ts"

        result = tracker.analyze_imports(
            file_paths=[str(user_service_file)], include_type_imports=True, resolve_paths=True
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True
        assert isinstance(result.imports, list)
        assert len(result.imports) > 0

        # Should detect named imports
        repository_import = None
        types_import = None
        utils_imports = []

        for import_info in result.imports:
            assert isinstance(import_info, ImportInfo)
            assert import_info.import_type in [ImportType.NAMED, ImportType.DEFAULT, ImportType.NAMESPACE]
            assert import_info.source_file == str(user_service_file)

            if "user-repository" in import_info.module_path:
                repository_import = import_info
            elif import_info.module_path.endswith("types") or import_info.module_path.endswith("types/index.ts"):
                types_import = import_info
            elif "utils" in import_info.module_path:
                utils_imports.append(import_info)

        # Should find UserRepository import
        assert repository_import is not None
        assert repository_import.import_type == ImportType.NAMED
        assert "UserRepository" in repository_import.imported_names

        # Should find types import
        assert types_import is not None
        assert repository_import.import_type == ImportType.NAMED
        assert len(types_import.imported_names) > 0

        # Should find utility imports
        assert len(utils_imports) >= 2  # validateEmail and logger

    def test_export_detection(self, tracker, dependency_project):
        """Test detection of export statements."""
        types_index_file = dependency_project / "src" / "types" / "index.ts"

        result = tracker.analyze_exports(file_paths=[str(types_index_file)], include_re_exports=True)

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True
        assert isinstance(result.exports, list)
        assert len(result.exports) > 0

        # Should detect re-exports
        re_exports = [exp for exp in result.exports if exp.export_type == ExportType.RE_EXPORT]
        assert len(re_exports) >= 2  # from base and user modules

        # Should detect default export
        default_exports = [exp for exp in result.exports if exp.export_type == ExportType.DEFAULT]
        assert len(default_exports) >= 1  # DefaultUser

        for export_info in result.exports:
            assert isinstance(export_info, ExportInfo)
            assert export_info.source_file == str(types_index_file)
            assert export_info.export_type in [ExportType.NAMED, ExportType.DEFAULT, ExportType.RE_EXPORT]

    def test_dependency_graph_construction(self, tracker, dependency_project):
        """Test construction of module dependency graph."""
        # Analyze all TypeScript files in the project
        project_files = []
        for file_path in dependency_project.rglob("*.ts"):
            if not file_path.name.endswith(".test.ts"):
                project_files.append(str(file_path))

        result = tracker.build_dependency_graph(
            file_paths=project_files,
            include_external_modules=False,  # Focus on internal dependencies
            resolve_circular_deps=True,
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True
        assert hasattr(result, "dependency_graph")
        assert isinstance(result.dependency_graph, DependencyGraph)

        graph = result.dependency_graph

        # Should have nodes for each module
        assert hasattr(graph, "nodes")
        assert hasattr(graph, "edges")
        assert len(graph.nodes) >= len(project_files)

        # Should detect dependency relationships
        assert len(graph.edges) > 0

        # Verify specific dependency relationships
        user_service_node = None
        user_repo_node = None

        for node in graph.nodes:
            if node.file_path.endswith("user-service.ts"):
                user_service_node = node
            elif node.file_path.endswith("user-repository.ts"):
                user_repo_node = node

        assert user_service_node is not None
        assert user_repo_node is not None

        # UserService should depend on UserRepository
        service_dependencies = [edge.target for edge in graph.edges if edge.source == user_service_node.module_id]
        assert user_repo_node.module_id in service_dependencies

    def test_circular_dependency_detection(self, tracker, dependency_project):
        """Test detection of circular dependencies."""
        circular_files = [
            str(dependency_project / "src" / "circular" / "module-a.ts"),
            str(dependency_project / "src" / "circular" / "module-b.ts"),
        ]

        result = tracker.build_dependency_graph(
            file_paths=circular_files, include_external_modules=False, resolve_circular_deps=True, detect_cycles=True
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should detect circular dependencies
        assert hasattr(result, "circular_dependencies")
        assert isinstance(result.circular_dependencies, list)
        assert len(result.circular_dependencies) > 0

        # Should find the A -> B -> A cycle
        cycle = result.circular_dependencies[0]
        assert isinstance(cycle, CircularDependency)
        assert hasattr(cycle, "cycle_path")
        assert hasattr(cycle, "cycle_length")

        # Cycle should include both modules
        cycle_modules = [node.file_path for node in cycle.cycle_path]
        assert any("module-a.ts" in path for path in cycle_modules)
        assert any("module-b.ts" in path for path in cycle_modules)
        assert cycle.cycle_length == 2

    def test_module_resolution(self, tracker, dependency_project):
        """Test resolution of module paths to actual files."""
        # Test various import path styles
        test_imports = [
            ("../types", dependency_project / "src" / "core" / "user-service.ts"),
            ("./user-repository", dependency_project / "src" / "core" / "user-service.ts"),
            ("../utils/validation", dependency_project / "src" / "core" / "user-service.ts"),
        ]

        for import_path, from_file in test_imports:
            resolved_path = tracker.resolve_module_path(
                import_path=import_path, from_file=str(from_file), project_root=str(dependency_project)
            )

            assert resolved_path is not None
            assert isinstance(resolved_path, str)
            assert Path(resolved_path).exists()

            # Should resolve to correct file
            if import_path == "../types":
                assert resolved_path.endswith("types/index.ts")
            elif import_path == "./user-repository":
                assert resolved_path.endswith("user-repository.ts")
            elif import_path == "../utils/validation":
                assert resolved_path.endswith("validation.ts")

    def test_type_only_imports(self, tracker, dependency_project):
        """Test handling of TypeScript type-only imports."""
        user_repo_file = dependency_project / "src" / "core" / "user-repository.ts"

        result = tracker.analyze_imports(
            file_paths=[str(user_repo_file)], include_type_imports=True, distinguish_type_imports=True
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should distinguish between value and type imports
        type_imports = [imp for imp in result.imports if imp.is_type_only]
        value_imports = [imp for imp in result.imports if not imp.is_type_only]

        # Should find type-only import for Entity
        entity_type_import = None
        for imp in type_imports:
            if "Entity" in imp.imported_names:
                entity_type_import = imp
                break

        assert entity_type_import is not None
        assert entity_type_import.is_type_only is True
        assert "Entity" in entity_type_import.imported_names

    def test_dynamic_imports(self, tracker, dependency_project):
        """Test detection of dynamic imports."""
        main_file = dependency_project / "src" / "main.ts"

        result = tracker.analyze_imports(
            file_paths=[str(main_file)], include_dynamic_imports=True, analyze_import_expressions=True
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should detect dynamic import() expressions
        dynamic_imports = [imp for imp in result.imports if imp.import_type == ImportType.DYNAMIC]
        assert len(dynamic_imports) > 0

        # Should find the config file dynamic import
        config_import = None
        for imp in dynamic_imports:
            if "app-config.json" in imp.module_path:
                config_import = imp
                break

        assert config_import is not None
        assert config_import.import_type == ImportType.DYNAMIC
        assert config_import.is_async is True

    def test_external_module_handling(self, tracker, dependency_project):
        """Test handling of external module imports (node_modules)."""
        react_component_file = dependency_project / "src" / "components" / "user-list.tsx"

        result = tracker.analyze_imports(
            file_paths=[str(react_component_file)],
            include_external_modules=True,
            resolve_node_modules=False,  # Don't actually resolve for testing
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should detect React import
        react_import = None
        for imp in result.imports:
            if imp.module_path == "react":
                react_import = imp
                break

        assert react_import is not None
        assert react_import.import_type == ImportType.DEFAULT
        assert react_import.is_external is True
        assert "React" in react_import.imported_names or react_import.default_import == "React"

        # Should also detect named imports from React
        react_named_imports = [
            imp for imp in result.imports if imp.module_path == "react" and imp.import_type == ImportType.NAMED
        ]
        assert len(react_named_imports) > 0

        # Should find useState and useEffect
        react_hooks = set()
        for imp in react_named_imports:
            react_hooks.update(imp.imported_names)

        assert "useState" in react_hooks
        assert "useEffect" in react_hooks

    def test_import_analysis_performance(self, tracker, dependency_project):
        """Test performance of import analysis on realistic project."""
        # Get all TypeScript files
        all_files = []
        for file_path in dependency_project.rglob("*.ts"):
            all_files.append(str(file_path))
        for file_path in dependency_project.rglob("*.tsx"):
            all_files.append(str(file_path))

        start_time = time.perf_counter()

        result = tracker.build_dependency_graph(
            file_paths=all_files, include_external_modules=True, resolve_circular_deps=True, detect_cycles=True
        )

        end_time = time.perf_counter()
        analysis_time = end_time - start_time

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should complete within reasonable time
        assert analysis_time < 10.0, f"Import analysis took {analysis_time:.2f}s, should be <10s"

        # Should provide performance statistics
        assert hasattr(result.dependency_graph, "analysis_stats")
        stats = result.dependency_graph.analysis_stats

        assert hasattr(stats, "files_analyzed")
        assert hasattr(stats, "imports_resolved")
        assert hasattr(stats, "exports_found")
        assert hasattr(stats, "analysis_time_ms")

        assert stats.files_analyzed >= len(all_files)
        assert stats.imports_resolved > 0
        assert stats.analysis_time_ms > 0

    def test_import_caching_behavior(self, tracker, dependency_project):
        """Test caching of import analysis results."""
        user_service_file = str(dependency_project / "src" / "core" / "user-service.ts")

        # First analysis - cache miss
        start_time = time.perf_counter()
        result1 = tracker.analyze_imports(file_paths=[user_service_file], include_type_imports=True, resolve_paths=True)
        first_time = time.perf_counter() - start_time

        # Second analysis - should use cache
        start_time = time.perf_counter()
        result2 = tracker.analyze_imports(file_paths=[user_service_file], include_type_imports=True, resolve_paths=True)
        second_time = time.perf_counter() - start_time

        assert isinstance(result1, ImportAnalysisResult)
        assert isinstance(result2, ImportAnalysisResult)
        assert result1.success is True
        assert result2.success is True

        # Results should be identical
        assert len(result1.imports) == len(result2.imports)

        # Second analysis should be significantly faster
        assert (
            second_time < first_time / 2
        ), f"Cache didn't improve performance: {first_time:.3f}s vs {second_time:.3f}s"

        # Should provide cache statistics
        cache_stats = tracker.get_cache_stats()
        assert hasattr(cache_stats, "hits")
        assert hasattr(cache_stats, "misses")
        assert hasattr(cache_stats, "hit_rate")
        assert cache_stats.hits > 0

    def test_error_handling_during_import_analysis(self, tracker, dependency_project):
        """Test error handling during import analysis."""
        # Mix valid and invalid files
        mixed_files = [
            str(dependency_project / "src" / "types" / "user.ts"),  # Valid
            "/nonexistent/module.ts",  # Invalid
            str(dependency_project / "src" / "utils" / "logger.ts"),  # Valid
        ]

        result = tracker.analyze_imports(file_paths=mixed_files, include_type_imports=True, continue_on_error=True)

        assert isinstance(result, ImportAnalysisResult)
        # Should partially succeed
        assert len(result.imports) > 0
        assert len(result.errors) > 0

        # Should have structured errors
        file_error = None
        for error in result.errors:
            assert isinstance(error, AnalysisError)
            assert error.code in ["NOT_FOUND", "PARSE_ERROR", "RESOLUTION_ERROR"]
            if "/nonexistent/module.ts" in error.file:
                file_error = error

        assert file_error is not None
        assert file_error.code == "NOT_FOUND"

    def test_import_analysis_with_pagination(self, tracker, dependency_project):
        """Test pagination support for large import analysis results."""
        # Get all project files
        all_files = []
        for file_path in dependency_project.rglob("*.ts"):
            all_files.append(str(file_path))

        # Test with pagination
        result = tracker.build_dependency_graph(
            file_paths=all_files, include_external_modules=True, page=1, max_tokens=8000  # Limit to test pagination
        )

        assert isinstance(result, ImportAnalysisResult)
        assert result.success is True

        # Should include pagination metadata
        assert hasattr(result, "total")
        assert hasattr(result, "page_size")
        assert hasattr(result, "next_cursor")
        assert hasattr(result, "has_more")

        # Verify pagination fields
        assert isinstance(result.total, int)
        assert result.total >= 0
        assert isinstance(result.has_more, bool)

        # If paginated, should have reasonable limits
        if result.has_more:
            assert result.next_cursor is not None
            total_items = len(result.imports) + len(result.exports)
            if hasattr(result, "dependency_graph") and result.dependency_graph:
                total_items += len(result.dependency_graph.nodes) + len(result.dependency_graph.edges)
            assert total_items > 0

    def test_module_info_extraction(self, tracker, dependency_project):
        """Test extraction of detailed module information."""
        types_user_file = dependency_project / "src" / "types" / "user.ts"

        result = tracker.get_module_info(
            file_path=str(types_user_file), include_dependencies=True, include_dependents=True, analyze_exports=True
        )

        assert isinstance(result, ModuleInfo)
        assert result.file_path == str(types_user_file)
        assert hasattr(result, "imports")
        assert hasattr(result, "exports")
        assert hasattr(result, "dependencies")
        assert hasattr(result, "dependents")

        # Should have imports from './base'
        base_import = None
        for imp in result.imports:
            if imp.module_path.endswith("base.ts") or "base" in imp.module_path:
                base_import = imp
                break

        assert base_import is not None
        assert "Entity" in base_import.imported_names
        assert "Status" in base_import.imported_names

        # Should have exports
        assert len(result.exports) > 0
        export_names = set()
        for exp in result.exports:
            if exp.export_type == ExportType.NAMED:
                export_names.update(exp.exported_names)

        assert "User" in export_names
        assert "UserProfile" in export_names
        assert "UserWithProfile" in export_names
