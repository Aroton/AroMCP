"""Standards registry for centralized management of coding standards.

This module provides a centralized registry for managing coding standards,
their metadata, and file pattern mappings.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ...filesystem_server._security import get_project_root
from ..utils.rule_cache import get_rule_cache
from .pattern_matcher import PatternMatcher
from .metadata_parser import MetadataParser


class StandardsRegistry:
    """Central registry for managing coding standards.
    
    Provides functionality to load, cache, and query coding standards
    with efficient pattern matching and metadata management.
    """

    def __init__(self, project_root: Optional[str] = None):
        """Initialize standards registry.
        
        Args:
            project_root: Project root directory (auto-detected if None)
        """
        self._project_root = project_root or get_project_root()
        self._standards: Dict[str, Dict[str, Any]] = {}
        self._pattern_matcher = PatternMatcher()
        self._metadata_parser = MetadataParser()
        self._rule_cache = get_rule_cache()
        self._last_loaded: Optional[float] = None
        self._standards_dir = Path(self._project_root) / ".aromcp" / "standards"

    def load_standards(self, standards_dir: Optional[str] = None, force_reload: bool = False) -> Dict[str, Any]:
        """Load all coding standards from directory.
        
        Args:
            standards_dir: Directory containing standards (defaults to .aromcp/standards)
            force_reload: Force reload even if already loaded
            
        Returns:
            Dictionary containing loaded standards and metadata
        """
        if standards_dir:
            self._standards_dir = Path(standards_dir)
        else:
            self._standards_dir = Path(self._project_root) / ".aromcp" / "standards"

        # Check if reload is needed
        if not force_reload and self._last_loaded is not None:
            # Check if any standard files have been modified
            if not self._needs_reload():
                return self._get_standards_summary()

        try:
            # Clear existing standards
            self._standards.clear()
            
            # Load standards from directory
            if not self._standards_dir.exists():
                return {
                    "standards": [],
                    "total": 0,
                    "categories": [],
                    "patterns": {},
                    "load_time": time.time(),
                    "standards_directory": str(self._standards_dir)
                }

            loaded_count = 0
            errors = []

            # Recursively find all markdown files
            for md_file in self._standards_dir.rglob("*.md"):
                try:
                    standard = self._load_single_standard(md_file)
                    if standard:
                        self._standards[standard["id"]] = standard
                        loaded_count += 1
                except Exception as e:
                    errors.append({
                        "file": str(md_file),
                        "error": str(e)
                    })

            # Build pattern mappings
            pattern_mappings = self._build_pattern_mappings()
            
            # Extract categories
            categories = self._extract_categories()
            
            self._last_loaded = time.time()
            
            result = {
                "standards": list(self._standards.values()),
                "total": loaded_count,
                "categories": categories,
                "patterns": pattern_mappings,
                "errors": errors,
                "load_time": self._last_loaded,
                "standards_directory": str(self._standards_dir)
            }
            
            return result

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to load standards: {str(e)}"
                }
            }

    def _load_single_standard(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a single standard file.
        
        Args:
            file_path: Path to the standard file
            
        Returns:
            Parsed standard or None if failed
        """
        try:
            # Check cache first
            cached_standard = self._rule_cache.get_parsed_standard(str(file_path))
            if cached_standard is not None:
                return cached_standard

            # Read file content
            content = file_path.read_text(encoding='utf-8')
            
            # Parse metadata and content
            metadata, body = self._metadata_parser.parse_frontmatter(content)
            
            # Validate metadata first
            validation = self._metadata_parser.validate_standard_metadata(metadata)
            if not validation["valid"]:
                print(f"Warning: Invalid metadata in {file_path}: {'; '.join(validation['errors'])}")
                return None
            
            metadata = validation["metadata"]
            
            # Generate standard ID from metadata
            standard_id = metadata.get("id")
            if not standard_id:
                print(f"Warning: Missing required 'id' field in {file_path}")
                return None
            
            # Parse content structure using new template parser
            from .metadata_parser import parse_content_structure
            parsed_content = parse_content_structure(body)
            
            # Build standard object
            standard = {
                "id": standard_id,
                "path": str(file_path.relative_to(Path(self._project_root))),
                "absolute_path": str(file_path),
                "name": metadata.get("name", standard_id.replace("-", " ").title()),
                "metadata": metadata,
                "content": parsed_content,
                "applies_to": metadata.get("applies_to", []),
                "category": metadata.get("category", "general"),
                "tags": metadata.get("tags", []),
                "severity": metadata.get("severity", "error"),
                "enabled": metadata.get("enabled", True),
                "priority": metadata.get("priority", "recommended"),
                "dependencies": metadata.get("dependencies", []),
                "file_size": file_path.stat().st_size,
                "modified_time": file_path.stat().st_mtime,
                "loaded_at": time.time()
            }
            
            # Cache the parsed standard
            self._rule_cache.put_parsed_standard(str(file_path), standard)
            
            return standard
            
        except Exception as e:
            # Log error but don't fail the entire loading process
            print(f"Warning: Failed to load standard {file_path}: {e}")
            return None

    def _needs_reload(self) -> bool:
        """Check if standards need to be reloaded.
        
        Returns:
            True if reload is needed
        """
        try:
            if not self._standards_dir.exists():
                return True
                
            # Check if any markdown files have been modified since last load
            for md_file in self._standards_dir.rglob("*.md"):
                if md_file.stat().st_mtime > self._last_loaded:
                    return True
                    
            return False
            
        except Exception:
            # If we can't check, assume reload is needed
            return True

    def _build_pattern_mappings(self) -> Dict[str, List[str]]:
        """Build file pattern to standards mappings.
        
        Returns:
            Dictionary mapping patterns to standard IDs
        """
        pattern_mappings = {}
        
        for standard_id, standard in self._standards.items():
            patterns = standard.get("applies_to", [])
            for pattern in patterns:
                if pattern not in pattern_mappings:
                    pattern_mappings[pattern] = []
                pattern_mappings[pattern].append(standard_id)
        
        return pattern_mappings

    def _extract_categories(self) -> List[str]:
        """Extract unique categories from all standards.
        
        Returns:
            List of unique categories/tags
        """
        categories = set()
        
        for standard in self._standards.values():
            tags = standard.get("tags", [])
            categories.update(tags)
        
        return sorted(list(categories))

    def _get_standards_summary(self) -> Dict[str, Any]:
        """Get summary of currently loaded standards.
        
        Returns:
            Summary of loaded standards
        """
        return {
            "standards": list(self._standards.values()),
            "total": len(self._standards),
            "categories": self._extract_categories(),
            "patterns": self._build_pattern_mappings(),
            "load_time": self._last_loaded,
            "standards_directory": str(self._standards_dir)
        }

    def get_relevant_standards(self, file_path: str, include_general: bool = True) -> Dict[str, Any]:
        """Get standards relevant to a specific file.
        
        Args:
            file_path: Path to the file to analyze
            include_general: Whether to include general/default standards
            
        Returns:
            Dictionary containing matched standards and metadata
        """
        try:
            # Ensure standards are loaded
            if not self._standards or self._last_loaded is None:
                self.load_standards()

            # Normalize file path
            file_path = str(Path(file_path).resolve())
            project_path = Path(self._project_root).resolve()
            
            try:
                relative_path = str(Path(file_path).relative_to(project_path))
            except ValueError:
                # File is outside project, use absolute path
                relative_path = file_path

            matched_standards = []
            general_standards = []

            # Match patterns
            for standard_id, standard in self._standards.items():
                if not standard.get("enabled", True):
                    continue

                patterns = standard.get("applies_to", [])
                
                if not patterns:
                    # No patterns means it's a general standard
                    if include_general:
                        general_standards.append({
                            "standard": standard,
                            "match_reason": "General/default standard",
                            "specificity": 0.1,
                            "pattern_matched": None
                        })
                    continue

                # Check each pattern
                for pattern in patterns:
                    if self._pattern_matcher.matches(relative_path, pattern):
                        specificity = self._pattern_matcher.calculate_specificity(pattern)
                        matched_standards.append({
                            "standard": standard,
                            "match_reason": f"Pattern '{pattern}' matched",
                            "specificity": specificity,
                            "pattern_matched": pattern
                        })
                        break  # Only count first matching pattern per standard

            # Combine and sort by specificity
            all_matches = matched_standards + general_standards
            all_matches.sort(key=lambda x: (x["specificity"], x["standard"]["priority"]), reverse=True)

            # Extract categories from matched standards
            categories = set()
            for match in all_matches:
                categories.update(match["standard"].get("tags", []))

            return {
                "file_path": relative_path,
                "matched_standards": [
                    {
                        "id": match["standard"]["id"],
                        "name": match["standard"]["name"],
                        "path": match["standard"]["path"],
                        "match_reason": match["match_reason"],
                        "specificity": match["specificity"],
                        "pattern_matched": match["pattern_matched"],
                        "priority": match["standard"]["priority"],
                        "tags": match["standard"].get("tags", []),
                        "severity": match["standard"].get("severity", "error")
                    }
                    for match in all_matches
                ],
                "categories": sorted(list(categories)),
                "total_matches": len(all_matches)
            }

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to get relevant standards: {str(e)}"
                }
            }

    def get_standard_by_id(self, standard_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific standard by ID.
        
        Args:
            standard_id: ID of the standard to retrieve
            
        Returns:
            Standard dictionary or None if not found
        """
        # Ensure standards are loaded
        if not self._standards or self._last_loaded is None:
            self.load_standards()
            
        return self._standards.get(standard_id)

    def get_standards_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all standards that belong to a specific category.
        
        Args:
            category: Category/tag to filter by
            
        Returns:
            List of standards in the category
        """
        # Ensure standards are loaded
        if not self._standards or self._last_loaded is None:
            self.load_standards()

        matching_standards = []
        
        for standard in self._standards.values():
            if category in standard.get("tags", []):
                matching_standards.append(standard)
        
        # Sort by priority
        matching_standards.sort(key=lambda s: s.get("priority", 1), reverse=True)
        
        return matching_standards

    def search_standards(self, query: str) -> List[Dict[str, Any]]:
        """Search standards by name, tags, or content.
        
        Args:
            query: Search query
            
        Returns:
            List of matching standards
        """
        # Ensure standards are loaded
        if not self._standards or self._last_loaded is None:
            self.load_standards()

        query_lower = query.lower()
        matching_standards = []
        
        for standard in self._standards.values():
            score = 0
            
            # Check name
            if query_lower in standard.get("name", "").lower():
                score += 10
            
            # Check ID
            if query_lower in standard["id"].lower():
                score += 8
            
            # Check tags
            for tag in standard.get("tags", []):
                if query_lower in tag.lower():
                    score += 5
            
            # Check content
            content_text = json.dumps(standard.get("content", {})).lower()
            if query_lower in content_text:
                score += 2
            
            if score > 0:
                standard_copy = standard.copy()
                standard_copy["search_score"] = score
                matching_standards.append(standard_copy)
        
        # Sort by search score
        matching_standards.sort(key=lambda s: s["search_score"], reverse=True)
        
        return matching_standards

    def validate_standard(self, standard: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a standard object.
        
        Args:
            standard: Standard to validate
            
        Returns:
            Validation result with errors/warnings
        """
        errors = []
        warnings = []
        
        # Required fields
        if "id" not in standard or not standard["id"]:
            errors.append("Standard must have an 'id' field")
        
        if "name" not in standard or not standard["name"]:
            warnings.append("Standard should have a 'name' field")
        
        # Validate applies_to patterns
        applies_to = standard.get("applies_to", [])
        for pattern in applies_to:
            try:
                from .pattern_matcher import match_pattern
                match_pattern("test/file.py", pattern, "/dummy")
            except Exception as e:
                errors.append(f"Invalid pattern '{pattern}': {e}")
        
        # Validate category
        category = standard.get("category")
        if not category:
            errors.append("Standard must have a 'category' field")
        else:
            valid_categories = ["api", "database", "frontend", "architecture", "security", "pipeline", "general"]
            if category not in valid_categories:
                warnings.append(f"Unknown category '{category}'. Should be one of: {', '.join(valid_categories)}")
        
        # Validate severity
        severity = standard.get("severity", "error")
        if severity not in ["error", "warning", "info"]:
            warnings.append(f"Unknown severity level '{severity}'. Should be one of: error, warning, info")
        
        # Validate priority
        priority = standard.get("priority")
        if not priority:
            errors.append("Standard must have a 'priority' field")
        else:
            valid_priorities = ["required", "important", "recommended"]
            if priority not in valid_priorities:
                warnings.append(f"Unknown priority '{priority}'. Should be one of: {', '.join(valid_priorities)}")
        
        # Check for dependencies
        dependencies = standard.get("dependencies", [])
        for dep_id in dependencies:
            if dep_id not in self._standards:
                warnings.append(f"Dependency '{dep_id}' not found in loaded standards")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "score": max(0, 100 - len(errors) * 20 - len(warnings) * 5)
        }

    def invalidate_cache(self, standard_id: Optional[str] = None) -> None:
        """Invalidate cache for standards.
        
        Args:
            standard_id: Specific standard to invalidate (all if None)
        """
        if standard_id:
            # Invalidate specific standard
            if standard_id in self._standards:
                standard_path = self._standards[standard_id]["absolute_path"]
                self._rule_cache.invalidate_standard(standard_path)
                self._rule_cache.invalidate_rules(standard_id)
        else:
            # Invalidate all standards
            for standard in self._standards.values():
                self._rule_cache.invalidate_standard(standard["absolute_path"])
                self._rule_cache.invalidate_rules(standard["id"])
            
            # Clear in-memory cache
            self._standards.clear()
            self._last_loaded = None

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        # Ensure standards are loaded
        if not self._standards or self._last_loaded is None:
            self.load_standards()

        # Count by category
        category_counts = {}
        for standard in self._standards.values():
            for tag in standard.get("tags", []):
                category_counts[tag] = category_counts.get(tag, 0) + 1

        # Count by severity
        severity_counts = {}
        for standard in self._standards.values():
            severity = standard.get("severity", "error")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Calculate total patterns
        total_patterns = sum(len(s.get("patterns", [])) for s in self._standards.values())
        
        # Calculate average file size
        total_size = sum(s.get("file_size", 0) for s in self._standards.values())
        avg_size = total_size / max(len(self._standards), 1)

        return {
            "total_standards": len(self._standards),
            "total_patterns": total_patterns,
            "total_categories": len(self._extract_categories()),
            "category_distribution": category_counts,
            "severity_distribution": severity_counts,
            "average_file_size_bytes": round(avg_size, 2),
            "total_size_bytes": total_size,
            "last_loaded": self._last_loaded,
            "standards_directory": str(self._standards_dir),
            "cache_stats": self._rule_cache.get_stats()
        }


# Global registry instance
_global_standards_registry: Optional[StandardsRegistry] = None


def get_standards_registry(project_root: Optional[str] = None) -> StandardsRegistry:
    """Get global standards registry instance.
    
    Args:
        project_root: Project root directory (uses global if None)
        
    Returns:
        Global standards registry instance
    """
    global _global_standards_registry
    if _global_standards_registry is None or (project_root and project_root != _global_standards_registry._project_root):
        _global_standards_registry = StandardsRegistry(project_root)
    return _global_standards_registry


def clear_standards_registry() -> None:
    """Clear the global standards registry."""
    global _global_standards_registry
    if _global_standards_registry is not None:
        _global_standards_registry.invalidate_cache()
        _global_standards_registry = None