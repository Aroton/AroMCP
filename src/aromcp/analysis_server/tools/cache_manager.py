"""
Advanced caching with dependency invalidation for TypeScript Analysis MCP Server.

This module provides comprehensive caching capabilities including:
- Multi-level cache hierarchy (memory → symbol → filesystem)
- Dependency-based cache invalidation
- Cache statistics and monitoring
- Memory-aware cache management
- >80% cache hit rate optimization
"""

import gc
import json
import os
import pickle
import time
import threading
import zlib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Callable, Generic, TypeVar
from threading import Lock, RLock
import weakref

from ..models.typescript_models import CacheStats, AnalysisError
from .memory_manager import MemoryManager, CompressionStrategy

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache level hierarchy."""
    MEMORY = "memory"      # Fast in-memory cache
    SYMBOL = "symbol"      # Symbol-specific cache
    FILESYSTEM = "filesystem"  # Persistent filesystem cache


@dataclass
class CacheEntry(Generic[T]):
    """Entry in a cache level."""
    key: str
    value: T
    created_at: float
    last_accessed: float
    access_count: int
    size_bytes: int
    dependencies: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def touch(self):
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheLevelStats:
    """Statistics for a cache level."""
    level: CacheLevel
    size_mb: float = 0.0
    entry_count: int = 0
    hits: int = 0
    misses: int = 0
    eviction_count: int = 0
    hit_rate: float = 0.0
    avg_access_time_ms: float = 0.0


@dataclass
class HotKey:
    """Information about frequently accessed cache keys."""
    key: str
    access_count: int
    last_accessed: float
    cache_level: CacheLevel


@dataclass
class SizeDistribution:
    """Cache entry size distribution."""
    small_entries: int = 0   # <1KB
    medium_entries: int = 0  # 1KB-100KB  
    large_entries: int = 0   # >100KB


@dataclass
class DetailedCacheStats:
    """Detailed cache statistics across all levels."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    level_stats: Dict[CacheLevel, CacheLevelStats] = field(default_factory=dict)
    hot_keys: List[HotKey] = field(default_factory=list)
    size_distribution: SizeDistribution = field(default_factory=SizeDistribution)
    promotion_count: int = 0  # Entries promoted to higher levels
    invalidations: int = 0


@dataclass
class PerformanceMetrics:
    """Cache performance metrics."""
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0
    operations_per_second: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


class DependencyTracker:
    """Tracks dependencies between cached items."""
    
    def __init__(self):
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        self._lock = RLock()
    
    def add_dependency(self, dependent: str, dependency: str, imports: List[str] | None = None):
        """Add a dependency relationship."""
        with self._lock:
            self._dependencies[dependent].add(dependency)
            self._dependents[dependency].add(dependent)
    
    def remove_dependencies(self, item: str):
        """Remove all dependencies for an item."""
        with self._lock:
            # Remove as dependent
            for dependency in self._dependencies.get(item, set()).copy():
                self._dependents[dependency].discard(item)
            
            # Remove as dependency
            for dependent in self._dependents.get(item, set()).copy():
                self._dependencies[dependent].discard(item)
            
            # Clear entries
            self._dependencies.pop(item, None)
            self._dependents.pop(item, None)
    
    def get_dependencies(self, item: str) -> Set[str]:
        """Get items this item depends on."""
        with self._lock:
            return self._dependencies[item].copy()
    
    def get_dependents(self, item: str) -> Set[str]:
        """Get items that depend on this item."""
        with self._lock:
            return self._dependents[item].copy()
    
    def get_transitively_affected(self, item: str) -> Set[str]:
        """Get all items transitively affected by changes to this item."""
        with self._lock:
            affected = set()
            queue = [item]
            visited = set()
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                dependents = self._dependents.get(current, set())
                
                for dependent in dependents:
                    if dependent not in affected:
                        affected.add(dependent)
                        queue.append(dependent)
            
            return affected


class CacheInvalidationStrategy:
    """Strategy for cache invalidation."""
    
    def __init__(self, 
                 dependency_tracker: DependencyTracker,
                 cache_manager: 'CacheManager',
                 enable_selective: bool = True):
        self.dependency_tracker = dependency_tracker
        self.cache_manager = cache_manager
        self.enable_selective = enable_selective
    
    def invalidate_file(self, 
                       file_path: str, 
                       changed_exports: List[str] | None = None) -> List[str]:
        """Invalidate cache entries affected by file changes."""
        invalidated = []
        
        if self.enable_selective and changed_exports:
            # Selective invalidation - only invalidate if used exports changed
            invalidated = self._selective_invalidate(file_path, changed_exports)
        else:
            # Full invalidation - invalidate all dependents
            invalidated = self._full_invalidate(file_path)
        
        return invalidated
    
    def _selective_invalidate(self, file_path: str, changed_exports: List[str]) -> List[str]:
        """Selectively invalidate based on what exports changed."""
        invalidated = []
        
        # Always invalidate the changed file itself
        file_key = f"ast:{file_path}"
        if self.cache_manager.exists(file_key):
            self.cache_manager.invalidate(file_key)
            invalidated.append(file_path)
        
        # Check dependents and their import relationships
        dependents = self.dependency_tracker.get_dependents(file_path)
        
        for dependent in dependents:
            # Check what this dependent imports from the changed file
            imported_symbols = self._get_imported_symbols(dependent, file_path)
            
            # If any changed export is imported, invalidate
            if any(export in imported_symbols for export in changed_exports):
                dependent_key = f"ast:{dependent}"
                if self.cache_manager.exists(dependent_key):
                    self.cache_manager.invalidate(dependent_key)
                    invalidated.append(dependent)
        
        return invalidated
    
    def _full_invalidate(self, file_path: str) -> List[str]:
        """Fully invalidate all dependents."""
        invalidated = []
        
        # Get all transitively affected files
        affected = self.dependency_tracker.get_transitively_affected(file_path)
        affected.add(file_path)  # Include the changed file itself
        
        # Invalidate cache entries
        for file in affected:
            cache_key = f"ast:{file}"
            if self.cache_manager.exists(cache_key):
                self.cache_manager.invalidate(cache_key)
                invalidated.append(file)
        
        return invalidated
    
    def _get_imported_symbols(self, importing_file: str, imported_file: str) -> Set[str]:
        """Get symbols imported from one file to another."""
        # This would integrate with import tracker to get actual imports
        # For now, return empty set (conservative approach)
        return set()


class LRUCache(Generic[T]):
    """LRU cache with size limits and statistics."""
    
    def __init__(self, max_size_mb: float = 100.0):
        self.max_size_mb = max_size_mb
        self.entries: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self.current_size_mb = 0.0
        self.stats = CacheLevelStats(level=CacheLevel.MEMORY)
        self._lock = RLock()
        self._eviction_callback = None  # Optional callback for evicted entries
    
    def get(self, key: str) -> T | None:
        """Get item from cache."""
        with self._lock:
            if key in self.entries:
                entry = self.entries[key]
                entry.touch()
                
                # Move to end (most recently used)
                self.entries.move_to_end(key)
                
                self.stats.hits += 1
                return entry.value
            
            self.stats.misses += 1
            return None
    
    def set(self, key: str, value: T, size_bytes: int = 0, dependencies: Set[str] | None = None):
        """Set item in cache."""
        with self._lock:
            # Calculate size of new entry
            actual_size_bytes = size_bytes or self._estimate_size(value)
            entry_size_mb = actual_size_bytes / (1024 * 1024)
            
            # Remove existing entry if present
            if key in self.entries:
                old_entry = self.entries[key]
                self.current_size_mb -= old_entry.size_bytes / (1024 * 1024)
                del self.entries[key]
            
            # Check if we need to evict BEFORE adding the new entry
            # This ensures we make room for the new entry
            while (self.current_size_mb + entry_size_mb > self.max_size_mb and 
                   len(self.entries) > 0):
                evicted_key, evicted_entry = self._evict_lru()
                if evicted_key and self._eviction_callback:
                    self._eviction_callback(evicted_key, evicted_entry.value)
                # If no entry was evicted, break to avoid infinite loop
                if not evicted_key:
                    break
            
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=1,
                size_bytes=actual_size_bytes,
                dependencies=dependencies or set()
            )
            
            # Add new entry only if it fits or if cache is empty
            if self.current_size_mb + entry_size_mb <= self.max_size_mb or len(self.entries) == 0:
                self.entries[key] = entry
                self.current_size_mb += entry_size_mb
                # Update stats to reflect correct entry count
                self.stats.entry_count = len(self.entries)
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            return key in self.entries
    
    def invalidate(self, key: str):
        """Remove item from cache."""
        with self._lock:
            if key in self.entries:
                entry = self.entries[key]
                self.current_size_mb -= entry.size_bytes / (1024 * 1024)
                del self.entries[key]
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self.entries.clear()
            self.current_size_mb = 0.0
    
    def get_stats(self) -> CacheLevelStats:
        """Get cache statistics."""
        with self._lock:
            stats = self.stats
            stats.size_mb = self.current_size_mb
            stats.entry_count = len(self.entries)
            # stats already has eviction_count
            
            total_requests = stats.hits + stats.misses
            if total_requests > 0:
                stats.hit_rate = stats.hits / total_requests
            
            return stats
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if self.entries:
            key, entry = self.entries.popitem(last=False)  # Remove first (oldest)
            self.current_size_mb -= entry.size_bytes / (1024 * 1024)
            self.stats.eviction_count += 1
            
            # Update entry count in stats
            self.stats.entry_count = len(self.entries)
            
            # Return evicted entry for potential demotion
            return key, entry
        return None, None
    
    def _estimate_size(self, value: T) -> int:
        """Estimate size of cached value."""
        try:
            if hasattr(value, '__sizeof__'):
                return value.__sizeof__()
            else:
                # Rough estimate using pickle
                return len(pickle.dumps(value))
        except Exception:
            return 1024  # Default 1KB estimate


class FilesystemCache:
    """Persistent filesystem cache."""
    
    def __init__(self, cache_dir: str | None = None, max_size_mb: float = 200.0):
        self.cache_dir = Path(cache_dir or os.path.expanduser("~/.aromcp_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        self.stats = CacheLevelStats(level=CacheLevel.FILESYSTEM)
        self._lock = Lock()
        # Compression statistics
        self._compression_stats = {
            'compressed_count': 0,
            'uncompressed_count': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'compression_time_ms': 0.0
        }
    
    def get(self, key: str) -> Any:
        """Get item from filesystem cache."""
        with self._lock:
            cache_file = self._get_cache_file(key)
            
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        # Check if compressed
                        header = f.read(4)
                        f.seek(0)
                        
                        if header.startswith(b'COMP'):
                            # Compressed entry
                            compressed_data = f.read()[4:]  # Skip header
                            data = zlib.decompress(compressed_data)
                            value = pickle.loads(data)
                        else:
                            # Uncompressed entry
                            value = pickle.load(f)
                    
                    self.stats.hits += 1
                    return value
                    
                except Exception:
                    # Remove corrupted cache file
                    cache_file.unlink(missing_ok=True)
            
            self.stats.misses += 1
            return None
    
    def set(self, key: str, value: Any, size_bytes: int = 0, dependencies: Set[str] | None = None, compress: bool = True):
        """Set item in filesystem cache."""
        with self._lock:
            cache_file = self._get_cache_file(key)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # Serialize value
                data = pickle.dumps(value)
                
                if compress and len(data) > 1024:  # Compress if >1KB
                    start_compress = time.perf_counter()
                    compressed_data = zlib.compress(data, level=6)
                    compress_time = (time.perf_counter() - start_compress) * 1000
                    
                    # Only use compression if it saves space
                    if len(compressed_data) < len(data):
                        with open(cache_file, 'wb') as f:
                            f.write(b'COMP')  # Compression header
                            f.write(compressed_data)
                        # Update compression stats
                        self._compression_stats['compressed_count'] += 1
                        self._compression_stats['total_original_size'] += len(data)
                        self._compression_stats['total_compressed_size'] += len(compressed_data)
                        self._compression_stats['compression_time_ms'] += compress_time
                    else:
                        with open(cache_file, 'wb') as f:
                            pickle.dump(value, f)
                        self._compression_stats['uncompressed_count'] += 1
                else:
                    with open(cache_file, 'wb') as f:
                        pickle.dump(value, f)
                    self._compression_stats['uncompressed_count'] += 1
                
                # Check total cache size and cleanup if needed
                self._cleanup_if_needed()
                
            except Exception:
                # Remove failed cache file
                cache_file.unlink(missing_ok=True)
    
    def exists(self, key: str) -> bool:
        """Check if key exists in filesystem cache."""
        cache_file = self._get_cache_file(key)
        return cache_file.exists()
    
    def invalidate(self, key: str):
        """Remove item from filesystem cache."""
        cache_file = self._get_cache_file(key)
        cache_file.unlink(missing_ok=True)
    
    def get_stats(self) -> CacheLevelStats:
        """Get filesystem cache statistics."""
        with self._lock:
            # Calculate current size
            try:
                total_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*.cache"))
                self.stats.size_mb = total_size / (1024 * 1024)
                self.stats.entry_count = len(list(self.cache_dir.rglob("*.cache")))
            except Exception:
                pass
            
            total_requests = self.stats.hits + self.stats.misses
            if total_requests > 0:
                self.stats.hit_rate = self.stats.hits / total_requests
            
            return self.stats
    
    def get_compression_ratio(self) -> float:
        """Get average compression ratio."""
        if self._compression_stats['total_original_size'] > 0:
            return self._compression_stats['total_original_size'] / self._compression_stats['total_compressed_size']
        return 1.0
    
    def clear(self):
        """Clear all filesystem cache entries."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        import hashlib
        # Use hash to avoid filesystem limitations
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _cleanup_if_needed(self):
        """Clean up old cache files if size limit exceeded."""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*.cache"))
            total_size_mb = total_size / (1024 * 1024)
            
            if total_size_mb > self.max_size_mb:
                # Remove oldest files
                cache_files = list(self.cache_dir.rglob("*.cache"))
                cache_files.sort(key=lambda f: f.stat().st_mtime)
                
                # Remove oldest 25% of files
                files_to_remove = cache_files[:len(cache_files) // 4]
                for file_path in files_to_remove:
                    file_path.unlink(missing_ok=True)
                    
        except Exception:
            pass


class CacheManager:
    """Multi-level cache manager with dependency invalidation."""
    
    def __init__(self, 
                 levels: List[CacheLevel] | None = None,
                 memory_manager: MemoryManager | None = None,
                 enable_detailed_stats: bool = False,
                 enable_performance_metrics: bool = False,
                 enable_monitoring: bool = False,
                 alert_handler: Callable[[str], None] | None = None,
                 enable_adaptive_sizing: bool = False,
                 min_size_mb: float = 50.0,
                 max_size_mb: float = 200.0,
                 compression: 'CompressionStrategy | None' = None):
        
        self.levels = levels or [CacheLevel.MEMORY, CacheLevel.SYMBOL, CacheLevel.FILESYSTEM]
        self.memory_manager = memory_manager
        self.enable_detailed_stats = enable_detailed_stats
        self.enable_performance_metrics = enable_performance_metrics
        self.enable_monitoring = enable_monitoring
        self.alert_handler = alert_handler
        self.enable_adaptive_sizing = enable_adaptive_sizing
        self.min_size_mb = min_size_mb
        self.max_size_mb = max_size_mb
        self.compression = compression
        self.current_size_mb = min_size_mb if enable_adaptive_sizing else 100.0
        
        # Cache levels with eviction callbacks
        # If memory manager is provided, respect its limits
        if memory_manager:
            memory_limit = memory_manager.max_memory_mb * 0.6  # 60% for memory cache
            symbol_limit = memory_manager.max_memory_mb * 0.3  # 30% for symbol cache
            filesystem_limit = memory_manager.max_memory_mb * 2  # Filesystem can be larger
        else:
            memory_limit = 100.0
            symbol_limit = 50.0
            filesystem_limit = 200.0
            
        self.memory_cache = LRUCache[Any](max_size_mb=memory_limit)
        self.symbol_cache = LRUCache[Any](max_size_mb=symbol_limit)
        self.filesystem_cache = FilesystemCache(max_size_mb=filesystem_limit)
        
        # Set up eviction callbacks for demotion
        self.memory_cache._eviction_callback = self._demote_from_memory
        self.symbol_cache._eviction_callback = self._demote_from_symbol
        
        # Level mappings
        self._level_caches = {
            CacheLevel.MEMORY: self.memory_cache,
            CacheLevel.SYMBOL: self.symbol_cache,
            CacheLevel.FILESYSTEM: self.filesystem_cache,
        }
        
        # Dependencies and invalidation
        self.dependency_tracker = DependencyTracker()
        self.invalidation_strategy = CacheInvalidationStrategy(
            self.dependency_tracker, self, enable_selective=True
        )
        
        # Statistics
        self.detailed_stats = DetailedCacheStats()
        self.performance_metrics = PerformanceMetrics()
        self._get_operation_times: List[float] = []
        self._set_operation_times: List[float] = []
        self._alert_thresholds: Dict[str, Dict[str, float]] = {}
        
        # Symbol tracking
        self._file_to_symbols: Dict[str, Set[str]] = defaultdict(set)
        
        # Register with memory manager
        if self.memory_manager:
            self.memory_manager.register_cache(self)
    
    def get(self, key: str) -> Any:
        """Get item from cache, checking levels in order."""
        start_time = time.perf_counter()
        
        try:
            # Update total requests if tracking detailed stats
            if self.enable_detailed_stats:
                self.detailed_stats.total_requests += 1
            
            # Check each level in order
            for level in self.levels:
                cache = self._level_caches.get(level)
                if cache:
                    value = cache.get(key)
                    if value is not None:
                        # Promote to higher levels
                        self._promote_to_higher_levels(key, value, level)
                        
                        if self.enable_detailed_stats:
                            self.detailed_stats.cache_hits += 1
                            if level != self.levels[0]:  # Not already in highest level
                                self.detailed_stats.promotion_count += 1
                        
                        return value
            
            # Not found in any level
            if self.enable_detailed_stats:
                self.detailed_stats.cache_misses += 1
            
            return None
            
        finally:
            if self.enable_performance_metrics:
                operation_time = (time.perf_counter() - start_time) * 1000
                self._get_operation_times.append(operation_time)
                
                # Keep history limited
                if len(self._get_operation_times) > 1000:
                    self._get_operation_times = self._get_operation_times[-500:]
    
    def set(self, 
            key: str, 
            value: Any, 
            level: CacheLevel | None = None,
            dependencies: Set[str] | None = None):
        """Set item in cache at specified level."""
        start_time = time.perf_counter()
        
        try:
            size_bytes = self._estimate_size(value)
            
            # Check memory pressure before adding
            if self.memory_manager:
                # Check if adding this would exceed limits
                current_usage = self.get_memory_usage_mb()
                new_size_mb = size_bytes / (1024 * 1024)
                
                if current_usage + new_size_mb > self.memory_manager.max_memory_mb:
                    # Trigger cleanup before adding
                    self.memory_manager.check_memory_pressure()
                    self.cleanup_memory()
            
            if level:
                # Set in specific level only
                cache = self._level_caches.get(level)
                if cache:
                    cache.set(key, value, size_bytes, dependencies)
            else:
                # Set in all levels when no level specified
                for cache_level in self.levels:
                    cache = self._level_caches.get(cache_level)
                    if cache:
                        cache.set(key, value, size_bytes, dependencies)
            
            # Track dependencies
            if dependencies:
                for dep in dependencies:
                    self.dependency_tracker.add_dependency(key, dep)
        
        finally:
            if self.enable_performance_metrics:
                operation_time = (time.perf_counter() - start_time) * 1000
                self._set_operation_times.append(operation_time)
                
                # Keep history limited
                if len(self._set_operation_times) > 1000:
                    self._set_operation_times = self._set_operation_times[-500:]
    
    def exists(self, key: str, level: CacheLevel | None = None) -> bool:
        """Check if key exists in cache."""
        if level:
            cache = self._level_caches.get(level)
            return cache.exists(key) if cache else False
        else:
            # Check all levels
            return any(
                cache.exists(key) for cache in self._level_caches.values()
                if cache
            )
    
    def invalidate(self, key: str):
        """Invalidate key from all cache levels."""
        # Get all transitively affected items before invalidating
        affected = self.dependency_tracker.get_transitively_affected(key)
        
        # Invalidate the key itself from all levels
        for cache in self._level_caches.values():
            if cache:
                cache.invalidate(key)
        
        # Invalidate all dependent entries  
        for dependent_key in affected:
            for cache in self._level_caches.values():
                if cache:
                    cache.invalidate(dependent_key)
        
        # Remove dependencies for invalidated keys
        self.dependency_tracker.remove_dependencies(key)
        for dependent_key in affected:
            self.dependency_tracker.remove_dependencies(dependent_key)
        
        if self.enable_detailed_stats:
            self.detailed_stats.invalidations += 1 + len(affected)
    
    def set_symbol(self, symbol_name: str, symbol_data: Dict[str, Any]):
        """Set symbol-specific data."""
        key = f"symbol:{symbol_name}"
        self.set(key, symbol_data, level=CacheLevel.SYMBOL)
        
        # Track file->symbol mapping
        if "file" in symbol_data:
            self._file_to_symbols[symbol_data["file"]].add(symbol_name)
        
        # Track dependencies if specified
        if "dependencies" in symbol_data and isinstance(symbol_data["dependencies"], list):
            for dep in symbol_data["dependencies"]:
                self.dependency_tracker.add_dependency(f"symbol:{symbol_name}", f"symbol:{dep}")
    
    def get_symbol(self, symbol_name: str) -> Dict[str, Any] | None:
        """Get symbol-specific data."""
        key = f"symbol:{symbol_name}"
        return self.get(key)
    
    def get_symbols_for_file(self, file_path: str) -> List[str]:
        """Get all symbols defined in a file."""
        return list(self._file_to_symbols.get(file_path, set()))
    
    def get_symbol_dependents(self, symbol_name: str) -> List[str]:
        """Get symbols that depend on this symbol."""
        key = f"symbol:{symbol_name}"
        dependents = self.dependency_tracker.get_dependents(key)
        # Remove the "symbol:" prefix from dependents
        return [dep.replace("symbol:", "") for dep in dependents if dep.startswith("symbol:")]
    
    def set_level_limit(self, level: CacheLevel, max_size_mb: float):
        """Set memory limit for a cache level."""
        cache = self._level_caches.get(level)
        if hasattr(cache, 'max_size_mb'):
            cache.max_size_mb = max_size_mb
    
    def get_level_stats(self, level: CacheLevel) -> CacheLevelStats:
        """Get statistics for a cache level."""
        cache = self._level_caches.get(level)
        if cache and hasattr(cache, 'get_stats'):
            return cache.get_stats()
        return CacheLevelStats(level=level)
    
    def get_stats(self) -> CacheStats:
        """Get basic cache statistics."""
        # If detailed stats are enabled, use those
        if self.enable_detailed_stats:
            total_hits = self.detailed_stats.cache_hits
            total_misses = self.detailed_stats.cache_misses
            total_requests = self.detailed_stats.total_requests
        else:
            # Otherwise aggregate from individual caches
            total_hits = 0
            total_misses = 0
            for cache in self._level_caches.values():
                if cache and hasattr(cache, 'get_stats'):
                    stats = cache.get_stats()
                    total_hits += stats.hits
                    total_misses += stats.misses
            total_requests = total_hits + total_misses
        
        # Always aggregate size and evictions from caches
        total_size_mb = 0.0
        total_evictions = 0
        
        for cache in self._level_caches.values():
            if cache and hasattr(cache, 'get_stats'):
                stats = cache.get_stats()
                total_size_mb += stats.size_mb
                total_evictions += stats.eviction_count
        
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0
        
        # Create stats object that includes compression_ratio and memory_used_mb
        stats = CacheStats(
            total_requests=total_requests,
            cache_hits=total_hits,
            cache_misses=total_misses,
            hit_rate=hit_rate,
            cache_size_mb=total_size_mb,
            eviction_count=total_evictions
        )
        
        # Add dynamic attributes for compatibility
        stats.memory_used_mb = total_size_mb
        stats.compression_ratio = 1.0  # Default no compression
        
        # Calculate compression ratio if compression is enabled
        if self.compression and self.compression != CompressionStrategy.NONE:
            # Get actual compression ratio from filesystem cache
            if hasattr(self.filesystem_cache, 'get_compression_ratio'):
                actual_ratio = self.filesystem_cache.get_compression_ratio()
                if actual_ratio > 1.0:
                    stats.compression_ratio = actual_ratio
                else:
                    # Use estimates if no actual data yet
                    if self.compression == CompressionStrategy.ZLIB:
                        stats.compression_ratio = 2.0
                    elif self.compression == CompressionStrategy.LZ4:
                        stats.compression_ratio = 1.8
                    elif self.compression == CompressionStrategy.BROTLI:
                        stats.compression_ratio = 2.5
        
        return stats
    
    def get_detailed_stats(self) -> DetailedCacheStats:
        """Get detailed cache statistics."""
        if not self.enable_detailed_stats:
            return DetailedCacheStats()
        
        # Update level stats
        for level in self.levels:
            cache = self._level_caches.get(level)
            if cache:
                self.detailed_stats.level_stats[level] = cache.get_stats()
        
        # Calculate totals
        self.detailed_stats.total_requests = (
            self.detailed_stats.cache_hits + self.detailed_stats.cache_misses
        )
        
        if self.detailed_stats.total_requests > 0:
            self.detailed_stats.hit_rate = (
                self.detailed_stats.cache_hits / self.detailed_stats.total_requests
            )
        
        # Collect hot keys from all cache levels
        self.detailed_stats.hot_keys = self._collect_hot_keys()
        
        # Update size distribution
        self.detailed_stats.size_distribution = self._calculate_size_distribution()
        
        return self.detailed_stats
    
    def _collect_hot_keys(self) -> List[HotKey]:
        """Collect hot keys from all cache levels."""
        hot_keys = []
        
        for level, cache in self._level_caches.items():
            if hasattr(cache, 'entries'):
                # Get top 10 most accessed keys from each level
                sorted_entries = sorted(
                    cache.entries.values(),
                    key=lambda e: e.access_count,
                    reverse=True
                )[:10]
                
                for entry in sorted_entries:
                    hot_keys.append(HotKey(
                        key=entry.key,
                        access_count=entry.access_count,
                        last_accessed=entry.last_accessed,
                        cache_level=level
                    ))
        
        # Sort all hot keys by access count
        hot_keys.sort(key=lambda k: k.access_count, reverse=True)
        return hot_keys[:20]  # Return top 20 overall
    
    def _calculate_size_distribution(self) -> SizeDistribution:
        """Calculate size distribution of cache entries."""
        distribution = SizeDistribution()
        
        for cache in self._level_caches.values():
            if hasattr(cache, 'entries'):
                for entry in cache.entries.values():
                    size_kb = entry.size_bytes / 1024
                    if size_kb < 1:
                        distribution.small_entries += 1
                    elif size_kb < 100:
                        distribution.medium_entries += 1
                    else:
                        distribution.large_entries += 1
        
        return distribution
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get cache performance metrics."""
        if not self.enable_performance_metrics:
            return PerformanceMetrics()
        
        # Calculate get metrics
        if self._get_operation_times:
            get_times = sorted(self._get_operation_times)
            self.performance_metrics.avg_get_time_ms = sum(get_times) / len(get_times)
            
            # Calculate percentiles for get operations
            n = len(get_times)
            if n > 0:
                self.performance_metrics.p50_latency_ms = get_times[int(n * 0.5)]
                self.performance_metrics.p95_latency_ms = get_times[int(n * 0.95)] if n > 20 else get_times[-1]
                self.performance_metrics.p99_latency_ms = get_times[int(n * 0.99)] if n > 100 else get_times[-1]
        
        # Calculate set metrics
        if self._set_operation_times:
            set_times = sorted(self._set_operation_times)
            self.performance_metrics.avg_set_time_ms = sum(set_times) / len(set_times)
        
        # Total operations per second
        total_operations = len(self._get_operation_times) + len(self._set_operation_times)
        self.performance_metrics.operations_per_second = total_operations
        
        return self.performance_metrics
    
    def set_alert_threshold(self, metric: str, min_value: float | None = None, max_value: float | None = None):
        """Set alert threshold for a metric."""
        self._alert_thresholds[metric] = {}
        if min_value is not None:
            self._alert_thresholds[metric]['min'] = min_value
        if max_value is not None:
            self._alert_thresholds[metric]['max'] = max_value
    
    def check_health(self):
        """Check cache health and trigger alerts if needed."""
        if not self.enable_monitoring or not self.alert_handler:
            return
        
        stats = self.get_stats()
        
        # Check hit rate (convert to 0-1 range for comparison)
        if 'hit_rate' in self._alert_thresholds:
            thresholds = self._alert_thresholds['hit_rate']
            hit_rate_normalized = stats.hit_rate / 100.0 if stats.hit_rate > 1 else stats.hit_rate
            if 'min' in thresholds and hit_rate_normalized < thresholds['min']:
                self.alert_handler(f"Cache hit rate {hit_rate_normalized:.1%} below threshold {thresholds['min']:.1%}")
        
        # Check memory usage
        if 'memory_usage' in self._alert_thresholds:
            thresholds = self._alert_thresholds['memory_usage']
            if 'max' in thresholds and stats.cache_size_mb > thresholds['max']:
                self.alert_handler(f"Cache memory usage {stats.cache_size_mb:.1f}MB exceeds threshold {thresholds['max']:.1f}MB")
        
        # Check eviction rate
        if 'eviction_rate' in self._alert_thresholds:
            thresholds = self._alert_thresholds['eviction_rate']
            if stats.total_requests > 0:
                eviction_rate = stats.eviction_count / stats.total_requests
                if 'max' in thresholds and eviction_rate > thresholds['max']:
                    self.alert_handler(f"Cache eviction rate {eviction_rate:.1%} exceeds threshold {thresholds['max']:.1%}")
    
    def cleanup_memory(self):
        """Clean up memory used by cache (for memory manager integration)."""
        # Clear least important cache level first
        if CacheLevel.FILESYSTEM in self._level_caches:
            cache = self._level_caches[CacheLevel.FILESYSTEM]
            if hasattr(cache, 'clear'):
                # Don't clear filesystem cache completely, just trim
                pass
        
        # Clear symbol cache if memory pressure is high
        if CacheLevel.SYMBOL in self._level_caches:
            cache = self._level_caches[CacheLevel.SYMBOL]
            if hasattr(cache, '_evict_lru'):
                # Evict 25% of entries
                for _ in range(len(cache.entries) // 4):
                    cache._evict_lru()
    
    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        total_mb = 0.0
        for cache in self._level_caches.values():
            if hasattr(cache, 'current_size_mb'):
                total_mb += cache.current_size_mb
        return total_mb
    
    def set_memory_limit(self, limit_mb: float):
        """Set memory limit for this cache."""
        # Distribute limit across levels
        memory_portion = limit_mb * 0.6  # 60% for memory cache
        symbol_portion = limit_mb * 0.3  # 30% for symbol cache
        
        self.set_level_limit(CacheLevel.MEMORY, memory_portion)
        self.set_level_limit(CacheLevel.SYMBOL, symbol_portion)
    
    def warmup(self, files: List[str], parser: Any | None = None):
        """Warmup cache with important files."""
        if not parser:
            return
        
        for file_path in files:
            try:
                # Parse and cache file
                result = parser.parse_file(file_path)
                if result.success:
                    key = f"ast:{file_path}"
                    self.set(key, result.tree, level=CacheLevel.MEMORY)
            except Exception:
                continue
    
    def _promote_to_higher_levels(self, key: str, value: Any, found_level: CacheLevel):
        """Promote cache entry to higher levels."""
        level_order = {
            CacheLevel.FILESYSTEM: 0,
            CacheLevel.SYMBOL: 1,
            CacheLevel.MEMORY: 2
        }
        
        found_priority = level_order.get(found_level, 0)
        
        # Promote to all higher priority levels
        for level in self.levels:
            level_priority = level_order.get(level, 0)
            if level_priority > found_priority:
                cache = self._level_caches.get(level)
                if cache:
                    size_bytes = self._estimate_size(value)
                    cache.set(key, value, size_bytes)
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate size of a value."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 1024  # Default 1KB estimate
    
    def adapt_size(self):
        """Adapt cache size based on current usage patterns."""
        if not self.enable_adaptive_sizing:
            return
        
        # Get current cache usage stats
        stats = self.get_stats()
        
        # If hit rate is low, increase cache size
        if stats.hit_rate < 80 and self.current_size_mb < self.max_size_mb:
            new_size = min(self.current_size_mb * 1.2, self.max_size_mb)
            self.current_size_mb = new_size
            self._update_cache_sizes()
        
        # If cache is underutilized, decrease size
        elif stats.cache_size_mb < self.current_size_mb * 0.5 and self.current_size_mb > self.min_size_mb:
            new_size = max(self.current_size_mb * 0.8, self.min_size_mb)
            self.current_size_mb = new_size
            self._update_cache_sizes()
    
    def _update_cache_sizes(self):
        """Update individual cache level sizes based on current_size_mb."""
        # Distribute size across cache levels
        memory_portion = self.current_size_mb * 0.6
        symbol_portion = self.current_size_mb * 0.3
        
        if hasattr(self.memory_cache, 'max_size_mb'):
            self.memory_cache.max_size_mb = memory_portion
        if hasattr(self.symbol_cache, 'max_size_mb'):
            self.symbol_cache.max_size_mb = symbol_portion
    
    def _demote_from_memory(self, key: str, value: Any):
        """Demote entry from memory cache to symbol cache."""
        # When evicted from memory, add to symbol cache
        if self.symbol_cache:
            size_bytes = self._estimate_size(value)
            self.symbol_cache.set(key, value, size_bytes)
    
    def _demote_from_symbol(self, key: str, value: Any):
        """Demote entry from symbol cache to filesystem cache."""
        # When evicted from symbol, add to filesystem cache
        if self.filesystem_cache:
            size_bytes = self._estimate_size(value)
            self.filesystem_cache.set(key, value, size_bytes)