"""Rule compression engine for standards server v2."""

import logging
from typing import Any

from ..models.enhanced_rule import EnhancedRule
from .session_manager import SessionState

logger = logging.getLogger(__name__)


class RuleCompressor:
    """Compress rules based on context and session state."""

    def __init__(self):
        self.compression_strategies = {
            "first_time": self._format_for_first_time,
            "familiar": self._format_for_familiar,
            "expert": self._format_for_expert,
            "reference": self._format_for_reference,
        }

    def _get_example_by_visit_count(self, rule: EnhancedRule, visit_count: int) -> str:
        """Get example based on visit count, progressing from largest to smallest."""
        # Order examples from largest to smallest
        examples_by_size = []

        # Collect all available examples with their lengths
        if rule.examples.full and rule.examples.full.strip():
            examples_by_size.append(("full", rule.examples.full, len(rule.examples.full)))
        if rule.examples.detailed and rule.examples.detailed.strip():
            examples_by_size.append(("detailed", rule.examples.detailed, len(rule.examples.detailed)))
        if rule.examples.standard and rule.examples.standard.strip():
            examples_by_size.append(("standard", rule.examples.standard, len(rule.examples.standard)))
        if rule.examples.minimal and rule.examples.minimal.strip():
            examples_by_size.append(("minimal", rule.examples.minimal, len(rule.examples.minimal)))

        # Sort by length descending (largest first)
        examples_by_size.sort(key=lambda x: x[2], reverse=True)

        # Select example based on visit count (0-indexed)
        if examples_by_size:
            index = min(visit_count, len(examples_by_size) - 1)
            return examples_by_size[index][1]

        # Fallback to rule text if no examples
        return rule.rule or ""

    def _estimate_example_tokens(self, example: str) -> int:
        """Estimate token count for an example."""
        from ..utils.token_utils import estimate_tokens

        return estimate_tokens(example)

    def _get_expert_example_by_visit_count(self, rule: EnhancedRule, visit_count: int) -> str:
        """Get example for experts, starting from smallest and progressing up."""
        # Order examples from smallest to largest for experts
        examples_by_size = []

        # Collect all available examples with their lengths
        if rule.examples.minimal and rule.examples.minimal.strip():
            examples_by_size.append(("minimal", rule.examples.minimal, len(rule.examples.minimal)))
        if rule.examples.standard and rule.examples.standard.strip():
            examples_by_size.append(("standard", rule.examples.standard, len(rule.examples.standard)))
        if rule.examples.detailed and rule.examples.detailed.strip():
            examples_by_size.append(("detailed", rule.examples.detailed, len(rule.examples.detailed)))
        if rule.examples.full and rule.examples.full.strip():
            examples_by_size.append(("full", rule.examples.full, len(rule.examples.full)))

        # Sort by length ascending (smallest first for experts)
        examples_by_size.sort(key=lambda x: x[2])

        # Select example based on visit count (0-indexed)
        if examples_by_size:
            index = min(visit_count, len(examples_by_size) - 1)
            return examples_by_size[index][1]

        # Fallback to rule text if no examples
        return rule.rule or ""

    def compress_rule(self, rule: EnhancedRule, context: dict[str, Any], session: SessionState) -> dict[str, Any]:
        """Apply smart compression to a rule."""
        try:
            # Determine compression strategy
            strategy = self._determine_compression_strategy(rule, context, session)

            # Apply compression
            compressed = self.compression_strategies[strategy](rule, context, session)

            # Add metadata
            compressed["compression_strategy"] = strategy
            compressed["original_tokens"] = rule.tokens.full

            return compressed

        except Exception as e:
            logger.error(f"Error compressing rule {rule.rule_id}: {e}")
            return self._create_fallback_rule(rule)

    def _determine_compression_strategy(
        self, rule: EnhancedRule, context: dict[str, Any], session: SessionState
    ) -> str:
        """Determine appropriate compression strategy."""

        # Check if rule was already loaded
        if session.is_rule_loaded(rule.rule_id):
            return "reference"

        # Check pattern familiarity
        pattern_familiarity = context.get("pattern_familiarity", {})
        rule_familiarity = pattern_familiarity.get(rule.metadata.pattern_type, "new")

        if rule_familiarity == "expert":
            return "expert"
        elif rule_familiarity in ["familiar", "novice"]:
            return "familiar"
        else:
            return "first_time"

    def _format_for_first_time(
        self, rule: EnhancedRule, context: dict[str, Any], session: SessionState
    ) -> dict[str, Any]:
        """Format rule for first-time viewing."""
        # Get progressive example based on visit count
        visit_count = session.get_rule_visit_count(rule.rule_id)
        example = self._get_example_by_visit_count(rule, visit_count)

        detail_level = self._determine_detail_level(rule, context, session)

        if detail_level == "detailed":
            return {
                "rule_id": rule.rule_id,
                "rule": rule.rule,
                "context": rule.context,
                "example": example,
                "imports": rule.import_map,
                "metadata": {
                    "pattern_type": rule.metadata.pattern_type,
                    "complexity": rule.metadata.complexity,
                    "rule_type": rule.metadata.rule_type,
                },
                "tokens": self._estimate_example_tokens(example),
                "has_eslint_rule": rule.has_eslint_rule,
                "visit_count": visit_count,
            }
        else:
            return {
                "rule_id": rule.rule_id,
                "rule": rule.rule,
                "context": rule.context[:200] + "..." if len(rule.context) > 200 else rule.context,
                "example": example,
                "imports": rule.import_map,
                "pattern_type": rule.metadata.pattern_type,
                "tokens": self._estimate_example_tokens(example),
                "has_eslint_rule": rule.has_eslint_rule,
                "visit_count": visit_count,
            }

    def _format_for_familiar(
        self, rule: EnhancedRule, context: dict[str, Any], session: SessionState
    ) -> dict[str, Any]:
        """Format rule for familiar patterns."""
        # Get progressive example based on visit count
        visit_count = session.get_rule_visit_count(rule.rule_id)
        example = self._get_example_by_visit_count(rule, visit_count)

        return {
            "rule_id": rule.rule_id,
            "rule": rule.rule,
            "hint": rule.examples.minimal or f"Apply {rule.metadata.pattern_type} pattern",
            "example": example,
            "imports": rule.import_map if rule.import_map else None,
            "tokens": self._estimate_example_tokens(example),
            "has_eslint_rule": rule.has_eslint_rule,
            "visit_count": visit_count,
        }

    def _format_for_expert(self, rule: EnhancedRule, context: dict[str, Any], session: SessionState) -> dict[str, Any]:
        """Format rule for expert users."""
        # Even experts get progressive examples, but starting from smaller ones
        visit_count = session.get_rule_visit_count(rule.rule_id)
        # For experts, start from minimal examples and progress
        expert_example = self._get_expert_example_by_visit_count(rule, visit_count)

        return {
            "rule_id": rule.rule_id,
            "rule": rule.rule,
            "hint": rule.examples.minimal or f"{rule.metadata.pattern_type}",
            "example": expert_example,
            "imports": rule.import_map if rule.import_map else None,
            "tokens": self._estimate_example_tokens(expert_example),
            "has_eslint_rule": rule.has_eslint_rule,
            "visit_count": visit_count,
        }

    def _format_for_reference(
        self, rule: EnhancedRule, context: dict[str, Any], session: SessionState
    ) -> dict[str, Any]:
        """Format rule as reference (already seen)."""
        return {
            "rule_id": rule.rule_id,
            "reference": f"Previously loaded: {rule.rule[:50]}...",
            "pattern_type": rule.metadata.pattern_type,
            "tokens": 5,  # Minimal token cost for reference
            "has_eslint_rule": rule.has_eslint_rule,
        }

    def _determine_detail_level(self, rule: EnhancedRule, context: dict[str, Any], session: SessionState) -> str:
        """Determine appropriate detail level."""

        # Task-specific detail adjustments
        task_type = context.get("task_type", "feature_development")

        if task_type == "debugging":
            return "minimal"  # Just reminders when debugging
        elif task_type in ["learning", "exploration"]:
            return "detailed"  # More explanation when learning
        elif task_type == "refactoring":
            return "standard"  # Balanced view for refactoring

        # Complexity-based adjustments
        complexity_level = context.get("complexity_level", "intermediate")
        rule_complexity = rule.metadata.complexity

        if complexity_level == "expert" and rule_complexity == "basic":
            return "minimal"
        elif complexity_level == "basic" and rule_complexity == "advanced":
            return "detailed"

        # Session phase adjustments
        session_phase = context.get("session_phase", "implementation")

        if session_phase == "exploration":
            return "detailed"
        elif session_phase == "refinement":
            return "minimal"

        return "standard"  # Default

    def _create_fallback_rule(self, rule: EnhancedRule) -> dict[str, Any]:
        """Create fallback rule when compression fails."""
        return {
            "rule_id": rule.rule_id,
            "rule": rule.rule,
            "context": rule.context,
            "example": rule.examples.full,
            "tokens": rule.tokens.full,
            "compression_strategy": "fallback",
            "has_eslint_rule": rule.has_eslint_rule,
        }

    def compress_rule_batch(
        self,
        rules: list[EnhancedRule],
        context: dict[str, Any],
        session: SessionState,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Compress a batch of rules within token budget."""
        compressed_rules = []
        references = []
        current_tokens = 0

        # Sort rules by priority and relevance
        sorted_rules = self._sort_rules_by_priority(rules, context, session)

        for rule in sorted_rules:
            compressed = self.compress_rule(rule, context, session)
            rule_tokens = compressed.get("tokens", 100)

            # Check token budget
            if current_tokens + rule_tokens > max_tokens:
                # Try to fit remaining rules as references
                if not session.is_rule_loaded(rule.rule_id):
                    references.append(
                        {"rule_id": rule.rule_id, "rule": rule.rule[:50] + "...", "reason": "token_limit"}
                    )
                continue

            compressed_rules.append(compressed)
            current_tokens += rule_tokens

            # Update session state
            session.add_rule(rule.rule_id, rule.metadata.pattern_type, rule_tokens)

        return {
            "rules": compressed_rules,
            "references": references,
            "total_tokens": current_tokens,
            "compression_stats": self._get_compression_stats(compressed_rules),
        }

    def _sort_rules_by_priority(
        self, rules: list[EnhancedRule], context: dict[str, Any], session: SessionState
    ) -> list[EnhancedRule]:
        """Sort rules by priority and relevance."""

        def priority_score(rule: EnhancedRule) -> float:
            score = 0.0

            # Priority from metadata
            if rule.metadata.rule_type == "must":
                score += 10.0
            elif rule.metadata.rule_type == "should":
                score += 5.0

            # Complexity match
            complexity_level = context.get("complexity_level", "intermediate")
            if rule.metadata.complexity == complexity_level:
                score += 3.0

            # Pattern familiarity (less familiar = higher priority)
            pattern_familiarity = context.get("pattern_familiarity", {})
            familiarity = pattern_familiarity.get(rule.metadata.pattern_type, "new")
            if familiarity == "new":
                score += 5.0
            elif familiarity == "novice":
                score += 2.0

            # Task type relevance
            task_type = context.get("task_type", "feature_development")
            if task_type in getattr(rule.metadata, "task_types", []):
                score += 4.0

            return score

        return sorted(rules, key=priority_score, reverse=True)

    def _get_compression_stats(self, compressed_rules: list[dict[str, Any]]) -> dict[str, Any]:
        """Get compression statistics."""
        strategies = {}
        total_original = 0
        total_compressed = 0

        for rule in compressed_rules:
            strategy = rule.get("compression_strategy", "unknown")
            strategies[strategy] = strategies.get(strategy, 0) + 1

            total_original += rule.get("original_tokens", 0)
            total_compressed += rule.get("tokens", 0)

        compression_ratio = 1.0 - (total_compressed / total_original) if total_original > 0 else 0.0

        return {
            "strategies_used": strategies,
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
            "compression_ratio": compression_ratio,
            "rules_processed": len(compressed_rules),
        }
