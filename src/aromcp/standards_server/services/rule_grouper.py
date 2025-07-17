"""Rule grouping service for standards server v2."""

import logging
from typing import Any

from ..models.enhanced_rule import EnhancedRule
from .session_manager import SessionState

logger = logging.getLogger(__name__)


class RuleGrouper:
    """Group similar rules for compression and better organization."""

    def __init__(self):
        self.grouping_strategies = {
            "pattern_type": self._group_by_pattern_type,
            "complexity": self._group_by_complexity,
            "context": self._group_by_context,
            "hybrid": self._group_by_hybrid,
        }

    def group_similar_rules(self, rules: list[EnhancedRule], strategy: str = "hybrid") -> list[dict[str, Any]]:
        """Group rules by similarity using specified strategy."""
        try:
            if strategy not in self.grouping_strategies:
                logger.warning(f"Unknown grouping strategy: {strategy}, using hybrid")
                strategy = "hybrid"

            return self.grouping_strategies[strategy](rules)

        except Exception as e:
            logger.error(f"Error grouping rules: {e}")
            return [{"type": "individual", "rule": rule.dict()} for rule in rules]

    def _group_by_pattern_type(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Group rules by pattern type."""
        groups = {}

        for rule in rules:
            pattern = rule.metadata.pattern_type
            if pattern not in groups:
                groups[pattern] = []
            groups[pattern].append(rule)

        result = []
        for pattern, group_rules in groups.items():
            if len(group_rules) == 1:
                result.append({"type": "individual", "rule": group_rules[0].dict()})
            else:
                result.append(self._create_pattern_group(pattern, group_rules))

        return result

    def _group_by_complexity(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Group rules by complexity level."""
        groups = {}

        for rule in rules:
            complexity = rule.metadata.complexity
            if complexity not in groups:
                groups[complexity] = []
            groups[complexity].append(rule)

        result = []
        for complexity, group_rules in groups.items():
            if len(group_rules) == 1:
                result.append({"type": "individual", "rule": group_rules[0].dict()})
            else:
                result.append(self._create_complexity_group(complexity, group_rules))

        return result

    def _group_by_context(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Group rules by context similarity."""
        groups = {}

        for rule in rules:
            # Use first few words of context as grouping key
            context_key = " ".join(rule.context.split()[:5])
            if context_key not in groups:
                groups[context_key] = []
            groups[context_key].append(rule)

        result = []
        for context_key, group_rules in groups.items():
            if len(group_rules) == 1:
                result.append({"type": "individual", "rule": group_rules[0].dict()})
            else:
                result.append(self._create_context_group(context_key, group_rules))

        return result

    def _group_by_hybrid(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Group rules using hybrid approach combining multiple factors."""

        # First, group by pattern type
        pattern_groups = {}
        for rule in rules:
            pattern = rule.metadata.pattern_type
            if pattern not in pattern_groups:
                pattern_groups[pattern] = []
            pattern_groups[pattern].append(rule)

        result = []

        for pattern, pattern_rules in pattern_groups.items():
            if len(pattern_rules) == 1:
                result.append({"type": "individual", "rule": pattern_rules[0].dict()})
            elif len(pattern_rules) <= 3:
                # Small groups - create simple pattern group
                result.append(self._create_pattern_group(pattern, pattern_rules))
            else:
                # Large groups - further subdivide by complexity or context
                subgroups = self._subdivide_large_group(pattern_rules)
                for subgroup in subgroups:
                    result.append(subgroup)

        return result

    def _subdivide_large_group(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Subdivide large groups into smaller, more manageable ones."""

        # Group by complexity within pattern type
        complexity_groups = {}
        for rule in rules:
            complexity = rule.metadata.complexity
            if complexity not in complexity_groups:
                complexity_groups[complexity] = []
            complexity_groups[complexity].append(rule)

        result = []
        for complexity, complexity_rules in complexity_groups.items():
            if len(complexity_rules) <= 3:
                result.append(
                    self._create_mixed_group(f"{rules[0].metadata.pattern_type}_{complexity}", complexity_rules)
                )
            else:
                # Still too large, create individual rules
                for rule in complexity_rules:
                    result.append({"type": "individual", "rule": rule.dict()})

        return result

    def _create_pattern_group(self, pattern: str, rules: list[EnhancedRule]) -> dict[str, Any]:
        """Create compressed group representation for pattern type."""

        # Find common elements
        common_imports = self._find_common_imports(rules)
        common_context = self._find_common_context(rules)

        # Select best example
        best_example = self._select_best_example(rules)

        return {
            "type": "pattern_group",
            "pattern": pattern,
            "rule_count": len(rules),
            "common_context": common_context,
            "common_imports": common_imports,
            "best_example": best_example,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule": rule.rule,
                    "specific_context": rule.context if rule.context != common_context else None,
                    "complexity": rule.metadata.complexity,
                    "rule_type": rule.metadata.rule_type,
                    "has_eslint_rule": rule.has_eslint_rule,
                }
                for rule in rules
            ],
            "tokens": self._estimate_group_tokens(rules, "pattern"),
        }

    def _create_complexity_group(self, complexity: str, rules: list[EnhancedRule]) -> dict[str, Any]:
        """Create compressed group representation for complexity level."""

        return {
            "type": "complexity_group",
            "complexity": complexity,
            "rule_count": len(rules),
            "pattern_types": list({rule.metadata.pattern_type for rule in rules}),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule": rule.rule,
                    "pattern_type": rule.metadata.pattern_type,
                    "example": rule.examples.minimal or rule.examples.standard,
                    "has_eslint_rule": rule.has_eslint_rule,
                }
                for rule in rules
            ],
            "tokens": self._estimate_group_tokens(rules, "complexity"),
        }

    def _create_context_group(self, context_key: str, rules: list[EnhancedRule]) -> dict[str, Any]:
        """Create compressed group representation for context similarity."""

        return {
            "type": "context_group",
            "context_key": context_key,
            "rule_count": len(rules),
            "common_context": self._find_common_context(rules),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule": rule.rule,
                    "pattern_type": rule.metadata.pattern_type,
                    "specific_example": rule.examples.minimal,
                    "has_eslint_rule": rule.has_eslint_rule,
                }
                for rule in rules
            ],
            "tokens": self._estimate_group_tokens(rules, "context"),
        }

    def _create_mixed_group(self, group_id: str, rules: list[EnhancedRule]) -> dict[str, Any]:
        """Create mixed group for hybrid grouping."""

        return {
            "type": "mixed_group",
            "group_id": group_id,
            "rule_count": len(rules),
            "pattern_types": list({rule.metadata.pattern_type for rule in rules}),
            "complexity_levels": list({rule.metadata.complexity for rule in rules}),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule": rule.rule,
                    "pattern_type": rule.metadata.pattern_type,
                    "complexity": rule.metadata.complexity,
                    "example": rule.examples.minimal or rule.examples.standard,
                    "has_eslint_rule": rule.has_eslint_rule,
                }
                for rule in rules
            ],
            "tokens": self._estimate_group_tokens(rules, "mixed"),
        }

    def _find_common_imports(self, rules: list[EnhancedRule]) -> list[dict[str, Any]]:
        """Find imports common to all rules in group."""
        if not rules:
            return []

        # Start with first rule's imports
        common = set()
        if rules[0].importMap:
            common = {(imp.get("import", ""), imp.get("from", "")) for imp in rules[0].importMap}

        # Find intersection with other rules
        for rule in rules[1:]:
            if rule.importMap:
                rule_imports = {(imp.get("import", ""), imp.get("from", "")) for imp in rule.importMap}
                common &= rule_imports
            else:
                common = set()  # No common imports if any rule has no imports
                break

        # Convert back to list format
        return [{"import": imp, "from": from_} for imp, from_ in common]

    def _find_common_context(self, rules: list[EnhancedRule]) -> str:
        """Find common context prefix among rules."""
        if not rules:
            return ""

        contexts = [rule.context for rule in rules]

        # Find common prefix
        if len(contexts) == 1:
            return contexts[0]

        # Find longest common prefix
        common_prefix = ""
        min_length = min(len(context) for context in contexts)

        for i in range(min_length):
            char = contexts[0][i]
            if all(context[i] == char for context in contexts):
                common_prefix += char
            else:
                break

        # Trim to last complete word
        if common_prefix:
            last_space = common_prefix.rfind(" ")
            if last_space > 0:
                common_prefix = common_prefix[:last_space]

        return common_prefix

    def _select_best_example(self, rules: list[EnhancedRule]) -> str | None:
        """Select best example from group of rules."""

        # Prefer standard examples
        for rule in rules:
            if rule.examples.standard:
                return rule.examples.standard

        # Fall back to minimal examples
        for rule in rules:
            if rule.examples.minimal:
                return rule.examples.minimal

        # Last resort: first rule's full example
        if rules:
            return rules[0].examples.full

        return None

    def _estimate_group_tokens(self, rules: list[EnhancedRule], group_type: str) -> int:
        """Estimate tokens for grouped representation."""

        # Base tokens for group structure
        base_tokens = 50

        # Tokens per rule in group (compressed)
        rule_tokens = len(rules) * 30  # Compressed representation

        # Adjustment based on group type
        if group_type == "pattern":
            # Pattern groups can share more context
            adjustment = 0.8
        elif group_type == "complexity":
            # Complexity groups have less sharing
            adjustment = 0.9
        elif group_type == "context":
            # Context groups can share examples
            adjustment = 0.7
        else:  # mixed
            adjustment = 0.85

        total_tokens = base_tokens + int(rule_tokens * adjustment)

        # Ensure we don't exceed sum of individual rules
        individual_total = sum(rule.tokens.minimal for rule in rules)
        return min(total_tokens, individual_total)

    def group_rules_for_session(
        self, rules: list[EnhancedRule], session: SessionState, max_tokens: int
    ) -> dict[str, Any]:
        """Group rules optimized for session context."""

        # Filter out already loaded rules
        new_rules = [rule for rule in rules if not session.is_rule_loaded(rule.rule_id)]

        # Group the new rules
        grouped = self.group_similar_rules(new_rules, strategy="hybrid")

        # Apply token budget
        result_groups = []
        current_tokens = 0

        for group in grouped:
            group_tokens = group.get("tokens", 100)

            if current_tokens + group_tokens <= max_tokens:
                result_groups.append(group)
                current_tokens += group_tokens
            else:
                # Try to fit partial group or skip
                if group["type"] == "individual":
                    # Skip individual rule
                    continue
                else:
                    # Try to fit some rules from group
                    partial_group = self._create_partial_group(group, max_tokens - current_tokens)
                    if partial_group:
                        result_groups.append(partial_group)
                        current_tokens += partial_group["tokens"]
                break

        return {
            "groups": result_groups,
            "total_tokens": current_tokens,
            "rules_processed": sum(group.get("rule_count", 1) for group in result_groups),
            "compression_ratio": current_tokens / sum(rule.tokens.full for rule in new_rules) if new_rules else 0,
        }

    def _create_partial_group(self, group: dict[str, Any], available_tokens: int) -> dict[str, Any] | None:
        """Create partial group that fits within token budget."""

        if group["type"] == "individual":
            return group if group.get("tokens", 100) <= available_tokens else None

        # Estimate tokens per rule in group
        rule_count = group.get("rule_count", 1)
        group_tokens = group.get("tokens", 100)
        tokens_per_rule = group_tokens / rule_count

        # Calculate how many rules we can fit
        max_rules = int(available_tokens / tokens_per_rule)

        if max_rules <= 0:
            return None

        # Create partial group
        partial = group.copy()
        partial["rules"] = group["rules"][:max_rules]
        partial["rule_count"] = max_rules
        partial["tokens"] = int(max_rules * tokens_per_rule)
        partial["partial"] = True

        return partial
