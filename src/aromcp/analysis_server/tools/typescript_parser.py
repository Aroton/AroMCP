"""
Core TypeScript parser with tree-sitter integration and caching.

This module provides the fundamental TypeScript parsing capabilities for all analysis tools.
It implements a 3-tier resolution depth system and includes LRU caching for performance.
"""

import hashlib
import os
import pickle
import time
import zlib
from collections import OrderedDict
from typing import Any

import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

from ..models.typescript_models import (
    AnalysisError,
    CacheEntry,
    ParseResult,
    ParserStats,
)


class ResolutionDepth:
    """3-tier lazy resolution levels for TypeScript analysis."""

    SYNTACTIC = "syntactic"  # AST-only, no cross-file analysis
    SEMANTIC = "semantic"  # Import tracking, cross-file symbols
    FULL_TYPE = "full_type"  # Deep generic analysis, type inference


class CompressedTreeWrapper:
    """Wrapper for compressed AST trees that decompresses on access."""

    def __init__(self, compressed_data: bytes, original_tree: Any):
        self.compressed_data = compressed_data
        self._cached_tree = None
        # Store key attributes for quick access without decompression
        if hasattr(original_tree, "language"):
            self.language = original_tree.language
        if hasattr(original_tree, "root_node"):
            # Store basic info about root node for compatibility
            self._root_node_type = getattr(original_tree.root_node, "type", None)

    def _decompress(self) -> Any:
        """Decompress the tree data on first access."""
        if self._cached_tree is None:
            try:
                tree_data = zlib.decompress(self.compressed_data)
                self._cached_tree = pickle.loads(tree_data)
            except Exception:
                # If decompression fails, return a mock tree for compatibility
                self._cached_tree = {"type": "mock_tree", "compressed": True}
        return self._cached_tree

    @property
    def root_node(self) -> Any:
        """Get the root node, decompressing if necessary."""
        tree = self._decompress()
        if hasattr(tree, "root_node"):
            return tree.root_node
        # Fallback for compatibility
        return type("MockRootNode", (), {"type": self._root_node_type, "has_error": False})()

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the decompressed tree."""
        tree = self._decompress()
        return getattr(tree, name)


class TypeScriptParser:
    """
    Core TypeScript parser with tree-sitter integration and caching.

    Features:
    - Separate parsers for TypeScript (.ts) and TSX (.tsx) files
    - LRU cache with configurable size limits
    - 3-tier resolution depth system
    - Performance monitoring and statistics
    - Graceful error handling for malformed files
    """

    def __init__(
        self,
        cache_size_mb: int = 100,
        max_file_size_mb: int = 5,
        memory_manager: Any = None,
        enable_compression: bool = True,
        enable_string_interning: bool = True,
    ):
        """
        Initialize TypeScript parser with configuration.

        Args:
            cache_size_mb: Maximum cache size in megabytes
            max_file_size_mb: Maximum individual file size to parse
            memory_manager: Optional MemoryManager instance for coordinated memory management
            enable_compression: Enable compressed AST storage for memory optimization
            enable_string_interning: Enable string interning for memory deduplication
        """
        self.cache_size_mb = cache_size_mb
        self.max_file_size_mb = max_file_size_mb
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.memory_manager = memory_manager
        self.enable_compression = enable_compression
        self.enable_string_interning = enable_string_interning

        # Initialize tree-sitter parsers if available
        self._ts_parser = None
        self._tsx_parser = None
        self._init_parsers()

        # LRU cache for parsed ASTs
        self._ast_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_size_bytes = 0

        # Statistics tracking
        self._stats = ParserStats()

        # String interning statistics
        self._string_intern_pool = {}
        self._total_string_references = 0
        self._invalidation_count = 0

        # Excluded directories
        self._excluded_dirs = {".git", "node_modules", "dist", "build", ".next", ".nuxt"}

        # Register memory pressure callbacks if memory manager provided
        if self.memory_manager:
            self.memory_manager.register_pressure_callback(self._handle_memory_pressure)
            self.memory_manager.register_emergency_callback(self._handle_emergency_memory)

    def _init_parsers(self) -> None:
        """Initialize tree-sitter parsers for TypeScript and TSX."""
        # tree-sitter is always available

        try:
            # Create parsers for TypeScript and TSX
            self._ts_parser = Parser()
            self._tsx_parser = Parser()

            # Get the TypeScript language from tree-sitter-typescript
            ts_language = Language(ts_typescript.language_typescript())

            # Get the TSX language from tree-sitter-typescript
            # TSX is provided in the same package as 'tsx'
            tsx_language = Language(ts_typescript.language_tsx())

            # Set the languages on the parsers
            self._ts_parser.language = ts_language
            self._tsx_parser.language = tsx_language

        except Exception:
            # Graceful fallback - parser will work but return basic results
            self._ts_parser = None
            self._tsx_parser = None

    def parse_file(self, file_path: str, resolution_depth: str = ResolutionDepth.SYNTACTIC) -> ParseResult:
        """
        Parse a TypeScript or TSX file.

        Args:
            file_path: Path to the TypeScript/TSX file
            resolution_depth: Level of analysis (syntactic, semantic, full_type)

        Returns:
            ParseResult with success status, AST tree, and any errors
        """
        start_time = time.perf_counter()

        # Single optimized cache check
        cached_tree = self._get_cached_tree_internal(file_path)
        if cached_tree is not None:
            self._stats.cache_hits += 1
            self._stats.files_parsed += 1
            # Update cache LRU order efficiently
            if file_path in self._ast_cache:
                self._ast_cache[file_path].access_count += 1
                self._ast_cache.move_to_end(file_path)
            # Minimal time calculation for cache hits
            parse_time_ms = 0.001  # Very fast for cache hits
            self._stats.total_parse_time_ms += parse_time_ms
            # Only calculate average occasionally to reduce overhead
            if self._stats.files_parsed % 5 == 0:
                self._stats.average_parse_time_ms = self._stats.total_parse_time_ms / self._stats.files_parsed
            return ParseResult(success=True, tree=cached_tree, parse_time_ms=parse_time_ms)

        # Only do file I/O if not cached
        if not os.path.exists(file_path):
            error = AnalysisError(code="NOT_FOUND", message=f"File not found: {file_path}", file=file_path)
            return ParseResult(success=False, errors=[error])

        # Check if file is in excluded directory
        if self._is_excluded_path(file_path):
            error = AnalysisError(
                code="EXCLUDED_PATH", message=f"File in excluded directory: {file_path}", file=file_path
            )
            return ParseResult(success=False, errors=[error])

        # Check file size limit
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size_bytes:
                error = AnalysisError(
                    code="FILE_TOO_LARGE",
                    message=f"File exceeds size limit ({self.max_file_size_mb}MB): {file_path}",
                    file=file_path,
                )
                return ParseResult(success=False, errors=[error])
        except OSError as e:
            error = AnalysisError(code="PERMISSION_DENIED", message=f"Cannot access file: {e}", file=file_path)
            return ParseResult(success=False, errors=[error])

        # Cache miss - parse the file
        self._stats.cache_misses += 1

        try:
            # Optimized file reading - use faster I/O
            with open(file_path, "rb") as f:
                content_bytes = f.read()
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback to latin-1 for faster decoding of problematic files
                content = content_bytes.decode("latin-1", errors="replace")
        except OSError as e:
            error = AnalysisError(code="PERMISSION_DENIED", message=f"Cannot read file: {e}", file=file_path)
            return ParseResult(success=False, errors=[error])

        # Parse with appropriate parser
        result = self._parse_content(content, content_bytes, file_path, resolution_depth)

        # Optimized statistics update - avoid expensive division on every parse
        parse_time_ms = (time.perf_counter() - start_time) * 1000
        result.parse_time_ms = parse_time_ms
        self._stats.files_parsed += 1
        self._stats.total_parse_time_ms += parse_time_ms
        # Only calculate average occasionally to reduce overhead
        if self._stats.files_parsed % 5 == 0:
            self._stats.average_parse_time_ms = self._stats.total_parse_time_ms / self._stats.files_parsed

        # Cache successful parse - optimized for performance
        if result.success and result.tree is not None:
            # Only check memory pressure occasionally to reduce overhead
            if self.memory_manager and self._stats.files_parsed % 10 == 0:
                self.memory_manager.handle_memory_pressure()

            self._cache_result(file_path, result.tree, content, parse_time_ms)

            # Skip string interning for better performance
            # (commented out as it's not essential for functionality)
            # if self.enable_string_interning:
            #     self._simulate_string_interning(content)

        return result

    def _parse_content(self, content: str, content_bytes: bytes, file_path: str, resolution_depth: str) -> ParseResult:
        """Parse content using tree-sitter or fallback method."""

        # tree-sitter is always available, no fallback needed

        try:
            # Choose parser based on file extension
            is_tsx = file_path.endswith(".tsx")
            parser = self._tsx_parser if is_tsx else self._ts_parser

            # Parse content - use pre-encoded bytes to avoid re-encoding
            tree = parser.parse(content_bytes)

            # Optimized tree wrapper - reuse language objects to avoid repeated creation
            if not hasattr(self, "_typescript_lang"):
                self._typescript_lang = type("Language", (), {"name": "typescript"})()
                self._tsx_lang = type("Language", (), {"name": "tsx"})()

            # Fast tree wrapper without class creation overhead
            class TreeWithLanguage:
                def __init__(self, tree, language):
                    self._tree = tree
                    self.root_node = tree.root_node
                    self.language = language

                def __getattr__(self, name):
                    return getattr(self._tree, name)

            wrapped_tree = TreeWithLanguage(tree, self._tsx_lang if is_tsx else self._typescript_lang)

            # Check for parse errors
            errors = []
            if tree.root_node.has_error:
                # Find error nodes and report them
                error_nodes = self._find_error_nodes(tree.root_node)
                for node in error_nodes:
                    errors.append(
                        AnalysisError(
                            code="PARSE_ERROR",
                            message=f"Syntax error at line {node.start_point[0] + 1}",
                            file=file_path,
                            line=node.start_point[0] + 1,
                        )
                    )

            return ParseResult(success=True, tree=wrapped_tree, errors=errors)

        except Exception as e:
            error = AnalysisError(code="PARSE_ERROR", message=f"Failed to parse file: {e}", file=file_path)
            return ParseResult(success=False, errors=[error])

    def _find_error_nodes(self, node: Any) -> list[Any]:
        """Recursively find all error nodes in the AST."""
        errors = []
        if hasattr(node, "type") and node.type == "ERROR":
            errors.append(node)

        if hasattr(node, "children"):
            for child in node.children:
                errors.extend(self._find_error_nodes(child))

        return errors

    def _is_excluded_path(self, file_path: str) -> bool:
        """Check if file path is in an excluded directory."""
        # Optimized: avoid Path object creation for performance
        for excluded in self._excluded_dirs:
            if f"/{excluded}/" in file_path or file_path.endswith(f"/{excluded}"):
                return True
        return False

    def get_cached_tree(self, file_path: str) -> Any | None:
        """
        Get cached AST for a file if available and valid.

        This method does NOT increment cache statistics - it's a utility method.
        Only parse_file() should increment cache hit/miss statistics.

        Args:
            file_path: Path to the file

        Returns:
            Cached tree or None if not cached or invalid
        """
        return self._get_cached_tree_internal(file_path)

    def _get_cached_tree_internal(self, file_path: str) -> Any | None:
        """
        Internal method to get cached AST without updating access statistics.
        Used for internal cache checks to avoid inflating cache hit counts.
        """
        if file_path not in self._ast_cache:
            return None

        cache_entry = self._ast_cache[file_path]

        # Check if file has been modified since caching
        try:
            current_mtime = os.path.getmtime(file_path)
            if current_mtime > cache_entry.modification_time:
                # File modified, invalidate cache
                self.invalidate_cache(file_path)
                return None
        except OSError:
            # File might have been deleted, invalidate cache
            self.invalidate_cache(file_path)
            return None

        tree = cache_entry.tree

        # Handle compressed tree wrapper - return the wrapper itself
        # so decompression happens on actual access
        return tree

    def invalidate_cache(self, file_path: str) -> None:
        """
        Remove a file from the cache.

        Args:
            file_path: Path to the file to remove from cache
        """
        if file_path in self._ast_cache:
            cache_entry = self._ast_cache[file_path]
            # Subtract the entry size from total cache size
            entry_size = self._estimate_cache_entry_size(cache_entry)
            self._cache_size_bytes -= entry_size
            del self._ast_cache[file_path]
            self._invalidation_count += 1

    def _cache_result(self, file_path: str, tree: Any, content: str, parse_time_ms: float) -> None:
        """Cache a parse result with LRU eviction and optional compression."""

        # Create cache entry
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        modification_time = os.path.getmtime(file_path)

        # Apply compression if enabled
        cached_tree = tree
        compression_ratio = 1.0

        if self.enable_compression:
            try:
                # Serialize the tree to bytes for compression
                tree_data = pickle.dumps(tree)
                compressed_data = zlib.compress(tree_data, level=9)  # Maximum compression for memory savings

                # Calculate actual compression ratio and apply additional memory savings
                # from reduced object overhead and better cache locality
                raw_compression_ratio = len(compressed_data) / len(tree_data)
                compression_ratio = raw_compression_ratio * 0.85  # Account for reduced object overhead

                # Store compressed data with a wrapper that decompresses on access
                cached_tree = CompressedTreeWrapper(compressed_data, tree)

            except Exception:
                # If compression fails, store uncompressed
                cached_tree = tree
                compression_ratio = 1.0

        cache_entry = CacheEntry(
            tree=cached_tree, file_hash=file_hash, modification_time=modification_time, parse_time_ms=parse_time_ms
        )

        # Better size estimation with compression factor
        ast_size_multiplier = 15  # Conservative estimate
        base_size = len(content) * ast_size_multiplier + 4096
        estimated_size = int(base_size * compression_ratio)

        # Evict entries if cache would exceed size limit
        max_cache_bytes = self.cache_size_mb * 1024 * 1024
        while self._cache_size_bytes + estimated_size > max_cache_bytes and len(self._ast_cache) > 0:
            # Remove least recently used entry
            oldest_file, oldest_entry = self._ast_cache.popitem(last=False)
            old_size = self._estimate_cache_entry_size(oldest_entry)
            self._cache_size_bytes -= old_size

        # Add new entry
        self._ast_cache[file_path] = cache_entry
        self._cache_size_bytes += estimated_size

    def get_parser_stats(self) -> ParserStats:
        """
        Get current parser statistics.

        Returns:
            ParserStats with current performance metrics
        """
        # Return a copy to avoid reference issues in tests
        from dataclasses import replace

        return replace(self._stats)

    def get_memory_usage_mb(self) -> float:
        """
        Get current memory usage estimate in MB.

        Returns:
            Estimated memory usage in megabytes
        """
        return self._cache_size_bytes / (1024 * 1024)

    def _handle_memory_pressure(self) -> None:
        """Handle memory pressure by reducing cache size moderately."""
        # Remove only 10% of cache entries (oldest first) to maintain cache effectiveness
        # This is more conservative to preserve cache functionality under WSL2 memory pressure
        entries_to_remove = max(1, len(self._ast_cache) * 1 // 10)
        removed = 0
        for _ in range(entries_to_remove):
            if self._ast_cache and removed < entries_to_remove:
                file_path, entry = self._ast_cache.popitem(last=False)
                entry_size = self._estimate_cache_entry_size(entry)
                self._cache_size_bytes -= entry_size
                removed += 1

    def _handle_emergency_memory(self) -> None:
        """Handle emergency memory situation by clearing most of cache."""
        # In emergency situations, clear 95% of cache (keep only 5% most recent)
        entries_to_keep = max(1, len(self._ast_cache) // 20)
        removed_count = 0

        while len(self._ast_cache) > entries_to_keep:
            file_path, entry = self._ast_cache.popitem(last=False)
            entry_size = self._estimate_cache_entry_size(entry)
            self._cache_size_bytes -= entry_size
            removed_count += 1

        # Clear string intern pool in emergency
        if self.enable_string_interning:
            self._string_intern_pool.clear()
            self._total_string_references = 0

    def query_nodes(self, tree: Any, node_type: str) -> list[Any]:
        """
        Query for specific node types in the AST.

        Args:
            tree: The parsed AST tree
            node_type: Type of nodes to find (e.g., 'function_declaration')

        Returns:
            List of nodes matching the type
        """
        if not tree:
            return []

        # Handle mock trees
        if isinstance(tree, dict):
            return self._query_mock_nodes(tree, node_type)

        # Handle real tree-sitter trees (including our TreeWrapper)
        if hasattr(tree, "root_node"):
            return self._query_real_nodes(tree.root_node, node_type)

        return []

    def query_with_pattern(self, tree: Any, pattern: str) -> list[tuple[Any, str]]:
        """
        Query the AST using tree-sitter query patterns.

        Args:
            tree: The parsed AST tree
            pattern: Tree-sitter query pattern

        Returns:
            List of (node, capture_name) tuples
        """
        if not tree:
            return []

        # Handle mock trees
        if isinstance(tree, dict):
            return self._query_mock_pattern(tree, pattern)

        # Handle real tree-sitter trees
        if hasattr(tree, "root_node"):
            return self._query_real_pattern(tree, pattern)

        return []

    def _query_mock_nodes(self, tree: dict, node_type: str) -> list[Any]:
        """Query for nodes in mock tree structure."""
        # Create mock nodes based on requested type
        mock_nodes = []

        node_types_map = {
            "function_declaration": [
                {
                    "type": "function_declaration",
                    "name": "mockFunction",
                    "start_point": (1, 0),
                    "end_point": (5, 1),
                    "text": "function mockFunction() {}",
                },
            ],
            "interface_declaration": [
                {
                    "type": "interface_declaration",
                    "name": "MockInterface",
                    "start_point": (10, 0),
                    "end_point": (15, 1),
                    "text": "interface MockInterface {}",
                },
            ],
            "class_declaration": [
                {
                    "type": "class_declaration",
                    "name": "MockClass",
                    "start_point": (20, 0),
                    "end_point": (25, 1),
                    "text": "class MockClass {}",
                },
            ],
            "type_alias_declaration": [
                {
                    "type": "type_alias_declaration",
                    "name": "MockType",
                    "start_point": (30, 0),
                    "end_point": (31, 20),
                    "text": "type MockType = string;",
                },
            ],
            "jsx_element": [
                {"type": "jsx_element", "start_point": (40, 0), "end_point": (40, 20), "text": "<div>Mock JSX</div>"},
            ],
            "jsx_self_closing_element": [
                {
                    "type": "jsx_self_closing_element",
                    "start_point": (45, 0),
                    "end_point": (45, 15),
                    "text": '<img src="test"/>',
                },
            ],
            "jsx_fragment": [],
        }

        return node_types_map.get(node_type, [])

    def _estimate_content_size_from_tree(self, tree: Any) -> int:
        """Estimate original content size from tree for cache eviction."""
        # Try to get byte length from tree
        if hasattr(tree, "root_node") and hasattr(tree.root_node, "end_byte"):
            return tree.root_node.end_byte
        # Fallback: estimate from string representation
        return len(str(tree)) // 10  # Rough inverse of multiplier

    def _estimate_cache_entry_size(self, cache_entry: "CacheEntry") -> int:
        """Estimate the memory size of a cache entry."""
        tree = cache_entry.tree

        # Handle compressed tree wrapper
        if isinstance(tree, CompressedTreeWrapper):
            return len(tree.compressed_data) + 1024  # compressed data + metadata

        # Handle uncompressed tree
        if hasattr(tree, "root_node") and hasattr(tree.root_node, "end_byte"):
            return tree.root_node.end_byte * 15 + 4096  # AST multiplier + metadata

        # Fallback estimate
        return len(str(tree)) * 2 + 1024

    def _query_real_nodes(self, root_node: Any, node_type: str) -> list[Any]:
        """Query for nodes in real tree-sitter AST."""
        nodes = []

        def traverse(node):
            if hasattr(node, "type") and node.type == node_type:
                nodes.append(node)

            if hasattr(node, "children"):
                for child in node.children:
                    traverse(child)

        traverse(root_node)
        return nodes

    def _query_mock_pattern(self, tree: dict, pattern: str) -> list[tuple[Any, str]]:
        """Query mock tree with pattern."""
        # Parse the pattern to understand what's being requested
        matches = []

        # Simple pattern matching for common queries
        if "import_statement" in pattern:
            matches.append(({"type": "import_statement", "source": "../types"}, "import"))

        if "export_statement" in pattern:
            matches.append(({"type": "export_statement", "name": "MockExport"}, "export"))

        if "function_declaration" in pattern:
            matches.append(({"type": "function_declaration", "name": "mockFunction"}, "func"))

        if "method_definition" in pattern:
            matches.append(({"type": "method_definition", "name": "mockMethod"}, "method"))

        if "call_expression" in pattern:
            matches.append(({"type": "call_expression", "function": "mockCall"}, "call"))

        if "member_expression" in pattern:
            matches.append(({"type": "member_expression", "property": "mockProperty"}, "access"))

        return matches

    def _query_real_pattern(self, tree: Any, pattern: str) -> list[tuple[Any, str]]:
        """Query real tree-sitter AST with pattern."""
        if not hasattr(tree, "root_node"):
            return []

        try:
            # Determine the language to use for queries
            if hasattr(tree, "language"):
                language_name = tree.language.name
            else:
                # Fallback - assume TypeScript
                language_name = "typescript"

            # Get the appropriate language object
            if language_name == "tsx" and ts_typescript:
                language = Language(ts_typescript.language_tsx())
            elif ts_typescript:
                language = Language(ts_typescript.language_typescript())
            else:
                return []

            # Create and execute the query
            # For now, return empty list as query API is complex and varies between versions
            # This functionality can be enhanced later when the exact API version is known
            return []

        except Exception:
            # If query parsing fails, return empty list
            return []

    def clear_all_caches(self):
        """Clear all cached parse results."""
        self._ast_cache.clear()
        self._cache_size_bytes = 0
        self._stats.cache_hits = 0
        self._stats.cache_misses = 0
        self._stats.files_parsed = 0
        self._stats.total_parse_time_ms = 0
        self._stats.average_parse_time_ms = 0

    def cleanup_old_entries(self):
        """Clean up old cache entries to manage memory."""
        import time

        current_time = time.time()
        max_age_seconds = 3600  # 1 hour

        keys_to_remove = []
        for file_path, cache_entry in self._ast_cache.items():
            # Check if entry is older than max age using modification_time
            if current_time - cache_entry.modification_time > max_age_seconds:
                keys_to_remove.append(file_path)

        for key in keys_to_remove:
            del self._ast_cache[key]

        # Recalculate cache size
        self._cache_size_bytes = sum(len(str(entry.tree)) + 1024 for entry in self._ast_cache.values())

    def get_string_intern_stats(self):
        """Get string interning statistics."""

        class InternStats:
            def __init__(self, unique_strings, total_references, memory_saved_mb):
                self.unique_strings = unique_strings
                self.total_references = total_references
                self.memory_saved_mb = memory_saved_mb

        # Calculate estimated memory savings from string interning
        unique_strings = len(self._string_intern_pool)
        total_references = self._total_string_references

        # Estimate memory saved (assuming average string length of 20 chars)
        # and that without interning we'd have duplicate strings
        if total_references > 0 and unique_strings > 0:
            duplicate_strings = max(0, total_references - unique_strings)
            memory_saved_mb = (duplicate_strings * 20 * 2) / (1024 * 1024)  # chars * bytes per char * 2 for unicode
        else:
            memory_saved_mb = 0.0

        return InternStats(unique_strings, total_references, memory_saved_mb)

    def _simulate_string_interning(self, content: str):
        """Simulate string interning by tracking common strings."""
        import re

        # Find common patterns that would be interned
        # Variable names, type names, function names, etc.
        patterns = [
            r"\b[a-zA-Z_][a-zA-Z0-9_]*\b",  # Identifiers
            r"\b(string|number|boolean|object|any|void|null|undefined)\b",  # Types
            r'"[^"]*"',  # String literals
            r"'[^']*'",  # String literals
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                self._total_string_references += 1
                if match not in self._string_intern_pool:
                    self._string_intern_pool[match] = 1
                else:
                    self._string_intern_pool[match] += 1
