"""AST caching utilities for performance optimization.

This module provides caching functionality for parsed ASTs to avoid
re-parsing the same files multiple times during analysis operations.
"""

import ast
import hashlib
import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ...filesystem_server._security import get_project_root


class ASTCache:
    """Cache for parsed Abstract Syntax Trees (ASTs).
    
    Provides in-memory and optional persistent caching of parsed ASTs
    with automatic cache invalidation based on file modification times.
    """

    def __init__(self, max_size: int = 1000, enable_persistent: bool = True):
        """Initialize AST cache.
        
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
            self._cache_dir = Path(project_root) / ".aromcp" / "cache" / "ast"
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fall back to memory-only cache if persistent cache fails
            self._enable_persistent = False
            self._cache_dir = None

    def get(self, file_path: str) -> Optional[ast.AST]:
        """Get cached AST for a file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Cached AST or None if not found or invalid
        """
        # Normalize file path
        file_path = str(Path(file_path).resolve())
        
        # Check if file exists
        if not Path(file_path).exists():
            return None
            
        # Get file modification time
        try:
            file_mtime = Path(file_path).stat().st_mtime
        except OSError:
            return None

        # Check memory cache first
        if file_path in self._memory_cache:
            cache_entry = self._memory_cache[file_path]
            if cache_entry["mtime"] >= file_mtime:
                # Update access time
                self._access_times[file_path] = time.time()
                return cache_entry["ast"]
            else:
                # File modified, invalidate cache entry
                del self._memory_cache[file_path]
                if file_path in self._access_times:
                    del self._access_times[file_path]

        # Check persistent cache
        if self._enable_persistent and self._cache_dir:
            cached_ast = self._load_from_persistent_cache(file_path, file_mtime)
            if cached_ast is not None:
                # Store in memory cache for faster access
                self._store_in_memory(file_path, cached_ast, file_mtime)
                return cached_ast

        return None

    def put(self, file_path: str, parsed_ast: ast.AST) -> None:
        """Store AST in cache.
        
        Args:
            file_path: Path to the source file
            parsed_ast: Parsed AST to cache
        """
        # Normalize file path
        file_path = str(Path(file_path).resolve())
        
        # Get file modification time
        try:
            file_mtime = Path(file_path).stat().st_mtime
        except OSError:
            return

        # Store in memory cache
        self._store_in_memory(file_path, parsed_ast, file_mtime)
        
        # Store in persistent cache
        if self._enable_persistent and self._cache_dir:
            self._store_in_persistent_cache(file_path, parsed_ast, file_mtime)

    def _store_in_memory(self, file_path: str, parsed_ast: ast.AST, file_mtime: float) -> None:
        """Store AST in memory cache with LRU eviction.
        
        Args:
            file_path: Path to the source file
            parsed_ast: Parsed AST to cache
            file_mtime: File modification time
        """
        # Evict least recently used entries if cache is full
        if len(self._memory_cache) >= self._max_size and file_path not in self._memory_cache:
            self._evict_lru()

        # Store the AST
        self._memory_cache[file_path] = {
            "ast": parsed_ast,
            "mtime": file_mtime,
            "cached_at": time.time()
        }
        self._access_times[file_path] = time.time()

    def _evict_lru(self) -> None:
        """Evict least recently used cache entry."""
        if not self._access_times:
            return
            
        # Find least recently used entry
        lru_file = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        
        # Remove from caches
        if lru_file in self._memory_cache:
            del self._memory_cache[lru_file]
        del self._access_times[lru_file]

    def _get_cache_file_path(self, file_path: str) -> Path:
        """Get cache file path for a source file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Path to the cache file
        """
        # Create hash of file path for cache filename
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return self._cache_dir / f"{file_hash}.ast_cache"

    def _load_from_persistent_cache(self, file_path: str, file_mtime: float) -> Optional[ast.AST]:
        """Load AST from persistent cache.
        
        Args:
            file_path: Path to the source file
            file_mtime: File modification time
            
        Returns:
            Cached AST or None if not found or invalid
        """
        try:
            cache_file = self._get_cache_file_path(file_path)
            
            if not cache_file.exists():
                return None
                
            # Load cache metadata and content
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                
            # Validate cache entry
            if (cache_data.get("file_path") != file_path or
                cache_data.get("mtime", 0) < file_mtime):
                # Cache is stale, remove it
                cache_file.unlink(missing_ok=True)
                return None
                
            return cache_data.get("ast")
            
        except Exception:
            # Cache loading failed, ignore
            return None

    def _store_in_persistent_cache(self, file_path: str, parsed_ast: ast.AST, file_mtime: float) -> None:
        """Store AST in persistent cache.
        
        Args:
            file_path: Path to the source file
            parsed_ast: Parsed AST to cache
            file_mtime: File modification time
        """
        try:
            cache_file = self._get_cache_file_path(file_path)
            
            cache_data = {
                "file_path": file_path,
                "ast": parsed_ast,
                "mtime": file_mtime,
                "cached_at": time.time()
            }
            
            # Write cache file atomically
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                pickle.dump(cache_data, f)
            temp_file.rename(cache_file)
            
        except Exception:
            # Cache storage failed, ignore
            pass

    def parse_file(self, file_path: str) -> Optional[ast.AST]:
        """Parse file with caching.
        
        Args:
            file_path: Path to the Python file to parse
            
        Returns:
            Parsed AST or None if parsing failed
        """
        # Check cache first
        cached_ast = self.get(file_path)
        if cached_ast is not None:
            return cached_ast

        # Parse file
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            parsed_ast = ast.parse(content, filename=file_path)
            
            # Store in cache
            self.put(file_path, parsed_ast)
            
            return parsed_ast
            
        except (SyntaxError, OSError):
            # Parsing failed
            return None

    def invalidate(self, file_path: str) -> None:
        """Invalidate cache entry for a file.
        
        Args:
            file_path: Path to the file to invalidate
        """
        file_path = str(Path(file_path).resolve())
        
        # Remove from memory cache
        if file_path in self._memory_cache:
            del self._memory_cache[file_path]
        if file_path in self._access_times:
            del self._access_times[file_path]
            
        # Remove from persistent cache
        if self._enable_persistent and self._cache_dir:
            try:
                cache_file = self._get_cache_file_path(file_path)
                cache_file.unlink(missing_ok=True)
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
                for cache_file in self._cache_dir.glob("*.ast_cache"):
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
                persistent_size = len(list(self._cache_dir.glob("*.ast_cache")))
            except Exception:
                persistent_size = 0

        return {
            "memory_entries": memory_size,
            "persistent_entries": persistent_size,
            "max_memory_size": self._max_size,
            "persistent_cache_enabled": self._enable_persistent,
            "cache_directory": str(self._cache_dir) if self._cache_dir else None
        }

    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
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
        expired_files = []
        for file_path, cache_entry in self._memory_cache.items():
            if current_time - cache_entry["cached_at"] > max_age_seconds:
                expired_files.append(file_path)

        for file_path in expired_files:
            del self._memory_cache[file_path]
            if file_path in self._access_times:
                del self._access_times[file_path]
            removed_count += 1

        # Clean persistent cache
        if self._enable_persistent and self._cache_dir and self._cache_dir.exists():
            try:
                for cache_file in self._cache_dir.glob("*.ast_cache"):
                    try:
                        with open(cache_file, 'rb') as f:
                            cache_data = pickle.load(f)
                        
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
_global_ast_cache: Optional[ASTCache] = None


def get_ast_cache() -> ASTCache:
    """Get global AST cache instance.
    
    Returns:
        Global AST cache instance
    """
    global _global_ast_cache
    if _global_ast_cache is None:
        _global_ast_cache = ASTCache()
    return _global_ast_cache


def parse_file_cached(file_path: str) -> Optional[ast.AST]:
    """Parse Python file with global cache.
    
    Args:
        file_path: Path to the Python file to parse
        
    Returns:
        Parsed AST or None if parsing failed
    """
    return get_ast_cache().parse_file(file_path)


def clear_ast_cache() -> None:
    """Clear the global AST cache."""
    global _global_ast_cache
    if _global_ast_cache is not None:
        _global_ast_cache.clear()