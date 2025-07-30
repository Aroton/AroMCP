"""
Memory management utilities for TypeScript Analysis Server.

Provides memory monitoring, pressure handling, and garbage collection coordination.
"""

import gc
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Dict, Any

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """Compression strategies for cache storage."""
    NONE = "none"
    ZLIB = "zlib"
    LZ4 = "lz4"
    BROTLI = "brotli"


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    current_memory_mb: float = 0.0
    memory_percent: float = 0.0
    pressure_level: str = "normal"
    gc_triggers: int = 0
    emergency_cleanups: int = 0
    time_since_gc: float = 0.0
    
    @property
    def gc_triggered(self) -> bool:
        """Compatibility property for tests."""
        return self.gc_triggers > 0


@dataclass
class MemoryUsageStats:
    """Detailed memory usage statistics."""
    total_memory_mb: float = 0.0
    cache_memory_mb: float = 0.0
    parser_memory_mb: float = 0.0
    available_memory_mb: float = 0.0
    memory_pressure: str = "normal"


@dataclass
class MemoryProfile:
    """Memory profiling information."""
    component_usage: Dict[str, float]
    peak_usage_mb: float = 0.0
    allocation_count: int = 0


class MemoryOptimizer:
    """Memory usage optimizer."""
    
    def __init__(self):
        pass
    
    def optimize(self) -> Dict[str, Any]:
        """Optimize memory usage."""
        return {"status": "optimized"}


class MemoryManager:
    """
    Manages memory usage for the TypeScript analysis server.
    
    Features:
    - Memory usage monitoring
    - Pressure detection and handling
    - Coordinated garbage collection
    - Cache size recommendations
    """
    
    def __init__(
        self,
        max_memory_mb: int = 500,
        gc_threshold_mb: int = 400,
        emergency_threshold_mb: int = 450,
        enable_monitoring: bool = True,
        enable_profiling: bool = False
    ):
        """
        Initialize memory manager.
        
        Args:
            max_memory_mb: Maximum allowed memory usage
            gc_threshold_mb: Trigger GC when memory exceeds this
            emergency_threshold_mb: Emergency cleanup threshold
            enable_monitoring: Enable active memory monitoring
            enable_profiling: Enable memory profiling
        """
        self.max_memory_mb = max_memory_mb
        self.gc_threshold_mb = gc_threshold_mb
        self.emergency_threshold_mb = emergency_threshold_mb
        self.enable_monitoring = enable_monitoring and PSUTIL_AVAILABLE
        self.enable_profiling = enable_profiling
        
        # Callbacks for memory pressure
        self._pressure_callbacks: list[Callable[[], None]] = []
        self._emergency_callbacks: list[Callable[[], None]] = []
        
        # Statistics
        self._gc_count = 0
        self._emergency_count = 0
        self._last_gc_time = time.time()
        
        # Registered caches for memory management
        self._registered_caches = []
        
        # Memory profile data
        self._component_usage = {"parser": 0.0, "cache": 0.0}
        self._peak_usage_mb = 0.0
        
        if not PSUTIL_AVAILABLE and enable_monitoring:
            logger.warning("psutil not available, memory monitoring disabled")
    
    def get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB."""
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return 0.0
    
    def get_memory_percent(self) -> float:
        """Get memory usage as percentage of system memory."""
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            process = psutil.Process()
            return process.memory_percent()
        except Exception as e:
            logger.error(f"Failed to get memory percent: {e}")
            return 0.0
    
    def check_memory_pressure(self) -> str:
        """
        Check current memory pressure level and trigger action if needed.
        
        Returns:
            One of: 'normal', 'high', 'emergency'
        """
        if not self.enable_monitoring:
            return 'normal'
        
        current_mb = self.get_memory_usage_mb()
        
        if current_mb >= self.emergency_threshold_mb:
            self._handle_emergency()
            
            # Check if emergency handling brought us back under control
            post_emergency_mb = self.get_memory_usage_mb()
            if post_emergency_mb >= self.emergency_threshold_mb:
                # Still in emergency - try more aggressive cleanup
                self._handle_super_emergency()
            
            return 'emergency'
        elif current_mb >= self.gc_threshold_mb:
            self._handle_high_pressure()
            return 'high'
        else:
            return 'normal'
    
    def handle_memory_pressure(self) -> bool:
        """
        Handle memory pressure by triggering appropriate actions.
        
        Returns:
            True if action was taken, False otherwise
        """
        pressure_level = self.check_memory_pressure()
        
        if pressure_level == 'emergency':
            self._handle_emergency()
            return True
        elif pressure_level == 'high':
            self._handle_high_pressure()
            return True
        
        return False
    
    def _handle_high_pressure(self) -> None:
        """Handle high memory pressure."""
        logger.info(f"High memory pressure detected: {self.get_memory_usage_mb():.1f}MB")
        
        # Run pressure callbacks
        for callback in self._pressure_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Pressure callback failed: {e}")
        
        # Force garbage collection
        self._run_gc()
        
        # Check if we're still over threshold after GC and callbacks
        current_mb = self.get_memory_usage_mb()
        if current_mb >= self.gc_threshold_mb:
            # If still high, run emergency callbacks too
            for callback in self._emergency_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Emergency callback failed: {e}")
            
            # Run more aggressive GC
            self._run_gc(generation=2)
    
    def _handle_emergency(self) -> None:
        """Handle emergency memory situation."""
        logger.warning(f"Emergency memory pressure: {self.get_memory_usage_mb():.1f}MB")
        
        # Run emergency callbacks first
        for callback in self._emergency_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Emergency callback failed: {e}")
        
        # Then run normal pressure callbacks
        for callback in self._pressure_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Pressure callback failed: {e}")
        
        # Aggressive garbage collection
        self._run_gc(generation=2)
        self._emergency_count += 1
    
    def _handle_super_emergency(self) -> None:
        """Handle extreme memory situations that couldn't be resolved."""
        logger.critical(f"Super emergency memory pressure: {self.get_memory_usage_mb():.1f}MB")
        
        # Run emergency callbacks multiple times if needed
        for attempt in range(5):  # Try up to 5 times
            initial_memory = self.get_memory_usage_mb()
            
            for callback in self._emergency_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Super emergency callback failed: {e}")
            
            # Multiple rounds of aggressive garbage collection
            for generation in [2, 1, 0]:
                self._run_gc(generation=generation)
            
            # Check if we've freed enough memory
            current_memory = self.get_memory_usage_mb()
            if current_memory < self.gc_threshold_mb:
                break
                
            # If memory didn't decrease much, break to avoid infinite loop
            if attempt > 0 and (initial_memory - current_memory) < 5.0:
                logger.warning(f"Super emergency cleanup not effective after {attempt + 1} attempts")
                break
    
    def _run_gc(self, generation: int = 1) -> None:
        """Run garbage collection."""
        before_mb = self.get_memory_usage_mb()
        
        gc.collect(generation)
        
        after_mb = self.get_memory_usage_mb()
        freed_mb = before_mb - after_mb
        
        logger.info(f"GC freed {freed_mb:.1f}MB (gen={generation})")
        
        self._gc_count += 1
        self._last_gc_time = time.time()
    
    def register_pressure_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for high memory pressure."""
        self._pressure_callbacks.append(callback)
    
    def register_emergency_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for emergency memory situations."""
        self._emergency_callbacks.append(callback)
    
    def get_recommended_cache_size_mb(self) -> int:
        """Get recommended cache size based on available memory."""
        if not PSUTIL_AVAILABLE:
            # Conservative default
            return min(100, self.max_memory_mb // 5)
        
        try:
            # Get available system memory
            mem = psutil.virtual_memory()
            available_mb = mem.available / (1024 * 1024)
            
            # Use up to 20% of available memory for cache
            recommended = min(
                int(available_mb * 0.2),
                self.max_memory_mb // 3,  # At most 1/3 of our limit
                200  # Cap at 200MB
            )
            
            return max(recommended, 50)  # At least 50MB
            
        except Exception as e:
            logger.error(f"Failed to calculate cache size: {e}")
            return 100
    
    def get_stats(self) -> MemoryStats:
        """Get memory management statistics."""
        return MemoryStats(
            current_memory_mb=self.get_memory_usage_mb(),
            memory_percent=self.get_memory_percent(),
            pressure_level=self.check_memory_pressure(),
            gc_triggers=self._gc_count,
            emergency_cleanups=self._emergency_count,
            time_since_gc=time.time() - self._last_gc_time
        )
    
    def get_current_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.get_memory_usage_mb()
    
    def register_cache(self, cache):
        """Register a cache for memory management."""
        self._registered_caches.append(cache)
    
    def get_memory_profile(self) -> MemoryProfile:
        """Get memory profiling information."""
        if not self.enable_profiling:
            return MemoryProfile(component_usage={"parser": 0.0, "cache": 0.0})
        
        # Update current usage
        current_mb = self.get_memory_usage_mb()
        if current_mb > self._peak_usage_mb:
            self._peak_usage_mb = current_mb
        
        # Estimate component usage
        total_cache_mb = 0.0
        for cache in self._registered_caches:
            if hasattr(cache, 'get_memory_usage_mb'):
                total_cache_mb += cache.get_memory_usage_mb()
        
        self._component_usage["cache"] = total_cache_mb
        self._component_usage["parser"] = max(0.0, current_mb - total_cache_mb)
        
        return MemoryProfile(
            component_usage=self._component_usage.copy(),
            peak_usage_mb=self._peak_usage_mb,
            allocation_count=0  # Not implemented
        )
    
    def can_allocate_mb(self, size_mb: float) -> bool:
        """Check if we can safely allocate more memory."""
        if not self.enable_monitoring:
            return True
        
        current_mb = self.get_memory_usage_mb()
        projected_mb = current_mb + size_mb
        
        return projected_mb < self.gc_threshold_mb