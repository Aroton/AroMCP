"""
Update the rule manifest with metadata.

This tool maintains a manifest.json file that tracks all generated rules and their metadata.
"""

import os
import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from ...utils.json_parameter_middleware import json_convert
from ...filesystem_server._security import get_project_root, validate_file_path


def update_rule_manifest_impl(
    rule_id: str,
    metadata: dict[str, Any],
    manifest_path: str = ".aromcp/generated-rules/manifest.json",
    project_root: str | None = None
) -> dict[str, Any]:
    """Update the rule manifest with metadata.
    
    Args:
        rule_id: Unique identifier for the rule
        metadata: Rule metadata to store
        manifest_path: Path to manifest.json file
        project_root: Project root directory (auto-resolved if None)
        
    Returns:
        Dict with manifest update results
    """
    if project_root is None:
        project_root = get_project_root()
        
    try:
        # Validate inputs
        if not rule_id:
            return {"error": {"code": "INVALID_INPUT", "message": "Rule ID cannot be empty"}}
            
        if not isinstance(metadata, dict):
            return {"error": {"code": "INVALID_INPUT", "message": "Metadata must be a dictionary"}}
            
        # Get full manifest path
        full_manifest_path = os.path.join(project_root, manifest_path)
        manifest_dir = os.path.dirname(full_manifest_path)
        
        # Create directory if it doesn't exist
        os.makedirs(manifest_dir, exist_ok=True)
        
        # Validate path
        validation_result = validate_file_path(full_manifest_path, project_root)
        if not validation_result["valid"]:
            return {"error": {"code": "PERMISSION_DENIED", "message": validation_result["error"]}}
            
        # Load existing manifest or create new one
        manifest = _load_or_create_manifest(full_manifest_path)
        
        # Update rule metadata
        rule_metadata = {
            "updated": _get_timestamp(),
            **metadata
        }
        
        manifest["rules"][rule_id] = rule_metadata
        manifest["last_updated"] = _get_timestamp()
        
        # Update statistics
        _update_manifest_statistics(manifest)
        
        # Write updated manifest
        with open(full_manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            
        return {
            "data": {
                "rule_id": rule_id,
                "manifest_path": manifest_path,
                "total_rules": len(manifest["rules"]),
                "updated_at": rule_metadata["updated"],
                "success": True
            }
        }
        
    except Exception as e:
        return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to update manifest: {str(e)}"}}


def _load_or_create_manifest(manifest_path: str) -> dict[str, Any]:
    """Load existing manifest or create a new one."""
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                
            # Ensure required structure exists
            if "rules" not in manifest:
                manifest["rules"] = {}
            if "statistics" not in manifest:
                manifest["statistics"] = {}
                
            return manifest
            
        except (json.JSONDecodeError, IOError):
            pass
            
    # Create new manifest
    return {
        "version": "1.0",
        "generated": _get_timestamp(),
        "last_updated": _get_timestamp(),
        "project": {
            "analyzed_at": _get_timestamp()
        },
        "rules": {},
        "statistics": {
            "total_standards": 0,
            "eslint_rules_generated": 0,
            "ai_context_sections": 0,
            "hybrid_implementations": 0
        }
    }


def _update_manifest_statistics(manifest: dict[str, Any]) -> None:
    """Update manifest statistics based on current rules."""
    rules = manifest.get("rules", {})
    
    eslint_count = 0
    ai_context_count = 0
    hybrid_count = 0
    
    for rule_id, rule_meta in rules.items():
        rule_type = rule_meta.get("type", "eslint_rule")
        
        if rule_type == "eslint_rule":
            eslint_count += 1
        elif rule_type == "ai_context":
            ai_context_count += 1
        elif rule_type == "hybrid":
            hybrid_count += 1
            
    manifest["statistics"] = {
        "total_standards": len(rules),
        "eslint_rules_generated": eslint_count,
        "ai_context_sections": ai_context_count,
        "hybrid_implementations": hybrid_count
    }


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.now().isoformat()


def register_update_rule_manifest(mcp: FastMCP):
    """Register the update_rule_manifest tool with FastMCP."""
    
    @mcp.tool
    @json_convert
    def update_rule_manifest(
        rule_id: str,
        metadata: dict[str, Any],
        manifest_path: str = ".aromcp/generated-rules/manifest.json",
        project_root: str | None = None
    ) -> dict[str, Any]:
        """Update the rule manifest with metadata.
        
        Args:
            rule_id: Unique identifier for the rule
            metadata: Rule metadata to store
            manifest_path: Path to manifest.json file
            project_root: Project root directory (auto-resolved if None)
            
        Returns:
            Dict with manifest update results
        """
        return update_rule_manifest_impl(rule_id, metadata, manifest_path, project_root)