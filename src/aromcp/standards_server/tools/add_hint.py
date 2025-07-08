"""Add a single hint to a standard."""

import json
import logging
from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import build_index, get_standard_hints_dir, load_manifest
from ..models.enhanced_rule import EnhancedRule, RuleCompression, RuleExamples, RuleMetadata, TokenCount
from ..utils.example_generators import generate_minimal_example, generate_standard_example
from ..utils.token_utils import calculate_token_counts
from .hints_for_file import invalidate_index_cache

logger = logging.getLogger(__name__)


def add_hint_impl(
    standard_id: str,
    hint_data: dict[str, Any] | str,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Add a single hint to a standard.

    Args:
        standard_id: ID of the standard to add the hint to
        hint_data: Single hint data in enhanced format
        project_root: Project root directory

    Returns:
        Dict with success status and hint info
    """
    try:
        project_root = get_project_root(project_root)

        # Parse hint data if it's a string
        if isinstance(hint_data, str):
            try:
                hint_data = json.loads(hint_data)
            except json.JSONDecodeError as e:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid JSON in hint_data: {str(e)}"
                    }
                }

        # Validate that the standard exists
        manifest = load_manifest(project_root)
        if standard_id not in manifest.get("standards", {}):
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Standard {standard_id} not found"
                }
            }

        # Create enhanced rule from hint data
        enhanced_rule = _create_enhanced_rule(hint_data)

        # Get the standard's hints directory
        standard_dir = get_standard_hints_dir(standard_id, project_root)

        # Find the next available hint number
        hint_number = _get_next_hint_number(standard_dir)

        # Save the hint
        hint_file = standard_dir / f"hint-{hint_number:03d}.json"
        rule_data = enhanced_rule.model_dump()

        with open(hint_file, 'w', encoding='utf-8') as f:
            json.dump(rule_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Added hint {hint_number} to standard {standard_id}")

        # Rebuild index and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": {
                "standardId": standard_id,
                "hintNumber": hint_number,
                "hintId": enhanced_rule.rule_id,
                "hintFile": str(hint_file),
                "tokens": enhanced_rule.tokens.model_dump()
            }
        }

    except Exception as e:
        logger.error(f"Error in add_hint_impl: {e}")
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to add hint: {str(e)}"
            }
        }


def _get_next_hint_number(standard_dir) -> int:
    """Get the next available hint number."""
    if not standard_dir.exists():
        standard_dir.mkdir(parents=True, exist_ok=True)
        return 1

    # Find existing hint files
    hint_files = list(standard_dir.glob("hint-*.json"))
    if not hint_files:
        return 1

    # Extract numbers and find the highest
    numbers = []
    for hint_file in hint_files:
        try:
            # Extract number from filename like "hint-001.json"
            number_str = hint_file.stem.split('-')[1]
            numbers.append(int(number_str))
        except (IndexError, ValueError):
            continue

    return max(numbers) + 1 if numbers else 1


def _create_enhanced_rule(rule_data: dict[str, Any]) -> EnhancedRule:
    """Create enhanced rule from rule data."""

    # Extract basic information
    rule_text = rule_data.get("rule", "")
    rule_id = rule_data.get("rule_id", f"rule_{hash(rule_text)}")
    context = rule_data.get("context", "")

    # Create metadata
    metadata_data = rule_data.get("metadata", {})
    rule_metadata = RuleMetadata(
        pattern_type=metadata_data.get("pattern_type", "general"),
        complexity=metadata_data.get("complexity", "intermediate"),
        rule_type=metadata_data.get("rule_type", "should"),
        nextjs_api=metadata_data.get("nextjs_api", []),
        client_server=metadata_data.get("client_server", "isomorphic")
    )

    # Create compression config
    compression_data = rule_data.get("compression", {})
    compression = RuleCompression(
        example_sharable=compression_data.get("example_sharable", True),
        pattern_extractable=compression_data.get("pattern_extractable", True),
        progressive_detail=compression_data.get("progressive_detail", ["minimal", "standard", "detailed", "full"])
    )

    # Create examples
    examples_data = rule_data.get("examples", {})
    full_example = examples_data.get("full", "")

    examples = RuleExamples(
        minimal=examples_data.get("minimal"),
        standard=examples_data.get("standard"),
        detailed=examples_data.get("detailed"),
        full=full_example,
        reference=examples_data.get("reference"),
        context_variants=examples_data.get("context_variants", {})
    )

    # Create enhanced rule
    enhanced_rule = EnhancedRule(
        rule=rule_text,
        rule_id=rule_id,
        context=context,
        metadata=rule_metadata,
        compression=compression,
        examples=examples,
        tokens=TokenCount(full=100, detailed=75, standard=50, minimal=25),  # Placeholder
        import_map=rule_data.get("import_map", []),
        has_eslint_rule=rule_data.get("has_eslint_rule", False),
        relationships=rule_data.get("relationships", {})
    )

    # Auto-generate missing examples
    if not examples.minimal and full_example:
        enhanced_rule.examples.minimal = generate_minimal_example(enhanced_rule)

    if not examples.standard and full_example:
        enhanced_rule.examples.standard = generate_standard_example(enhanced_rule)

    # Calculate token counts
    enhanced_rule.tokens = calculate_token_counts(enhanced_rule)

    return enhanced_rule
