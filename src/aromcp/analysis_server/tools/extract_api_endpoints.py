"""Tool for extracting and documenting API endpoints from route files."""

import logging
import re
from pathlib import Path
from typing import Any

from ...filesystem_server.tools.list_files import list_files_impl
from ...filesystem_server.tools.read_files import read_files_impl

logger = logging.getLogger(__name__)


def extract_api_endpoints_impl(
    project_root: str,
    route_patterns: list[str] | None = None,
    include_middleware: bool = True
) -> dict[str, Any]:
    """Extract and document API endpoints from route files.

    Args:
        project_root: Root directory of the project
        route_patterns: Glob patterns for route files (defaults to common patterns)
        include_middleware: Whether to include middleware information

    Returns:
        Dictionary containing extracted API endpoints documentation
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

        # Default route patterns if none provided
        if route_patterns is None:
            route_patterns = [
                "**/routes/**/*.ts",
                "**/routes/**/*.js",
                "**/api/**/*.ts",
                "**/api/**/*.js",
                "**/endpoints/**/*.ts",
                "**/endpoints/**/*.js",
                "**/controllers/**/*.ts",
                "**/controllers/**/*.js",
                "**/*router*.ts",
                "**/*router*.js",
                "**/*route*.ts",
                "**/*route*.js"
            ]

        # Set the project root temporarily for list_files_impl
        import os
        old_project_root = os.environ.get("MCP_FILE_ROOT")
        os.environ["MCP_FILE_ROOT"] = project_root

        try:
            # Get route files
            route_files = []
            for pattern in route_patterns:
                files = list_files_impl(patterns=[pattern])
                route_files.extend(files)

            # Remove duplicates
            route_files = list(set(route_files))
        finally:
            # Restore original project root
            if old_project_root:
                os.environ["MCP_FILE_ROOT"] = old_project_root
            elif "MCP_FILE_ROOT" in os.environ:
                del os.environ["MCP_FILE_ROOT"]

        if not route_files:
            return {
                "data": {
                    "endpoints": [],
                    "middleware": [],
                    "summary": {
                        "total_endpoints": 0,
                        "files_analyzed": 0,
                        "http_methods": {},
                        "route_groups": {}
                    }
                }
            }

        # Set the project root temporarily for read_files_impl
        old_project_root = os.environ.get("MCP_FILE_ROOT")
        os.environ["MCP_FILE_ROOT"] = project_root

        try:
            # Read all route files
            files_response = read_files_impl(files=route_files)
            # Extract items from paginated response
            if "items" in files_response:
                files_content = files_response["items"]
            else:
                files_content = files_response  # Fallback for non-paginated response
        finally:
            # Restore original project root
            if old_project_root:
                os.environ["MCP_FILE_ROOT"] = old_project_root
            elif "MCP_FILE_ROOT" in os.environ:
                del os.environ["MCP_FILE_ROOT"]

        # Extract endpoints and middleware
        all_endpoints = []
        all_middleware = []
        method_stats = {}
        route_groups = {}

        for file_data in files_content:
            file_path = "unknown"  # Default value in case of early failure
            try:
                file_path = file_data["file"]
                content = file_data["content"]
                file_endpoints = _extract_endpoints_from_file(file_path, content)
                all_endpoints.extend(file_endpoints)

                if include_middleware:
                    file_middleware = _extract_middleware_from_file(file_path, content)
                    all_middleware.extend(file_middleware)

                # Update statistics
                for endpoint in file_endpoints:
                    method = endpoint["method"]
                    method_stats[method] = method_stats.get(method, 0) + 1

                    # Group by base path
                    base_path = _get_base_path(endpoint["path"])
                    route_groups[base_path] = route_groups.get(base_path, 0) + 1

            except Exception as e:
                # Skip files that can't be parsed
                logger.warning(
                    "Failed to parse file %s: %s", file_path, str(e)
                )
                continue

        # Sort endpoints by path and method
        all_endpoints.sort(key=lambda x: (x["path"], x["method"]))

        return {
            "data": {
                "endpoints": all_endpoints,
                "middleware": all_middleware if include_middleware else [],
                "summary": {
                    "total_endpoints": len(all_endpoints),
                    "files_analyzed": len(route_files),
                    "http_methods": method_stats,
                    "route_groups": route_groups
                }
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to extract API endpoints: {str(e)}"
            }
        }


def _extract_endpoints_from_file(file_path: str, content: str) -> list[dict[str, Any]]:
    """Extract API endpoints from a single file."""
    endpoints = []

    # Common HTTP methods
    http_methods = ["get", "post", "put", "patch", "delete", "head", "options", "all"]

    # Express.js style patterns
    express_patterns = [
        # router.get('/path', handler)
        rf"(?:router|app)\.({'|'.join(http_methods)})\s*\(\s*['\"]([^'\"]+)['\"]",
        # app.get('/path', handler)
        rf"app\.({'|'.join(http_methods)})\s*\(\s*['\"]([^'\"]+)['\"]"
    ]

    # FastAPI style patterns
    fastapi_patterns = [
        # @app.get("/path")
        rf"@(?:app|router)\.({'|'.join(http_methods)})\s*\(\s*['\"]([^'\"]+)['\"]",
        # @router.get("/path")
        rf"@router\.({'|'.join(http_methods)})\s*\(\s*['\"]([^'\"]+)['\"]"
    ]

    # NestJS style patterns
    nestjs_patterns = [
        # @Get('path') or @Get()
        rf"@({'|'.join([m.capitalize() for m in http_methods])})\s*\("
        rf"\s*['\"]?([^'\"]*)['\"]?\s*\)",
    ]

    # NextJS API routes patterns
    nextjs_patterns = [
        # export function GET() or export async function POST()
        rf"export\s+(?:async\s+)?function\s+"
        rf"({'|'.join([m.upper() for m in http_methods])})\s*\(([^)]*)\)",
    ]

    all_patterns = (
        express_patterns + fastapi_patterns + nestjs_patterns + nextjs_patterns
    )

    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()

        # Check all patterns
        for pattern in all_patterns:
            matches = re.finditer(pattern, line_stripped, re.IGNORECASE)
            for match in matches:
                method = match.group(1).upper()
                path = match.group(2) if len(match.groups()) > 1 else ""

                # For Next.js, derive path from file path
                if not path and "api" in file_path.lower():
                    path = _derive_nextjs_path(file_path)

                # Extract additional information
                handler_info = _extract_handler_info(line_stripped, lines, line_num - 1)

                endpoint = {
                    "method": method,
                    "path": path,
                    "file_path": file_path,
                    "line_number": line_num,
                    "handler_name": handler_info.get("handler_name", ""),
                    "is_async": handler_info.get("is_async", False),
                    "parameters": _extract_path_parameters(path),
                    "description": _extract_description(lines, line_num - 1),
                    "middleware": _extract_inline_middleware(line_stripped)
                }

                endpoints.append(endpoint)

    return endpoints


def _extract_middleware_from_file(file_path: str, content: str) -> list[dict[str, Any]]:
    """Extract middleware definitions from a file."""
    middleware = []

    # Express.js middleware patterns
    middleware_patterns = [
        # app.use(middleware)
        r"(?:app|router)\.use\s*\(\s*([^,)]+)",
        # router.use('/path', middleware)
        r"(?:app|router)\.use\s*\(\s*['\"]([^'\"]+)['\"],\s*([^,)]+)",
    ]

    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()

        for pattern in middleware_patterns:
            matches = re.finditer(pattern, line_stripped)
            for match in matches:
                if len(match.groups()) == 1:
                    # Global middleware
                    middleware_name = match.group(1).strip()
                    path = "*"
                else:
                    # Path-specific middleware
                    path = match.group(1)
                    middleware_name = match.group(2).strip()

                middleware_info = {
                    "name": middleware_name,
                    "path": path,
                    "file_path": file_path,
                    "line_number": line_num,
                    "type": "global" if path == "*" else "path-specific",
                    "description": _extract_description(lines, line_num - 1)
                }

                middleware.append(middleware_info)

    return middleware


def _extract_handler_info(
    line: str, lines: list[str], line_index: int
) -> dict[str, Any]:
    """Extract handler function information."""
    info = {
        "handler_name": "",
        "is_async": False
    }

    # Look for handler name in the same line
    handler_match = re.search(r"(?:,\s*|=>\s*)(\w+)", line)
    if handler_match:
        info["handler_name"] = handler_match.group(1)

    # Check if it's async
    if "async" in line.lower():
        info["is_async"] = True

    # Look at following lines for function definition
    for i in range(line_index + 1, min(line_index + 5, len(lines))):
        next_line = lines[i].strip()
        if next_line.startswith("async"):
            info["is_async"] = True
        if "function" in next_line:
            func_match = re.search(r"function\s+(\w+)", next_line)
            if func_match and not info["handler_name"]:
                info["handler_name"] = func_match.group(1)

    return info


def _extract_path_parameters(path: str) -> list[str]:
    """Extract path parameters from a route path."""
    parameters = []

    # Express.js style parameters (:param)
    express_params = re.findall(r":(\w+)", path)
    parameters.extend(express_params)

    # FastAPI style parameters ({param})
    fastapi_params = re.findall(r"\{(\w+)\}", path)
    parameters.extend(fastapi_params)

    return list(set(parameters))  # Remove duplicates


def _extract_description(lines: list[str], line_index: int) -> str:
    """Extract description from comments above the endpoint or function docstring."""
    description_lines = []

    # Look backwards for comments
    for i in range(line_index - 1, max(line_index - 10, -1), -1):
        line = lines[i].strip()

        if not line:
            continue

        # Single line comments
        if line.startswith("//") or line.startswith("#"):
            if line.startswith("//"):
                comment = line[2:].strip()
            else:
                comment = line[1:].strip()
            if comment:
                description_lines.insert(0, comment)
        # Multi-line comments
        elif line.startswith("/*") or line.startswith("*"):
            comment = line.lstrip("/* ").rstrip("*/").strip()
            if comment:
                description_lines.insert(0, comment)
        # Docstrings
        elif '"""' in line or "'''" in line:
            # Simple docstring extraction
            docstring = line.replace('"""', '').replace("'''", '').strip()
            if docstring:
                description_lines.insert(0, docstring)
        else:
            # Stop if we hit non-comment code
            break

    # If no description found, look forward for function docstring
    if not description_lines:
        # Look forward for function definition and its docstring
        for i in range(line_index, min(line_index + 10, len(lines))):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                continue

            # Look for function definition
            if line.startswith("def ") or line.startswith("async def "):
                # Look for docstring in next few lines
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if '"""' in next_line or "'''" in next_line:
                        # Extract docstring content
                        docstring = (
                            next_line.replace('"""', '').replace("'''", '').strip()
                        )
                        if docstring:
                            description_lines.append(docstring)
                        break
                    elif (
                        not next_line.startswith("#")
                        and not next_line.startswith("//")
                    ):
                        # Hit code, stop looking
                        break
                break

    return " ".join(description_lines) if description_lines else ""


def _extract_inline_middleware(line: str) -> list[str]:
    """Extract middleware mentioned inline with the route."""
    middleware = []

    # Look for middleware functions between route definition and handler
    # Example: router.get('/path', auth, validate, handler)
    parts = line.split(',')
    if len(parts) > 2:  # More than just path and handler
        for part in parts[1:-1]:  # Skip path and handler
            middleware_name = part.strip()
            # Filter out obvious non-middleware tokens
            if middleware_name and not any(
                char in middleware_name for char in ['(', ')', '"', "'"]
            ):
                middleware.append(middleware_name)

    return middleware


def _derive_nextjs_path(file_path: str) -> str:
    """Derive API path from Next.js file path."""
    path_parts = Path(file_path).parts

    # Find 'api' in the path
    try:
        api_index = path_parts.index('api')
        # Take everything after 'api'
        route_parts = path_parts[api_index + 1:]
        # Remove file extension from last part
        if route_parts:
            last_part = route_parts[-1]
            route_parts = route_parts[:-1] + (Path(last_part).stem,)

        # Convert to API path
        api_path = "/" + "/".join(route_parts)
        return api_path if api_path != "/" else "/api"
    except ValueError:
        return ""


def _get_base_path(path: str) -> str:
    """Get the base path for grouping routes."""
    if not path:
        return "/"

    # Remove parameters and get first path segment
    clean_path = re.sub(r'[:{][^}/]*[}]?', '', path)
    parts = [p for p in clean_path.split('/') if p]

    if not parts:
        return "/"

    return f"/{parts[0]}"
