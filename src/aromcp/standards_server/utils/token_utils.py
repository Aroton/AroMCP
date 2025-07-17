"""Token calculation utilities for standards server v2."""

import re
from typing import Any

from ..models.enhanced_rule import EnhancedRule, TokenCount


def estimate_tokens(text: str) -> int:
    """Estimate token count for text using conservative approach."""
    if not text:
        return 0

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Rough estimate: 1 token ≈ 4 characters
    # This is conservative to avoid exceeding token limits
    base_estimate = len(text) // 4

    # Adjust for code vs prose
    if is_code_text(text):
        # Code tends to be more token-dense
        return int(base_estimate * 1.2)
    else:
        # Prose is typically less token-dense
        return int(base_estimate * 0.9)


def is_code_text(text: str) -> bool:
    """Determine if text is primarily code."""
    code_indicators = [
        r"function\s+\w+",
        r"const\s+\w+",
        r"import\s+.*from",
        r"export\s+",
        r"class\s+\w+",
        r"interface\s+\w+",
        r"type\s+\w+",
        r"{\s*[^}]*}",
        r"[\[\](){}]",
        r"=>",
        r"===?",
        r"!==?",
        r"//",
        r"/\*",
    ]

    code_matches = sum(1 for pattern in code_indicators if re.search(pattern, text))
    return code_matches >= 3  # Threshold for considering text as code


def calculate_token_counts(rule: EnhancedRule) -> TokenCount:
    """Calculate token counts for all rule formats."""

    # Calculate base tokens
    full_tokens = estimate_tokens(rule.examples.full)

    # Calculate or estimate other formats
    minimal_tokens = estimate_tokens(rule.examples.minimal) if rule.examples.minimal else 20
    standard_tokens = estimate_tokens(rule.examples.standard) if rule.examples.standard else min(100, full_tokens // 2)
    detailed_tokens = (
        estimate_tokens(rule.examples.detailed) if rule.examples.detailed else min(200, full_tokens * 3 // 4)
    )

    # Ensure logical ordering: minimal <= standard <= detailed <= full
    minimal_tokens = min(minimal_tokens, 30)  # Cap minimal at 30
    standard_tokens = max(standard_tokens, minimal_tokens)
    standard_tokens = min(standard_tokens, 150)  # Cap standard at 150
    detailed_tokens = max(detailed_tokens, standard_tokens)
    detailed_tokens = min(detailed_tokens, 300)  # Cap detailed at 300
    full_tokens = max(full_tokens, detailed_tokens)

    return TokenCount(minimal=minimal_tokens, standard=standard_tokens, detailed=detailed_tokens, full=full_tokens)


def estimate_content_tokens(content: dict[str, Any]) -> int:
    """Estimate tokens for structured content."""
    if not content:
        return 0

    total_tokens = 0

    # Count tokens in different content types
    if isinstance(content, dict):
        for key, value in content.items():
            # Key tokens
            total_tokens += estimate_tokens(str(key))

            # Value tokens
            if isinstance(value, str):
                total_tokens += estimate_tokens(value)
            elif isinstance(value, list | dict):
                total_tokens += estimate_content_tokens(value)
            else:
                total_tokens += estimate_tokens(str(value))

    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                total_tokens += estimate_tokens(item)
            elif isinstance(item, list | dict):
                total_tokens += estimate_content_tokens(item)
            else:
                total_tokens += estimate_tokens(str(item))

    else:
        total_tokens = estimate_tokens(str(content))

    return total_tokens


def calculate_compression_ratio(original_tokens: int, compressed_tokens: int) -> float:
    """Calculate compression ratio."""
    if original_tokens == 0:
        return 0.0
    return 1.0 - (compressed_tokens / original_tokens)


def estimate_rule_overhead() -> int:
    """Estimate overhead tokens for rule structure."""
    # Base overhead for JSON structure, field names, etc.
    return 15


def optimize_token_distribution(rules: list, target_tokens: int) -> dict[str, Any]:
    """Optimize token distribution across rules."""
    if not rules:
        return {"rules": [], "total_tokens": 0}

    # Calculate current token usage
    current_tokens = sum(rule.get("tokens", 100) for rule in rules)

    if current_tokens <= target_tokens:
        return {"rules": rules, "total_tokens": current_tokens}

    # Sort rules by token count (descending) to reduce largest first
    sorted_rules = sorted(rules, key=lambda r: r.get("tokens", 100), reverse=True)

    optimized_rules = []
    remaining_tokens = target_tokens

    for rule in sorted_rules:
        rule_tokens = rule.get("tokens", 100)

        if rule_tokens <= remaining_tokens:
            optimized_rules.append(rule)
            remaining_tokens -= rule_tokens
        else:
            # Try to create a compressed version
            if remaining_tokens >= 30:  # Minimum viable rule size
                compressed_rule = create_compressed_rule(rule, remaining_tokens)
                if compressed_rule:
                    optimized_rules.append(compressed_rule)
                    remaining_tokens = 0
            break

    final_tokens = sum(rule.get("tokens", 100) for rule in optimized_rules)

    return {
        "rules": optimized_rules,
        "total_tokens": final_tokens,
        "compression_ratio": calculate_compression_ratio(current_tokens, final_tokens),
        "rules_included": len(optimized_rules),
        "rules_excluded": len(rules) - len(optimized_rules),
    }


def create_compressed_rule(rule: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    """Create compressed version of rule within token budget."""
    if max_tokens < 30:  # Minimum viable rule
        return None

    # Create minimal version
    compressed = {
        "rule_id": rule.get("rule_id"),
        "rule": rule.get("rule", "")[:100] + "..." if len(rule.get("rule", "")) > 100 else rule.get("rule", ""),
        "tokens": min(max_tokens, 30),
        "compressed": True,
    }

    # Add hint if space allows
    if max_tokens >= 50:
        hint = rule.get("hint", "")
        compressed["hint"] = hint[:50] + "..." if len(hint) > 50 else hint
        compressed["tokens"] = min(max_tokens, 50)

    return compressed


def calculate_session_token_budget(session_stats: dict[str, Any], max_tokens: int) -> int:
    """Calculate appropriate token budget for session."""

    # Base budget
    budget = max_tokens

    # Adjust based on session phase
    session_phase = session_stats.get("session_phase", "implementation")

    if session_phase == "exploration":
        # Exploration phase needs more detailed examples
        budget = int(budget * 1.2)
    elif session_phase == "refinement":
        # Refinement phase can use compressed rules
        budget = int(budget * 0.8)

    # Adjust based on complexity level
    complexity_level = session_stats.get("complexity_level", "intermediate")

    if complexity_level == "expert":
        # Expert users can work with less detail
        budget = int(budget * 0.7)
    elif complexity_level == "basic":
        # Basic users need more detail
        budget = int(budget * 1.3)

    # Ensure budget doesn't exceed max or go below minimum
    budget = max(min(budget, max_tokens * 2), max_tokens // 2)

    return budget
