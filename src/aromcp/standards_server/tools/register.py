"""Enhanced register tool with support for enhanced metadata (v2)."""

import json
import logging
from datetime import datetime
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path_legacy
from .._storage import build_index, load_manifest, save_manifest, save_standard_metadata
from ..models.standard_metadata import ContextTriggers, EnhancedStandardMetadata, OptimizationHints
from .hints_for_file import invalidate_index_cache

logger = logging.getLogger(__name__)


def register_impl(
    source_path: str,
    metadata: dict[str, Any] | str,
    project_root: str | None = None,
    enhanced_format: bool = False
) -> dict[str, Any]:
    """
    Register a standard with enhanced metadata and rule processing.

    Args:
        source_path: Path to the source markdown file
        metadata: Standard metadata (legacy or enhanced format)
        project_root: Project root directory
        enhanced_format: Whether to use enhanced format features

    Returns:
        Dict with standardId, isNew flag, and enhancement stats
    """
    try:
        project_root = get_project_root(project_root)

        # Validate source path
        from pathlib import Path
        validate_file_path_legacy(source_path, Path(project_root))

        # Parse metadata if it's a string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid JSON in metadata: {str(e)}"
                    }
                }

        if enhanced_format:
            return _register_enhanced_standard(source_path, metadata, project_root)
        else:
            return _register_legacy_standard(source_path, metadata, project_root)

    except Exception as e:
        logger.error(f"Error in register_impl: {e}")
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to register standard: {str(e)}"
            }
        }


def _register_enhanced_standard(source_path: str, metadata: dict[str, Any] | str, project_root: str) -> dict[str, Any]:
    """Register standard using enhanced format."""

    # Ensure metadata is dict
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Convert legacy metadata to enhanced format if needed
    if not _is_enhanced_metadata(metadata):
        metadata = _convert_to_enhanced_metadata(metadata)

    # Validate enhanced metadata
    try:
        enhanced_metadata = EnhancedStandardMetadata(**metadata)
    except Exception as e:
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": f"Invalid enhanced metadata: {str(e)}"
            }
        }

    # Check if this is a new standard
    manifest = load_manifest(project_root)
    is_new = enhanced_metadata.id not in manifest.get("standards", {})

    # Clear existing hints and rules
    _clear_existing_hints_and_rules(enhanced_metadata.id, project_root)

    # Save enhanced standard metadata
    save_standard_metadata(enhanced_metadata.id, enhanced_metadata.model_dump(), project_root)

    # Update manifest
    if "standards" not in manifest:
        manifest["standards"] = {}

    manifest["standards"][enhanced_metadata.id] = {
        "sourcePath": source_path,
        "lastModified": metadata.get("updated", datetime.now().isoformat()),
        "registered": True,
        "enhanced": True,
        "version": "v2"
    }

    save_manifest(manifest, project_root)

    # Rebuild index and invalidate cache
    build_index(project_root)
    invalidate_index_cache()

    return {
        "data": {
            "standardId": enhanced_metadata.id,
            "isNew": is_new,
            "enhanced": True,
            "optimization_enabled": enhanced_metadata.optimization.model_dump(),
            "context_triggers": enhanced_metadata.context_triggers.model_dump()
        }
    }


def _register_legacy_standard(source_path: str, metadata: dict[str, Any] | str, project_root: str) -> dict[str, Any]:
    """Register standard using legacy format (backwards compatibility)."""

    # Ensure metadata is dict
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Validate required metadata fields
    required_fields = [
        "id", "name", "category", "tags", "appliesTo", "severity", "priority"
    ]
    for field in required_fields:
        if field not in metadata:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Missing required metadata field: {field}"
                }
            }

    # Ensure updated field is properly mapped from template
    if "updated" not in metadata:
        metadata["updated"] = datetime.now().isoformat()

    # Validate enum values
    valid_severities = ["error", "warning", "info"]
    valid_priorities = ["required", "important", "recommended"]

    if metadata["severity"] not in valid_severities:
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": f"Invalid severity. Must be one of: {valid_severities}"
            }
        }

    if metadata["priority"] not in valid_priorities:
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": f"Invalid priority. Must be one of: {valid_priorities}"
            }
        }

    # Validate arrays
    if not isinstance(metadata["tags"], list):
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": "tags must be an array"
            }
        }

    if not isinstance(metadata["appliesTo"], list):
        return {
            "error": {
                "code": "INVALID_INPUT",
                "message": "appliesTo must be an array"
            }
        }

    standard_id = metadata["id"]

    # Check if this is a new standard
    manifest = load_manifest(project_root)
    is_new = standard_id not in manifest.get("standards", {})

    # Clear existing hints and rules
    _clear_existing_hints_and_rules(standard_id, project_root)

    # Save standard metadata
    save_standard_metadata(standard_id, metadata, project_root)

    # Update manifest
    if "standards" not in manifest:
        manifest["standards"] = {}

    manifest["standards"][standard_id] = {
        "sourcePath": source_path,
        "lastModified": metadata.get("updated", ""),
        "registered": True,
        "enhanced": False,
        "version": "v1"
    }

    save_manifest(manifest, project_root)

    # Rebuild index and invalidate cache
    build_index(project_root)
    invalidate_index_cache()

    return {
        "data": {
            "standardId": standard_id,
            "isNew": is_new,
            "enhanced": False
        }
    }


def _is_enhanced_metadata(metadata: dict[str, Any]) -> bool:
    """Check if metadata is in enhanced format."""
    enhanced_indicators = [
        "context_triggers",
        "optimization",
        "relationships",
        "nextjs_config"
    ]

    return any(indicator in metadata for indicator in enhanced_indicators)


def _convert_to_enhanced_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy metadata to enhanced format."""

    # Detect context triggers from existing data
    context_triggers = ContextTriggers()

    # Map categories to task types
    category_to_tasks = {
        "validation": ["validation", "form_handling"],
        "routing": ["routing", "navigation"],
        "components": ["component_development", "ui_development"],
        "api": ["api_development", "backend_development"],
        "state": ["state_management", "data_handling"],
        "testing": ["testing", "quality_assurance"],
        "security": ["security", "authentication"],
        "performance": ["optimization", "performance"]
    }

    category = metadata.get("category", "general")
    if category in category_to_tasks:
        context_triggers.task_types = category_to_tasks[category]

    # Map appliesTo to file patterns
    applies_to = metadata.get("appliesTo", [])
    context_triggers.file_patterns = applies_to

    # Detect Next.js features from tags
    nextjs_features = []
    tags = metadata.get("tags", [])
    for tag in tags:
        if "nextjs" in tag.lower() or "next.js" in tag.lower():
            nextjs_features.append(tag)
    context_triggers.nextjs_features = nextjs_features

    # Create optimization hints
    optimization = OptimizationHints()

    # Map priority to optimization priority
    priority_mapping = {
        "required": "critical",
        "important": "high",
        "recommended": "medium"
    }

    priority = metadata.get("priority", "recommended")
    optimization.priority = priority_mapping.get(priority, "medium")

    # Determine load frequency from category
    high_frequency_categories = ["validation", "error-handling", "security"]
    if category in high_frequency_categories:
        optimization.load_frequency = "common"
    else:
        optimization.load_frequency = "conditional"

    # Build enhanced metadata
    enhanced = metadata.copy()
    enhanced["context_triggers"] = context_triggers.model_dump()
    enhanced["optimization"] = optimization.model_dump()
    enhanced["relationships"] = {}
    enhanced["nextjs_config"] = {}

    return enhanced


def _clear_existing_hints_and_rules(standard_id: str, project_root: str) -> None:
    """Clear existing hints and ESLint rules for a standard."""
    try:
        import shutil

        from .._storage import get_standard_hints_dir

        # Clear existing hints
        hints_dir = get_standard_hints_dir(standard_id, project_root)
        if hints_dir.exists():
            shutil.rmtree(hints_dir)
            logger.info(f"Cleared existing hints for standard {standard_id}")

        # Clear existing ESLint rules
        from .._storage import get_eslint_dir
        eslint_dir = get_eslint_dir(project_root)
        rules_dir = eslint_dir / "rules"
        if rules_dir.exists():
            # Remove all files that start with the standard_id
            for rule_file in rules_dir.glob(f"{standard_id}*.js"):
                rule_file.unlink()
                logger.info(f"Cleared ESLint rule file: {rule_file.name}")

        logger.info(f"Cleared existing hints and rules for standard {standard_id}")

    except Exception as e:
        logger.error(f"Error clearing existing hints and rules: {e}")
        # Don't raise - this is not critical, just log


# Backwards compatibility
def register_legacy(
    source_path: str,
    metadata: dict[str, Any] | str,
    project_root: str | None = None
) -> dict[str, Any]:
    """Legacy register function for backwards compatibility."""
    return register_impl(
        source_path=source_path,
        metadata=metadata,
        project_root=project_root,
        enhanced_format=False
    )
