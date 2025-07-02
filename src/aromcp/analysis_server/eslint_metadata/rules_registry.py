"""Registry for loading and managing generated ESLint rules."""

import time
from pathlib import Path
from typing import Any

from ..standards_management.pattern_matcher import match_pattern
from .rule_parser import (
    get_rule_specificity,
    parse_eslint_rule_file,
    validate_rule_metadata,
)


class ESLintRulesRegistry:
    """Registry for managing generated ESLint rules with caching."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.rules_dir = self.project_root / ".aromcp" / "generated-rules" / "rules"
        self._cache = {}
        self._cache_timestamps = {}
        self._last_scan = 0

    def load_generated_rules(self, force_reload: bool = False) -> dict[str, Any]:
        """Load all generated ESLint rules from the rules directory.
        
        Args:
            force_reload: Force reload even if cache is valid
            
        Returns:
            Dictionary containing rules registry and metadata
        """
        try:
            # Check if rules directory exists
            if not self.rules_dir.exists():
                return {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Generated rules directory not found: {self.rules_dir}",
                        "suggestion": "Run the ESLint rule generation command first to create rules"
                    }
                }

            # Check if we need to reload
            current_time = time.time()
            if not force_reload and (current_time - self._last_scan) < 5.0:
                # Use cache if last scan was recent
                if self._cache:
                    return {"data": self._cache}

            rules = {}
            errors = []
            warnings = []
            total_files = 0
            valid_rules = 0

            # Scan for .js files in the rules directory
            for rule_file in self.rules_dir.glob("*.js"):
                total_files += 1
                file_path = str(rule_file)

                # Check if file was modified since last cache
                try:
                    file_mtime = rule_file.stat().st_mtime
                    cached_mtime = self._cache_timestamps.get(file_path, 0)

                    if not force_reload and file_mtime <= cached_mtime and file_path in self._cache.get("rules", {}):
                        # Use cached version
                        rules[file_path] = self._cache["rules"][file_path]
                        valid_rules += 1
                        continue

                except OSError:
                    # File might have been deleted, skip
                    continue

                # Parse the rule file
                rule_data = parse_eslint_rule_file(file_path)

                if "error" in rule_data:
                    errors.append({
                        "file": file_path,
                        "error": rule_data["error"]["message"]
                    })
                    continue

                # Validate rule metadata
                validation = validate_rule_metadata(rule_data)
                if not validation["valid"]:
                    errors.append({
                        "file": file_path,
                        "error": f"Invalid metadata: {', '.join(validation['errors'])}"
                    })
                    continue

                if validation["warnings"]:
                    warnings.extend([
                        {"file": file_path, "warning": w}
                        for w in validation["warnings"]
                    ])

                # Calculate rule specificity
                rule_data["specificity"] = get_rule_specificity(rule_data["patterns"])

                # Store in registry
                rules[file_path] = rule_data
                valid_rules += 1

                # Update cache timestamp
                try:
                    self._cache_timestamps[file_path] = rule_file.stat().st_mtime
                except OSError:
                    pass

            # Update cache
            registry_data = {
                "rules": rules,
                "summary": {
                    "total_files": total_files,
                    "valid_rules": valid_rules,
                    "errors": len(errors),
                    "warnings": len(warnings)
                },
                "errors": errors,
                "warnings": warnings,
                "rules_directory": str(self.rules_dir),
                "last_updated": current_time
            }

            self._cache = registry_data
            self._last_scan = current_time

            return {"data": registry_data}

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to load ESLint rules: {str(e)}"
                }
            }

    def find_applicable_rules(self, file_path: str, registry_data: dict[str, Any] = None) -> list[dict[str, Any]]:
        """Find ESLint rules that apply to a specific file path.
        
        Args:
            file_path: File path to find applicable rules for
            registry_data: Optional registry data (will load if not provided)
            
        Returns:
            List of applicable rules sorted by specificity
        """
        if registry_data is None:
            registry_result = self.load_generated_rules()
            if "error" in registry_result:
                return []
            registry_data = registry_result["data"]

        applicable_rules = []
        rules = registry_data.get("rules", {})

        for rule_file, rule_data in rules.items():
            patterns = rule_data.get("patterns", [])

            # Check if any pattern matches the file
            best_match = None
            best_specificity = 0.0

            for pattern in patterns:
                is_match, specificity = match_pattern(
                    file_path, pattern, str(self.project_root)
                )

                if is_match and specificity > best_specificity:
                    best_match = pattern
                    best_specificity = specificity

            if best_match:
                # Create rule result with match information
                rule_result = dict(rule_data)  # Copy rule data
                rule_result.update({
                    "pattern_matched": best_match,
                    "match_specificity": best_specificity
                })
                applicable_rules.append(rule_result)

        # Sort by specificity (highest first)
        applicable_rules.sort(key=lambda x: x.get("match_specificity", 0), reverse=True)

        return applicable_rules

    def get_rule_coverage_report(self, registry_data: dict[str, Any] = None) -> dict[str, Any]:
        """Generate a coverage report for the loaded ESLint rules.
        
        Args:
            registry_data: Optional registry data (will load if not provided)
            
        Returns:
            Coverage report with statistics and analysis
        """
        if registry_data is None:
            registry_result = self.load_generated_rules()
            if "error" in registry_result:
                return {"error": registry_result["error"]}
            registry_data = registry_result["data"]

        rules = registry_data.get("rules", {})

        # Analyze patterns
        all_patterns = []
        pattern_specificity = {}
        rules_by_category = {}
        severity_distribution = {}

        for rule_file, rule_data in rules.items():
            patterns = rule_data.get("patterns", [])
            severity = rule_data.get("severity", "warn")
            tags = rule_data.get("tags", [])

            all_patterns.extend(patterns)

            # Track severity distribution
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1

            # Track patterns and their specificity
            for pattern in patterns:
                pattern_specificity[pattern] = get_rule_specificity([pattern])

            # Group by tags/categories
            for tag in tags:
                if tag not in rules_by_category:
                    rules_by_category[tag] = []
                rules_by_category[tag].append(rule_data.get("rule_id", "unknown"))

        # Find potential overlaps (simplified)
        overlapping_patterns = []
        for i, pattern1 in enumerate(all_patterns):
            for pattern2 in all_patterns[i+1:]:
                if pattern1 != pattern2:
                    # Simple overlap detection
                    if (pattern1 in pattern2 or pattern2 in pattern1):
                        overlapping_patterns.append({
                            "pattern1": pattern1,
                            "pattern2": pattern2
                        })

        return {
            "total_rules": len(rules),
            "total_patterns": len(all_patterns),
            "unique_patterns": len(set(all_patterns)),
            "severity_distribution": severity_distribution,
            "rules_by_category": rules_by_category,
            "pattern_specificity_range": {
                "min": min(pattern_specificity.values()) if pattern_specificity else 0,
                "max": max(pattern_specificity.values()) if pattern_specificity else 0,
                "avg": sum(pattern_specificity.values()) / len(pattern_specificity) if pattern_specificity else 0
            },
            "potential_overlaps": len(overlapping_patterns),
            "overlap_details": overlapping_patterns[:10]  # First 10 for brevity
        }


def load_generated_rules(project_root: str) -> dict[str, Any]:
    """Convenience function to load generated ESLint rules.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        Registry data or error
    """
    registry = ESLintRulesRegistry(project_root)
    return registry.load_generated_rules()


def find_applicable_rules(file_path: str, registry: ESLintRulesRegistry) -> list[dict[str, Any]]:
    """Convenience function to find applicable rules for a file.
    
    Args:
        file_path: File path to find rules for
        registry: Initialized ESLintRulesRegistry instance
        
    Returns:
        List of applicable rules
    """
    return registry.find_applicable_rules(file_path)
