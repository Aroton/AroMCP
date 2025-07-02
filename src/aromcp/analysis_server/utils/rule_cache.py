"""Rule caching utilities for performance optimization.

This module provides caching functionality for generated ESLint rules and
parsed coding standards to avoid regenerating the same rules multiple times.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...filesystem_server._security import get_project_root


class RuleCache:
    """Cache for generated ESLint rules and parsed standards.
    
    Provides in-memory and persistent caching of generated rules with
    automatic cache invalidation based on source file modifications.
    """

    def __init__(self, max_size: int = 500, enable_persistent: bool = True):
        """Initialize rule cache.
        
        Args:
            max_size: Maximum number of entries to keep in memory
            enable_persistent: Whether to enable persistent disk cache
        """
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._max_size = max_size
        self._enable_persistent = enable_persistent
        self._cache_dir: Optional[Path] = None
        
        if enable_persistent:
            self._init_persistent_cache()

    def _init_persistent_cache(self) -> None:
        """Initialize persistent cache directory."""
        try:
            project_root = get_project_root()
            self._cache_dir = Path(project_root) / ".aromcp" / "cache" / "rules"
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fall back to memory-only cache if persistent cache fails
            self._enable_persistent = False
            self._cache_dir = None

    def _generate_cache_key(self, standard_id: str, content_hash: str, options: Dict[str, Any]) -> str:
        """Generate cache key for a rule generation request.
        
        Args:
            standard_id: ID of the coding standard
            content_hash: Hash of the standard content
            options: Generation options that affect output
            
        Returns:
            Cache key string
        """
        # Include options that affect rule generation
        key_data = {
            "standard_id": standard_id,
            "content_hash": content_hash,
            "options": sorted(options.items())
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_content_hash(self, content: str) -> str:
        """Generate hash of content for cache invalidation.
        
        Args:
            content: Content to hash
            
        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content.encode()).hexdigest()

    def get_generated_rules(self, standard_id: str, content: str, options: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get cached generated rules for a standard.
        
        Args:
            standard_id: ID of the coding standard
            content: Standard content (for cache invalidation)
            options: Generation options
            
        Returns:
            Cached rules or None if not found or invalid
        """
        if options is None:
            options = {}
            
        content_hash = self._get_content_hash(content)
        cache_key = self._generate_cache_key(standard_id, content_hash, options)
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            cache_entry = self._memory_cache[cache_key]
            # Update access time
            self._access_times[cache_key] = time.time()
            return cache_entry["rules"]

        # Check persistent cache
        if self._enable_persistent and self._cache_dir:
            cached_rules = self._load_from_persistent_cache(cache_key)
            if cached_rules is not None:
                # Store in memory cache for faster access
                self._store_in_memory(cache_key, cached_rules)
                return cached_rules

        return None

    def put_generated_rules(self, standard_id: str, content: str, rules: Dict[str, Any], options: Dict[str, Any] = None) -> None:
        """Store generated rules in cache.
        
        Args:
            standard_id: ID of the coding standard
            content: Standard content
            rules: Generated rules to cache
            options: Generation options
        """
        if options is None:
            options = {}
            
        content_hash = self._get_content_hash(content)
        cache_key = self._generate_cache_key(standard_id, content_hash, options)
        
        # Store in memory cache
        self._store_in_memory(cache_key, rules)
        
        # Store in persistent cache
        if self._enable_persistent and self._cache_dir:
            self._store_in_persistent_cache(cache_key, rules, {
                "standard_id": standard_id,
                "content_hash": content_hash,
                "options": options
            })

    def _store_in_memory(self, cache_key: str, rules: Dict[str, Any]) -> None:
        """Store rules in memory cache with LRU eviction.
        
        Args:
            cache_key: Cache key
            rules: Rules to cache
        """
        # Evict least recently used entries if cache is full
        if len(self._memory_cache) >= self._max_size and cache_key not in self._memory_cache:
            self._evict_lru()

        # Store the rules
        self._memory_cache[cache_key] = {
            "rules": rules,
            "cached_at": time.time()
        }
        self._access_times[cache_key] = time.time()

    def _evict_lru(self) -> None:
        """Evict least recently used cache entry."""
        if not self._access_times:
            return
            
        # Find least recently used entry
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        
        # Remove from caches
        if lru_key in self._memory_cache:
            del self._memory_cache[lru_key]
        del self._access_times[lru_key]

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to the cache file
        """
        return self._cache_dir / f"{cache_key}.rule_cache"

    def _load_from_persistent_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load rules from persistent cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached rules or None if not found or invalid
        """
        try:
            cache_file = self._get_cache_file_path(cache_key)
            
            if not cache_file.exists():
                return None
                
            # Load cache content
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            return cache_data.get("rules")
            
        except Exception:
            # Cache loading failed, ignore
            return None

    def _store_in_persistent_cache(self, cache_key: str, rules: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Store rules in persistent cache.
        
        Args:
            cache_key: Cache key
            rules: Rules to cache
            metadata: Additional metadata
        """
        try:
            cache_file = self._get_cache_file_path(cache_key)
            
            cache_data = {
                "rules": rules,
                "metadata": metadata,
                "cached_at": time.time()
            }
            
            # Write cache file atomically
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            temp_file.rename(cache_file)
            
        except Exception:
            # Cache storage failed, ignore
            pass

    def get_parsed_standard(self, standard_path: str) -> Optional[Dict[str, Any]]:
        """Get cached parsed standard.
        
        Args:
            standard_path: Path to the standard file
            
        Returns:
            Cached parsed standard or None if not found or invalid
        """
        # Check if file exists and get modification time
        try:
            file_path = Path(standard_path)
            if not file_path.exists():
                return None
            file_mtime = file_path.stat().st_mtime
        except OSError:
            return None

        # Generate cache key based on file path
        cache_key = f"standard_{hashlib.md5(standard_path.encode()).hexdigest()}"
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            cache_entry = self._memory_cache[cache_key]
            if cache_entry.get("mtime", 0) >= file_mtime:
                # Update access time
                self._access_times[cache_key] = time.time()
                return cache_entry["standard"]
            else:
                # File modified, invalidate cache entry
                del self._memory_cache[cache_key]
                if cache_key in self._access_times:
                    del self._access_times[cache_key]

        # Check persistent cache
        if self._enable_persistent and self._cache_dir:
            cached_standard = self._load_standard_from_persistent_cache(cache_key, file_mtime)
            if cached_standard is not None:
                # Store in memory cache for faster access
                self._store_standard_in_memory(cache_key, cached_standard, file_mtime)
                return cached_standard

        return None

    def put_parsed_standard(self, standard_path: str, parsed_standard: Dict[str, Any]) -> None:
        """Store parsed standard in cache.
        
        Args:
            standard_path: Path to the standard file
            parsed_standard: Parsed standard to cache
        """
        # Get file modification time
        try:
            file_mtime = Path(standard_path).stat().st_mtime
        except OSError:
            return

        # Generate cache key
        cache_key = f"standard_{hashlib.md5(standard_path.encode()).hexdigest()}"
        
        # Store in memory cache
        self._store_standard_in_memory(cache_key, parsed_standard, file_mtime)
        
        # Store in persistent cache
        if self._enable_persistent and self._cache_dir:
            self._store_standard_in_persistent_cache(cache_key, parsed_standard, standard_path, file_mtime)

    def _store_standard_in_memory(self, cache_key: str, standard: Dict[str, Any], file_mtime: float) -> None:
        """Store standard in memory cache.
        
        Args:
            cache_key: Cache key
            standard: Standard to cache
            file_mtime: File modification time
        """
        # Evict least recently used entries if cache is full
        if len(self._memory_cache) >= self._max_size and cache_key not in self._memory_cache:
            self._evict_lru()

        # Store the standard
        self._memory_cache[cache_key] = {
            "standard": standard,
            "mtime": file_mtime,
            "cached_at": time.time()
        }
        self._access_times[cache_key] = time.time()

    def _load_standard_from_persistent_cache(self, cache_key: str, file_mtime: float) -> Optional[Dict[str, Any]]:
        """Load standard from persistent cache.
        
        Args:
            cache_key: Cache key
            file_mtime: File modification time
            
        Returns:
            Cached standard or None if not found or invalid
        """
        try:
            cache_file = self._get_cache_file_path(cache_key)
            
            if not cache_file.exists():
                return None
                
            # Load cache content
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # Validate cache entry
            if cache_data.get("mtime", 0) < file_mtime:
                # Cache is stale, remove it
                cache_file.unlink(missing_ok=True)
                return None
                
            return cache_data.get("standard")
            
        except Exception:
            # Cache loading failed, ignore
            return None

    def _store_standard_in_persistent_cache(self, cache_key: str, standard: Dict[str, Any], standard_path: str, file_mtime: float) -> None:
        """Store standard in persistent cache.
        
        Args:
            cache_key: Cache key
            standard: Standard to cache
            standard_path: Path to standard file
            file_mtime: File modification time
        """
        try:
            cache_file = self._get_cache_file_path(cache_key)
            
            cache_data = {
                "standard": standard,
                "standard_path": standard_path,
                "mtime": file_mtime,
                "cached_at": time.time()
            }
            
            # Write cache file atomically
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            temp_file.rename(cache_file)
            
        except Exception:
            # Cache storage failed, ignore
            pass

    def invalidate_standard(self, standard_path: str) -> None:
        """Invalidate cache entry for a standard file.
        
        Args:
            standard_path: Path to the standard file to invalidate
        """
        cache_key = f"standard_{hashlib.md5(standard_path.encode()).hexdigest()}"
        
        # Remove from memory cache
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        if cache_key in self._access_times:
            del self._access_times[cache_key]
            
        # Remove from persistent cache
        if self._enable_persistent and self._cache_dir:
            try:
                cache_file = self._get_cache_file_path(cache_key)
                cache_file.unlink(missing_ok=True)
            except Exception:
                pass

    def invalidate_rules(self, standard_id: str) -> None:
        """Invalidate all cached rules for a standard.
        
        Args:
            standard_id: ID of the standard to invalidate
        """
        # Find and remove memory cache entries
        keys_to_remove = []
        for cache_key, cache_entry in self._memory_cache.items():
            if cache_entry.get("metadata", {}).get("standard_id") == standard_id:
                keys_to_remove.append(cache_key)
        
        for cache_key in keys_to_remove:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            if cache_key in self._access_times:
                del self._access_times[cache_key]
        
        # Remove persistent cache entries
        if self._enable_persistent and self._cache_dir and self._cache_dir.exists():
            try:
                for cache_file in self._cache_dir.glob("*.rule_cache"):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        if cache_data.get("metadata", {}).get("standard_id") == standard_id:
                            cache_file.unlink()
                    except Exception:
                        continue
            except Exception:
                pass

    def clear(self) -> None:
        """Clear all cache entries."""
        # Clear memory cache
        self._memory_cache.clear()
        self._access_times.clear()
        
        # Clear persistent cache
        if self._enable_persistent and self._cache_dir and self._cache_dir.exists():
            try:
                for cache_file in self._cache_dir.glob("*.rule_cache"):
                    cache_file.unlink(missing_ok=True)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        memory_size = len(self._memory_cache)
        
        persistent_size = 0
        if self._enable_persistent and self._cache_dir and self._cache_dir.exists():
            try:
                persistent_size = len(list(self._cache_dir.glob("*.rule_cache")))
            except Exception:
                persistent_size = 0

        # Count different types of cached entries
        rule_entries = 0
        standard_entries = 0
        
        for cache_key in self._memory_cache:
            if cache_key.startswith("standard_"):
                standard_entries += 1
            else:
                rule_entries += 1

        return {
            "memory_entries": memory_size,
            "persistent_entries": persistent_size,
            "rule_entries": rule_entries,
            "standard_entries": standard_entries,
            "max_memory_size": self._max_size,
            "persistent_cache_enabled": self._enable_persistent,
            "cache_directory": str(self._cache_dir) if self._cache_dir else None
        }

    def cleanup_old_entries(self, max_age_hours: int = 48) -> int:
        """Clean up old cache entries.
        
        Args:
            max_age_hours: Maximum age of cache entries in hours
            
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        removed_count = 0

        # Clean memory cache
        expired_keys = []
        for cache_key, cache_entry in self._memory_cache.items():
            if current_time - cache_entry["cached_at"] > max_age_seconds:
                expired_keys.append(cache_key)

        for cache_key in expired_keys:
            del self._memory_cache[cache_key]
            if cache_key in self._access_times:
                del self._access_times[cache_key]
            removed_count += 1

        # Clean persistent cache
        if self._enable_persistent and self._cache_dir and self._cache_dir.exists():
            try:
                for cache_file in self._cache_dir.glob("*.rule_cache"):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        if current_time - cache_data.get("cached_at", 0) > max_age_seconds:
                            cache_file.unlink()
                            removed_count += 1
                    except Exception:
                        # Remove corrupted cache files
                        cache_file.unlink(missing_ok=True)
                        removed_count += 1
            except Exception:
                pass

        return removed_count


# Global cache instance
_global_rule_cache: Optional[RuleCache] = None


def get_rule_cache() -> RuleCache:
    """Get global rule cache instance.
    
    Returns:
        Global rule cache instance
    """
    global _global_rule_cache
    if _global_rule_cache is None:
        _global_rule_cache = RuleCache()
    return _global_rule_cache


def clear_rule_cache() -> None:
    """Clear the global rule cache."""
    global _global_rule_cache
    if _global_rule_cache is not None:
        _global_rule_cache.clear()