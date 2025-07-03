"""Find imports for files implementation."""

import ast
import os
import re
import time
from pathlib import Path
from typing import Any

from ...utils.pagination import paginate_list
from .._security import validate_file_path_legacy


def find_imports_for_files_impl(
    file_paths: str | list[str],
    project_root: str = ".",
    search_patterns: str | list[str] | None = None,
    expand_patterns: bool = True,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Identify which files import the given files (dependency analysis).
    
    Args:
        file_paths: List of files or glob patterns to find importers for
        project_root: Root directory of the project
        search_patterns: File patterns to search in (defaults to common code files)
        expand_patterns: Whether to expand glob patterns in file_paths (default: True)
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)
        
    Returns:
        Dictionary with paginated import analysis results
    """
    start_time = time.time()

    try:
        # Normalize file_paths to list
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        # Normalize search_patterns to list if string
        if isinstance(search_patterns, str):
            search_patterns = [search_patterns]

        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root does not exist: {project_root}"
                }
            }

        # Default search patterns for common code files
        if search_patterns is None:
            search_patterns = [
                "**/*.py",
                "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx",
                "**/*.vue", "**/*.svelte",
                "**/*.go", "**/*.rs", "**/*.java", "**/*.kt",
                "**/*.cpp", "**/*.c", "**/*.h", "**/*.hpp"
            ]

        # Expand patterns in file_paths if requested
        if expand_patterns:
            expanded_paths = []
            for file_path in file_paths:
                if any(char in file_path for char in ['*', '?', '[', ']']):
                    # This looks like a glob pattern
                    matches = list(project_path.glob(file_path))
                    if matches:
                        for match in matches:
                            if match.is_file():
                                try:
                                    rel_path = match.relative_to(project_path)
                                    expanded_paths.append(str(rel_path))
                                except ValueError:
                                    # Skip files outside project root
                                    continue
                    else:
                        # No matches found, keep original path for error reporting
                        expanded_paths.append(file_path)
                else:
                    # Not a pattern, use as-is
                    expanded_paths.append(file_path)

            # Remove duplicates while preserving order
            seen = set()
            actual_file_paths = []
            for path in expanded_paths:
                if path not in seen:
                    seen.add(path)
                    actual_file_paths.append(path)
        else:
            actual_file_paths = file_paths

        # Validate target files
        target_files = {}
        for file_path in actual_file_paths:
            abs_path = validate_file_path_legacy(file_path, project_path)
            if abs_path.exists():
                target_files[file_path] = {
                    "abs_path": abs_path,
                    "module_names": _generate_module_names(file_path, abs_path, project_path)
                }

        # Find all files to search
        search_files = _find_search_files(project_path, search_patterns)

        # Analyze imports in each search file
        import_results = {}
        for target_file in actual_file_paths:
            import_results[target_file] = {
                "importers": [],
                "import_count": 0,
                "module_names": target_files.get(target_file, {}).get("module_names", []),
                "file_exists": target_file in target_files
            }

        for search_file in search_files:
            try:
                imports_found = _analyze_file_imports(search_file, target_files, project_path)

                for target_file, import_info in imports_found.items():
                    if import_info:
                        rel_search_path = search_file.relative_to(project_path)

                        import_results[target_file]["importers"].append({
                            "file": str(rel_search_path),
                            "imports": import_info,
                            "import_types": list(set(imp["type"] for imp in import_info))
                        })
                        import_results[target_file]["import_count"] += len(import_info)

            except Exception:
                # Skip files that can't be parsed, but don't fail the whole operation
                continue

        # Sort importers by file path for consistent output
        for result in import_results.values():
            result["importers"].sort(key=lambda x: x["file"])

        duration_ms = int((time.time() - start_time) * 1000)

        # Create a flat list of all importers for pagination
        all_importers = []
        for target_file, result in import_results.items():
            for importer in result["importers"]:
                importer_with_target = importer.copy()
                importer_with_target["target_file"] = target_file
                all_importers.append(importer_with_target)

        # Create metadata for pagination
        metadata = {
            "imports_by_file": import_results,  # Include the original structure for reference
            "summary": {
                "target_files": len(actual_file_paths),
                "input_patterns": len(file_paths),
                "searched_files": len(search_files),
                "total_importers": sum(len(r["importers"]) for r in import_results.values()),
                "total_imports": sum(r["import_count"] for r in import_results.values()),
                "patterns_expanded": expand_patterns,
                "duration_ms": duration_ms
            }
        }

        # Apply pagination with deterministic sorting
        # Sort by target_file, then by importer file path
        return paginate_list(
            items=all_importers,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: (x.get("target_file", ""), x.get("file", "")),
            metadata=metadata
        )

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to find imports: {str(e)}"
            }
        }




def _generate_module_names(file_path: str, abs_path: Path, project_root: Path) -> list[str]:
    """Generate possible module names for a file."""
    module_names = []

    # Get relative path from project root
    try:
        rel_path = abs_path.relative_to(project_root)
    except ValueError:
        return module_names

    # Remove file extension
    path_without_ext = rel_path.with_suffix('')

    # Convert path separators to dots for Python-style imports
    python_module = str(path_without_ext).replace(os.sep, '.')
    module_names.append(python_module)

    # Add variations for different import styles
    path_parts = path_without_ext.parts

    # For nested files, add parent directory imports
    if len(path_parts) > 1:
        for i in range(1, len(path_parts)):
            partial_module = '.'.join(path_parts[i:])
            module_names.append(partial_module)

    # Add the file path itself (for relative imports)
    module_names.append(str(rel_path))
    module_names.append(str(path_without_ext))

    # Add basename without extension
    module_names.append(abs_path.stem)

    return list(set(module_names))  # Remove duplicates


def _find_search_files(project_path: Path, search_patterns: list[str]) -> list[Path]:
    """Find all files matching search patterns."""
    search_files = set()

    for pattern in search_patterns:
        matches = project_path.glob(pattern)
        for match in matches:
            if match.is_file():
                search_files.add(match)

    return list(search_files)


def _analyze_file_imports(
    file_path: Path,
    target_files: dict[str, dict[str, Any]],
    project_root: Path
) -> dict[str, list[dict[str, Any]]]:
    """Analyze imports in a single file."""

    file_extension = file_path.suffix.lower()

    if file_extension == '.py':
        return _analyze_python_imports(file_path, target_files, project_root)
    elif file_extension in ['.js', '.jsx', '.ts', '.tsx']:
        return _analyze_javascript_imports(file_path, target_files, project_root)
    else:
        # Generic text-based search for other file types
        return _analyze_generic_imports(file_path, target_files, project_root)


def _analyze_python_imports(
    file_path: Path,
    target_files: dict[str, dict[str, Any]],
    project_root: Path
) -> dict[str, list[dict[str, Any]]]:
    """Analyze Python imports using AST."""

    results = {target: [] for target in target_files.keys()}

    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        class ImportVisitor(ast.NodeVisitor):
            def __init__(self):
                self.imports = []

            def visit_Import(self, node):
                for alias in node.names:
                    self.imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno
                    })

            def visit_ImportFrom(self, node):
                module = node.module or ""
                for alias in node.names:
                    self.imports.append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "level": node.level  # Relative import level
                    })

        visitor = ImportVisitor()
        visitor.visit(tree)

        # Match imports against target files
        for target_file, target_info in target_files.items():
            module_names = target_info["module_names"]

            for import_info in visitor.imports:
                matched = False

                if import_info["type"] == "import":
                    # Direct module import
                    if import_info["module"] in module_names:
                        results[target_file].append(import_info)
                        matched = True

                elif import_info["type"] == "from_import":
                    # From import - check if module matches
                    if import_info["module"] in module_names:
                        results[target_file].append(import_info)
                        matched = True

                    # Also check if full path matches (module.name)
                    if import_info["module"]:
                        full_import = f"{import_info['module']}.{import_info['name']}"
                        if any(name.endswith(full_import) for name in module_names):
                            results[target_file].append(import_info)
                            matched = True

        return results

    except (SyntaxError, UnicodeDecodeError):
        # If we can't parse the Python file, fall back to text search
        return _analyze_generic_imports(file_path, target_files, project_root)


def _analyze_javascript_imports(
    file_path: Path,
    target_files: dict[str, dict[str, Any]],
    project_root: Path
) -> dict[str, list[dict[str, Any]]]:
    """Analyze JavaScript/TypeScript imports using regex."""

    results = {target: [] for target in target_files.keys()}

    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')

        # Patterns for different import types
        import_patterns = [
            # ES6 imports: import ... from '...'
            (r"import\s+(.+?)\s+from\s+['\"](.+?)['\"]", "es6_import"),
            # CommonJS: require('...')
            (r"require\s*\(\s*['\"](.+?)['\"]\s*\)", "require"),
            # Dynamic imports: import('...')
            (r"import\s*\(\s*['\"](.+?)['\"]\s*\)", "dynamic_import"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, import_type in import_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    if import_type == "es6_import":
                        imported_items = match.group(1).strip()
                        module_path = match.group(2)
                    else:
                        imported_items = None
                        module_path = match.group(1)

                    # Check against target files
                    for target_file, target_info in target_files.items():
                        if _matches_js_import(module_path, target_file, target_info, project_root, file_path):
                            results[target_file].append({
                                "type": import_type,
                                "module_path": module_path,
                                "imported_items": imported_items,
                                "line": line_num
                            })

        return results

    except UnicodeDecodeError:
        return _analyze_generic_imports(file_path, target_files, project_root)


def _matches_js_import(
    import_path: str,
    target_file: str,
    target_info: dict[str, Any],
    project_root: Path,
    importing_file: Path
) -> bool:
    """Check if a JavaScript import path matches a target file."""

    # Handle relative imports
    if import_path.startswith('./') or import_path.startswith('../'):
        # Resolve relative to the importing file
        importing_dir = importing_file.parent
        resolved_path = (importing_dir / import_path).resolve()

        # Try with and without common extensions
        for ext in ['', '.js', '.ts', '.jsx', '.tsx', '.json']:
            test_path = resolved_path.with_suffix(ext)
            if test_path == target_info["abs_path"]:
                return True

            # Also try index files
            if test_path.is_dir():
                for index_file in ['index.js', 'index.ts', 'index.jsx', 'index.tsx']:
                    if (test_path / index_file) == target_info["abs_path"]:
                        return True

    # Handle absolute imports (from node_modules or project root)
    else:
        # Check if it matches any of the module names
        target_stem = target_info["abs_path"].stem
        if import_path == target_stem or import_path.endswith(f"/{target_stem}"):
            return True

    return False


def _analyze_generic_imports(
    file_path: Path,
    target_files: dict[str, dict[str, Any]],
    project_root: Path
) -> dict[str, list[dict[str, Any]]]:
    """Generic text-based import analysis for unsupported file types."""

    results = {target: [] for target in target_files.keys()}

    try:
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for target_file, target_info in target_files.items():
                target_stem = target_info["abs_path"].stem

                # Simple text search for file references
                if target_stem in line:
                    # Try to avoid false positives
                    if (target_stem.lower() in line.lower() and
                        (len(target_stem) > 3 or line.count(target_stem) == 1)):

                        results[target_file].append({
                            "type": "text_reference",
                            "line": line_num,
                            "context": line.strip()[:100]  # First 100 chars for context
                        })

        return results

    except UnicodeDecodeError:
        return results
