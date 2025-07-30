"""
Isolated performance profiling test for TypeScript parser.
Used to identify specific bottlenecks in the parsing process.
"""

import time
import cProfile
import pstats
from pathlib import Path
from io import StringIO

import pytest

from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser, ResolutionDepth


class TestParserPerformanceProfile:
    """Profile parser performance to identify bottlenecks."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return TypeScriptParser(cache_size_mb=100, max_file_size_mb=5)
    
    @pytest.fixture 
    def fixtures_dir(self):
        """Get path to test fixtures."""
        return Path(__file__).parent / "fixtures"
    
    def test_profile_small_file_parsing(self, parser, fixtures_dir):
        """Profile parsing of small files to identify the bottleneck."""
        test_file = fixtures_dir / "valid_typescript.ts"
        
        # Read file to understand size
        with open(test_file, 'r') as f:
            content = f.read()
            lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('//')]
            loc = len(lines)
        
        print(f"\nFile: {test_file.name}")
        print(f"Lines of Code: {loc}")
        print(f"Content size: {len(content)} bytes")
        
        # First, warm up any lazy initialization
        parser.parse_file(str(test_file), ResolutionDepth.SYNTACTIC)
        
        # Clear cache to ensure cold parse
        parser.invalidate_cache(str(test_file))
        
        # Profile the parsing operation
        profiler = cProfile.Profile()
        
        # Time multiple runs
        parse_times = []
        for i in range(10):
            parser.invalidate_cache(str(test_file))
            
            start = time.perf_counter()
            profiler.enable()
            result = parser.parse_file(str(test_file), ResolutionDepth.SYNTACTIC)
            profiler.disable()
            end = time.perf_counter()
            
            parse_time_ms = (end - start) * 1000
            parse_times.append(parse_time_ms)
            
            assert result.success is True
        
        # Analyze results
        avg_time = sum(parse_times) / len(parse_times)
        min_time = min(parse_times)
        max_time = max(parse_times)
        
        print(f"\nParsing times (ms):")
        print(f"  Average: {avg_time:.2f}")
        print(f"  Min: {min_time:.2f}")
        print(f"  Max: {max_time:.2f}")
        print(f"  Expected max for {loc} LOC: {(loc / 1000.0) * 2.0:.2f}ms")
        
        # Print profiling results
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        print("\nTop time-consuming functions:")
        print(s.getvalue())
        
        # Also check what's taking the most time internally
        s2 = StringIO()
        ps2 = pstats.Stats(profiler, stream=s2).sort_stats('tottime')
        ps2.print_stats(10)
        print("\nFunctions by internal time:")
        print(s2.getvalue())
    
    def test_parser_initialization_overhead(self, fixtures_dir):
        """Test if parser initialization is causing overhead."""
        test_file = fixtures_dir / "valid_typescript.ts"
        
        # Time parser creation
        init_times = []
        for _ in range(5):
            start = time.perf_counter()
            parser = TypeScriptParser(cache_size_mb=100, max_file_size_mb=5)
            end = time.perf_counter()
            init_times.append((end - start) * 1000)
        
        avg_init_time = sum(init_times) / len(init_times)
        print(f"\nParser initialization time: {avg_init_time:.2f}ms")
        
        # Time first parse (includes any lazy initialization)
        parser = TypeScriptParser(cache_size_mb=100, max_file_size_mb=5)
        start = time.perf_counter()
        result = parser.parse_file(str(test_file), ResolutionDepth.SYNTACTIC)
        end = time.perf_counter()
        first_parse_time = (end - start) * 1000
        
        # Time second parse (warmed up)
        parser.invalidate_cache(str(test_file))
        start = time.perf_counter()
        result2 = parser.parse_file(str(test_file), ResolutionDepth.SYNTACTIC)
        end = time.perf_counter()
        second_parse_time = (end - start) * 1000
        
        print(f"First parse time: {first_parse_time:.2f}ms")
        print(f"Second parse time: {second_parse_time:.2f}ms")
        print(f"Overhead from first parse: {first_parse_time - second_parse_time:.2f}ms")
    
    def test_tree_sitter_overhead(self, parser, fixtures_dir):
        """Isolate tree-sitter parsing overhead."""
        test_file = fixtures_dir / "valid_typescript.ts"
        
        # Read content once
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Time just the tree-sitter parse
        ts_parser = parser._ts_parser
        
        parse_times = []
        for _ in range(20):
            start = time.perf_counter()
            tree = ts_parser.parse(content.encode('utf-8'))
            end = time.perf_counter()
            parse_times.append((end - start) * 1000)
        
        avg_ts_time = sum(parse_times) / len(parse_times)
        print(f"\nPure tree-sitter parse time: {avg_ts_time:.2f}ms")
        print(f"Min: {min(parse_times):.2f}ms")
        print(f"Max: {max(parse_times):.2f}ms")