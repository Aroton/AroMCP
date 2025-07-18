"""Tool for detecting circular import dependencies in the codebase."""

import ast
import logging
import re
import traceback
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def find_import_cycles_impl(
    project_root: str, max_depth: int = 10, include_node_modules: bool = False
) -> dict[str, Any]:
    """Detect circular import dependencies in the codebase.

    Args:
        project_root: Root directory of the project
        max_depth: Maximum cycle depth to search for
        include_node_modules: Whether to include node_modules in analysis

    Returns:
        Dictionary containing detected import cycles and analysis results
    """
    try:
        # Validate project root
        project_path = Path(project_root)
        if not project_path.exists():
            return {"error": {"code": "NOT_FOUND", "message": f"Project root directory does not exist: {project_root}"}}

        # Validate max_depth
        if not 1 <= max_depth <= 50:
            return {
                "error": {"code": "INVALID_INPUT", "message": f"Max depth must be between 1 and 50, got: {max_depth}"}
            }

        # Get project files
        code_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        if not include_node_modules:
            # Exclude node_modules by filtering results
            pass  # We'll filter in _get_project_files

        project_files = _get_project_files(project_root, code_patterns, include_node_modules)

        if not project_files:
            return {"error": {"code": "NOT_FOUND", "message": "No code files found in the project"}}

        # Build dependency graph
        dependency_graph = _build_dependency_graph(project_files, project_root)

        # Find cycles
        cycles = _find_cycles_in_graph(dependency_graph, max_depth)

        # Analyze cycle severity and impact
        cycle_analysis = _analyze_cycles(cycles, dependency_graph)

        # Calculate summary statistics
        summary = _calculate_cycle_summary(cycles, dependency_graph, project_files)

        return {
            "cycles": cycle_analysis,
            "total_cycles": len(cycle_analysis),
            "files_affected": len({file for cycle in cycles for file in cycle}),
            "max_depth_searched": max_depth,
            "summary": summary,
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to find import cycles: {str(e)}",
                "traceback": traceback.format_exc(),
            }
        }


def _get_project_files(project_root: str, patterns: list[str], include_node_modules: bool) -> list[str]:
    """Get all project files matching the patterns.

    Args:
        project_root: Root directory of the project
        patterns: File patterns to match
        include_node_modules: Whether to include node_modules

    Returns:
        List of file paths
    """
    # Use pathlib directly instead of list_files_impl to avoid MCP_FILE_ROOT dependency
    from pathlib import Path

    project_path = Path(project_root)
    all_files = []

    for pattern in patterns:
        if pattern.startswith("/"):
            # Absolute pattern within project
            matches = list(project_path.glob(pattern[1:]))
        else:
            # Relative pattern
            matches = list(project_path.rglob(pattern))

        for match in matches:
            if match.is_file():
                rel_path = str(match.relative_to(project_path))

                # Filter out node_modules if not included
                if not include_node_modules and "node_modules" in rel_path:
                    continue

                all_files.append(rel_path)

    # Remove duplicates and sort
    return sorted(set(all_files))


def _build_dependency_graph(project_files: list[str], project_root: str) -> dict[str, list[str]]:
    """Build a dependency graph from import statements.

    Args:
        project_files: List of project files
        project_root: Project root directory

    Returns:
        Dictionary representing the dependency graph
    """
    graph = {}

    for file_path in project_files:
        absolute_path = Path(project_root) / file_path

        try:
            # Get imports for this file
            imports = _extract_imports_from_file(str(absolute_path), project_root)

            # Resolve import paths to actual files
            resolved_imports = _resolve_import_paths(imports, str(absolute_path), project_root)

            # Convert absolute paths to relative paths for the graph
            relative_imports = []
            for imp in resolved_imports:
                try:
                    rel_path = str(Path(imp).relative_to(Path(project_root)))
                    relative_imports.append(rel_path)
                except ValueError:
                    # If it's not relative to project, skip it
                    pass

            # Add to graph (use relative path as key)
            graph[file_path] = relative_imports

        except Exception:
            # Skip files that can't be analyzed
            graph[file_path] = []

    return graph


def _extract_imports_from_file(file_path: str, project_root: str) -> list[str]:
    """Extract import statements from a file.

    Args:
        file_path: Path to the file
        project_root: Project root directory

    Returns:
        List of import module names
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

        if file_path.endswith(".py"):
            return _extract_python_imports(content)
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            return _extract_javascript_imports(content)
        else:
            return []

    except Exception:
        return []


def _extract_python_imports(content: str) -> list[str]:
    """Extract imports from Python code using AST.

    Args:
        content: Python file content

    Returns:
        List of imported module names
    """
    imports = []

    try:
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

    except SyntaxError:
        # Fall back to regex for files with syntax errors
        imports = _extract_python_imports_regex(content)

    return imports


def _extract_python_imports_regex(content: str) -> list[str]:
    """Extract Python imports using regex as fallback.

    Args:
        content: Python file content

    Returns:
        List of imported module names
    """
    imports = []

    # Match import statements
    import_patterns = [r"^import\s+([a-zA-Z_][a-zA-Z0-9_.]*)", r"^from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import"]

    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        for pattern in import_patterns:
            match = re.match(pattern, line)
            if match:
                imports.append(match.group(1))
                break

    return imports


def _extract_javascript_imports(content: str) -> list[str]:
    """Extract imports from JavaScript/TypeScript code.

    Args:
        content: JavaScript/TypeScript file content

    Returns:
        List of imported module names
    """
    imports = []

    # Import patterns for JavaScript/TypeScript
    patterns = [
        r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"import\s+['\"]([^'\"]+)['\"]",
        r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",  # Dynamic imports
    ]

    lines = content.splitlines()
    for line in lines:
        line = line.strip()

        # Skip comments
        if line.startswith("//") or line.startswith("/*"):
            continue

        for pattern in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                import_path = match.group(1)
                # Filter out external modules (those without relative paths)
                if import_path.startswith(".") or import_path.startswith("/"):
                    imports.append(import_path)

    return imports


def _resolve_import_paths(imports: list[str], current_file: str, project_root: str) -> list[str]:
    """Resolve import paths to actual file paths.

    Args:
        imports: List of import module names
        current_file: Current file path
        project_root: Project root directory

    Returns:
        List of resolved file paths
    """
    resolved = []
    current_dir = Path(current_file).parent
    project_path = Path(project_root)

    for import_path in imports:
        try:
            # Handle different import types
            if import_path.startswith("."):
                # Relative import
                resolved_path = _resolve_relative_import(import_path, current_dir, project_path)
            elif import_path.startswith("/"):
                # Absolute import (from project root)
                resolved_path = project_path / import_path.lstrip("/")
            else:
                # Module import - try to resolve within project
                resolved_path = _resolve_module_import(import_path, project_path)

            if resolved_path and resolved_path.exists():
                resolved.append(str(resolved_path))

        except Exception as e:
            logger.warning("Failed to resolve import %s in file %s: %s", import_path, current_file, str(e))
            continue

    return resolved


def _resolve_relative_import(import_path: str, current_dir: Path, project_path: Path) -> Path | None:
    """Resolve relative import path.

    Args:
        import_path: Relative import path
        current_dir: Directory of current file
        project_path: Project root path

    Returns:
        Resolved file path or None
    """
    # Handle JavaScript-style imports (e.g., './module.js', '../utils/helper.ts')
    if "/" in import_path:
        # JavaScript/TypeScript style import
        if import_path.startswith("./"):
            # Same directory
            target_path = current_dir / import_path[2:]  # Remove './'
        elif import_path.startswith("../"):
            # Parent directory(ies)
            parts = import_path.split("/")
            target_dir = current_dir
            # Count the number of '../' parts
            up_count = 0
            remaining_parts = []
            for part in parts:
                if part == "..":
                    up_count += 1
                elif part:  # Skip empty parts
                    remaining_parts.append(part)

            # Go up the specified number of directories
            for _ in range(up_count):
                target_dir = target_dir.parent
                if not target_dir.is_relative_to(project_path):
                    return None

            # Add remaining path
            if remaining_parts:
                target_path = target_dir / "/".join(remaining_parts)
            else:
                target_path = target_dir
        else:
            # Treat as direct path from current directory
            target_path = current_dir / import_path

        # Check if the exact path exists
        if target_path.exists() and target_path.is_relative_to(project_path):
            return target_path

        # If not, try adding common extensions
        extensions = [".js", ".ts", ".jsx", ".tsx", ".py"]
        for ext in extensions:
            candidate = Path(str(target_path) + ext)
            if candidate.exists() and candidate.is_relative_to(project_path):
                return candidate

        return None

    else:
        # Python-style import (e.g., '..module.submodule')
        parts = import_path.split(".")
        up_levels = len([p for p in parts if p == ""])

        # Start from current directory and go up
        target_dir = current_dir
        for _ in range(up_levels - 1):
            target_dir = target_dir.parent
            if not target_dir.is_relative_to(project_path):
                return None

        # Add remaining path parts
        remaining_parts = [p for p in parts if p != ""]
        if remaining_parts:
            target_path = target_dir / "/".join(remaining_parts)
        else:
            target_path = target_dir

        # Try different file extensions
        extensions = [".py", ".js", ".ts", ".jsx", ".tsx", "/__init__.py", "/index.js", "/index.ts"]

        for ext in extensions:
            candidate = Path(str(target_path) + ext)
            if candidate.exists() and candidate.is_relative_to(project_path):
                return candidate

        return None


def _resolve_module_import(import_path: str, project_path: Path) -> Path | None:
    """Resolve module import within project.

    Args:
        import_path: Module import path
        project_path: Project root path

    Returns:
        Resolved file path or None
    """
    # Convert module path to file path
    module_parts = import_path.split(".")

    # Try different combinations
    candidates = []

    # Direct file match
    candidates.append(project_path / "/".join(module_parts))

    # With extensions
    for ext in [".py", ".js", ".ts"]:
        candidates.append(project_path / (f"{'/'.join(module_parts)}{ext}"))

    # As package
    candidates.append(project_path / "/".join(module_parts) / "__init__.py")
    candidates.append(project_path / "/".join(module_parts) / "index.js")
    candidates.append(project_path / "/".join(module_parts) / "index.ts")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _find_cycles_in_graph(graph: dict[str, list[str]], max_depth: int) -> list[list[str]]:
    """Find cycles in the dependency graph using DFS.

    Args:
        graph: Dependency graph
        max_depth: Maximum cycle depth to search

    Returns:
        List of cycles (each cycle is a list of file paths)
    """
    cycles = []

    def dfs(node: str, path: list[str], visited: set[str]) -> None:
        if len(path) > max_depth:
            return

        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            dfs(neighbor, path.copy(), visited.copy())

    # Start DFS from each node
    for node in graph:
        dfs(node, [], set())

    # Remove duplicate cycles
    unique_cycles = []
    seen_cycle_sets = set()

    for cycle in cycles:
        if len(cycle) <= 1:  # Skip invalid cycles
            continue

        # Normalize cycle (start from lexicographically smallest)
        cycle_nodes = cycle[:-1]  # Remove duplicate last element
        if not cycle_nodes:
            continue

        min_idx = cycle_nodes.index(min(cycle_nodes))
        normalized = cycle_nodes[min_idx:] + cycle_nodes[:min_idx] + [cycle_nodes[min_idx]]
        cycle_set = frozenset(cycle_nodes)

        if cycle_set not in seen_cycle_sets:
            seen_cycle_sets.add(cycle_set)
            unique_cycles.append(normalized)

    return unique_cycles


def _analyze_cycles(cycles: list[list[str]], graph: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Analyze cycles for severity and impact.

    Args:
        cycles: List of detected cycles
        graph: Dependency graph

    Returns:
        List of cycle analysis results
    """
    analyzed_cycles = []

    for i, cycle in enumerate(cycles):
        cycle_files = cycle[:-1]  # Remove duplicate last element

        analysis = {
            "id": f"cycle_{i + 1}",
            "files": cycle_files,
            "length": len(cycle_files),
            "severity": _calculate_cycle_severity(cycle_files, graph),
            "impact": _calculate_cycle_impact(cycle_files, graph),
            "type": _classify_cycle_type(cycle_files),
            "suggestions": _generate_cycle_suggestions(cycle_files),
        }

        analyzed_cycles.append(analysis)

    # Sort by severity (highest first)
    analyzed_cycles.sort(key=lambda x: (x["severity"], x["length"]), reverse=True)

    return analyzed_cycles


def _calculate_cycle_severity(cycle_files: list[str], graph: dict[str, list[str]]) -> int:
    """Calculate severity score for a cycle.

    Args:
        cycle_files: Files in the cycle
        graph: Dependency graph

    Returns:
        Severity score (1-10)
    """
    # Base severity on cycle length
    length_score = min(len(cycle_files), 5)

    # Consider how deeply connected the files are
    total_connections = sum(len(graph.get(file, [])) for file in cycle_files)
    connection_score = min(total_connections // len(cycle_files), 3)

    # Check if cycle involves core/important files
    importance_score = 0
    for file in cycle_files:
        if any(keyword in file.lower() for keyword in ["main", "index", "app", "core", "base"]):
            importance_score += 1

    return min(length_score + connection_score + importance_score, 10)


def _calculate_cycle_impact(cycle_files: list[str], graph: dict[str, list[str]]) -> str:
    """Calculate impact level of a cycle.

    Args:
        cycle_files: Files in the cycle
        graph: Dependency graph

    Returns:
        Impact level string
    """
    # Count how many other files depend on files in the cycle
    dependents = set()
    for file in graph:
        if file not in cycle_files:
            dependencies = graph.get(file, [])
            if any(dep in cycle_files for dep in dependencies):
                dependents.add(file)

    dependent_count = len(dependents)

    if dependent_count > 10:
        return "high"
    elif dependent_count > 3:
        return "medium"
    else:
        return "low"


def _classify_cycle_type(cycle_files: list[str]) -> str:
    """Classify the type of cycle based on file patterns.

    Args:
        cycle_files: Files in the cycle

    Returns:
        Cycle type classification
    """
    # Check file extensions
    extensions = [Path(f).suffix for f in cycle_files]

    if all(ext == ".py" for ext in extensions):
        return "python_module_cycle"
    elif all(ext in [".js", ".ts", ".jsx", ".tsx"] for ext in extensions):
        return "javascript_module_cycle"
    elif len(set(extensions)) > 1:
        return "mixed_language_cycle"
    else:
        return "unknown_cycle"


def _generate_cycle_suggestions(cycle_files: list[str]) -> list[str]:
    """Generate suggestions for breaking a cycle.

    Args:
        cycle_files: Files in the cycle

    Returns:
        List of suggestions
    """
    suggestions = [
        "Extract common functionality into a separate module",
        "Use dependency injection to break direct dependencies",
        "Consider using interfaces or abstract base classes",
        "Move shared constants/types to a separate file",
    ]

    # Add specific suggestions based on file types
    if any(f.endswith(".py") for f in cycle_files):
        suggestions.append("Use TYPE_CHECKING imports for type hints")

    if any(f.endswith((".js", ".ts")) for f in cycle_files):
        suggestions.append("Consider using barrel exports (index files)")

    return suggestions


def _generate_cycle_recommendations(cycle_analysis: list[dict[str, Any]]) -> list[str]:
    """Generate overall recommendations for dealing with cycles.

    Args:
        cycle_analysis: List of analyzed cycles

    Returns:
        List of recommendations
    """
    recommendations = []

    if not cycle_analysis:
        recommendations.append("No import cycles detected - good dependency management!")
        return recommendations

    high_severity_cycles = [c for c in cycle_analysis if c["severity"] >= 7]
    medium_severity_cycles = [c for c in cycle_analysis if 4 <= c["severity"] < 7]

    if high_severity_cycles:
        recommendations.append(f"Address {len(high_severity_cycles)} high-severity cycles immediately")

    if medium_severity_cycles:
        recommendations.append(f"Review {len(medium_severity_cycles)} medium-severity cycles")

    recommendations.extend(
        [
            "Consider implementing dependency inversion principle",
            "Use static analysis tools in your CI/CD pipeline to prevent future cycles",
            "Document intended dependency flow in your architecture",
            "Regular refactoring can help prevent cycles from forming",
        ]
    )

    return recommendations


def _calculate_cycle_summary(
    cycles: list[list[str]], graph: dict[str, list[str]], project_files: list[dict[str, Any]]
) -> dict[str, Any]:
    """Calculate summary statistics for cycle analysis.

    Args:
        cycles: Detected cycles
        graph: Dependency graph
        project_files: All project files

    Returns:
        Summary statistics
    """
    total_files = len(project_files)
    files_in_cycles = len({file for cycle in cycles for file in cycle[:-1]})

    if cycles:
        avg_cycle_length = sum(len(cycle) - 1 for cycle in cycles) / len(cycles)
        max_cycle_length = max(len(cycle) - 1 for cycle in cycles)
    else:
        avg_cycle_length = 0
        max_cycle_length = 0

    return {
        "total_files_analyzed": total_files,
        "total_cycles_found": len(cycles),
        "files_involved_in_cycles": files_in_cycles,
        "cycle_percentage": round((files_in_cycles / max(total_files, 1)) * 100, 2),
        "average_cycle_length": round(avg_cycle_length, 1),
        "maximum_cycle_length": max_cycle_length,
        "dependency_graph_size": len(graph),
        "total_dependencies": sum(len(deps) for deps in graph.values()),
    }


def _simplify_graph_for_output(graph: dict[str, list[str]]) -> dict[str, Any]:
    """Simplify dependency graph for JSON output.

    Args:
        graph: Full dependency graph

    Returns:
        Simplified graph with statistics
    """
    # Don't include the full graph in output (can be very large)
    # Instead, provide summary statistics

    most_dependencies = max(graph.keys(), key=lambda k: len(graph[k])) if graph else None
    most_depended_on = (
        max(graph.keys(), key=lambda k: sum(1 for deps in graph.values() if k in deps)) if graph else None
    )

    return {
        "total_files": len(graph),
        "total_dependencies": sum(len(deps) for deps in graph.values()),
        "avg_dependencies_per_file": round(sum(len(deps) for deps in graph.values()) / max(len(graph), 1), 2),
        "file_with_most_dependencies": (
            {
                "file": most_dependencies,
                "dependency_count": len(graph.get(most_dependencies, [])),
            }
            if most_dependencies
            else None
        ),
        "most_depended_on_file": (
            {
                "file": most_depended_on,
                "dependent_count": sum(1 for deps in graph.values() if most_depended_on in deps),
            }
            if most_depended_on
            else None
        ),
    }
