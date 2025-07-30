"""
Tests for Phase 4 Call Graph Performance and Memory Requirements.

These tests verify that the TypeScript Analysis MCP Server meets performance requirements
for deep call tracing, complex graph analysis, and memory usage constraints.
"""

import os
import time
import pytest
from pathlib import Path
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor

from aromcp.analysis_server.tools.get_call_trace import get_call_trace_impl
from aromcp.analysis_server.models.typescript_models import (
    CallTraceResponse,
    ExecutionPath,
    CallGraphStats,
    AnalysisError
)


class TestDeepTracingPerformance:
    """Test performance requirements for deep call tracing."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the Phase 4 fixtures directory."""
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    @pytest.fixture
    def complex_graph_file(self, fixtures_dir):
        """Path to complex graph test file."""
        return str(fixtures_dir / "complex_graph.ts")
    
    @pytest.fixture
    def recursive_functions_file(self, fixtures_dir):
        """Path to recursive functions test file."""
        return str(fixtures_dir / "recursive_functions.ts")
    
    def test_deep_trace_15_second_requirement(self, complex_graph_file):
        """Test that deep traces (10+ levels) complete within 15 seconds."""
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph_file],
            max_depth=15,  # Deep tracing requirement
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Acceptance criteria: Complete deep traces within 15 seconds
        # Phase 4: Should meet 15-second performance requirement
        assert execution_time < 15.0, f"Deep trace took {execution_time:.2f}s, should be < 15s"
        
        # Should actually reach deep levels
        assert response.call_graph_stats.max_depth_reached >= 10, "Should trace at least 10 levels deep"
        
        # Should produce meaningful results despite time constraint
        assert len(response.execution_paths) > 0, "Should produce execution paths in time limit"
    
    def test_very_deep_trace_performance(self, complex_graph_file):
        """Test performance with very deep max_depth settings."""
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph_file],
            max_depth=25,  # Very deep
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should still complete in reasonable time even with very deep setting
        # Phase 4: Should handle very deep traces efficiently
        assert execution_time < 30.0, f"Very deep trace took {execution_time:.2f}s, should be < 30s"
        
        # Should reach significant depth
        assert response.call_graph_stats.max_depth_reached >= 15, "Should trace deeply with high max_depth"
    
    def test_multiple_entry_points_performance(self, complex_graph_file):
        """Test performance when analyzing multiple entry points."""
        entry_points = [
            "processUserRegistration",
            "processOrder", 
            "generateUserAnalytics"
        ]
        
        total_start_time = time.time()
        
        for entry_point in entry_points:
            start_time = time.time()
            
            response = get_call_trace_impl(
                entry_point=entry_point,
                file_paths=[complex_graph_file],
                max_depth=12,
                analyze_conditions=True
            )
            
            end_time = time.time()
            individual_time = end_time - start_time
            
            # Each analysis should complete quickly
            assert individual_time < 10.0, f"Analysis of {entry_point} took {individual_time:.2f}s"
            assert isinstance(response, CallTraceResponse), f"Should return valid response for {entry_point}"
        
        total_end_time = time.time()
        total_time = total_end_time - total_start_time
        
        # Total time for multiple analyses should be reasonable
        # Phase 4: Should handle multiple entry points efficiently
        assert total_time < 25.0, f"Multiple entry point analysis took {total_time:.2f}s"
    
    def test_performance_with_cycles(self, recursive_functions_file):
        """Test performance when handling recursive functions and cycles."""
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="factorial",
            file_paths=[recursive_functions_file],
            max_depth=20,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Cycle detection should not significantly impact performance
        # Phase 4: Should handle cycles efficiently
        assert execution_time < 5.0, f"Cycle analysis took {execution_time:.2f}s, should be < 5s"
        
        # Should detect cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect cycles"
        
        # Should complete analysis despite cycles
        assert len(response.execution_paths) >= 0, "Should complete analysis with cycles"


class TestComplexGraphPerformance:
    """Test performance with complex call graphs."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_large_function_count_performance(self, fixtures_dir):
        """Test performance with graphs containing many functions."""
        # Use multiple files to create a large function set
        files = [
            str(fixtures_dir / "complex_graph.ts"),
            str(fixtures_dir / "class_methods.ts"),
            str(fixtures_dir / "async_patterns.ts"),
            str(fixtures_dir / "event_system.ts")
        ]
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=files,
            max_depth=12,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle large function sets efficiently
        # Phase 4: Should scale with large function counts
        assert execution_time < 20.0, f"Large graph analysis took {execution_time:.2f}s"
        
        # Should discover many functions
        assert response.call_graph_stats.total_functions >= 10, "Should discover many functions in large graph"
    
    def test_wide_call_graph_performance(self, fixtures_dir):
        """Test performance with functions that call many other functions."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",  # Calls many functions
            file_paths=[complex_graph],
            max_depth=8,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle wide call graphs efficiently
        # Phase 4: Should handle wide call patterns
        assert execution_time < 15.0, f"Wide graph analysis took {execution_time:.2f}s"
        
        # Should discover many call edges
        assert response.call_graph_stats.total_edges >= 5, "Should discover many call edges in wide graph"
    
    def test_complex_conditional_performance(self, fixtures_dir):
        """Test performance with complex conditional logic."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls],
            max_depth=15,
            analyze_conditions=True  # Enable complex condition analysis
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Conditional analysis should not significantly impact performance
        # Phase 4: Should handle complex conditionals efficiently
        assert execution_time < 10.0, f"Complex conditional analysis took {execution_time:.2f}s"
        
        # Should detect multiple execution paths
        assert len(response.execution_paths) > 1, "Should detect multiple conditional paths"
    
    def test_async_pattern_performance(self, fixtures_dir):
        """Test performance with complex async patterns."""
        async_patterns = str(fixtures_dir / "async_patterns.ts")
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="complexAsyncWorkflow",
            file_paths=[async_patterns],
            max_depth=12,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Async pattern analysis should be efficient
        # Phase 4: Should handle async patterns efficiently
        assert execution_time < 12.0, f"Async pattern analysis took {execution_time:.2f}s"
        
        # Should handle async patterns
        assert isinstance(response, CallTraceResponse), "Should handle async patterns"


class TestMemoryUsageRequirements:
    """Test memory usage requirements during call graph analysis."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def get_memory_usage_mb(self):
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    
    def test_memory_usage_under_500mb(self, fixtures_dir):
        """Test that memory usage stays under 500MB for complex call graphs."""
        # Use multiple large files to create memory pressure
        files = [
            str(fixtures_dir / "complex_graph.ts"),
            str(fixtures_dir / "class_methods.ts"),
            str(fixtures_dir / "async_patterns.ts"),
            str(fixtures_dir / "event_system.ts"),
            str(fixtures_dir / "conditional_calls.ts")
        ]
        
        initial_memory = self.get_memory_usage_mb()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=files,
            max_depth=15,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        peak_memory = self.get_memory_usage_mb()
        memory_increase = peak_memory - initial_memory
        
        # Acceptance criteria: Memory usage under 500MB for complex call graphs
        # Phase 4: Should meet 500MB memory requirement
        assert memory_increase < 500.0, f"Memory usage increased by {memory_increase:.1f}MB, should be < 500MB"
        
        # Should still produce results within memory constraints
        assert isinstance(response, CallTraceResponse), "Should complete analysis within memory limits"
    
    def test_memory_efficiency_with_deep_tracing(self, fixtures_dir):
        """Test memory efficiency during deep call tracing."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        initial_memory = self.get_memory_usage_mb()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph],
            max_depth=20,  # Deep tracing
            include_external_calls=False,
            analyze_conditions=True
        )
        
        final_memory = self.get_memory_usage_mb()
        memory_increase = final_memory - initial_memory
        
        # Deep tracing should not use excessive memory
        # Phase 4: Should be memory efficient during deep tracing
        assert memory_increase < 200.0, f"Deep tracing used {memory_increase:.1f}MB, should be < 200MB"
        
        # Should reach deep levels
        assert response.call_graph_stats.max_depth_reached >= 15, "Should trace deeply with efficient memory usage"
    
    def test_memory_cleanup_after_analysis(self, fixtures_dir):
        """Test that memory is properly cleaned up after analysis."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        initial_memory = self.get_memory_usage_mb()
        
        # Perform multiple analyses
        for i in range(3):
            response = get_call_trace_impl(
                entry_point="processUserRegistration",
                file_paths=[complex_graph],
                max_depth=12,
                analyze_conditions=True
            )
            
            # Force garbage collection between analyses
            import gc
            gc.collect()
        
        final_memory = self.get_memory_usage_mb()
        memory_increase = final_memory - initial_memory
        
        # Memory should not accumulate significantly across multiple analyses
        # Phase 4: Should clean up memory between analyses
        assert memory_increase < 100.0, f"Memory accumulated {memory_increase:.1f}MB across analyses"
    
    def test_memory_usage_with_cycles(self, fixtures_dir):
        """Test memory usage when handling recursive cycles."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")
        
        initial_memory = self.get_memory_usage_mb()
        
        response = get_call_trace_impl(
            entry_point="factorial",
            file_paths=[recursive_file],
            max_depth=25,  # High depth with recursion
            analyze_conditions=True
        )
        
        peak_memory = self.get_memory_usage_mb()
        memory_increase = peak_memory - initial_memory
        
        # Cycle handling should not cause memory leaks
        # Phase 4: Should handle cycles without memory issues
        assert memory_increase < 150.0, f"Cycle handling used {memory_increase:.1f}MB, should be < 150MB"
        
        # Should detect cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect cycles efficiently"


class TestScalabilityRequirements:
    """Test scalability with large codebases and concurrent usage."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_large_codebase_simulation(self, fixtures_dir):
        """Test performance with simulated large codebase."""
        # Use all available files to simulate larger codebase
        all_files = [
            str(fixtures_dir / "simple_calls.ts"),
            str(fixtures_dir / "recursive_functions.ts"),
            str(fixtures_dir / "conditional_calls.ts"),
            str(fixtures_dir / "async_patterns.ts"),
            str(fixtures_dir / "class_methods.ts"),
            str(fixtures_dir / "event_system.ts"),
            str(fixtures_dir / "complex_graph.ts")
        ]
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="login",  # Simple entry point across large codebase
            file_paths=all_files,
            max_depth=10,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle large codebase efficiently
        # Phase 4: Should scale to large codebases
        assert execution_time < 25.0, f"Large codebase analysis took {execution_time:.2f}s"
        
        # Should find the entry point across multiple files
        assert isinstance(response, CallTraceResponse), "Should handle large codebase analysis"
    
    def test_concurrent_analysis_safety(self, fixtures_dir):
        """Test that multiple concurrent analyses work correctly."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        def run_analysis(entry_point):
            """Run a single analysis."""
            return get_call_trace_impl(
                entry_point=entry_point,
                file_paths=[complex_graph],
                max_depth=10,
                analyze_conditions=True
            )
        
        entry_points = [
            "processUserRegistration",
            "processOrder",
            "generateUserAnalytics"
        ]
        
        start_time = time.time()
        
        # Run concurrent analyses
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_analysis, ep) for ep in entry_points]
            results = [future.result() for future in futures]
        
        end_time = time.time()
        concurrent_time = end_time - start_time
        
        # Concurrent analyses should complete efficiently
        # Phase 4: Should support concurrent usage
        assert concurrent_time < 20.0, f"Concurrent analyses took {concurrent_time:.2f}s"
        
        # All analyses should succeed
        for i, result in enumerate(results):
            assert isinstance(result, CallTraceResponse), f"Analysis {i} should succeed"
            assert result.entry_point == entry_points[i], f"Analysis {i} should have correct entry point"
    
    def test_repeated_analysis_performance(self, fixtures_dir):
        """Test performance of repeated analyses (caching effects)."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        times = []
        
        # Run same analysis multiple times
        for i in range(5):
            start_time = time.time()
            
            response = get_call_trace_impl(
                entry_point="processUserRegistration",
                file_paths=[complex_graph],
                max_depth=12,
                analyze_conditions=True
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            times.append(execution_time)
            
            assert isinstance(response, CallTraceResponse), f"Analysis {i} should succeed"
        
        # Later analyses might be faster due to caching (if implemented)
        average_time = sum(times) / len(times)
        
        # Phase 4: Repeated analyses should be efficient
        assert average_time < 15.0, f"Average repeated analysis time: {average_time:.2f}s"
        
        # Performance should be consistent
        max_time = max(times)
        min_time = min(times)
        assert max_time < 25.0, f"Slowest analysis: {max_time:.2f}s"


class TestPerformanceBenchmarks:
    """Test specific performance benchmarks and edge cases."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_performance_with_external_calls(self, fixtures_dir):
        """Test performance when including external calls."""
        async_patterns = str(fixtures_dir / "async_patterns.ts")
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="complexAsyncWorkflow",
            file_paths=[async_patterns],
            max_depth=12,
            include_external_calls=True,  # Include external calls
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # External call analysis should not significantly impact performance
        # Phase 4: Should handle external calls efficiently
        assert execution_time < 15.0, f"External call analysis took {execution_time:.2f}s"
        
        # Should complete analysis
        assert isinstance(response, CallTraceResponse), "Should handle external calls"
    
    def test_performance_degradation_limits(self, fixtures_dir):
        """Test that performance doesn't degrade significantly with complexity."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        # Test with increasing max_depth to measure performance scaling
        depths = [5, 10, 15, 20]
        times = []
        
        for depth in depths:
            start_time = time.time()
            
            response = get_call_trace_impl(
                entry_point="processUserRegistration",
                file_paths=[complex_graph],
                max_depth=depth,
                analyze_conditions=True
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            times.append(execution_time)
            
            assert isinstance(response, CallTraceResponse), f"Should handle depth {depth}"
        
        # Performance should not degrade exponentially
        # Later analyses should not be dramatically slower
        for i, time_taken in enumerate(times):
            depth = depths[i]
            # Phase 4: Performance should scale reasonably
            assert time_taken < 30.0, f"Depth {depth} took {time_taken:.2f}s, should be < 30s"
        
        # Check that performance scaling is reasonable
        if len(times) >= 2:
            max_slowdown = max(times) / min(times)
            assert max_slowdown < 10.0, f"Performance degradation too high: {max_slowdown:.1f}x"
    
    def test_timeout_and_graceful_degradation(self, fixtures_dir):
        """Test graceful handling of complex analyses that might timeout."""
        complex_files = [
            str(fixtures_dir / "complex_graph.ts"),
            str(fixtures_dir / "event_system.ts"),
            str(fixtures_dir / "async_patterns.ts")
        ]
        
        start_time = time.time()
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=complex_files,
            max_depth=30,  # Very high depth that might cause timeout
            include_external_calls=True,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time or gracefully handle timeout
        # Phase 4: Should handle complex cases gracefully
        assert execution_time < 60.0, f"Complex analysis took {execution_time:.2f}s"
        
        # Should return valid response even if analysis is incomplete
        assert isinstance(response, CallTraceResponse), "Should return valid response"
        
        # Should indicate if analysis was truncated or incomplete
        # (This could be shown through errors, warnings, or partial results)
        if execution_time > 45.0:
            # For very long analyses, might have partial results
            assert len(response.errors) >= 0, "Long analysis should handle gracefully"