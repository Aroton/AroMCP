"""Pattern matching utilities for ESLint rules."""

from typing import Any

from ..standards_management.pattern_matcher import calculate_pattern_specificity
from ..standards_management.pattern_matcher import match_pattern as base_match_pattern


def match_file_to_eslint_rules(
    file_path: str,
    rules_registry: dict[str, Any],
    project_root: str
) -> list[dict[str, Any]]:
    """Match a file path to applicable ESLint rules.
    
    Args:
        file_path: File path to match against
        rules_registry: Registry data containing ESLint rules
        project_root: Project root directory
        
    Returns:
        List of matching rules with match information
    """
    matches = []
    rules = rules_registry.get("rules", {})

    for rule_file, rule_data in rules.items():
        patterns = rule_data.get("patterns", [])

        # Find the best matching pattern for this rule
        best_match, best_specificity = find_best_pattern_match(
            file_path, patterns, project_root
        )

        if best_match:
            match_info = dict(rule_data)  # Copy rule data
            match_info.update({
                "pattern_matched": best_match,
                "match_specificity": best_specificity,
                "rule_file": rule_file
            })
            matches.append(match_info)

    # Sort by specificity (highest first)
    matches.sort(key=lambda x: x.get("match_specificity", 0), reverse=True)

    return matches


def find_best_pattern_match(
    file_path: str,
    patterns: list[str],
    project_root: str
) -> tuple[str, float]:
    """Find the best matching pattern from a list for a file path.
    
    Args:
        file_path: File path to match
        patterns: List of glob patterns to test
        project_root: Project root directory
        
    Returns:
        Tuple of (best_pattern, specificity) or (None, 0.0)
    """
    best_pattern = None
    best_specificity = 0.0

    for pattern in patterns:
        is_match, specificity = base_match_pattern(file_path, pattern, project_root)
        if is_match and specificity > best_specificity:
            best_pattern = pattern
            best_specificity = specificity

    return best_pattern, best_specificity


def calculate_eslint_rule_specificity(rule_patterns: list[str]) -> float:
    """Calculate specificity score for ESLint rule patterns.
    
    Args:
        rule_patterns: List of glob patterns for the rule
        
    Returns:
        Highest specificity score among all patterns
    """
    if not rule_patterns:
        return 0.1  # Default low specificity

    specificities = [calculate_pattern_specificity(pattern) for pattern in rule_patterns]
    return max(specificities)


def resolve_rule_conflicts(overlapping_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve conflicts when multiple ESLint rules apply to the same file.
    
    Uses precedence rules:
    1. Pattern specificity (higher wins)
    2. Rule severity (error > warn > info)
    3. Alphabetical rule name (for consistency)
    
    Args:
        overlapping_rules: List of rules that all match the same file
        
    Returns:
        Sorted list of rules by precedence
    """
    def get_severity_priority(severity: str) -> int:
        """Get numeric priority for severity levels."""
        priority_map = {
            "error": 3,
            "warn": 2,
            "info": 1,
            "off": 0
        }
        return priority_map.get(severity.lower(), 1)

    def rule_sort_key(rule: dict[str, Any]) -> tuple[float, int, str]:
        """Generate sort key for rule precedence."""
        specificity = rule.get("match_specificity", rule.get("specificity", 0.0))
        severity = rule.get("severity", "warn")
        rule_id = rule.get("rule_id", rule.get("eslint_rule_name", ""))

        return (
            -specificity,  # Negative for descending order (higher specificity first)
            -get_severity_priority(severity),  # Negative for descending order
            rule_id  # Alphabetical order for tie-breaking
        )

    # Sort rules by precedence
    return sorted(overlapping_rules, key=rule_sort_key)


def categorize_rules_by_file_type(
    rules: list[dict[str, Any]],
    file_path: str
) -> dict[str, list[dict[str, Any]]]:
    """Categorize ESLint rules by their relevance to the file type.
    
    Args:
        rules: List of ESLint rules that match the file
        file_path: File path being analyzed
        
    Returns:
        Dictionary categorizing rules by type (critical, recommended, optional)
    """
    from pathlib import Path

    file_ext = Path(file_path).suffix.lower()
    categorized = {
        "critical": [],      # Rules with error severity
        "recommended": [],   # Rules with warn severity and high specificity
        "optional": []       # Other applicable rules
    }

    for rule in rules:
        severity = rule.get("severity", "warn").lower()
        specificity = rule.get("match_specificity", rule.get("specificity", 0.0))

        if severity == "error":
            categorized["critical"].append(rule)
        elif severity == "warn" and specificity > 0.5:
            categorized["recommended"].append(rule)
        else:
            categorized["optional"].append(rule)

    return categorized


def get_file_type_from_patterns(patterns: list[str]) -> list[str]:
    """Extract file types/categories from ESLint rule patterns.
    
    Args:
        patterns: List of glob patterns
        
    Returns:
        List of inferred file types/categories
    """
    categories = set()

    for pattern in patterns:
        pattern_lower = pattern.lower()

        # File extension categories
        if '.ts' in pattern_lower:
            categories.add('typescript')
        if '.js' in pattern_lower:
            categories.add('javascript')
        if '.tsx' in pattern_lower or '.jsx' in pattern_lower:
            categories.add('react')
        if '.py' in pattern_lower:
            categories.add('python')

        # Directory-based categories
        if '/api/' in pattern_lower or '/routes/' in pattern_lower:
            categories.add('api')
        if '/component' in pattern_lower:
            categories.add('components')
        if '/test' in pattern_lower or '/spec' in pattern_lower:
            categories.add('tests')
        if '/util' in pattern_lower:
            categories.add('utilities')
        if '/service' in pattern_lower:
            categories.add('services')

    return list(categories)
