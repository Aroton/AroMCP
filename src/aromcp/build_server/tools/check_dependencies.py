"""Check dependencies tool implementation for Build Tools."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path


def check_dependencies_impl(
    project_root: str | None = None,
    package_manager: str = "auto",
    check_outdated: bool = True,
    check_security: bool = True
) -> dict[str, Any]:
    """Analyze package.json and installed dependencies.
    
    Args:
        project_root: Directory containing package.json (defaults to MCP_FILE_ROOT)
        package_manager: Package manager to use ("npm", "yarn", "pnpm", or "auto")
        check_outdated: Whether to check for outdated packages
        check_security: Whether to run security audit
        
    Returns:
        Dictionary with dependency analysis results
    """
    try:
        # Resolve project root
        if project_root is None:
            project_root = get_project_root()
            
        # Validate project root path
        validation_result = validate_file_path(project_root, project_root)
        if not validation_result.get("valid", False):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": validation_result.get("error", "Invalid project root path")
                }
            }
            
        project_path = Path(project_root)
        package_json_path = project_path / "package.json"
        
        # Check if package.json exists
        if not package_json_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "package.json not found in project root"
                }
            }
            
        # Read and parse package.json
        try:
            package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Failed to parse package.json: {str(e)}"
                }
            }
            
        # Detect package manager if auto
        if package_manager == "auto":
            if (project_path / "yarn.lock").exists():
                package_manager = "yarn"
            elif (project_path / "pnpm-lock.yaml").exists():
                package_manager = "pnpm"
            elif (project_path / "package-lock.json").exists():
                package_manager = "npm"
            else:
                package_manager = "npm"  # Default fallback
                
        # Extract dependencies from package.json
        dependencies = package_json.get("dependencies", {})
        dev_dependencies = package_json.get("devDependencies", {})
        peer_dependencies = package_json.get("peerDependencies", {})
        optional_dependencies = package_json.get("optionalDependencies", {})
        
        all_dependencies = {
            **dependencies,
            **dev_dependencies,
            **peer_dependencies,
            **optional_dependencies
        }
        
        result = {
            "package_manager": package_manager,
            "dependencies": {
                "production": dependencies,
                "development": dev_dependencies,
                "peer": peer_dependencies,
                "optional": optional_dependencies,
                "total_count": len(all_dependencies)
            },
            "outdated": [],
            "security": [],
            "engines": package_json.get("engines", {}),
            "scripts": package_json.get("scripts", {})
        }
        
        # Check for outdated packages
        if check_outdated:
            try:
                outdated_cmd = _get_outdated_command(package_manager)
                if outdated_cmd:
                    outdated_result = subprocess.run(
                        outdated_cmd,
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if package_manager == "npm":
                        result["outdated"] = _parse_npm_outdated(outdated_result.stdout)
                    elif package_manager == "yarn":
                        result["outdated"] = _parse_yarn_outdated(outdated_result.stdout)
                    elif package_manager == "pnpm":
                        result["outdated"] = _parse_pnpm_outdated(outdated_result.stdout)
                        
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                result["outdated"] = {"error": "Failed to check outdated packages"}
                
        # Check for security vulnerabilities
        if check_security:
            try:
                audit_cmd = _get_audit_command(package_manager)
                if audit_cmd:
                    audit_result = subprocess.run(
                        audit_cmd,
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if package_manager == "npm":
                        result["security"] = _parse_npm_audit(audit_result.stdout)
                    elif package_manager == "yarn":
                        result["security"] = _parse_yarn_audit(audit_result.stdout)
                    elif package_manager == "pnpm":
                        result["security"] = _parse_pnpm_audit(audit_result.stdout)
                        
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                result["security"] = {"error": "Failed to run security audit"}
                
        return {"data": result}
        
    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to analyze dependencies: {str(e)}"
            }
        }


def _get_outdated_command(package_manager: str) -> list[str] | None:
    """Get the command to check for outdated packages."""
    commands = {
        "npm": ["npm", "outdated", "--json"],
        "yarn": ["yarn", "outdated", "--json"],
        "pnpm": ["pnpm", "outdated", "--format", "json"]
    }
    return commands.get(package_manager)


def _get_audit_command(package_manager: str) -> list[str] | None:
    """Get the command to run security audit."""
    commands = {
        "npm": ["npm", "audit", "--json"],
        "yarn": ["yarn", "audit", "--json"],
        "pnpm": ["pnpm", "audit", "--json"]
    }
    return commands.get(package_manager)


def _parse_npm_outdated(output: str) -> list[dict[str, Any]]:
    """Parse npm outdated output."""
    try:
        if not output.strip():
            return []
            
        data = json.loads(output)
        outdated = []
        
        for package, info in data.items():
            outdated.append({
                "package": package,
                "current": info.get("current"),
                "wanted": info.get("wanted"),
                "latest": info.get("latest"),
                "location": info.get("location")
            })
            
        return outdated
    except (json.JSONDecodeError, AttributeError):
        return []


def _parse_yarn_outdated(output: str) -> list[dict[str, Any]]:
    """Parse yarn outdated output."""
    try:
        if not output.strip():
            return []
            
        data = json.loads(output)
        return data.get("data", {}).get("body", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def _parse_pnpm_outdated(output: str) -> list[dict[str, Any]]:
    """Parse pnpm outdated output."""
    try:
        if not output.strip():
            return []
            
        data = json.loads(output)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, AttributeError):
        return []


def _parse_npm_audit(output: str) -> dict[str, Any]:
    """Parse npm audit output."""
    try:
        if not output.strip():
            return {"vulnerabilities": [], "summary": {"total": 0}}
            
        data = json.loads(output)
        
        # Extract vulnerability summary
        summary = {
            "total": data.get("metadata", {}).get("vulnerabilities", {}).get("total", 0),
            "low": data.get("metadata", {}).get("vulnerabilities", {}).get("low", 0),
            "moderate": data.get("metadata", {}).get("vulnerabilities", {}).get("moderate", 0),
            "high": data.get("metadata", {}).get("vulnerabilities", {}).get("high", 0),
            "critical": data.get("metadata", {}).get("vulnerabilities", {}).get("critical", 0)
        }
        
        # Extract individual vulnerabilities
        vulnerabilities = []
        for advisory_id, advisory in data.get("advisories", {}).items():
            vulnerabilities.append({
                "id": advisory_id,
                "title": advisory.get("title"),
                "severity": advisory.get("severity"),
                "vulnerable_versions": advisory.get("vulnerable_versions"),
                "patched_versions": advisory.get("patched_versions"),
                "module_name": advisory.get("module_name")
            })
            
        return {
            "summary": summary,
            "vulnerabilities": vulnerabilities
        }
        
    except (json.JSONDecodeError, AttributeError):
        return {"vulnerabilities": [], "summary": {"total": 0}}


def _parse_yarn_audit(output: str) -> dict[str, Any]:
    """Parse yarn audit output."""
    try:
        if not output.strip():
            return {"vulnerabilities": [], "summary": {"total": 0}}
            
        data = json.loads(output)
        
        # Yarn audit format may vary, extract what we can
        vulnerabilities = data.get("data", {}).get("vulnerabilities", [])
        summary = data.get("data", {}).get("summary", {"total": len(vulnerabilities)})
        
        return {
            "summary": summary,
            "vulnerabilities": vulnerabilities
        }
        
    except (json.JSONDecodeError, AttributeError):
        return {"vulnerabilities": [], "summary": {"total": 0}}


def _parse_pnpm_audit(output: str) -> dict[str, Any]:
    """Parse pnpm audit output."""
    try:
        if not output.strip():
            return {"vulnerabilities": [], "summary": {"total": 0}}
            
        data = json.loads(output)
        
        # Extract vulnerabilities from pnpm format
        vulnerabilities = []
        if isinstance(data, dict) and "advisories" in data:
            for advisory_id, advisory in data["advisories"].items():
                vulnerabilities.append({
                    "id": advisory_id,
                    "title": advisory.get("title"),
                    "severity": advisory.get("severity"),
                    "module_name": advisory.get("module_name")
                })
                
        return {
            "summary": {"total": len(vulnerabilities)},
            "vulnerabilities": vulnerabilities
        }
        
    except (json.JSONDecodeError, AttributeError):
        return {"vulnerabilities": [], "summary": {"total": 0}}