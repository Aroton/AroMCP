"""Storage utilities for standards management."""

import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..filesystem_server._security import get_project_root, validate_file_path_legacy


def get_aromcp_dir(project_root: str | None = None) -> Path:
    """Get the .aromcp directory path."""
    if project_root is None:
        project_root = get_project_root()

    aromcp_dir = Path(project_root) / ".aromcp"
    aromcp_dir.mkdir(exist_ok=True)
    return aromcp_dir


def get_manifest_path(project_root: str | None = None) -> Path:
    """Get the manifest.json file path."""
    return get_aromcp_dir(project_root) / "manifest.json"


def load_manifest(project_root: str | None = None) -> dict[str, Any]:
    """Load the standards manifest."""
    manifest_path = get_manifest_path(project_root)

    if not manifest_path.exists():
        return {"standards": {}, "lastUpdated": datetime.now().isoformat()}

    try:
        with open(manifest_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"standards": {}, "lastUpdated": datetime.now().isoformat()}


def save_manifest(manifest: dict[str, Any], project_root: str | None = None) -> None:
    """Save the standards manifest."""
    manifest_path = get_manifest_path(project_root)
    manifest["lastUpdated"] = datetime.now().isoformat()

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)


def get_hints_dir(project_root: str | None = None) -> Path:
    """Get the hints directory path."""
    hints_dir = get_aromcp_dir(project_root) / "hints"
    hints_dir.mkdir(exist_ok=True)
    return hints_dir


def get_standard_hints_dir(standard_id: str, project_root: str | None = None) -> Path:
    """Get the hints directory for a specific standard."""
    standard_dir = get_hints_dir(project_root) / standard_id
    standard_dir.mkdir(exist_ok=True)
    return standard_dir


def get_eslint_dir(project_root: str | None = None) -> Path:
    """Get the eslint directory path."""
    eslint_dir = get_aromcp_dir(project_root) / "eslint"
    eslint_dir.mkdir(exist_ok=True)
    return eslint_dir


def update_eslint_config(project_root: str | None = None) -> None:
    """Update the master ESLint configuration files."""
    eslint_dir = get_eslint_dir(project_root)
    rules_dir = eslint_dir / "rules"

    # Find all rule files
    rule_files = []
    if rules_dir.exists():
        rule_files = list(rules_dir.glob("*.js"))

    # Extract rule names from filenames
    rule_names = [f.stem for f in rule_files]

    # Generate custom-rules plugin index
    plugin_content = "module.exports = {\n  rules: {\n"
    for rule_name in rule_names:
        plugin_content += f"    '{rule_name}': require('./rules/{rule_name}'),\n"
    plugin_content += "  }\n};\n"

    plugin_file = eslint_dir / "custom-rules.js"
    with open(plugin_file, 'w', encoding='utf-8') as f:
        f.write(plugin_content)

    # Generate standards config that can be extended
    config_content = "module.exports = {\n"
    config_content += "  plugins: ['./custom-rules'],\n"
    config_content += "  rules: {\n"
    for rule_name in rule_names:
        config_content += f"    'custom-rules/{rule_name}': 'error',\n"
    config_content += "  }\n};\n"

    config_file = eslint_dir / "standards-config.js"
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)

    # Also create a JSON version for easier parsing
    config_json = {
        "plugins": ["./custom-rules"],
        "rules": {f"custom-rules/{rule_name}": "error" for rule_name in rule_names}
    }

    config_json_file = eslint_dir / "standards-config.json"
    with open(config_json_file, 'w', encoding='utf-8') as f:
        json.dump(config_json, f, indent=2)


def save_standard_metadata(standard_id: str, metadata: dict[str, Any], project_root: str | None = None) -> None:
    """Save metadata for a standard."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)
    metadata_path = standard_dir / "metadata.json"

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)


def load_standard_metadata(standard_id: str, project_root: str | None = None) -> dict[str, Any] | None:
    """Load metadata for a standard."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)
    metadata_path = standard_dir / "metadata.json"

    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_ai_hints(standard_id: str, hints: list[dict[str, Any]], project_root: str | None = None) -> int:
    """Save AI hints for a standard. Returns number of hints saved."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)

    count = 0
    for i, hint in enumerate(hints, 1):
        hint_path = standard_dir / f"hint-{i:03d}.json"

        # Generate import map for code examples
        hint_with_imports = _add_import_map_to_hint(hint)

        # Add token count estimation (4 chars per token) - put it at the end
        hint_json = json.dumps(hint_with_imports)
        tokens = len(hint_json) // 4
        hint_with_imports["tokens"] = tokens

        with open(hint_path, 'w', encoding='utf-8') as f:
            json.dump(hint_with_imports, f, indent=2)
        count += 1

    return count


def load_ai_hints(standard_id: str, project_root: str | None = None) -> list[dict[str, Any]]:
    """Load all AI hints for a standard."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)

    hints = []
    for hint_file in sorted(standard_dir.glob("hint-*.json")):
        try:
            with open(hint_file, encoding='utf-8') as f:
                hints.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue

    return hints


def clear_ai_hints(standard_id: str, project_root: str | None = None) -> int:
    """Clear all AI hints for a standard. Returns number of hints removed."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)

    count = 0
    for hint_file in standard_dir.glob("hint-*.json"):
        hint_file.unlink()
        count += 1

    return count


def save_eslint_rules(standard_id: str, rules: dict[str, Any], project_root: str | None = None) -> None:
    """Save ESLint rules for a standard."""
    eslint_dir = get_eslint_dir(project_root)
    rules_path = eslint_dir / f"{standard_id}.json"

    with open(rules_path, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=2)


def load_eslint_rules(standard_id: str, project_root: str | None = None) -> dict[str, Any] | None:
    """Load ESLint rules for a standard."""
    eslint_dir = get_eslint_dir(project_root)
    rules_path = eslint_dir / f"{standard_id}.json"

    if not rules_path.exists():
        return None

    try:
        with open(rules_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def delete_eslint_rules(standard_id: str, project_root: str | None = None) -> bool:
    """Delete ESLint rules for a standard. Returns True if file existed."""
    eslint_dir = get_eslint_dir(project_root)
    rules_path = eslint_dir / f"{standard_id}.json"

    if rules_path.exists():
        rules_path.unlink()
        return True
    return False


def delete_standard(standard_id: str, project_root: str | None = None) -> dict[str, Any]:
    """Delete all data for a standard. Returns deletion summary."""
    standard_dir = get_standard_hints_dir(standard_id, project_root)

    # Count hints before deletion
    hint_count = len(list(standard_dir.glob("hint-*.json")))

    # Delete hints directory
    if standard_dir.exists():
        shutil.rmtree(standard_dir)

    # Delete ESLint rules
    eslint_existed = delete_eslint_rules(standard_id, project_root)

    # Remove from manifest
    manifest = load_manifest(project_root)
    if standard_id in manifest["standards"]:
        del manifest["standards"][standard_id]
        save_manifest(manifest, project_root)

    return {
        "aiHints": hint_count,
        "eslintRules": eslint_existed
    }


def find_markdown_files(standards_path: str, project_root: str | None = None) -> list[dict[str, Any]]:
    """Find all markdown files in the standards directory."""
    if project_root is None:
        project_root = get_project_root()

    # Validate standards path
    validate_file_path_legacy(standards_path, Path(project_root))

    standards_dir = Path(project_root) / standards_path
    if not standards_dir.exists():
        return []

    files = []
    for md_file in standards_dir.rglob("*.md"):
        # Skip files with "template" in their name
        if "template" in md_file.name.lower():
            continue

        try:
            stat = md_file.stat()
            files.append({
                "path": str(md_file.relative_to(Path(project_root))),
                "absolutePath": str(md_file),
                "lastModified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size
            })
        except (OSError, ValueError):
            continue

    return files


def build_index(project_root: str | None = None) -> None:
    """Build the search index for fast lookups."""
    hints_dir = get_hints_dir(project_root)

    index = {"standards": {}, "lastBuilt": datetime.now().isoformat()}

    for standard_dir in hints_dir.iterdir():
        if not standard_dir.is_dir():
            continue

        standard_id = standard_dir.name
        metadata = load_standard_metadata(standard_id, project_root)

        if metadata:
            index["standards"][standard_id] = {
                "category": metadata.get("category", ""),
                "tags": metadata.get("tags", []),
                "appliesTo": metadata.get("appliesTo", []),
                "priority": metadata.get("priority", "recommended"),
                "hintCount": len(list(standard_dir.glob("hint-*.json")))
            }

    index_path = hints_dir / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)


def load_index(project_root: str | None = None) -> dict[str, Any]:
    """Load the search index."""
    hints_dir = get_hints_dir(project_root)
    index_path = hints_dir / "index.json"

    if not index_path.exists():
        build_index(project_root)

    try:
        with open(index_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        build_index(project_root)
        with open(index_path, encoding='utf-8') as f:
            return json.load(f)


def _add_import_map_to_hint(hint: dict[str, Any]) -> dict[str, Any]:
    """Add import map to hint based on code examples."""
    hint_with_imports = hint.copy()

    # Extract imports from correctExample only
    unique_imports = {}

    correct_example = hint.get("correctExample", "")

    # Collect imports only from correct examples
    if correct_example:
        imports = _extract_imports_from_code(correct_example)

        # Create global import map by deduplicating imports
        # Use statement as the key to avoid duplicates
        for import_item in imports:
            statement = import_item.get("statement", "")
            if statement and statement not in unique_imports:
                unique_imports[statement] = import_item

    if unique_imports:
        # Convert to list and sort for consistent output
        import_list = list(unique_imports.values())
        import_list.sort(key=lambda x: x.get("statement", ""))
        hint_with_imports["importMap"] = import_list

    return hint_with_imports


def _extract_imports_from_code(code: str) -> list[dict[str, str]]:
    """Extract import statements from code examples."""
    imports = []

    # Try Python AST parsing first
    python_imports = _extract_python_imports(code)
    if python_imports:
        imports.extend(python_imports)

    # Try JavaScript/TypeScript regex patterns
    js_imports = _extract_js_imports(code)
    if js_imports:
        imports.extend(js_imports)

    return imports


def _strip_imports_from_code(code: str) -> str:
    """Strip import statements from code examples."""
    lines = code.split('\n')
    filtered_lines = []

    for line in lines:
        stripped_line = line.strip()

        # Skip Python import lines
        if (stripped_line.startswith('import ') or
            stripped_line.startswith('from ') or
            # Handle multi-line imports
            (stripped_line.startswith('from ') and '(' in stripped_line)):
            continue

        # Skip JavaScript/TypeScript import lines
        if (stripped_line.startswith('import ') or
            stripped_line.startswith('const ') and 'require(' in stripped_line or
            stripped_line.startswith('import(')):
            continue

        filtered_lines.append(line)

    # Join lines and clean up excessive whitespace
    result = '\n'.join(filtered_lines)

    # Remove excessive blank lines at the start
    while result.startswith('\n\n'):
        result = result[1:]

    # Remove excessive blank lines at the end
    while result.endswith('\n\n'):
        result = result[:-1]

    return result


def _extract_python_imports(code: str) -> list[dict[str, str]]:
    """Extract Python imports using AST."""
    imports = []

    try:
        tree = ast.parse(code)

        class ImportVisitor(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname or alias.name,
                        "statement": f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                    })

            def visit_ImportFrom(self, node):
                module = node.module or ""
                for alias in node.names:
                    statement = f"from {module} import {alias.name}"
                    if alias.asname:
                        statement += f" as {alias.asname}"

                    imports.append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname or alias.name,
                        "statement": statement
                    })

        visitor = ImportVisitor()
        visitor.visit(tree)

    except (SyntaxError, ValueError):
        # If AST parsing fails, fall back to regex
        pass

    return imports


def _extract_js_imports(code: str) -> list[dict[str, str]]:
    """Extract JavaScript/TypeScript imports using regex."""
    imports = []

    # ES6 imports: import ... from '...'
    es6_pattern = r"import\s+(.+?)\s+from\s+['\"](.+?)['\"]"
    for match in re.finditer(es6_pattern, code):
        imported_items = match.group(1).strip()
        module_path = match.group(2)

        imports.append({
            "type": "es6_import",
            "module": module_path,
            "imported_items": imported_items,
            "statement": f"import {imported_items} from '{module_path}'"
        })

    # CommonJS: require('...')
    require_pattern = r"require\s*\(\s*['\"](.+?)['\"]\s*\)"
    for match in re.finditer(require_pattern, code):
        module_path = match.group(1)

        imports.append({
            "type": "require",
            "module": module_path,
            "statement": f"require('{module_path}')"
        })

    # Dynamic imports: import('...')
    dynamic_pattern = r"import\s*\(\s*['\"](.+?)['\"]\s*\)"
    for match in re.finditer(dynamic_pattern, code):
        module_path = match.group(1)

        imports.append({
            "type": "dynamic_import",
            "module": module_path,
            "statement": f"import('{module_path}')"
        })

    return imports
