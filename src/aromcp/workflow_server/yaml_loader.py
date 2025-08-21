"""YAML file loading with caching and path validation."""

import threading
import time
from pathlib import Path
from typing import Any

import yaml
from cachetools import TTLCache

from ..filesystem_server._security import get_project_root, validate_file_path


class YAMLLoader:
    """YAML file loader with TTL-based caching and path validation."""

    def __init__(self, cache_ttl: int = 300, max_cache_size: int = 100):
        """Initialize the YAML loader.
        
        Args:
            cache_ttl: Time-to-live for cache entries in seconds
            max_cache_size: Maximum number of files to cache
        """
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=max_cache_size, ttl=cache_ttl
        )
        self._lock = threading.RLock()

    def load_yaml(self, file_path: str, project_root: str | None = None) -> dict[str, Any]:
        """Load and parse a YAML file with caching.
        
        Args:
            file_path: Path to the YAML file to load
            project_root: Project root for path validation (uses MCP_FILE_ROOT if None)
            
        Returns:
            Dictionary containing parsed YAML content
            
        Raises:
            ValueError: If file path is invalid or outside project root
            FileNotFoundError: If file does not exist
            yaml.YAMLError: If YAML parsing fails
            PermissionError: If file cannot be read
        """
        # Resolve project root
        resolved_project_root = get_project_root(project_root)

        # Validate file path
        validation_result = validate_file_path(file_path, resolved_project_root)
        if not validation_result["valid"]:
            raise ValueError(validation_result["error"])

        abs_path = validation_result["abs_path"]
        cache_key = str(abs_path)

        # Check cache first
        with self._lock:
            if cache_key in self._cache:
                # Verify file hasn't been modified since caching
                cached_entry = self._cache[cache_key]
                if self._is_cache_valid(abs_path, cached_entry):
                    return cached_entry["content"]
                else:
                    # Remove stale cache entry
                    del self._cache[cache_key]

        # Load and parse file
        try:
            content = self._load_and_parse_file(abs_path)

            # Cache the result with file metadata
            with self._lock:
                self._cache[cache_key] = {
                    "content": content,
                    "mtime": abs_path.stat().st_mtime,
                    "size": abs_path.stat().st_size,
                    "loaded_at": time.time(),
                }

            return content

        except FileNotFoundError:
            raise FileNotFoundError(f"YAML file not found: {file_path}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading YAML file: {file_path}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML parsing error in {file_path}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error loading YAML file {file_path}: {str(e)}")

    def _load_and_parse_file(self, abs_path: Path) -> dict[str, Any]:
        """Load and parse YAML file from filesystem."""
        if not abs_path.exists():
            raise FileNotFoundError(f"File does not exist: {abs_path}")

        if not abs_path.is_file():
            raise ValueError(f"Path is not a file: {abs_path}")

        try:
            with open(abs_path, encoding="utf-8") as f:
                content = yaml.safe_load(f)

            # Ensure we return a dictionary
            if content is None:
                return {}
            elif not isinstance(content, dict):
                raise yaml.YAMLError(f"YAML file must contain a dictionary/mapping, got {type(content).__name__}")

            return content

        except UnicodeDecodeError as e:
            raise ValueError(f"File encoding error: {str(e)}")

    def _is_cache_valid(self, abs_path: Path, cached_entry: dict[str, Any]) -> bool:
        """Check if cached entry is still valid."""
        try:
            if not abs_path.exists():
                return False

            stat = abs_path.stat()
            return (
                stat.st_mtime == cached_entry["mtime"] and
                stat.st_size == cached_entry["size"]
            )
        except (OSError, KeyError):
            return False

    def invalidate_cache(self, file_path: str | None = None, project_root: str | None = None) -> int:
        """Invalidate cache entries.
        
        Args:
            file_path: Specific file to invalidate, or None to clear entire cache
            project_root: Project root for path validation (uses MCP_FILE_ROOT if None)
            
        Returns:
            Number of cache entries invalidated
        """
        with self._lock:
            if file_path is None:
                # Clear entire cache
                count = len(self._cache)
                self._cache.clear()
                return count

            # Invalidate specific file
            try:
                resolved_project_root = get_project_root(project_root)
                validation_result = validate_file_path(file_path, resolved_project_root)
                if validation_result["valid"]:
                    cache_key = str(validation_result["abs_path"])
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                        return 1
            except Exception:
                # If path validation fails, just continue
                pass

            return 0

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache performance statistics
        """
        with self._lock:
            current_time = time.time()

            # Calculate cache ages
            ages = []
            for entry in self._cache.values():
                age = current_time - entry.get("loaded_at", current_time)
                ages.append(age)

            return {
                "cache_size": len(self._cache),
                "max_cache_size": self.max_cache_size,
                "cache_ttl": self.cache_ttl,
                "cache_utilization_percent": (len(self._cache) / self.max_cache_size) * 100,
                "oldest_entry_age_seconds": max(ages) if ages else 0,
                "newest_entry_age_seconds": min(ages) if ages else 0,
                "average_entry_age_seconds": sum(ages) / len(ages) if ages else 0,
            }

    def preload_directory(self, directory_path: str, pattern: str = "*.yaml", project_root: str | None = None) -> dict[str, Any]:
        """Preload YAML files from a directory into cache.
        
        Args:
            directory_path: Directory to scan for YAML files
            pattern: Glob pattern for YAML files (default: "*.yaml")
            project_root: Project root for path validation (uses MCP_FILE_ROOT if None)
            
        Returns:
            Dictionary with preload statistics and any errors
        """
        resolved_project_root = get_project_root(project_root)

        # Validate directory path
        validation_result = validate_file_path(directory_path, resolved_project_root)
        if not validation_result["valid"]:
            raise ValueError(validation_result["error"])

        dir_path = validation_result["abs_path"]

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")

        loaded_count = 0
        errors = []

        try:
            # Find YAML files matching pattern
            yaml_files = list(dir_path.glob(pattern))
            yaml_files.extend(dir_path.glob(pattern.replace(".yaml", ".yml")))

            for yaml_file in yaml_files:
                try:
                    # Load file (which will cache it)
                    self.load_yaml(str(yaml_file), resolved_project_root)
                    loaded_count += 1
                except Exception as e:
                    errors.append(f"{yaml_file}: {str(e)}")

        except Exception as e:
            errors.append(f"Directory scan error: {str(e)}")

        return {
            "directory": directory_path,
            "pattern": pattern,
            "files_loaded": loaded_count,
            "errors": errors,
        }


# Global singleton instance
_yaml_loader: YAMLLoader | None = None
_loader_lock = threading.Lock()


def get_yaml_loader() -> YAMLLoader:
    """Get the global YAML loader instance."""
    global _yaml_loader

    if _yaml_loader is None:
        with _loader_lock:
            if _yaml_loader is None:
                from .config import get_config
                config = get_config()
                _yaml_loader = YAMLLoader(
                    cache_ttl=config.yaml_cache_ttl,
                    max_cache_size=100  # Reasonable default
                )

    return _yaml_loader


def reset_yaml_loader() -> None:
    """Reset the global YAML loader (for testing)."""
    global _yaml_loader
    with _loader_lock:
        _yaml_loader = None


def load_workflow_yaml(file_path: str, project_root: str | None = None) -> dict[str, Any]:
    """Convenience function to load a workflow YAML file.
    
    Args:
        file_path: Path to the workflow YAML file
        project_root: Project root for path validation (uses MCP_FILE_ROOT if None)
        
    Returns:
        Dictionary containing parsed workflow definition
        
    Raises:
        ValueError: If file path is invalid or YAML structure is invalid
        FileNotFoundError: If file does not exist
        yaml.YAMLError: If YAML parsing fails
    """
    loader = get_yaml_loader()
    workflow_def = loader.load_yaml(file_path, project_root)

    # Basic workflow validation
    required_fields = ["name", "steps"]
    for field in required_fields:
        if field not in workflow_def:
            raise ValueError(f"Workflow YAML missing required field: {field}")

    if not isinstance(workflow_def["steps"], list):
        raise ValueError("Workflow 'steps' field must be a list")

    return workflow_def
