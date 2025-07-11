"""Tool for finding unused code that can potentially be removed."""

import ast
import logging
import re
from pathlib import Path
from typing import Any

from ...filesystem_server.tools.list_files import list_files_impl
from .._security import validate_file_path_legacy

logger = logging.getLogger(__name__)


def find_dead_code_impl(
    project_root: str,
    entry_points: list[str] | None = None,
    include_tests: bool = False,
    confidence_threshold: float = 0.8
) -> dict[str, Any]:
    """Find unused code that can potentially be removed.

    Args:
        project_root: Root directory of the project
        entry_points: List of entry point files (auto-detected if None)
        include_tests: Whether to include test files as entry points
        confidence_threshold: Minimum confidence score to report as dead code

    Returns:
        Dictionary containing detected dead code and analysis results
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

        # Validate confidence threshold
        if not 0.0 <= confidence_threshold <= 1.0:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": (
                        f"Confidence threshold must be between 0.0 and 1.0, "
                        f"got: {confidence_threshold}"
                    )
                }
            }

        # Get project files
        code_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        project_files = _get_project_files(project_root, code_patterns)

        # Determine entry points
        if entry_points is None:
            entry_points = _detect_entry_points(project_files, include_tests, project_root)
        else:
            # Validate provided entry points
            validated_entry_points = []
            for entry_point in entry_points:
                try:
                    validated_path = validate_file_path_legacy(
                        entry_point, project_path
                    )
                    if validated_path.exists():
                        validated_entry_points.append(str(validated_path))
                except Exception as e:
                    logger.warning(
                        "Failed to validate entry point %s: %s", entry_point, str(e)
                    )
                    continue
            entry_points = validated_entry_points

        if not entry_points:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "No entry points found or provided"
                }
            }

        # Analyze code usage
        usage_analysis = _analyze_code_usage(project_files, entry_points, project_root)

        # Find potentially dead code
        dead_code_candidates = _find_dead_code_candidates(
            usage_analysis,
            confidence_threshold
        )

        # Generate recommendations
        recommendations = _generate_dead_code_recommendations(dead_code_candidates)

        # Calculate statistics
        summary = _calculate_dead_code_summary(
            dead_code_candidates,
            project_files,
            usage_analysis,
            project_root
        )

        return {
            "data": {
                "dead_code_candidates": dead_code_candidates,
                "entry_points": entry_points,
                "usage_analysis": usage_analysis,
                "recommendations": recommendations,
                "summary": summary,
                "confidence_threshold": confidence_threshold
            }
        }

    except Exception as e:
        import traceback
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to find dead code: {str(e)}",
                "traceback": traceback.format_exc()
            }
        }


def _get_project_files(project_root: str, patterns: list[str]) -> list[str]:
    """Get all project files matching the patterns.

    Args:
        project_root: Root directory of the project
        patterns: File patterns to match

    Returns:
        List of file paths
    """
    # Set the project root temporarily for list_files_impl
    import os
    old_project_root = os.environ.get("MCP_FILE_ROOT")
    os.environ["MCP_FILE_ROOT"] = project_root

    try:
        all_files = []

        for pattern in patterns:
            files = list_files_impl(patterns=[pattern])
            all_files.extend(files)

        # Remove duplicates and sort
        return sorted(set(all_files))

    finally:
        # Restore original project root
        if old_project_root:
            os.environ["MCP_FILE_ROOT"] = old_project_root
        elif "MCP_FILE_ROOT" in os.environ:
            del os.environ["MCP_FILE_ROOT"]


def _detect_entry_points(
    project_files: list[str], include_tests: bool, project_root: str
) -> list[str]:
    """Detect entry points in the project.

    Args:
        project_files: List of project files
        include_tests: Whether to include test files

    Returns:
        List of entry point file paths
    """
    entry_points = []

    # Common entry point patterns
    entry_point_patterns = [
        r"main\.py$",
        r"__main__\.py$",
        r"app\.py$",
        r"server\.py$",
        r"index\.(js|ts)$",
        r"main\.(js|ts)$",
        r"app\.(js|ts)$"
    ]

    # Test file patterns (if including tests)
    test_patterns = [
        r"test_.*\.py$",
        r".*_test\.py$",
        r".*\.test\.(js|ts)$",
        r".*\.spec\.(js|ts)$"
    ] if include_tests else []

    all_patterns = entry_point_patterns + test_patterns

    for file_path in project_files:
        # project_files is now a simple list of file paths
        absolute_path = Path(project_root) / file_path

        # Check against patterns
        for pattern in all_patterns:
            if re.search(pattern, file_path):
                entry_points.append(str(absolute_path))
                break

        # Check for executable scripts (Python)
        if file_path.endswith('.py'):
            try:
                content = Path(absolute_path).read_text(
                    encoding='utf-8', errors='ignore'
                )
                if 'if __name__ == "__main__"' in content:
                    entry_points.append(str(absolute_path))
            except Exception as e:
                logger.warning(
                    "Failed to read file %s for entry point detection: %s",
                    absolute_path, str(e)
                )
                continue

    return list(set(entry_points))  # Remove duplicates


def _analyze_code_usage(
    project_files: list[str], entry_points: list[str], project_root: str
) -> dict[str, Any]:
    """Analyze code usage patterns across the project.

    Args:
        project_files: List of project files
        entry_points: List of entry point files

    Returns:
        Usage analysis results
    """
    # Track definitions and usages
    definitions = {}  # {identifier: [file_locations]}
    usages = {}       # {identifier: [file_locations]}
    imports = {}      # {file: [imported_modules]}
    exports = {}      # {file: [exported_identifiers]}

    # Analyze each file
    for file_path in project_files:
        # project_files is now a simple list of file paths
        absolute_path = Path(project_root) / file_path

        try:
            analysis = _analyze_single_file(str(absolute_path))

            # Store definitions
            for identifier, locations in analysis["definitions"].items():
                if identifier not in definitions:
                    definitions[identifier] = []
                definitions[identifier].extend(locations)

            # Store usages
            for identifier, locations in analysis["usages"].items():
                if identifier not in usages:
                    usages[identifier] = []
                usages[identifier].extend(locations)

            # Store imports and exports
            imports[str(absolute_path)] = analysis["imports"]
            exports[str(absolute_path)] = analysis["exports"]

        except Exception as e:
            # Skip files that can't be analyzed
            logger.warning(
                "Failed to analyze file %s: %s", absolute_path, str(e)
            )
            continue

    # Calculate usage statistics
    usage_stats = {}
    for identifier in definitions:
        definition_count = len(definitions[identifier])
        usage_count = len(usages.get(identifier, []))

        # Check if used in entry points
        used_in_entry_points = any(
            any(loc["file"] == entry_point for loc in usages.get(identifier, []))
            for entry_point in entry_points
        )

        usage_stats[identifier] = {
            "definitions": definition_count,
            "usages": usage_count,
            "used_in_entry_points": used_in_entry_points,
            "definition_locations": definitions[identifier],
            "usage_locations": usages.get(identifier, [])
        }

    return {
        "definitions": definitions,
        "usages": usages,
        "imports": imports,
        "exports": exports,
        "usage_stats": usage_stats,
        "total_files_analyzed": len([
            f for f in project_files
            if _analyze_single_file_safe(str(Path(project_root) / f)) is not None
        ])
    }


def _analyze_single_file(file_path: str) -> dict[str, Any]:
    """Analyze a single file for definitions and usages.

    Args:
        file_path: Path to the file to analyze

    Returns:
        Analysis results for the file
    """
    content = Path(file_path).read_text(encoding='utf-8', errors='ignore')

    if file_path.endswith('.py'):
        return _analyze_python_file(file_path, content)
    elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
        return _analyze_javascript_file(file_path, content)
    else:
        return {"definitions": {}, "usages": {}, "imports": [], "exports": []}


def _analyze_single_file_safe(file_path: str) -> dict[str, Any] | None:
    """Safely analyze a single file, returning None on error.

    Args:
        file_path: Path to the file to analyze

    Returns:
        Analysis results or None if error
    """
    try:
        return _analyze_single_file(file_path)
    except Exception:
        return None


def _analyze_python_file(file_path: str, content: str) -> dict[str, Any]:
    """Analyze a Python file using AST.

    Args:
        file_path: Path to the file
        content: File content

    Returns:
        Analysis results
    """
    definitions = {}
    usages = {}
    imports = []
    exports = []

    try:
        tree = ast.parse(content)

        # Walk the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
                # Function/class definitions
                identifier = node.name
                location = {
                    "file": file_path,
                    "line": node.lineno,
                    "type": type(node).__name__
                }

                if identifier not in definitions:
                    definitions[identifier] = []
                definitions[identifier].append(location)

                # Check if it's exported (appears at module level)
                if node.col_offset == 0:
                    exports.append(identifier)

            elif isinstance(node, ast.Name):
                # Variable usages
                if isinstance(node.ctx, ast.Load):
                    identifier = node.id
                    location = {
                        "file": file_path,
                        "line": node.lineno,
                        "type": "usage"
                    }

                    if identifier not in usages:
                        usages[identifier] = []
                    usages[identifier].append(location)

            elif isinstance(node, ast.Import | ast.ImportFrom):
                # Import statements
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")

    except SyntaxError:
        # Skip files with syntax errors
        pass

    return {
        "definitions": definitions,
        "usages": usages,
        "imports": imports,
        "exports": exports
    }


def _analyze_javascript_file(file_path: str, content: str) -> dict[str, Any]:
    """Analyze a JavaScript/TypeScript file using regex patterns.

    Args:
        file_path: Path to the file
        content: File content

    Returns:
        Analysis results
    """
    definitions = {}
    usages = {}
    imports = []
    exports = []

    lines = content.splitlines()

    # Patterns for function/class definitions
    function_patterns = [
        r"function\s+(\w+)\s*\(",
        r"(\w+)\s*:\s*function\s*\(",
        r"(\w+)\s*=\s*function\s*\(",
        r"(\w+)\s*=\s*\([^)]*\)\s*=>\s*",
        r"const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*",
        r"let\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*",
        r"var\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*",
    ]

    class_patterns = [
        r"class\s+(\w+)",
        r"interface\s+(\w+)",
        r"type\s+(\w+)\s*="
    ]

    # Variable/const definitions
    var_patterns = [
        r"const\s+(\w+)\s*=",
        r"let\s+(\w+)\s*=",
        r"var\s+(\w+)\s*="
    ]

    # Import/export patterns
    import_patterns = [
        r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"import\s+['\"]([^'\"]+)['\"]",
        r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    ]

    export_patterns = [
        r"export\s+(?:default\s+)?(?:function\s+)?(\w+)",
        r"export\s*\{\s*([^}]+)\s*\}",
        r"module\.exports\s*=\s*(\w+)"
    ]

    all_patterns = function_patterns + class_patterns + var_patterns

    for line_num, line in enumerate(lines, 1):
        # Check for definitions
        for pattern in all_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                identifier = match.group(1)
                location = {
                    "file": file_path,
                    "line": line_num,
                    "type": "definition"
                }

                if identifier not in definitions:
                    definitions[identifier] = []
                definitions[identifier].append(location)

        # Check for imports
        for pattern in import_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                imports.append(match.group(1))

        # Check for exports
        for pattern in export_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                export_text = match.group(1)
                if "," in export_text:
                    # Multiple exports
                    exports.extend([name.strip() for name in export_text.split(",")])
                else:
                    exports.append(export_text)

        # Check for usages (identifiers that aren't part of definitions)
        # First, collect identifiers defined on this line
        defined_on_line = set()
        for pattern in all_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                defined_on_line.add(match.group(1))

        identifier_pattern = r"\b([a-zA-Z_$][a-zA-Z0-9_$]*)\b"
        matches = re.finditer(identifier_pattern, line)
        for match in matches:
            identifier = match.group(1)

            # Skip keywords
            if identifier in [
                "function", "class", "const", "let", "var", "if", "else",
                "for", "while", "return"
            ]:
                continue

            # Skip identifiers being defined on this same line
            if identifier in defined_on_line:
                continue

            location = {
                "file": file_path,
                "line": line_num,
                "type": "usage"
            }

            if identifier not in usages:
                usages[identifier] = []
            usages[identifier].append(location)

    return {
        "definitions": definitions,
        "usages": usages,
        "imports": imports,
        "exports": exports
    }


def _find_dead_code_candidates(
    usage_analysis: dict[str, Any], confidence_threshold: float
) -> list[dict[str, Any]]:
    """Find potentially dead code based on usage analysis.

    Args:
        usage_analysis: Results from usage analysis
        confidence_threshold: Minimum confidence score

    Returns:
        List of dead code candidates
    """
    candidates = []
    usage_stats = usage_analysis["usage_stats"]

    for identifier, stats in usage_stats.items():
        # Calculate confidence score
        confidence = _calculate_dead_code_confidence(stats)

        if confidence >= confidence_threshold:
            candidate = {
                "identifier": identifier,
                "confidence": confidence,
                "reason": _get_dead_code_reason(stats),
                "definition_locations": stats["definition_locations"],
                "usage_locations": stats["usage_locations"],
                "definitions_count": stats["definitions"],
                "usages_count": stats["usages"],
                "used_in_entry_points": stats["used_in_entry_points"]
            }
            candidates.append(candidate)

    # Sort by confidence (highest first)
    candidates.sort(key=lambda x: x["confidence"], reverse=True)

    return candidates


def _calculate_dead_code_confidence(stats: dict[str, Any]) -> float:
    """Calculate confidence score that code is dead.

    Args:
        stats: Usage statistics for an identifier

    Returns:
        Confidence score between 0.0 and 1.0
    """
    definitions = stats["definitions"]
    usages = stats["usages"]
    used_in_entry_points = stats["used_in_entry_points"]

    # Base confidence based on usage ratio
    if usages == 0:
        base_confidence = 0.9  # Very likely dead if no usages
    else:
        usage_ratio = usages / max(definitions, 1)
        base_confidence = max(0.0, 0.8 - (usage_ratio * 0.2))

    # Reduce confidence if used in entry points
    if used_in_entry_points:
        base_confidence *= 0.3

    # Consider definition/usage ratio
    if definitions > 1 and usages == 0:
        base_confidence = min(0.95, base_confidence + 0.1)

    return round(base_confidence, 2)


def _get_dead_code_reason(stats: dict[str, Any]) -> str:
    """Get reason why code might be dead.

    Args:
        stats: Usage statistics

    Returns:
        Human-readable reason
    """
    if stats["usages"] == 0:
        return "No usages found in codebase"
    elif not stats["used_in_entry_points"]:
        return "Not used in any entry points"
    else:
        usage_ratio = stats["usages"] / max(stats["definitions"], 1)
        return f"Low usage ratio ({usage_ratio:.2f})"


def _generate_dead_code_recommendations(candidates: list[dict[str, Any]]) -> list[str]:
    """Generate recommendations for handling dead code.

    Args:
        candidates: List of dead code candidates

    Returns:
        List of recommendations
    """
    recommendations = []

    if not candidates:
        recommendations.append("No dead code found with current confidence threshold")
        return recommendations

    high_confidence = [c for c in candidates if c["confidence"] >= 0.9]
    medium_confidence = [c for c in candidates if 0.7 <= c["confidence"] < 0.9]

    if high_confidence:
        recommendations.append(
            f"Review {len(high_confidence)} high-confidence dead code candidates "
            f"for removal"
        )

    if medium_confidence:
        recommendations.append(
            f"Investigate {len(medium_confidence)} medium-confidence candidates"
        )

    recommendations.extend([
        "Consider running tests after removing dead code to ensure functionality is "
        "preserved",
        "Use version control to safely remove dead code with ability to rollback",
        "Review dependencies - some 'dead' code might be used by external tools"
    ])

    return recommendations


def _calculate_dead_code_summary(
    candidates: list[dict[str, Any]],
    project_files: list[str],
    usage_analysis: dict[str, Any],
    project_root: str
) -> dict[str, Any]:
    """Calculate summary statistics for dead code analysis.

    Args:
        candidates: Dead code candidates
        project_files: All project files
        usage_analysis: Usage analysis results

    Returns:
        Summary statistics
    """
    total_identifiers = len(usage_analysis["usage_stats"])
    total_candidates = len(candidates)

    # Confidence breakdown
    confidence_breakdown = {
        "high": len([c for c in candidates if c["confidence"] >= 0.9]),
        "medium": len([c for c in candidates if 0.7 <= c["confidence"] < 0.9]),
        "low": len([c for c in candidates if c["confidence"] < 0.7])
    }

    # File breakdown
    files_with_dead_code = len({
        location["file"]
        for candidate in candidates
        for location in candidate["definition_locations"]
    })

    return {
        "total_files_analyzed": len(project_files),
        "total_identifiers": total_identifiers,
        "dead_code_candidates": total_candidates,
        "dead_code_percentage": round(
            (total_candidates / max(total_identifiers, 1)) * 100, 2
        ),
        "confidence_breakdown": confidence_breakdown,
        "files_with_dead_code": files_with_dead_code,
        "avg_confidence": round(
            sum(c["confidence"] for c in candidates) / max(len(candidates), 1), 2
        )
    }
