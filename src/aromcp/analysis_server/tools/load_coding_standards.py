"""Load coding standards tool implementation.

Enhanced in V2 to include generation status and metadata from manifest.json.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List

from .._security import validate_standards_directory, get_project_root
from ..standards_management.metadata_parser import parse_standard_file
from ..standards_management.pattern_matcher import create_pattern_report


def load_coding_standards_impl(
    project_root: str,
    standards_dir: str,
    include_metadata: bool
) -> Dict[str, Any]:
    """Implementation for load_coding_standards tool.
    
    Args:
        project_root: Root directory of the project
        standards_dir: Directory containing standards files (relative to project_root)
        include_metadata: Whether to parse and include YAML frontmatter metadata
        
    Returns:
        Dictionary with loaded standards data or error information
    """
    # Validate standards directory
    validation = validate_standards_directory(standards_dir, project_root)
    if not validation["valid"]:
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": validation["error"]
            }
        }
    
    standards_path = validation["abs_path"]
    
    # Check if standards directory exists
    if not standards_path.exists():
        return {
            "error": {
                "code": "NOT_FOUND",
                "message": f"Standards directory not found: {standards_dir}"
            }
        }
    
    if not standards_path.is_dir():
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": f"Standards path is not a directory: {standards_dir}"
            }
        }
    
    # Find all markdown files recursively
    try:
        markdown_files = list(standards_path.rglob("*.md"))
        if not markdown_files:
            return {
                "data": {
                    "standards": [],
                    "total": 0,
                    "warnings": [f"No markdown files found in {standards_dir}"]
                }
            }
        
    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to scan standards directory: {str(e)}"
            }
        }
    
    # Process each markdown file
    standards = []
    processing_errors = []
    all_warnings = []
    
    for file_path in markdown_files:
        try:
            # Parse the standard file
            result = parse_standard_file(file_path)
            
            if "error" in result:
                processing_errors.append({
                    "file": str(file_path.relative_to(Path(project_root))),
                    "error": result["error"]["message"]
                })
                continue
            
            standard_data = result["data"]
            
            # Build standard entry
            standard_entry = {
                "id": standard_data["metadata"].get("id", file_path.stem),
                "path": str(file_path.relative_to(Path(project_root))),
                "file_name": file_path.name,
            }
            
            if include_metadata:
                standard_entry["metadata"] = standard_data["metadata"]
                standard_entry["rule_metadata"] = standard_data["rule_metadata"]
                
                # Add content sections if requested
                if standard_data["content"]:
                    standard_entry["content_preview"] = standard_data["content"][:200] + ("..." if len(standard_data["content"]) > 200 else "")
                    standard_entry["content_length"] = len(standard_data["content"])
            
            # Add file statistics
            try:
                stat = file_path.stat()
                standard_entry["file_stats"] = {
                    "size_bytes": stat.st_size,
                    "modified_time": stat.st_mtime
                }
            except OSError:
                pass
            
            standards.append(standard_entry)
            
            # Collect warnings
            if standard_data.get("warnings"):
                for warning in standard_data["warnings"]:
                    all_warnings.append(f"{file_path.name}: {warning}")
                    
        except Exception as e:
            processing_errors.append({
                "file": str(file_path.relative_to(Path(project_root))),
                "error": f"Unexpected error: {str(e)}"
            })
    
    # Sort standards by ID for consistent ordering
    standards.sort(key=lambda x: x["id"])
    
    # Create pattern analysis report if metadata is included
    pattern_report = None
    if include_metadata and standards:
        try:
            # Filter standards that have metadata for pattern analysis
            standards_with_metadata = [s for s in standards if "metadata" in s]
            if standards_with_metadata:
                pattern_report = create_pattern_report(standards_with_metadata, project_root=project_root)
        except Exception as e:
            all_warnings.append(f"Pattern analysis failed: {str(e)}")
    
    # Load V2 generation status from manifest.json
    generation_status = _load_generation_status(project_root)
    
    # Enhance standards with generation information
    if generation_status:
        for standard in standards:
            standard_id = standard["id"]
            if standard_id in generation_status.get("rules", {}):
                rule_info = generation_status["rules"][standard_id]
                standard["generation_status"] = {
                    "generated": True,
                    "type": rule_info.get("type", "unknown"),
                    "last_updated": rule_info.get("updated"),
                    "severity": rule_info.get("severity")
                }
            else:
                standard["generation_status"] = {
                    "generated": False,
                    "type": None,
                    "last_updated": None,
                    "severity": None
                }

    # Build response data
    response_data = {
        "standards": standards,
        "total": len(standards),
        "standards_directory": standards_dir,
        "files_processed": len(markdown_files),
        "files_with_errors": len(processing_errors)
    }
    
    # Add V2 generation information
    if generation_status:
        response_data["v2_generation"] = {
            "manifest_found": True,
            "manifest_version": generation_status.get("version"),
            "last_generation": generation_status.get("last_updated"),
            "total_generated_rules": len(generation_status.get("rules", {})),
            "statistics": generation_status.get("statistics", {})
        }
    else:
        response_data["v2_generation"] = {
            "manifest_found": False,
            "suggestion": "Run ESLint rule generation to create V2 generated rules"
        }
    
    # Add warnings if any
    if all_warnings:
        response_data["warnings"] = all_warnings
    
    # Add processing errors if any
    if processing_errors:
        response_data["processing_errors"] = processing_errors
    
    # Add pattern analysis if available
    if pattern_report:
        response_data["pattern_analysis"] = {
            "total_patterns": pattern_report["total_patterns"],
            "standards_with_patterns": pattern_report["standards_with_patterns"],
            "overlapping_patterns_count": len(pattern_report["overlapping_patterns"]),
            "avg_pattern_specificity": (
                sum(pattern_report["pattern_specificity"].values()) / len(pattern_report["pattern_specificity"])
                if pattern_report["pattern_specificity"] else 0.0
            )
        }
    
    # Add summary statistics
    if include_metadata:
        tags_count = {}
        severity_count = {}
        enabled_count = {"enabled": 0, "disabled": 0}
        
        for standard in standards:
            if "metadata" in standard:
                metadata = standard["metadata"]
                
                # Count tags
                for tag in metadata.get("tags", []):
                    tags_count[tag] = tags_count.get(tag, 0) + 1
                
                # Count severities
                severity = metadata.get("severity", "error")
                severity_count[severity] = severity_count.get(severity, 0) + 1
                
                # Count enabled/disabled
                if metadata.get("enabled", True):
                    enabled_count["enabled"] += 1
                else:
                    enabled_count["disabled"] += 1
        
        response_data["summary"] = {
            "tags": tags_count,
            "severities": severity_count,
            "enabled_status": enabled_count
        }
    
    return {"data": response_data}


def _load_generation_status(project_root: str) -> dict[str, Any] | None:
    """Load V2 generation status from manifest.json."""
    try:
        manifest_path = os.path.join(project_root, ".aromcp", "generated-rules", "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return None