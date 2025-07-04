"""Extract method signatures implementation."""

import ast
import re
from pathlib import Path
from typing import Any

from ...utils.pagination import paginate_list
from .._security import get_project_root, validate_file_path_legacy


def extract_method_signatures_impl(
    file_paths: str | list[str],
    project_root: str | None = None,
    include_docstrings: bool = True,
    include_decorators: bool = True,
    expand_patterns: bool = True,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Parse code files to extract function/method signatures programmatically.

    Args:
        file_paths: Path to code file(s) or glob pattern(s) - can be string or list
        project_root: Root directory of the project
        include_docstrings: Whether to include function docstrings
        include_decorators: Whether to include function decorators
        expand_patterns: Whether to expand glob patterns in file_paths (default: True)
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)

    Returns:
        Dictionary with paginated extracted signatures and metadata
    """
    import time
    start_time = time.time()

    try:
        # Resolve project root
        project_root = get_project_root(project_root)

        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root does not exist: {project_root}"
                }
            }

        # Normalize file_paths to a list
        if isinstance(file_paths, str):
            input_paths = [file_paths]
        else:
            input_paths = file_paths

        # Expand patterns if requested
        if expand_patterns:
            expanded_paths = []
            for file_path in input_paths:
                if any(char in file_path for char in ['*', '?', '[', ']']):
                    # This looks like a glob pattern
                    matches = list(project_path.glob(file_path))
                    if matches:
                        for match in matches:
                            if (match.is_file() and
                                match.suffix.lower() in ['.py', '.js', '.ts', '.jsx', '.tsx']):
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
            actual_file_paths = input_paths

        # Process all files and collect signatures in a flat list
        all_signatures = []
        errors = []
        files_processed = 0

        for file_path in actual_file_paths:
            try:
                # Validate and normalize paths
                abs_file_path = validate_file_path_legacy(file_path, project_path)

                if not abs_file_path.exists():
                    errors.append({
                        "file": file_path,
                        "error": "File not found"
                    })
                    continue

                if not abs_file_path.is_file():
                    errors.append({
                        "file": file_path,
                        "error": "Path is not a file"
                    })
                    continue

                # Determine file type and parse accordingly
                file_extension = abs_file_path.suffix.lower()

                if file_extension == '.py':
                    signatures = _extract_python_signatures(
                        abs_file_path, include_docstrings, include_decorators
                    )
                elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
                    signatures = _extract_javascript_signatures(
                        abs_file_path, include_docstrings, include_decorators
                    )
                else:
                    errors.append({
                        "file": file_path,
                        "error": f"Unsupported file type: {file_extension}"
                    })
                    continue

                # Add file information to each signature and collect in flat list
                for signature in signatures:
                    signature["file_path"] = file_path
                    signature["file_type"] = file_extension[1:]  # Remove the dot
                    all_signatures.append(signature)

                files_processed += 1

            except Exception as e:
                errors.append({
                    "file": file_path,
                    "error": str(e)
                })

        duration_ms = int((time.time() - start_time) * 1000)

        # Create metadata for pagination
        metadata: dict[str, Any] = {
            "summary": {
                "total_files": len(actual_file_paths),
                "input_patterns": len(input_paths),
                "successful": files_processed,
                "failed": len(errors),
                "patterns_expanded": expand_patterns,
                "duration_ms": duration_ms
            }
        }

        if errors:
            metadata["errors"] = errors

        # Apply pagination with deterministic sorting
        # Sort by file_path, then by name for consistent ordering
        return paginate_list(
            items=all_signatures,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: (x.get("file_path", ""), x.get("name", "")),
            metadata=metadata
        )

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to extract signatures: {str(e)}"
            }
        }




def _extract_python_signatures(
    file_path: Path,
    include_docstrings: bool,
    include_decorators: bool
) -> list[dict[str, Any]]:
    """Extract signatures from Python files using AST."""

    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        signatures = []

        class SignatureExtractor(ast.NodeVisitor):
            def __init__(self):
                self.class_stack = []

            def visit_classdef(self, node):
                # Extract class signature
                class_sig = {
                    "name": node.name,
                    "type": "class",
                    "line": node.lineno,
                    "end_line": getattr(node, 'end_lineno', None),
                    "signature": f"class {node.name}",
                    "docstring": (
                        ast.get_docstring(node) if include_docstrings else None
                    ),
                    "decorators": (
                        [self._get_decorator_name(d) for d in node.decorator_list]
                        if include_decorators else []
                    ),
                    "bases": [self._get_base_name(base) for base in node.bases],
                    "methods": []
                }

                # Build full signature with bases
                if node.bases:
                    bases_str = ", ".join(class_sig["bases"])
                    class_sig["signature"] = f"class {node.name}({bases_str})"

                signatures.append(class_sig)

                # Visit methods within this class
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node):  # noqa: N802 # Required by ast.NodeVisitor
                self._extract_function(node, "function")

            def visit_AsyncFunctionDef(self, node):  # noqa: N802 # Required by ast.NodeVisitor
                self._extract_function(node, "async_function")

            def _extract_function(self, node, func_type):
                # Determine if this is a method or function
                is_method = len(self.class_stack) > 0
                actual_type = "method" if is_method else func_type

                # Build parameter list
                args = []
                defaults_offset = len(node.args.args) - len(node.args.defaults)

                for i, arg in enumerate(node.args.args):
                    param = {"name": arg.arg}

                    # Add type hint if present
                    if arg.annotation:
                        param["type"] = self._get_annotation_string(arg.annotation)

                    # Add default value if present
                    if i >= defaults_offset:
                        default_idx = i - defaults_offset
                        param["default"] = self._get_default_value(node.args.defaults[default_idx])

                    args.append(param)

                # Handle *args
                if node.args.vararg:
                    vararg = {"name": f"*{node.args.vararg.arg}"}
                    if node.args.vararg.annotation:
                        vararg["type"] = self._get_annotation_string(node.args.vararg.annotation)
                    args.append(vararg)

                # Handle **kwargs
                if node.args.kwarg:
                    kwarg = {"name": f"**{node.args.kwarg.arg}"}
                    if node.args.kwarg.annotation:
                        kwarg["type"] = self._get_annotation_string(node.args.kwarg.annotation)
                    args.append(kwarg)

                # Build signature string
                params_str = ", ".join(self._format_param(param) for param in args)
                signature = f"def {node.name}({params_str})"

                if func_type == "async_function":
                    signature = f"async {signature}"

                # Add return type annotation
                if node.returns:
                    return_type = self._get_annotation_string(node.returns)
                    signature += f" -> {return_type}"

                func_sig = {
                    "name": node.name,
                    "type": actual_type,
                    "line": node.lineno,
                    "end_line": getattr(node, 'end_lineno', None),
                    "signature": signature,
                    "parameters": args,
                    "docstring": ast.get_docstring(node) if include_docstrings else None,
                    "decorators": (
                        [self._get_decorator_name(d) for d in node.decorator_list]
                        if include_decorators else []
                    ),
                    "is_async": func_type == "async_function"
                }

                if is_method:
                    func_sig["class"] = self.class_stack[-1]

                signatures.append(func_sig)

            def _get_decorator_name(self, decorator):
                if isinstance(decorator, ast.Name):
                    return decorator.id
                elif isinstance(decorator, ast.Attribute):
                    return f"{self._get_attr_chain(decorator)}"
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        return f"{decorator.func.id}(...)"
                    elif isinstance(decorator.func, ast.Attribute):
                        return f"{self._get_attr_chain(decorator.func)}(...)"
                return "unknown_decorator"

            def _get_attr_chain(self, node):
                if isinstance(node, ast.Name):
                    return node.id
                elif isinstance(node, ast.Attribute):
                    return f"{self._get_attr_chain(node.value)}.{node.attr}"
                return "unknown"

            def _get_base_name(self, base):
                if isinstance(base, ast.Name):
                    return base.id
                elif isinstance(base, ast.Attribute):
                    return self._get_attr_chain(base)
                return "unknown_base"

            def _get_annotation_string(self, annotation):
                if isinstance(annotation, ast.Name):
                    return annotation.id
                elif isinstance(annotation, ast.Constant):
                    return repr(annotation.value)
                elif isinstance(annotation, ast.Attribute):
                    return self._get_attr_chain(annotation)
                elif isinstance(annotation, ast.Subscript):
                    # Handle generic types like List[str]
                    return (
                        f"{self._get_annotation_string(annotation.value)}"
                        f"[{self._get_annotation_string(annotation.slice)}]"
                    )
                return "unknown_type"

            def _get_default_value(self, default):
                if isinstance(default, ast.Constant):
                    return repr(default.value)
                elif isinstance(default, ast.Name):
                    return default.id
                elif isinstance(default, ast.Attribute):
                    return self._get_attr_chain(default)
                return "unknown_default"

            def _format_param(self, param):
                result = param["name"]
                if "type" in param:
                    result += f": {param['type']}"
                if "default" in param:
                    result += f" = {param['default']}"
                return result

        extractor = SignatureExtractor()
        extractor.visit(tree)

        return signatures

    except SyntaxError as e:
        raise Exception(f"Python syntax error: {e}") from e
    except Exception as e:
        raise Exception(f"Failed to parse Python file: {e}") from e


def _extract_javascript_signatures(
    file_path: Path,
    include_docstrings: bool,
    include_decorators: bool
) -> list[dict[str, Any]]:
    """Extract signatures from JavaScript/TypeScript files using regex patterns."""

    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        signatures = []
        lines = content.split('\n')

        # JavaScript/TypeScript keywords that should not be considered as methods
        control_keywords = {
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
            'try', 'catch', 'finally', 'throw', 'return', 'break', 'continue',
            'typeof', 'instanceof', 'new', 'delete', 'void', 'this', 'super',
            'with', 'debugger', 'var', 'let', 'const', 'import', 'export',
            'from', 'as', 'yield', 'await', 'async', 'function', 'class',
            'extends', 'implements', 'interface', 'type', 'enum', 'namespace',
            'module', 'declare', 'abstract', 'public', 'private', 'protected',
            'static', 'readonly', 'get', 'set'
        }

        # Track class context to properly identify methods
        class_depth = 0
        brace_depth = 0

        # Patterns for different function types
        patterns = [
            # Regular function declarations (top-level only)
            (
                r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+?))?\s*{',
                'function'
            ),
            # Arrow functions (top-level assignments)
            (
                r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:\((.*?)\)|(\w+))\s*=>\s*',
                'arrow_function'
            ),
            # Class declarations
            (
                r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?\s*{',
                'class'
            ),
            # Interface declarations (TypeScript)
            (r'^\s*(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?\s*{', 'interface'),
            # Type declarations (TypeScript)
            (r'^\s*(?:export\s+)?type\s+(\w+)\s*=\s*([^;]+);?', 'type'),
            # Method definitions (only when inside a class)
            (
                r'^\s*(?:(async|static|private|protected|public|readonly)\s+)*(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+?))?\s*{',
                'method'
            ),
        ]

        for line_num, line in enumerate(lines, 1):
            # Track brace depth to understand class context
            brace_depth += line.count('{') - line.count('}')

            for pattern, sig_type in patterns:
                match = re.match(pattern, line)
                if match:
                    # Special handling for method pattern
                    if sig_type == 'method':
                        # Extract method name - it's group 2 in our method pattern
                        method_name = match.group(2)

                        # Skip if this is a control structure keyword
                        if method_name in control_keywords:
                            continue

                        # Only process methods if we're inside a class or interface
                        if class_depth == 0:
                            continue

                    signature_info = _parse_js_signature(match, sig_type, line, line_num, class_depth > 0)
                    if signature_info:
                        signatures.append(signature_info)

                        # Update class context tracking
                        if sig_type in ['class', 'interface']:
                            class_depth += 1

            # Update class context when we exit a class
            if class_depth > 0 and brace_depth <= 0:
                class_depth = 0

        return signatures

    except Exception as e:
        raise Exception(f"Failed to parse JavaScript/TypeScript file: {e}") from e


def _parse_js_signature(match, sig_type, line, line_num, is_in_class=False):
    """Parse JavaScript/TypeScript signature from regex match."""

    if sig_type == 'function':
        name = match.group(1)
        params = match.group(2)
        return_type = match.group(3)

        return {
            "name": name,
            "type": "function",
            "line": line_num,
            "signature": f"function {name}({params})" + (f": {return_type.strip()}" if return_type else ""),
            "parameters": _parse_js_params(params),
            "return_type": return_type.strip() if return_type else None
        }

    elif sig_type == 'arrow_function':
        name = match.group(1)
        params = match.group(2) or match.group(3)

        return {
            "name": name,
            "type": "arrow_function",
            "line": line_num,
            "signature": f"const {name} = ({params}) =>",
            "parameters": _parse_js_params(params) if params else []
        }

    elif sig_type == 'method':
        # New pattern: (async|static|private|protected|public|readonly)\s+)*(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+?))?
        # Group 1: modifiers (could be None if no modifiers)
        # Group 2: method name
        # Group 3: parameters
        # Group 4: return type (optional)

        modifiers = match.group(1) if match.group(1) else ""
        name = match.group(2)
        params = match.group(3)
        return_type = match.group(4) if len(match.groups()) >= 4 else None

        is_async = 'async' in modifiers
        is_static = 'static' in modifiers

        # Build signature with modifiers
        signature_parts = []
        if modifiers.strip():
            signature_parts.append(modifiers.strip())
        signature_parts.append(f"{name}({params})")

        signature = " ".join(signature_parts)
        if return_type:
            signature += f": {return_type.strip()}"

        method_info = {
            "name": name,
            "type": "method",
            "line": line_num,
            "signature": signature,
            "parameters": _parse_js_params(params),
            "return_type": return_type.strip() if return_type else None,
            "is_async": is_async
        }

        if is_static:
            method_info["is_static"] = True

        return method_info

    elif sig_type == 'class':
        name = match.group(1)
        extends = match.group(2)

        signature = f"class {name}"
        if extends:
            signature += f" extends {extends}"

        return {
            "name": name,
            "type": "class",
            "line": line_num,
            "signature": signature,
            "extends": extends
        }

    elif sig_type == 'interface':
        name = match.group(1)
        extends = match.group(2)

        signature = f"interface {name}"
        if extends:
            signature += f" extends {extends.strip()}"

        return {
            "name": name,
            "type": "interface",
            "line": line_num,
            "signature": signature,
            "extends": extends.strip() if extends else None
        }

    elif sig_type == 'type':
        name = match.group(1)
        definition = match.group(2)

        return {
            "name": name,
            "type": "type_alias",
            "line": line_num,
            "signature": f"type {name} = {definition.strip()}",
            "definition": definition.strip()
        }

    return None


def _parse_js_params(params_str):
    """Parse JavaScript/TypeScript parameter string."""
    if not params_str or not params_str.strip():
        return []

    params = []
    # Simple parsing - could be enhanced for complex types
    for param in params_str.split(','):
        param = param.strip()
        if not param:
            continue

        # Handle optional parameters
        is_optional = '?' in param

        # Handle default values
        default_value = None
        if '=' in param:
            param_parts = param.split('=')
            param = param_parts[0].strip()
            default_value = param_parts[1].strip()

        # Handle type annotations
        param_type = None
        if ':' in param:
            param_parts = param.split(':')
            param = param_parts[0].strip()
            param_type = param_parts[1].strip()

        # Remove optional marker
        if param.endswith('?'):
            param = param[:-1]
            is_optional = True

        param_info = {"name": param}
        if param_type:
            param_info["type"] = param_type
        if default_value:
            param_info["default"] = default_value
        if is_optional:
            param_info["optional"] = True

        params.append(param_info)

    return params
