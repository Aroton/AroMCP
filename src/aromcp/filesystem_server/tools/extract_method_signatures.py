"""Extract method signatures implementation."""

import ast
import re
import time
from pathlib import Path
from typing import Any


def extract_method_signatures_impl(
    file_path: str,
    project_root: str = ".",
    include_docstrings: bool = True,
    include_decorators: bool = True
) -> dict[str, Any]:
    """Parse code files to extract function/method signatures programmatically.
    
    Args:
        file_path: Path to the code file
        project_root: Root directory of the project
        include_docstrings: Whether to include function docstrings
        include_decorators: Whether to include function decorators
        
    Returns:
        Dictionary with extracted signatures and metadata
    """
    start_time = time.time()

    try:
        # Validate and normalize paths
        project_path = Path(project_root).resolve()
        abs_file_path = _validate_file_path(file_path, project_path)

        if not abs_file_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"File not found: {file_path}"
                }
            }

        if not abs_file_path.is_file():
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Path is not a file: {file_path}"
                }
            }

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
            return {
                "error": {
                    "code": "UNSUPPORTED",
                    "message": f"Unsupported file type: {file_extension}"
                }
            }

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": {
                "file_path": file_path,
                "file_type": file_extension[1:],  # Remove the dot
                "signatures": signatures,
                "summary": {
                    "total_functions": len([s for s in signatures if s["type"] == "function"]),
                    "total_methods": len([s for s in signatures if s["type"] == "method"]),
                    "total_classes": len([s for s in signatures if s["type"] == "class"]),
                    "total_items": len(signatures)
                }
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to extract signatures: {str(e)}"
            }
        }


def _validate_file_path(file_path: str, project_root: Path) -> Path:
    """Validate file path to prevent directory traversal attacks."""
    path = Path(file_path)

    if path.is_absolute():
        abs_path = path.resolve()
    else:
        abs_path = (project_root / path).resolve()

    try:
        abs_path.relative_to(project_root)
    except ValueError:
        raise ValueError(f"File path outside project root: {file_path}")

    return abs_path


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

            def visit_ClassDef(self, node):
                # Extract class signature
                class_sig = {
                    "name": node.name,
                    "type": "class",
                    "line": node.lineno,
                    "end_line": getattr(node, 'end_lineno', None),
                    "signature": f"class {node.name}",
                    "docstring": ast.get_docstring(node) if include_docstrings else None,
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list] if include_decorators else [],
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

            def visit_FunctionDef(self, node):
                self._extract_function(node, "function")

            def visit_AsyncFunctionDef(self, node):
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
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list] if include_decorators else [],
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
                    return f"{self._get_annotation_string(annotation.value)}[{self._get_annotation_string(annotation.slice)}]"
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
        raise Exception(f"Python syntax error: {e}")
    except Exception as e:
        raise Exception(f"Failed to parse Python file: {e}")


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

        # Patterns for different function types
        patterns = [
            # Regular function declarations
            (r'^\s*function\s+(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+?))?\s*{', 'function'),
            # Arrow functions
            (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:\((.*?)\)|(\w+))\s*=>\s*', 'arrow_function'),
            # Method definitions in classes
            (r'^\s*(?:(async)\s+)?(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+?))?\s*{', 'method'),
            # Class declarations
            (r'^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{', 'class'),
            # Interface declarations (TypeScript)
            (r'^\s*(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?\s*{', 'interface'),
            # Type declarations (TypeScript)
            (r'^\s*(?:export\s+)?type\s+(\w+)\s*=\s*([^;]+);?', 'type'),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, sig_type in patterns:
                match = re.match(pattern, line)
                if match:
                    signature_info = _parse_js_signature(match, sig_type, line, line_num)
                    if signature_info:
                        signatures.append(signature_info)

        return signatures

    except Exception as e:
        raise Exception(f"Failed to parse JavaScript/TypeScript file: {e}")


def _parse_js_signature(match, sig_type, line, line_num):
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
        is_async = match.group(1) is not None
        name = match.group(2)
        params = match.group(3)
        return_type = match.group(4)

        signature = f"{'async ' if is_async else ''}{name}({params})"
        if return_type:
            signature += f": {return_type.strip()}"

        return {
            "name": name,
            "type": "method",
            "line": line_num,
            "signature": signature,
            "parameters": _parse_js_params(params),
            "return_type": return_type.strip() if return_type else None,
            "is_async": is_async
        }

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
