"""
Debug test to understand memory measurement in cache tests.
"""

import tempfile
from pathlib import Path

import pytest
import psutil

from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser, ResolutionDepth


class TestCacheMemoryDebug:
    """Debug memory measurement issues."""
    
    def test_memory_measurement_accuracy(self):
        """Test what exactly we're measuring."""
        if not psutil:
            pytest.skip("psutil not available")
        
        # Get baseline memory
        process = psutil.Process()
        baseline_memory_mb = process.memory_info().rss / (1024 * 1024)
        print(f"\nBaseline process memory: {baseline_memory_mb:.1f} MB")
        
        # Create parser
        cache_size_mb = 30
        parser = TypeScriptParser(cache_size_mb=cache_size_mb, max_file_size_mb=2)
        
        after_parser_mb = process.memory_info().rss / (1024 * 1024)
        print(f"After creating parser: {after_parser_mb:.1f} MB (increase: {after_parser_mb - baseline_memory_mb:.1f} MB)")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a large file
            content = "// Large file\n"
            content += "export interface LargeInterface {\n"
            for j in range(5000):
                content += f"    property{j:05d}: string;\n"
            content += "}\n"
            
            file_path = temp_path / "test.ts"
            file_path.write_text(content)
            
            print(f"\nFile content size: {len(content) / 1024:.1f} KB")
            
            # Parse the file
            memory_before_parse = process.memory_info().rss / (1024 * 1024)
            result = parser.parse_file(str(file_path), ResolutionDepth.SYNTACTIC)
            memory_after_parse = process.memory_info().rss / (1024 * 1024)
            
            print(f"Memory before parse: {memory_before_parse:.1f} MB")
            print(f"Memory after parse: {memory_after_parse:.1f} MB")
            print(f"Parse increase: {memory_after_parse - memory_before_parse:.1f} MB")
            
            # Check parser's reported cache size
            parser_cache_mb = parser.get_memory_usage_mb()
            print(f"\nParser reported cache size: {parser_cache_mb:.2f} MB")
            print(f"Parser cache size bytes: {parser._cache_size_bytes:,}")
            
            # Parse more files to see cache eviction
            for i in range(5):
                file_path = temp_path / f"test_{i}.ts"
                file_path.write_text(content)
                
                result = parser.parse_file(str(file_path), ResolutionDepth.SYNTACTIC)
                
                current_memory = process.memory_info().rss / (1024 * 1024)
                parser_cache_mb = parser.get_memory_usage_mb()
                
                print(f"\nAfter file {i}:")
                print(f"  Process memory: {current_memory:.1f} MB")
                print(f"  Parser cache: {parser_cache_mb:.2f} MB")
                print(f"  Cache entries: {len(parser._ast_cache)}")
    
    def test_actual_vs_reported_cache_size(self):
        """Compare actual memory usage with reported cache size."""
        parser = TypeScriptParser(cache_size_mb=10, max_file_size_mb=1)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files with known sizes
            for i in range(10):
                content = f"// File {i}\n" + ("x" * 10000)  # ~10KB files
                file_path = temp_path / f"file_{i}.ts"
                file_path.write_text(content)
                
                result = parser.parse_file(str(file_path), ResolutionDepth.SYNTACTIC)
                
                # Check if cache is respecting limits
                reported_mb = parser.get_memory_usage_mb()
                if reported_mb > parser.cache_size_mb:
                    print(f"\nCache exceeded limit! Reported: {reported_mb:.2f} MB, Limit: {parser.cache_size_mb} MB")
                    print(f"Cache entries: {len(parser._ast_cache)}")
                    
                    # Check individual entry sizes
                    for path, entry in parser._ast_cache.items():
                        print(f"  {Path(path).name}: has tree? {entry.tree is not None}")