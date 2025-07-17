"""Enhanced hints_for_file with session management and compression (v2)."""

import logging
import time
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path_legacy
from .._scoring import score_relevance, select_hints_by_budget
from .._storage import load_ai_hints, load_index, load_standard_metadata
from ..models.enhanced_rule import EnhancedRule
from ..services.context_detector import ContextDetector
from ..services.rule_compressor import RuleCompressor
from ..services.rule_grouper import RuleGrouper
from ..services.session_manager import SessionManager
from ..utils.token_utils import calculate_session_token_budget

logger = logging.getLogger(__name__)

# Global services (shared across requests)
_session_manager: SessionManager | None = None
_context_detector: ContextDetector | None = None
_rule_compressor: RuleCompressor | None = None
_rule_grouper: RuleGrouper | None = None

# Global cache for index data
_index_cache: dict[str, Any] | None = None
_cache_timestamp: float = 0
_cache_ttl: float = 300  # 5 minutes cache TTL


def _get_services() -> tuple[SessionManager, ContextDetector, RuleCompressor, RuleGrouper]:
    """Get or create shared service instances."""
    global _session_manager, _context_detector, _rule_compressor, _rule_grouper

    if _session_manager is None:
        _session_manager = SessionManager()
    if _context_detector is None:
        _context_detector = ContextDetector()
    if _rule_compressor is None:
        _rule_compressor = RuleCompressor()
    if _rule_grouper is None:
        _rule_grouper = RuleGrouper()

    return _session_manager, _context_detector, _rule_compressor, _rule_grouper


def _get_cached_index(project_root: str | None = None) -> dict[str, Any]:
    """Get index with caching for performance."""
    global _index_cache, _cache_timestamp

    current_time = time.time()

    # Check if cache is valid
    if _index_cache is not None and (current_time - _cache_timestamp) < _cache_ttl:
        return _index_cache

    # Cache miss or expired - reload index
    _index_cache = load_index(project_root)
    _cache_timestamp = current_time

    return _index_cache


def invalidate_index_cache() -> None:
    """Invalidate the index cache to force reload."""
    global _index_cache, _cache_timestamp
    _index_cache = None
    _cache_timestamp = 0


def hints_for_file_impl(
    file_path: str,
    max_tokens: int = 10000,
    project_root: str | None = None,
    session_id: str | None = None,
    compression_enabled: bool = True,
    grouping_enabled: bool = True,
) -> dict[str, Any]:
    """
    Gets relevant hints with smart compression and session deduplication.

    Args:
        file_path: Path to the file to get hints for
        max_tokens: Maximum tokens to return in response
        project_root: Project root directory
        session_id: Session identifier for deduplication
        compression_enabled: Whether to use compression
        grouping_enabled: Whether to use rule grouping

    Returns:
        Dict with enhanced hints and session statistics
    """
    try:
        project_root = get_project_root(project_root)

        # Validate file path
        from pathlib import Path

        validate_file_path_legacy(file_path, Path(project_root))

        # Validate max_tokens
        if max_tokens <= 0:
            return {"error": {"code": "INVALID_INPUT", "message": "maxTokens must be a positive integer"}}

        # Get services
        session_manager, context_detector, rule_compressor, rule_grouper = _get_services()

        # Get or create session
        session = session_manager.get_or_create_session(session_id or "default")

        # Detect context
        context = context_detector.analyze_session_context(session, file_path)

        # Calculate dynamic token budget
        dynamic_budget = calculate_session_token_budget(context, max_tokens)

        # Load the index for fast lookups (with caching)
        index = _get_cached_index(project_root)
        standards = index.get("standards", {})

        if not standards:
            return {"data": {"hints": [], "totalTokens": 0, "context": context, "session_stats": session.get_stats()}}

        # Collect all enhanced rules with relevance scores
        enhanced_rules: list[EnhancedRule] = []

        for standard_id in standards.keys():
            # Load metadata for scoring
            metadata = load_standard_metadata(standard_id, project_root)
            if not metadata:
                continue

            # Calculate relevance score
            relevance_score = score_relevance(metadata, file_path)

            # Skip if no relevance
            if relevance_score <= 0:
                continue

            # Load hints for this standard
            hints = load_ai_hints(standard_id, project_root)

            for hint in hints:
                # Convert old format to enhanced rule format
                enhanced_rule = _convert_hint_to_enhanced_rule(hint, metadata, standard_id, relevance_score)
                if enhanced_rule:
                    enhanced_rules.append(enhanced_rule)

        # Apply compression and grouping
        if compression_enabled:
            compressed_result = rule_compressor.compress_rule_batch(enhanced_rules, context, session, dynamic_budget)

            output_rules = compressed_result["rules"]
            references = compressed_result["references"]
            total_tokens = compressed_result["total_tokens"]
            compression_stats = compressed_result["compression_stats"]

        else:
            # Legacy processing without compression
            hints_with_scores = [(rule.model_dump(), 1.0) for rule in enhanced_rules]
            selected_hints, total_tokens = select_hints_by_budget(hints_with_scores, dynamic_budget)

            output_rules = selected_hints
            references = []
            compression_stats = {}

        # Apply grouping if enabled
        if grouping_enabled and len(output_rules) > 5:
            # Convert rules back to EnhancedRule objects for grouping
            rules_for_grouping = []
            for rule_dict in output_rules:
                if isinstance(rule_dict, dict) and "rule_id" in rule_dict:
                    try:
                        enhanced_rule = _dict_to_enhanced_rule(rule_dict)
                        if enhanced_rule:
                            rules_for_grouping.append(enhanced_rule)
                    except Exception as e:
                        logger.warning(f"Failed to convert rule for grouping: {e}")
                        continue

            if rules_for_grouping:
                grouping_result = rule_grouper.group_rules_for_session(rules_for_grouping, session, dynamic_budget)

                output_rules = grouping_result["groups"]
                total_tokens = grouping_result["total_tokens"]
                grouping_stats = {
                    "rules_processed": grouping_result["rules_processed"],
                    "compression_ratio": grouping_result["compression_ratio"],
                }
            else:
                grouping_stats = {}
        else:
            grouping_stats = {}

        # Extract import maps and optimize token usage (legacy support)
        global_import_maps = {}
        optimized_hints = []

        for rule in output_rules:
            if isinstance(rule, dict):
                # Handle grouped rules
                if rule.get("type") in ["pattern_group", "complexity_group", "context_group", "mixed_group"]:
                    optimized_hints.append(rule)
                    continue

                # Handle individual rules
                modules_used = []
                if "importMap" in rule:
                    import_map = rule["importMap"]

                    if import_map:
                        for import_item in import_map:
                            module_name = import_item.get("module", "")
                            if module_name:
                                if module_name not in global_import_maps:
                                    global_import_maps[module_name] = []

                                existing_statements = [
                                    imp.get("statement", "") for imp in global_import_maps[module_name]
                                ]
                                if import_item.get("statement", "") not in existing_statements:
                                    clean_import = {k: v for k, v in import_item.items() if k != "type"}
                                    global_import_maps[module_name].append(clean_import)

                                if module_name not in modules_used:
                                    modules_used.append(module_name)

                # Create optimized hint - exclude complex nested objects
                excluded_keys = ("importMap", "metadata", "standardId", "examples", "compression", "relationships")
                optimized_hint = {k: v for k, v in rule.items() if k not in excluded_keys}

                # Handle examples - convert enhanced format to legacy format for backward compatibility
                if "examples" in rule and isinstance(rule["examples"], dict):
                    examples = rule["examples"]
                    # Use standard example as primary, fall back to full, then minimal
                    if examples.get("standard"):
                        optimized_hint["correctExample"] = examples["standard"]
                    elif examples.get("full"):
                        optimized_hint["correctExample"] = examples["full"]
                    elif examples.get("minimal"):
                        optimized_hint["correctExample"] = examples["minimal"]

                    # Add other example variants if available
                    if examples.get("minimal"):
                        optimized_hint["minimalExample"] = examples["minimal"]
                    if examples.get("detailed"):
                        optimized_hint["detailedExample"] = examples["detailed"]
                    if examples.get("reference"):
                        optimized_hint["referenceExample"] = examples["reference"]

                # Add modules array
                if modules_used:
                    optimized_hint["modules"] = sorted(modules_used)

                # Apply import stripping to all example fields
                from .._storage import _strip_imports_from_code

                example_fields = ["correctExample", "incorrectExample", "example", "minimalExample", "detailedExample"]
                for example_field in example_fields:
                    if example_field in optimized_hint and optimized_hint[example_field]:
                        optimized_hint[example_field] = _strip_imports_from_code(optimized_hint[example_field])

                optimized_hints.append(optimized_hint)

        # Update session
        session.add_file(file_path)

        return {
            "data": {
                "hints": optimized_hints,
                "totalTokens": total_tokens,
                "importMaps": global_import_maps if global_import_maps else None,
                "context": context,
                "references": references,
                "session_stats": session.get_stats(),
                "compression_stats": compression_stats,
                "grouping_stats": grouping_stats,
                "optimization_enabled": {
                    "compression": compression_enabled,
                    "grouping": grouping_enabled,
                    "dynamic_budget": dynamic_budget != max_tokens,
                },
            }
        }

    except Exception as e:
        logger.error(f"Error in hints_for_file_impl: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get hints for file: {str(e)}"}}


def _convert_hint_to_enhanced_rule(
    hint: dict[str, Any], metadata: dict[str, Any], standard_id: str, relevance_score: float
) -> EnhancedRule | None:
    """Convert hint to enhanced rule format, handling both legacy and modern formats."""
    from ..models.enhanced_rule import EnhancedRule, RuleExamples, RuleMetadata, TokenCount
    from ..utils.token_utils import calculate_token_counts

    try:
        # Validate that hint is a dictionary
        if not isinstance(hint, dict):
            logger.error(f"Expected hint to be a dictionary, got {type(hint)}: {hint}")
            return None

        # Extract rule information
        rule_text = hint.get("rule", "")
        rule_id = hint.get("rule_id", f"{standard_id}_{hash(rule_text)}")
        context = hint.get("context", "")

        # Handle metadata - check if hint already has enhanced metadata
        hint_metadata = hint.get("metadata", {})
        if hint_metadata:
            # Use hint's metadata if present (modern format)
            rule_metadata = RuleMetadata(
                pattern_type=hint_metadata.get("pattern_type", metadata.get("category", "general")),
                complexity=hint_metadata.get("complexity", metadata.get("complexity", "intermediate")),
                rule_type=hint_metadata.get("rule_type", metadata.get("priority", "should")),
                nextjs_api=hint_metadata.get("nextjs_api", metadata.get("nextjs_features", [])),
                client_server=hint_metadata.get("client_server", metadata.get("client_server", "isomorphic")),
            )
        else:
            # Fallback to standard metadata (legacy format)
            rule_metadata = RuleMetadata(
                pattern_type=metadata.get("category", "general"),
                complexity=metadata.get("complexity", "intermediate"),
                rule_type=metadata.get("priority", "should"),
                nextjs_api=metadata.get("nextjs_features", []),
                client_server=metadata.get("client_server", "isomorphic"),
            )

        # Handle examples - check if hint already has enhanced examples
        hint_examples = hint.get("examples", {})
        if hint_examples:
            # Use hint's examples if present (modern format)
            examples = RuleExamples(
                minimal=hint_examples.get("minimal"),
                standard=hint_examples.get("standard"),
                detailed=hint_examples.get("detailed"),
                full=hint_examples.get("full", ""),
                reference=hint_examples.get("reference"),
                context_variants=hint_examples.get("context_variants", {}),
            )
        else:
            # Fallback to legacy example fields
            correct_example = hint.get("correctExample", "")
            examples = RuleExamples(
                full=correct_example,
                standard=correct_example[:500] if correct_example else None,
                minimal=rule_text[:100] if rule_text else None,
            )

        # Handle tokens - use existing if present and is a dict
        hint_tokens = hint.get("tokens", {})
        if isinstance(hint_tokens, dict) and hint_tokens:
            tokens = TokenCount(
                minimal=hint_tokens.get("minimal", 25),
                standard=hint_tokens.get("standard", 50),
                detailed=hint_tokens.get("detailed", 75),
                full=hint_tokens.get("full", 100),
            )
        else:
            tokens = TokenCount(full=100, detailed=75, standard=50, minimal=25)  # Placeholder

        # Create enhanced rule
        enhanced_rule = EnhancedRule(
            rule=rule_text,
            rule_id=rule_id,
            context=context,
            metadata=rule_metadata,
            examples=examples,
            tokens=tokens,
            import_map=hint.get("import_map", []),
            has_eslint_rule=hint.get("has_eslint_rule", False),
            relationships=hint.get("relationships", {}),
        )

        # Calculate actual token counts if they weren't provided as a dict
        if not isinstance(hint_tokens, dict) or not hint_tokens:
            enhanced_rule.tokens = calculate_token_counts(enhanced_rule)

        return enhanced_rule

    except Exception as e:
        logger.error(f"Error converting hint to enhanced rule: {e}")
        return None


def _dict_to_enhanced_rule(rule_dict: dict[str, Any]) -> EnhancedRule | None:
    """Convert rule dictionary back to EnhancedRule object."""
    try:
        from ..models.enhanced_rule import EnhancedRule

        # Handle compressed rule format
        if "compression_strategy" in rule_dict:
            # This is a compressed rule, create minimal enhanced rule
            return EnhancedRule(
                rule=rule_dict.get("rule", ""),
                rule_id=rule_dict.get("rule_id", ""),
                context=rule_dict.get("context", ""),
                metadata=rule_dict.get("metadata", {}),
                examples=rule_dict.get("examples", {}),
                tokens=rule_dict.get("tokens", {}),
            )
        else:
            # Try to create full enhanced rule
            return EnhancedRule(**rule_dict)

    except Exception as e:
        logger.error(f"Error converting dict to enhanced rule: {e}")
        return None


# Legacy function for backwards compatibility
def hints_for_file_legacy(file_path: str, max_tokens: int = 10000, project_root: str | None = None) -> dict[str, Any]:
    """Legacy version without session management."""
    return hints_for_file_impl(
        file_path=file_path,
        max_tokens=max_tokens,
        project_root=project_root,
        session_id=None,
        compression_enabled=False,
        grouping_enabled=False,
    )
