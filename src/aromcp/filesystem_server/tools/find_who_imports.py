"""Find who imports implementation."""

import ast
import re
from pathlib import Path
from typing import Any

from .._security import get_project_root


def find_who_imports_impl(file_path: str) -> dict[str, Any]:
    """Find all files that import the specified file.

    Args:
        file_path: File to find importers for

    Returns:
        Dictionary with dependents and safety info
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        # Validate file exists
        target_file = project_path / file_path
        if not target_file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get all code files to search
        search_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        all_files = []

        for pattern in search_patterns:
            matches = list(project_path.rglob(pattern))
            for match in matches:
                if match.is_file() and "node_modules" not in str(match):
                    all_files.append(str(match.relative_to(project_path)))

        # Find files that import the target
        dependents = []
        for search_file in all_files:
            if search_file == file_path:
                continue  # Skip self

            imports = _find_imports_in_file(project_path / search_file, file_path, project_path)
            if imports:
                dependents.append(
                    {
                        "file": search_file,
                        "imports": imports,
                        "line_numbers": [],  # TODO: Extract line numbers
                        "import_type": "module",  # TODO: Detect import type
                    }
                )

        # Determine if safe to modify/delete
        safe_to_delete = len(dependents) == 0
        risk_level = "low" if len(dependents) <= 2 else "medium" if len(dependents) <= 10 else "high"

        return {
            "target_file": file_path,
            "dependents": dependents,
            "total_dependents": len(dependents),
            "safe_to_delete": safe_to_delete,
            "impact_analysis": {
                "risk_level": risk_level,
                "files_affected": len(dependents),
                "total_imports": sum(len(dep["imports"]) for dep in dependents),
            },
        }

    except Exception as e:
        raise ValueError(f"Failed to find imports: {str(e)}") from e


def _find_imports_in_file(file_path: Path, target_file: str, project_root: Path) -> list[str]:
    """Find imports of target_file in the given file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        imports = []

        if file_path.suffix == ".py":
            imports.extend(_extract_python_imports(content, target_file))
        elif file_path.suffix in [".js", ".ts", ".jsx", ".tsx"]:
            imports.extend(_extract_js_imports(content, target_file, file_path, project_root))

        return imports

    except Exception:
        return []


def _extract_python_imports(content: str, target_file: str) -> list[str]:
    """Extract Python imports that reference the target file."""
    imports = []
    target_module = target_file.replace(".py", "").replace("/", ".")

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if target_module in alias.name:
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and target_module in node.module:
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
    except (SyntaxError, UnicodeDecodeError, OSError):
        # Fallback to regex for syntax errors
        import_patterns = [rf"import\s+.*{re.escape(target_module)}", rf"from\s+.*{re.escape(target_module)}"]
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)

    return imports


def _extract_js_imports(content: str, target_file: str, current_file: Path, project_root: Path) -> list[str]:
    """Extract JavaScript/TypeScript imports that reference the target file."""
    imports = []
    target_without_ext = target_file.replace(".js", "").replace(".ts", "").replace(".jsx", "").replace(".tsx", "")

    # Common import patterns
    patterns = [
        r'import\s+.*?from\s+[\'"]([^\'\"]+)[\'"]',
        r'require\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)',
        r'import\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            # Resolve relative imports
            if match.startswith("./") or match.startswith("../"):
                try:
                    resolved = (current_file.parent / match).resolve().relative_to(project_root)
                    extensions = [".js", ".ts", ".jsx", ".tsx"]
                    resolved_str = str(resolved)
                    for ext in extensions:
                        resolved_str = resolved_str.replace(ext, "")
                    if resolved_str == target_without_ext:
                        imports.append(match)
                except (OSError, ValueError):
                    pass
            elif target_without_ext in match:
                imports.append(match)

    return imports
