"""Tool for analyzing component/function usage patterns across the codebase."""

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

from ...filesystem_server.tools.get_target_files import get_target_files_impl
from ...filesystem_server.tools.read_files_batch import read_files_batch_impl
from .._security import validate_file_path_legacy


def analyze_component_usage_impl(
    project_root: str,
    component_patterns: list[str] | None = None,
    include_imports: bool = True
) -> dict[str, Any]:
    """Analyze component/function usage patterns across the codebase.
    
    Args:
        project_root: Root directory of the project
        component_patterns: Glob patterns for component files (defaults to common patterns)
        include_imports: Whether to track import usage in addition to direct calls
        
    Returns:
        Dictionary containing component usage analysis
    """
    try:
        # Validate project root
        project_path = Path(project_root)
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root directory does not exist: {project_root}"
                }
            }

        # Default component patterns if none provided
        if component_patterns is None:
            component_patterns = [
                "**/*.tsx",
                "**/*.jsx", 
                "**/*.ts",
                "**/*.js",
                "**/components/**/*",
                "**/hooks/**/*",
                "**/utils/**/*",
                "**/lib/**/*"
            ]

        # Get component files
        component_files_result = get_target_files_impl(
            status="pattern",
            patterns=component_patterns,
            project_root=project_root
        )
        
        if "error" in component_files_result:
            return component_files_result

        component_files = [f["absolute_path"] for f in component_files_result["data"]["files"]]
        
        if not component_files:
            return {
                "data": {
                    "components": [],
                    "usage_stats": {},
                    "unused_components": [],
                    "most_used_components": [],
                    "summary": {
                        "total_components": 0,
                        "total_usages": 0,
                        "unused_count": 0,
                        "avg_usage_per_component": 0
                    }
                }
            }

        # Read all component files
        files_content_result = read_files_batch_impl(
            file_paths=component_files,
            project_root=project_root,
            encoding="utf-8"
        )
        
        if "error" in files_content_result:
            return files_content_result

        files_content = files_content_result["data"]["files"]

        # Analyze components and their usage
        components = {}
        usage_tracker = defaultdict(lambda: {
            "import_count": 0,
            "call_count": 0,
            "files_imported_in": set(),
            "files_called_in": set(),
            "total_usage": 0
        })

        # First pass: Extract all components/functions
        for file_path, file_data in files_content.items():
            try:
                content = file_data["content"]
                file_components = _extract_components_from_file(file_path, content)
                components[file_path] = file_components
            except Exception as e:
                # Skip files that can't be parsed
                components[file_path] = []

        # Second pass: Track usage across all files
        for file_path, file_data in files_content.items():
            try:
                content = file_data["content"]
                _track_usage_in_file(file_path, content, components, usage_tracker, include_imports)
            except Exception as e:
                # Skip files that can't be analyzed
                continue

        # Process results
        component_analysis = []
        all_component_names = set()
        
        for file_path, file_components in components.items():
            for component in file_components:
                comp_name = component["name"]
                all_component_names.add(comp_name)
                
                usage_info = usage_tracker[comp_name]
                
                component_analysis.append({
                    "name": comp_name,
                    "type": component["type"],
                    "file_path": file_path,
                    "line_number": component["line_number"],
                    "is_exported": component["is_exported"],
                    "is_default_export": component["is_default_export"],
                    "import_count": usage_info["import_count"],
                    "call_count": usage_info["call_count"],
                    "total_usage": usage_info["import_count"] + usage_info["call_count"],
                    "files_imported_in": list(usage_info["files_imported_in"]),
                    "files_called_in": list(usage_info["files_called_in"]),
                    "is_unused": (usage_info["import_count"] + usage_info["call_count"]) == 0
                })

        # Sort by usage
        component_analysis.sort(key=lambda x: x["total_usage"], reverse=True)

        # Generate usage statistics
        usage_stats = {}
        for comp in component_analysis:
            usage_count = comp["total_usage"]
            if usage_count not in usage_stats:
                usage_stats[usage_count] = 0
            usage_stats[usage_count] += 1

        # Find unused components
        unused_components = [comp for comp in component_analysis if comp["is_unused"]]
        
        # Get most used components (top 10)
        most_used_components = component_analysis[:10]

        # Summary statistics
        total_components = len(component_analysis)
        total_usages = sum(comp["total_usage"] for comp in component_analysis)
        unused_count = len(unused_components)
        avg_usage = total_usages / total_components if total_components > 0 else 0

        return {
            "data": {
                "components": component_analysis,
                "usage_stats": dict(usage_stats),
                "unused_components": unused_components,
                "most_used_components": most_used_components,
                "summary": {
                    "total_components": total_components,
                    "total_usages": total_usages,
                    "unused_count": unused_count,
                    "avg_usage_per_component": round(avg_usage, 2),
                    "files_analyzed": len(component_files)
                }
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to analyze component usage: {str(e)}"
            }
        }


def _extract_components_from_file(file_path: str, content: str) -> List[Dict[str, Any]]:
    """Extract components/functions from a single file."""
    components = []
    file_extension = Path(file_path).suffix.lower()
    
    if file_extension == ".py":
        components.extend(_extract_python_components(content))
    elif file_extension in [".ts", ".tsx", ".js", ".jsx"]:
        components.extend(_extract_js_ts_components(content))
    
    return components


def _extract_python_components(content: str) -> List[Dict[str, Any]]:
    """Extract Python functions and classes."""
    components = []
    
    try:
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                is_exported = not node.name.startswith("_")
                components.append({
                    "name": node.name,
                    "type": "function",
                    "line_number": node.lineno,
                    "is_exported": is_exported,
                    "is_default_export": False
                })
            elif isinstance(node, ast.ClassDef):
                is_exported = not node.name.startswith("_")
                components.append({
                    "name": node.name,
                    "type": "class",
                    "line_number": node.lineno,
                    "is_exported": is_exported,
                    "is_default_export": False
                })
    except:
        pass  # Skip files that can't be parsed
    
    return components


def _extract_js_ts_components(content: str) -> List[Dict[str, Any]]:
    """Extract JavaScript/TypeScript components and functions using regex."""
    components = []
    
    # React functional components (const/let/var Component = ...)
    component_patterns = [
        # Function declarations
        r"(?:export\s+)?(?:default\s+)?function\s+(\w+)",
        # Arrow function components with const
        r"(?:export\s+)?(?:default\s+)?const\s+(\w+)\s*=",
        # Arrow function components with let
        r"(?:export\s+)?(?:default\s+)?let\s+(\w+)\s*=",
        # Arrow function components with var
        r"(?:export\s+)?(?:default\s+)?var\s+(\w+)\s*=",
        # Class components
        r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",
    ]
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        for pattern in component_patterns:
            match = re.search(pattern, line_stripped)
            if match:
                name = match.group(1)
                is_exported = "export" in line_stripped
                is_default_export = "default" in line_stripped
                
                # Determine type based on pattern and context
                if "class" in line_stripped.lower():
                    comp_type = "class"
                elif name[0].isupper():
                    comp_type = "component"
                else:
                    comp_type = "function"
                
                components.append({
                    "name": name,
                    "type": comp_type,
                    "line_number": line_num,
                    "is_exported": is_exported,
                    "is_default_export": is_default_export
                })
                break
    
    return components


def _track_usage_in_file(
    file_path: str, 
    content: str, 
    all_components: Dict[str, List[Dict[str, Any]]],
    usage_tracker: Dict[str, Any],
    include_imports: bool
):
    """Track usage of components in a single file."""
    file_extension = Path(file_path).suffix.lower()
    
    # Get all component names to look for
    all_component_names = set()
    for file_components in all_components.values():
        for comp in file_components:
            all_component_names.add(comp["name"])
    
    if file_extension == ".py":
        _track_python_usage(file_path, content, all_component_names, usage_tracker, include_imports)
    elif file_extension in [".ts", ".tsx", ".js", ".jsx"]:
        _track_js_ts_usage(file_path, content, all_component_names, usage_tracker, include_imports)


def _track_python_usage(
    file_path: str,
    content: str,
    component_names: Set[str],
    usage_tracker: Dict[str, Any],
    include_imports: bool
):
    """Track Python component usage."""
    try:
        tree = ast.parse(content)
        
        if include_imports:
            # Track imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        if name in component_names:
                            usage_tracker[name]["import_count"] += 1
                            usage_tracker[name]["files_imported_in"].add(file_path)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        if name in component_names:
                            usage_tracker[name]["import_count"] += 1
                            usage_tracker[name]["files_imported_in"].add(file_path)
        
        # Track function/class calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in component_names:
                    usage_tracker[node.func.id]["call_count"] += 1
                    usage_tracker[node.func.id]["files_called_in"].add(file_path)
    except:
        pass  # Skip files that can't be parsed


def _track_js_ts_usage(
    file_path: str,
    content: str,
    component_names: Set[str],
    usage_tracker: Dict[str, Any],
    include_imports: bool
):
    """Track JavaScript/TypeScript component usage."""
    lines = content.split('\n')
    
    if include_imports:
        # Track imports using regex
        import_patterns = [
            r"import\s+\{[^}]*\b(\w+)\b[^}]*\}",  # Named imports
            r"import\s+(\w+)\s+from",              # Default imports
            r"import\s*\*\s*as\s+(\w+)\s+from",    # Namespace imports
        ]
        
        for line in lines:
            for pattern in import_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    if isinstance(match, tuple):
                        for name in match:
                            if name in component_names:
                                usage_tracker[name]["import_count"] += 1
                                usage_tracker[name]["files_imported_in"].add(file_path)
                    else:
                        if match in component_names:
                            usage_tracker[match]["import_count"] += 1
                            usage_tracker[match]["files_imported_in"].add(file_path)
    
    # Track function calls and JSX usage
    for name in component_names:
        # Function calls: name(...) or name.method(...)
        call_pattern = rf"\b{re.escape(name)}\s*\("
        call_matches = len(re.findall(call_pattern, content))
        
        # JSX usage: <Name or <name
        jsx_pattern = rf"<\s*{re.escape(name)}\b"
        jsx_matches = len(re.findall(jsx_pattern, content, re.IGNORECASE))
        
        total_calls = call_matches + jsx_matches
        if total_calls > 0:
            usage_tracker[name]["call_count"] += total_calls
            usage_tracker[name]["files_called_in"].add(file_path)