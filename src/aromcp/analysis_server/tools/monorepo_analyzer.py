"""
Monorepo workspace analysis for TypeScript Analysis MCP Server.

This module provides comprehensive monorepo support including:
- Discovery of multiple tsconfig.json files across workspace
- Project dependency graph construction between TypeScript projects
- Cross-project symbol resolution in workspaces
- Isolated vs shared analysis contexts
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
import networkx as nx

from ..models.typescript_models import (
    AnalysisError,
    SymbolInfo,
    ReferenceInfo,
    AnalysisStats,
    MemoryStats,
)
from .typescript_parser import TypeScriptParser, ResolutionDepth
from .symbol_resolver import SymbolResolver
from .import_tracker import ImportTracker


@dataclass
class WorkspaceProject:
    """Information about a TypeScript project in the workspace."""
    name: str  # Project name from package.json
    root: str  # Project root directory
    tsconfig_path: str  # Path to tsconfig.json
    package_json_path: str | None = None  # Path to package.json if exists
    references: List[str] = field(default_factory=list)  # Project references
    source_files: List[str] = field(default_factory=list)  # Source files in project
    dependencies: List[str] = field(default_factory=list)  # NPM dependencies
    workspace_dependencies: List[str] = field(default_factory=list)  # Workspace deps


@dataclass
class ProjectDependencyGraph:
    """Dependency graph between workspace projects."""
    projects: Dict[str, WorkspaceProject] = field(default_factory=dict)
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    
    def get_dependencies(self, project_name: str) -> List[str]:
        """Get direct dependencies of a project."""
        if project_name not in self.graph:
            return []
        return list(self.graph.predecessors(project_name))
    
    def get_dependents(self, project_name: str) -> List[str]:
        """Get direct dependents of a project."""
        if project_name not in self.graph:
            return []
        return list(self.graph.successors(project_name))
    
    def get_build_order(self) -> List[str]:
        """Get topological sort order for building projects."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            # Handle cycles by returning partial order
            return list(self.graph.nodes())
    
    def has_circular_dependencies(self) -> bool:
        """Check if there are circular dependencies."""
        return not nx.is_directed_acyclic_graph(self.graph)
    
    def get_circular_dependencies(self) -> List[List[str]]:
        """Get all circular dependency chains."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXError:
            return []


@dataclass
class WorkspaceAnalysisResult:
    """Result of workspace analysis."""
    success: bool
    projects: Dict[str, WorkspaceProject] = field(default_factory=dict)
    dependency_graph: ProjectDependencyGraph | None = None
    analyzed_files: List[str] = field(default_factory=list)
    resolved_imports: List[str] = field(default_factory=list)
    unresolved_imports: List[str] = field(default_factory=list)
    total_symbols: int = 0
    analysis_stats: AnalysisStats = field(default_factory=AnalysisStats)
    memory_stats: MemoryStats = field(default_factory=MemoryStats)
    errors: List[AnalysisError] = field(default_factory=list)


@dataclass
class WorkspaceContext:
    """Shared context for workspace-wide analysis."""
    workspace_root: str
    projects: Dict[str, WorkspaceProject]
    dependency_graph: ProjectDependencyGraph
    symbol_resolver: SymbolResolver
    import_tracker: ImportTracker
    shared_symbols: Dict[str, SymbolInfo] = field(default_factory=dict)
    type_sharing_enabled: bool = True
    
    def find_references(self, symbol_name: str, project: str | None = None) -> List[ReferenceInfo]:
        """Find references to a symbol across the workspace."""
        references = []
        
        # Search in specified project or all projects
        if project:
            projects_to_search = [project]
            
            # Also include projects that this project depends on (for definitions)
            if project in self.projects:
                project_obj = self.projects[project]
                for dep_name in project_obj.workspace_dependencies:
                    if dep_name in self.projects:
                        projects_to_search.append(dep_name)
        else:
            projects_to_search = list(self.projects.keys())
        
        for proj_name in projects_to_search:
            if proj_name not in self.projects:
                continue
                
            project_obj = self.projects[proj_name]
            
            # Use symbol resolver to find references in project files
            for file_path in project_obj.source_files:
                file_refs = self.symbol_resolver.find_symbol_references(
                    symbol_name, file_path
                )
                references.extend(file_refs)
        
        return references
    
    def find_type_references(self, type_name: str) -> List[ReferenceInfo]:
        """Find references to a type across all projects."""
        references = []
        
        for project in self.projects.values():
            for file_path in project.source_files:
                type_refs = self.symbol_resolver.find_type_references(
                    type_name, file_path
                )
                references.extend(type_refs)
        
        return references
    
    def analyze_project(self, project_name: str, isolated: bool = False) -> WorkspaceAnalysisResult:
        """Analyze a single project with optional workspace context."""
        if project_name not in self.projects:
            return WorkspaceAnalysisResult(
                success=False,
                errors=[AnalysisError(
                    code="PROJECT_NOT_FOUND",
                    message=f"Project '{project_name}' not found in workspace"
                )]
            )
        
        project = self.projects[project_name]
        
        # Check for missing project references
        errors = []
        for ref_path in project.references:
            # Resolve the absolute path of the reference
            if not os.path.isabs(ref_path):
                abs_ref_path = os.path.join(project.root, ref_path)
            else:
                abs_ref_path = ref_path
            
            abs_ref_path = os.path.abspath(abs_ref_path)
            
            # Check if the referenced path exists and has a tsconfig.json
            tsconfig_path = os.path.join(abs_ref_path, 'tsconfig.json')
            if not os.path.exists(tsconfig_path):
                errors.append(AnalysisError(
                    code="MISSING_PROJECT_REFERENCE",
                    message=f"Project reference '{ref_path}' could not be resolved - path '{abs_ref_path}' does not exist or has no tsconfig.json"
                ))
        
        # Create isolated or shared context
        if isolated:
            # Analyze only files within this project
            context_files = project.source_files
            context_imports = []
        else:
            # Include workspace dependencies
            context_files = []
            context_imports = []
            
            # Add files from dependent projects
            for dep_name in project.workspace_dependencies:
                if dep_name in self.projects:
                    dep_project = self.projects[dep_name]
                    context_files.extend(dep_project.source_files)
            # Track cross-project imports from the main project files
            for file_path in project.source_files:
                try:
                    # Try advanced import analysis first
                    import_result = self.import_tracker.analyze_imports([file_path])
                    
                    # Always use fallback for now to avoid tree-sitter dependency issues
                    fallback_imports = self._extract_imports_fallback(file_path)
                    for module_path in fallback_imports:
                        # Check if this is a workspace import (starts with @, or matches workspace dependencies)
                        if (module_path.startswith("@") or 
                            any(dep_name in module_path for dep_name in project.workspace_dependencies)):
                            if self._can_resolve_workspace_import(module_path, context_files):
                                context_imports.append(module_path)
                except Exception as e:
                    # Try fallback import detection on error  
                    try:
                        fallback_imports = self._extract_imports_fallback(file_path)
                        for module_path in fallback_imports:
                            # Check if this is a workspace import (starts with @, or matches workspace dependencies)
                            if (module_path.startswith("@") or 
                                any(dep_name in module_path for dep_name in project.workspace_dependencies)):
                                if self._can_resolve_workspace_import(module_path, context_files):
                                    context_imports.append(module_path)
                    except Exception:
                        # Log the original error if fallback also fails
                        errors.append(AnalysisError(
                            code="IMPORT_ANALYSIS_ERROR",
                            message=f"Failed to analyze imports in {file_path}: {str(e)}",
                            file=file_path
                        ))
            
            context_files.extend(project.source_files)
        
        # Perform analysis
        analysis_result = WorkspaceAnalysisResult(success=True)
        analysis_result.projects = {project_name: project}  # Add the analyzed project to results
        analysis_result.analyzed_files = context_files
        analysis_result.resolved_imports = context_imports
        analysis_result.errors = errors
        
        # Count symbols
        total_symbols = 0
        for file_path in project.source_files:
            symbols = self.symbol_resolver.get_file_symbols(file_path)
            total_symbols += len(symbols)
        
        analysis_result.total_symbols = total_symbols
        
        return analysis_result
    
    def analyze_all_projects(self) -> WorkspaceAnalysisResult:
        """Analyze all projects in the workspace."""
        result = WorkspaceAnalysisResult(success=True)
        result.projects = self.projects.copy()
        result.dependency_graph = self.dependency_graph
        
        # Analyze each project
        all_files = set()
        total_symbols = 0
        
        for project_name in self.projects:
            project_result = self.analyze_project(project_name, isolated=False)
            
            all_files.update(project_result.analyzed_files)
            total_symbols += project_result.total_symbols
            result.errors.extend(project_result.errors)
        
        result.analyzed_files = list(all_files)
        result.total_symbols = total_symbols
        
        return result
    
    def _can_resolve_workspace_import(self, module_path: str, context_files: List[str]) -> bool:
        """Check if a workspace import can be resolved in the given context."""
        # Simple heuristic: check if any context file matches the module path pattern
        for file_path in context_files:
            # Extract the package name from scoped imports like @test/shared or @monorepo/core
            if module_path.startswith("@"):
                # Extract package name: @test/shared -> shared, @monorepo/core -> core
                package_name = module_path.split("/")[-1] if "/" in module_path else module_path
                if package_name in file_path:
                    return True
            elif module_path in file_path:
                return True
        return False
    
    def _resolve_relative_import(self, source_file: str, import_path: str) -> str | None:
        """Resolve a relative import path to an absolute path."""
        try:
            source_dir = os.path.dirname(source_file)
            resolved = os.path.abspath(os.path.join(source_dir, import_path))
            
            # Try common TypeScript extensions
            for ext in ['.ts', '.tsx', '.js', '.jsx']:
                if os.path.exists(resolved + ext):
                    return resolved + ext
            
            # Check if it's a directory with index file
            for ext in ['.ts', '.tsx', '.js', '.jsx']:
                index_path = os.path.join(resolved, 'index' + ext)
                if os.path.exists(index_path):
                    return index_path
                    
            return resolved if os.path.exists(resolved) else None
        except Exception:
            return None
    
    def _extract_imports_fallback(self, file_path: str) -> List[str]:
        """Fallback regex-based import extraction when tree-sitter fails."""
        import re
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Match import statements
            # import { ... } from 'module'
            # import * as name from 'module'  
            # import name from 'module'
            import_patterns = [
                r"import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)?\s*from\s+['\"]([^'\"]+)['\"]",
                r"import\s+['\"]([^'\"]+)['\"]",  # Side effect imports
                r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"  # Dynamic imports
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
            
            return imports
            
        except Exception:
            return []
    
    def update_changed_files(self, changed_files: List[str]) -> 'WorkspaceUpdateResult':
        """Update workspace context when files change."""
        update_result = WorkspaceUpdateResult()
        
        affected_projects = set()
        symbols_added = 0
        symbols_removed = 0
        
        for file_path in changed_files:
            # Find which project this file belongs to
            project_name = self._find_project_for_file(file_path)
            if project_name:
                affected_projects.add(project_name)
                
                # Reanalyze symbols in changed file
                old_symbols = self.symbol_resolver.get_file_symbols(file_path)
                self.symbol_resolver.reanalyze_file(file_path)
                new_symbols = self.symbol_resolver.get_file_symbols(file_path)
                
                symbols_removed += len(old_symbols)
                symbols_added += len(new_symbols)
        
        # Find transitively affected projects
        for project_name in list(affected_projects):
            dependents = self.dependency_graph.get_dependents(project_name)
            affected_projects.update(dependents)
        
        update_result.affected_projects = list(affected_projects)
        update_result.files_reanalyzed = len(changed_files)
        update_result.symbols_added = symbols_added - symbols_removed
        
        return update_result
    
    def get_shared_type_stats(self) -> 'SharedTypeStats':
        """Get statistics about shared type optimization."""
        stats = SharedTypeStats()
        
        if not self.type_sharing_enabled:
            return stats
        
        # Count shared types across projects
        type_definitions = {}  # Where types are defined
        type_usage = {}  # Where types are used
        
        # First pass: find all type definitions
        for project in self.projects.values():
            for file_path in project.source_files:
                symbols = self.symbol_resolver.get_file_symbols(file_path)
                for symbol in symbols:
                    if symbol.symbol_type in ["interface", "type", "class"]:
                        if symbol.name not in type_definitions:
                            type_definitions[symbol.name] = set()
                        type_definitions[symbol.name].add(project.name)
        
        # Second pass: find type usage through references
        for project in self.projects.values():
            for file_path in project.source_files:
                # Look for type references in this file
                for type_name in type_definitions:
                    refs = self.symbol_resolver.find_type_references(type_name, file_path)
                    if refs:
                        if type_name not in type_usage:
                            type_usage[type_name] = set()
                        type_usage[type_name].add(project.name)
        
        # Find types used across multiple projects
        shared_types = {
            type_name: projects 
            for type_name, projects in type_usage.items()
            if len(projects) > 1
        }
        
        stats.shared_types = list(shared_types.keys())
        stats.reuse_count = sum(len(projects) - 1 for projects in shared_types.values())
        stats.memory_savings_mb = stats.reuse_count * 0.1  # Estimated savings
        
        return stats
    
    def get_cache_stats(self) -> 'CacheStats':
        """Get cache statistics from workspace context."""
        cache_stats = CacheStats()
        cache_stats.symbol_cache_size = len(self.shared_symbols)
        cache_stats.cache_hit_rate = self.symbol_resolver.get_cache_hit_rate()
        cache_stats.invalidations = self.symbol_resolver.get_invalidation_count()
        return cache_stats
    
    def _find_project_for_file(self, file_path: str) -> str | None:
        """Find which project a file belongs to."""
        file_path = os.path.abspath(file_path)
        
        for project_name, project in self.projects.items():
            project_root = os.path.abspath(project.root)
            if file_path.startswith(project_root):
                return project_name
        
        return None


@dataclass
class WorkspaceUpdateResult:
    """Result of updating workspace after file changes."""
    affected_projects: List[str] = field(default_factory=list)
    files_reanalyzed: int = 0
    symbols_added: int = 0
    symbols_removed: int = 0


@dataclass
class SharedTypeStats:
    """Statistics about shared type context optimization."""
    shared_types: List[str] = field(default_factory=list)
    reuse_count: int = 0
    memory_savings_mb: float = 0.0


@dataclass
class CacheStats:
    """Cache statistics for workspace context."""
    symbol_cache_size: int = 0
    cache_hit_rate: float = 0.0
    invalidations: int = 0


class MonorepoAnalyzer:
    """Main analyzer for monorepo workspaces."""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.parser = TypeScriptParser()
        self.symbol_resolver = SymbolResolver()
        self.import_tracker = ImportTracker(self.parser)
        self.projects: Dict[str, WorkspaceProject] = {}
        self.dependency_graph: ProjectDependencyGraph | None = None
        
        # Automatically discover projects
        self.discover_projects()
    
    def discover_projects(self) -> List[WorkspaceProject]:
        """Discover all TypeScript projects in the workspace."""
        projects = []
        
        # Find all tsconfig.json files
        tsconfig_files = self._find_tsconfig_files()
        
        for tsconfig_path in tsconfig_files:
            project = self._analyze_project_config(tsconfig_path)
            if project:
                projects.append(project)
                self.projects[project.name] = project
        
        return projects
    
    def build_project_dependency_graph(self) -> ProjectDependencyGraph:
        """Build dependency graph between projects."""
        if not self.projects:
            self.discover_projects()
        
        dep_graph = ProjectDependencyGraph()
        dep_graph.projects = self.projects.copy()
        
        # Add nodes
        for project_name in self.projects:
            dep_graph.graph.add_node(project_name)
        
        # Add edges based on project references and workspace dependencies
        for project_name, project in self.projects.items():
            # Add edges from project references
            for ref_path in project.references:
                ref_project = self._resolve_project_reference(ref_path, project.root)
                if ref_project and ref_project in self.projects:
                    dep_graph.graph.add_edge(ref_project, project_name)
            
            # Add edges from workspace dependencies
            for dep_name in project.workspace_dependencies:
                if dep_name in self.projects:
                    dep_graph.graph.add_edge(dep_name, project_name)
        
        # Check for circular dependencies
        if dep_graph.has_circular_dependencies():
            import warnings
            circular_deps = dep_graph.get_circular_dependencies()
            warnings.warn(
                f"Circular dependency detected between projects: {circular_deps}",
                UserWarning
            )
        
        self.dependency_graph = dep_graph
        return dep_graph
    
    def create_workspace_context(self, enable_type_sharing: bool = True) -> WorkspaceContext:
        """Create a workspace context for cross-project analysis."""
        if not self.dependency_graph:
            self.build_project_dependency_graph()
        
        return WorkspaceContext(
            workspace_root=self.workspace_root,
            projects=self.projects,
            dependency_graph=self.dependency_graph,
            symbol_resolver=self.symbol_resolver,
            import_tracker=self.import_tracker,
            type_sharing_enabled=enable_type_sharing
        )
    
    def analyze_project(self, project_name: str, isolated: bool = False) -> WorkspaceAnalysisResult:
        """Analyze a specific project."""
        context = self.create_workspace_context()
        return context.analyze_project(project_name, isolated)
    
    def _find_tsconfig_files(self) -> List[str]:
        """Find all tsconfig.json files in the workspace."""
        tsconfig_files = []
        
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip node_modules and other common ignore patterns
            dirs[:] = [d for d in dirs if d not in {
                'node_modules', '.git', 'dist', 'build', 'coverage', '.next'
            }]
            
            if 'tsconfig.json' in files:
                tsconfig_path = os.path.join(root, 'tsconfig.json')
                tsconfig_files.append(tsconfig_path)
        
        return tsconfig_files
    
    def _analyze_project_config(self, tsconfig_path: str) -> WorkspaceProject | None:
        """Analyze a project's configuration files."""
        try:
            project_root = os.path.dirname(tsconfig_path)
            
            # Read tsconfig.json
            with open(tsconfig_path, 'r') as f:
                tsconfig = json.load(f)
            
            # Try to read package.json for project name
            package_json_path = os.path.join(project_root, 'package.json')
            project_name = None
            workspace_dependencies = []
            
            if os.path.exists(package_json_path):
                with open(package_json_path, 'r') as f:
                    package_json = json.load(f)
                    project_name = package_json.get('name', os.path.basename(project_root))
                    
                    # Extract workspace dependencies
                    deps = package_json.get('dependencies', {})
                    dev_deps = package_json.get('devDependencies', {})
                    
                    workspace_dependencies = [
                        name for name, version in {**deps, **dev_deps}.items()
                        if version.startswith('workspace:') or version.startswith('file:')
                    ]
            
            if not project_name:
                # Use directory name or "root" for workspace root
                if project_root == self.workspace_root:
                    project_name = "root"
                else:
                    project_name = os.path.basename(project_root)
            
            # Extract project references
            references = []
            if 'references' in tsconfig:
                for ref in tsconfig['references']:
                    if 'path' in ref:
                        references.append(ref['path'])
            
            # Find source files
            source_files = self._find_source_files(project_root, tsconfig)
            
            # Skip root projects that only have references 
            # These are typically workspace orchestrator configs
            if (project_root == self.workspace_root and references):
                return None
            
            return WorkspaceProject(
                name=project_name,
                root=project_root,
                tsconfig_path=tsconfig_path,
                package_json_path=package_json_path if os.path.exists(package_json_path) else None,
                references=references,
                source_files=source_files,
                workspace_dependencies=workspace_dependencies
            )
            
        except (json.JSONDecodeError, IOError) as e:
            # Return None for invalid project configs
            return None
    
    def _find_source_files(self, project_root: str, tsconfig: Dict[str, Any]) -> List[str]:
        """Find source files for a project based on tsconfig."""
        source_files = []
        
        # Get include patterns
        include_patterns = tsconfig.get('include', ['src/**/*'])
        exclude_patterns = tsconfig.get('exclude', ['node_modules', 'dist'])
        
        # Find TypeScript files
        for root, dirs, files in os.walk(project_root):
            # Apply exclude patterns
            dirs[:] = [d for d in dirs if not any(
                self._matches_pattern(d, pattern) for pattern in exclude_patterns
            )]
            
            for file in files:
                if file.endswith(('.ts', '.tsx')):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, project_root)
                    
                    # Check include patterns - be more permissive for now
                    should_include = False
                    for pattern in include_patterns:
                        if ('src' in pattern and 'src' in rel_path) or pattern == '**/*':
                            should_include = True
                            break
                        elif self._matches_pattern(rel_path, pattern):
                            should_include = True
                            break
                    
                    if should_include:
                        source_files.append(file_path)
        
        return source_files
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")
    
    def _resolve_project_reference(self, ref_path: str, project_root: str) -> str | None:
        """Resolve a project reference to a project name."""
        # Resolve relative path
        if not os.path.isabs(ref_path):
            ref_path = os.path.join(project_root, ref_path)
        
        ref_path = os.path.abspath(ref_path)
        
        # Find project with this root
        for project_name, project in self.projects.items():
            if os.path.abspath(project.root) == ref_path:
                return project_name
        
        return None