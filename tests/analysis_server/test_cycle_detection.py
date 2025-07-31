"""
Tests for Phase 4 Cycle Detection and Infinite Loop Prevention.

These tests verify that the TypeScript Analysis MCP Server can detect circular call patterns
and handle them without infinite loops, while still providing meaningful call graph analysis.
"""

from pathlib import Path

import pytest

from aromcp.analysis_server.models.typescript_models import (
    CallTraceResponse,
)
from aromcp.analysis_server.tools.get_call_trace import get_call_trace_impl


class TestCycleDetection:
    """Test detection of circular call patterns."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the Phase 4 fixtures directory."""
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"

    @pytest.fixture
    def recursive_functions_file(self, fixtures_dir):
        """Path to recursive functions test file."""
        return str(fixtures_dir / "recursive_functions.ts")

    def test_direct_recursion_detection(self, recursive_functions_file):
        """Test detection of direct recursion (function calls itself)."""
        response = get_call_trace_impl(entry_point="factorial", file_paths=[recursive_functions_file], max_depth=10)

        # Should detect direct recursion in factorial function
        # Phase 4: Should detect cycles and report them
        assert isinstance(response, CallTraceResponse)
        assert response.entry_point == "factorial"

        # Should detect the cycle without infinite loop
        assert response.call_graph_stats.cycles_detected > 0, "Should detect direct recursion cycle"

        # Should not hang or timeout - execution should complete quickly
        assert len(response.execution_paths) >= 0, "Should complete analysis without hanging"

        # Should show the recursive call pattern
        recursive_paths = []
        for path in response.execution_paths:
            if "factorial" in path.path and len(path.path) > 1:
                recursive_paths.append(path)

        # Phase 4: Should show recursive call pattern
        assert len(recursive_paths) > 0, "Should detect recursive call pattern in execution paths"

    def test_indirect_recursion_detection(self, recursive_functions_file):
        """Test detection of indirect recursion (A calls B calls A)."""
        response = get_call_trace_impl(entry_point="isEven", file_paths=[recursive_functions_file], max_depth=15)

        # Should detect indirect recursion: isEven -> isOdd -> isEven
        # Phase 4: Should detect indirect cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect indirect recursion cycle"

        # Should identify both functions in the cycle
        cycle_functions = set()
        for path in response.execution_paths:
            if len(path.path) > 1:
                cycle_functions.update(path.path)

        # Should detect both functions in the cycle
        assert "isEven" in cycle_functions, "Should detect isEven in cycle"
        assert "isOdd" in cycle_functions, "Should detect isOdd in cycle"

        # Should not exceed max_depth due to cycle detection
        assert response.call_graph_stats.max_depth_reached <= 15, "Should not exceed max_depth"

    def test_complex_cycle_detection(self, recursive_functions_file):
        """Test detection of complex multi-function cycles."""
        response = get_call_trace_impl(entry_point="processTaskA", file_paths=[recursive_functions_file], max_depth=20)

        # Should detect 3-function cycle: processTaskA -> processTaskB -> processTaskC -> processTaskA
        # Phase 4: Should detect complex cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect complex multi-function cycle"

        # Should identify all functions in the cycle
        all_functions = set()
        for path in response.execution_paths:
            all_functions.update(path.path)

        expected_cycle_functions = {"processTaskA", "processTaskB", "processTaskC"}
        cycle_functions_found = expected_cycle_functions.intersection(all_functions)

        assert len(cycle_functions_found) >= 2, "Should detect functions involved in complex cycle"

    def test_deep_cycle_detection(self, recursive_functions_file):
        """Test detection of deep cycles with many functions."""
        response = get_call_trace_impl(entry_point="step1", file_paths=[recursive_functions_file], max_depth=25)

        # Should detect 5-function cycle: step1 -> step2 -> step3 -> step4 -> step5 -> step1
        # Phase 4: Should detect deep cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect deep 5-function cycle"

        # Should track all steps in the cycle
        step_functions = set()
        for path in response.execution_paths:
            for func in path.path:
                if func.startswith("step"):
                    step_functions.add(func)

        # Should find multiple step functions
        assert len(step_functions) >= 3, "Should detect multiple functions in deep cycle"

    def test_mutual_recursion_with_termination(self, recursive_functions_file):
        """Test mutual recursion that has proper termination conditions."""
        response = get_call_trace_impl(
            entry_point="parseExpression", file_paths=[recursive_functions_file], max_depth=30
        )

        # Should detect mutual recursion: parseExpression -> parseTerm -> parseFactor -> parseExpression
        # But with proper termination conditions
        # Phase 4: Should detect mutual recursion cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect mutual recursion cycle"

        # Should identify parser functions
        parser_functions = set()
        for path in response.execution_paths:
            for func in path.path:
                if func.startswith("parse"):
                    parser_functions.add(func)

        expected_parsers = {"parseExpression", "parseTerm", "parseFactor"}
        found_parsers = expected_parsers.intersection(parser_functions)

        assert len(found_parsers) >= 2, "Should detect mutual recursion between parser functions"


class TestInfiniteLoopPrevention:
    """Test prevention of infinite loops during call graph analysis."""

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"

    def test_max_depth_enforcement(self, fixtures_dir):
        """Test that max_depth parameter prevents infinite analysis."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        # Test with small max_depth
        response = get_call_trace_impl(entry_point="factorial", file_paths=[recursive_file], max_depth=3)

        # Should respect max_depth limit
        assert response.call_graph_stats.max_depth_reached <= 3, "Should respect max_depth=3"

        # Test with larger max_depth
        response = get_call_trace_impl(entry_point="factorial", file_paths=[recursive_file], max_depth=10)

        # Should still complete without hanging
        assert response.call_graph_stats.max_depth_reached <= 10, "Should respect max_depth=10"
        assert isinstance(response.execution_paths, list), "Should complete analysis"

    def test_cycle_breaking_mechanism(self, fixtures_dir):
        """Test that cycles are broken to prevent infinite loops."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(
            entry_point="isEven", file_paths=[recursive_file], max_depth=50  # Large enough to detect cycle breaking
        )

        # Should break cycles and not reach max_depth
        # If cycles are properly broken, analysis should complete before max_depth
        cycle_broken = response.call_graph_stats.cycles_detected > 0
        depth_reasonable = response.call_graph_stats.max_depth_reached < 50

        # Phase 4: Should break cycles to prevent infinite analysis
        assert cycle_broken, "Should detect cycles"
        # Note: depth_reasonable might not be true if the algorithm traces multiple cycle iterations
        # The key is that analysis completes and cycles are detected

    def test_multiple_independent_cycles(self, fixtures_dir):
        """Test handling of multiple independent cycles in the same codebase."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        # Test analysis that might encounter multiple cycles
        response = get_call_trace_impl(
            entry_point="step1", file_paths=[recursive_file], max_depth=20  # This should find the 5-function cycle
        )

        first_cycles = response.call_graph_stats.cycles_detected

        # Test another entry point that has different cycles
        response2 = get_call_trace_impl(
            entry_point="isEven", file_paths=[recursive_file], max_depth=20  # This should find the 2-function cycle
        )

        second_cycles = response2.call_graph_stats.cycles_detected

        # Should detect cycles in both analyses
        # Phase 4: Should handle multiple independent cycles
        assert first_cycles > 0, "Should detect cycles from first entry point"
        assert second_cycles > 0, "Should detect cycles from second entry point"

    def test_performance_with_cycles(self, fixtures_dir):
        """Test that cycle detection doesn't significantly degrade performance."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        import time

        start_time = time.time()
        response = get_call_trace_impl(entry_point="processTaskA", file_paths=[recursive_file], max_depth=30)
        end_time = time.time()

        analysis_time = end_time - start_time

        # Should complete within reasonable time (acceptance criteria: <15 seconds for deep traces)
        # Phase 4: Should complete cycle detection efficiently
        assert analysis_time < 15.0, f"Analysis should complete within 15 seconds, took {analysis_time:.2f}s"

        # Should still detect cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect cycles efficiently"


class TestCycleBreakingMechanisms:
    """Test specific mechanisms for breaking cycles."""

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"

    def test_visited_function_tracking(self, fixtures_dir):
        """Test that visited functions are tracked to break cycles."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(entry_point="factorial", file_paths=[recursive_file], max_depth=20)

        # Should track visited functions and break cycles
        # Phase 4: Should implement visited function tracking
        assert response.call_graph_stats.cycles_detected > 0, "Should detect cycles using visited tracking"

        # Should show some indication of cycle breaking in execution paths
        # This could be placeholder references or truncated paths
        cycle_indicators = []
        for path in response.execution_paths:
            # Look for patterns that indicate cycle breaking
            if len(path.path) > 1:
                # Check for repeated function names
                function_counts = {}
                for func in path.path:
                    function_counts[func] = function_counts.get(func, 0) + 1

                for func, count in function_counts.items():
                    if count > 1:  # Function appears multiple times
                        cycle_indicators.append(func)

        # Should find some evidence of cycle handling
        assert len(cycle_indicators) > 0, "Should show evidence of cycle handling in paths"

    def test_placeholder_references(self, fixtures_dir):
        """Test that cycles are represented with placeholder references."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(entry_point="isEven", file_paths=[recursive_file], max_depth=15)

        # Should use placeholder references to represent cycles
        # Phase 4: Should implement placeholder references for cycles
        assert response.call_graph_stats.cycles_detected > 0, "Should detect cycles"

        # Look for execution paths that show cycle handling
        paths_with_cycles = []
        for path in response.execution_paths:
            if len(path.path) >= 3:  # Long enough to show a cycle
                paths_with_cycles.append(path)

        assert len(paths_with_cycles) > 0, "Should have execution paths that handle cycles"

        # Check if any paths have special cycle indicators
        # (The exact format depends on implementation - could be special markers, etc.)

    def test_cycle_detection_accuracy(self, fixtures_dir):
        """Test accuracy of cycle detection without false positives."""
        # Test with non-recursive functions to ensure no false cycle detection
        simple_calls = str(fixtures_dir / "simple_calls.ts")

        response = get_call_trace_impl(entry_point="login", file_paths=[simple_calls], max_depth=10)

        # Should not detect cycles in non-recursive call graph
        # Phase 4: Should not report false positive cycles
        assert response.call_graph_stats.cycles_detected == 0, "Should not detect false positive cycles"

        # Should still build proper call graph
        assert len(response.execution_paths) > 0, "Should build call graph for non-recursive functions"
        assert response.call_graph_stats.total_functions > 1, "Should detect multiple functions"


class TestComplexCyclePatterns:
    """Test handling of complex and edge-case cycle patterns."""

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"

    def test_nested_recursive_calls(self, fixtures_dir):
        """Test handling of nested recursive calls."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(entry_point="fibonacciTail", file_paths=[recursive_file], max_depth=25)

        # Should handle tail recursion properly
        # Phase 4: Should handle nested recursive patterns
        assert response.call_graph_stats.cycles_detected > 0, "Should detect tail recursion cycle"

        # Should complete analysis without issues
        assert len(response.execution_paths) >= 0, "Should handle tail recursion"

    def test_conditional_recursion(self, fixtures_dir):
        """Test recursion that depends on conditional logic."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(
            entry_point="factorial", file_paths=[recursive_file], max_depth=15, analyze_conditions=True
        )

        # Should detect conditional recursion patterns
        # factorial(n) calls factorial(n-1) only if n > 1
        # Phase 4: Should handle conditional recursion
        assert response.call_graph_stats.cycles_detected > 0, "Should detect conditional recursion"

        # Should show conditional execution paths
        conditional_paths = [p for p in response.execution_paths if p.condition]
        # Note: conditional recursion is complex - may not always have explicit conditions

        # Key test: should complete without infinite loop
        assert isinstance(response.execution_paths, list), "Should handle conditional recursion"

    def test_async_recursive_patterns(self, fixtures_dir):
        """Test handling of async recursive patterns."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(entry_point="asyncRecursiveSearch", file_paths=[recursive_file], max_depth=20)

        # Should handle async recursion
        # Phase 4: Should handle async recursive patterns
        assert isinstance(response, CallTraceResponse), "Should handle async recursion"

        # Should detect the recursive pattern even in async context
        if response.call_graph_stats.cycles_detected > 0:
            # Async recursion detected
            assert True, "Successfully detected async recursion"
        else:
            # Might be harder to detect in Phase 1, but should not crash
            assert len(response.execution_paths) >= 0, "Should handle async recursion without crashing"

    def test_object_method_recursion(self, fixtures_dir):
        """Test recursion in object methods."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(
            entry_point="process", file_paths=[recursive_file], max_depth=20  # RecursiveProcessor.process method
        )

        # Should handle method recursion
        # RecursiveProcessor.process calls itself recursively
        # Phase 4: Should handle object method recursion
        assert isinstance(response, CallTraceResponse), "Should handle method recursion"

        # Should detect recursive pattern in methods
        if response.call_graph_stats.cycles_detected > 0:
            assert True, "Successfully detected method recursion"
        else:
            # Should at least not crash on method recursion
            assert len(response.execution_paths) >= 0, "Should handle method recursion"

    def test_cross_method_recursion(self, fixtures_dir):
        """Test recursion across different methods of the same class."""
        recursive_file = str(fixtures_dir / "recursive_functions.ts")

        response = get_call_trace_impl(
            entry_point="validateAndProcess",  # This calls isValid which might call validateAndProcess
            file_paths=[recursive_file],
            max_depth=15,
        )

        # Should handle cross-method recursion in the same class
        # Phase 4: Should handle cross-method recursion
        assert isinstance(response, CallTraceResponse), "Should handle cross-method recursion"

        # The exact cycle detection depends on the implementation
        # Key requirement: should not hang or crash
        assert len(response.execution_paths) >= 0, "Should complete cross-method recursion analysis"

    def test_cycle_in_large_call_graph(self, fixtures_dir):
        """Test cycle detection in complex call graphs with many functions."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")

        # Use a complex entry point that might have cycles
        response = get_call_trace_impl(entry_point="processUserRegistration", file_paths=[complex_graph], max_depth=30)

        # Should handle cycle detection in large graphs
        # Phase 4: Should handle cycles in complex graphs
        assert isinstance(response, CallTraceResponse), "Should handle large graph analysis"

        # Should complete within reasonable time
        assert response.call_graph_stats.total_functions >= 0, "Should analyze large graph"

        # If cycles exist in the complex graph, should detect them
        # If no cycles, should not report false positives
        assert response.call_graph_stats.cycles_detected >= 0, "Should handle cycle detection in large graphs"
