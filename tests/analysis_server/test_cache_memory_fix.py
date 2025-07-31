"""
Test to understand and fix cache memory limit enforcement.
"""

import sys
import tempfile
from pathlib import Path

from aromcp.analysis_server.tools.typescript_parser import ResolutionDepth, TypeScriptParser


class TestCacheMemoryFix:
    """Test cache memory enforcement to understand the issue."""

    def test_cache_size_estimation_accuracy(self):
        """Test how accurately we're estimating cache sizes."""
        parser = TypeScriptParser(cache_size_mb=10, max_file_size_mb=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a file with known content size
            content = "// Test file\n" * 1000  # ~13KB of content
            file_path = temp_path / "test.ts"
            file_path.write_text(content)

            # Parse the file
            result = parser.parse_file(str(file_path), ResolutionDepth.SYNTACTIC)
            assert result.success is True

            # Check actual memory usage
            cache_entry = parser._ast_cache.get(str(file_path))
            if cache_entry:
                # Get actual size of cached data
                import pickle

                try:
                    pickled_size = len(pickle.dumps(cache_entry))
                    print(f"\nContent size: {len(content)} bytes")
                    print(f"Estimated cache size: {len(content) + 1024} bytes")
                    print(f"Actual pickled size: {pickled_size} bytes")

                    # Check tree object size
                    tree_repr_size = len(str(cache_entry.tree))
                    print(f"Tree repr size: {tree_repr_size} bytes")

                    # Get more accurate size estimate
                    if hasattr(cache_entry.tree, "__sizeof__"):
                        tree_size = sys.getsizeof(cache_entry.tree)
                        print(f"Tree object size: {tree_size} bytes")
                except Exception as e:
                    print(f"Could not pickle cache entry: {e}")

    def test_accurate_memory_tracking(self):
        """Test more accurate memory tracking for cache entries."""
        parser = TypeScriptParser(cache_size_mb=30, max_file_size_mb=2)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Track memory usage as we add files
            memory_measurements = []

            for i in range(10):
                # Create file with increasing size
                content = f"// File {i}\n"
                content += "export interface LargeInterface {\n"
                for j in range(500 * (i + 1)):  # Increasing number of properties
                    content += f"    property{j:05d}: string;\n"
                content += "}\n"

                file_path = temp_path / f"test_{i}.ts"
                file_path.write_text(content)

                # Parse and track memory
                result = parser.parse_file(str(file_path), ResolutionDepth.SYNTACTIC)
                assert result.success is True

                reported_memory = parser.get_memory_usage_mb()
                cache_entries = len(parser._ast_cache)

                memory_measurements.append(
                    {
                        "file_num": i,
                        "content_size": len(content),
                        "reported_memory_mb": reported_memory,
                        "cache_entries": cache_entries,
                        "cache_size_bytes": parser._cache_size_bytes,
                    }
                )

                print(f"\nFile {i}:")
                print(f"  Content size: {len(content):,} bytes")
                print(f"  Reported memory: {reported_memory:.2f} MB")
                print(f"  Cache entries: {cache_entries}")
                print(f"  Cache size bytes: {parser._cache_size_bytes:,}")

            # Check if memory tracking is reasonable
            final_memory = memory_measurements[-1]["reported_memory_mb"]
            print(f"\nFinal reported memory: {final_memory:.2f} MB")
            print(f"Cache limit: {parser.cache_size_mb} MB")

            # The issue is likely that we're not accounting for the actual AST size
            # which can be much larger than the source content
