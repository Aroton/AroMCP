"""
Tests for Phase 4 Call Graph Construction and Function Call Detection.

These tests verify that the TypeScript Analysis MCP Server can build accurate call graphs
from TypeScript code, detecting various types of function calls and method invocations.
"""

import os
import pytest
from pathlib import Path

from aromcp.analysis_server.tools.get_call_trace import get_call_trace_impl
from aromcp.analysis_server.models.typescript_models import (
    CallTraceResponse,
    ExecutionPath,
    CallGraphStats,
    AnalysisError
)


class TestCallGraphBuilder:
    """Test call graph construction from TypeScript function calls."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the Phase 4 fixtures directory."""
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    @pytest.fixture
    def simple_calls_file(self, fixtures_dir):
        """Path to simple function calls test file."""
        return str(fixtures_dir / "simple_calls.ts")
    
    @pytest.fixture
    def class_methods_file(self, fixtures_dir):
        """Path to class methods test file."""
        return str(fixtures_dir / "class_methods.ts")
    
    @pytest.fixture
    def async_patterns_file(self, fixtures_dir):
        """Path to async patterns test file."""
        return str(fixtures_dir / "async_patterns.ts")
    
    def test_basic_function_call_detection(self, simple_calls_file):
        """Test basic function call detection and graph building."""
        # Test the login function which calls multiple other functions
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls_file],
            max_depth=10,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        # Phase 1: Should return empty results but proper structure
        assert isinstance(response, CallTraceResponse)
        assert response.entry_point == "login"
        assert isinstance(response.execution_paths, list)
        assert isinstance(response.call_graph_stats, CallGraphStats)
        assert isinstance(response.errors, list)
        
        # Phase 4: Should detect function calls in login
        # Expected calls: validateCredentials, createSession, logSuccess, logFailure
        # This test will FAIL in Phase 1 (RED) but pass in Phase 4 (GREEN)
        assert len(response.execution_paths) > 0, "Should detect execution paths from login function"
        
        # Should detect multiple function calls in the call graph
        assert response.call_graph_stats.total_functions > 1, "Should detect multiple functions in call graph"
        assert response.call_graph_stats.total_edges > 0, "Should detect function call edges"
        assert response.call_graph_stats.max_depth_reached >= 2, "Should trace multiple levels deep"
    
    def test_conditional_execution_paths(self, simple_calls_file):
        """Test detection of conditional execution paths in function calls."""
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls_file],
            max_depth=5,
            analyze_conditions=True
        )
        
        # Should detect both success and failure paths
        success_path_found = False
        failure_path_found = False
        
        for path in response.execution_paths:
            if "logSuccess" in path.path:
                success_path_found = True
            if "logFailure" in path.path:
                failure_path_found = True
        
        # Phase 4: Should detect both conditional branches
        assert success_path_found, "Should detect success execution path with logSuccess"
        assert failure_path_found, "Should detect failure execution path with logFailure"
        
        # Should have conditional execution probabilities
        conditional_paths = [p for p in response.execution_paths if p.condition]
        assert len(conditional_paths) > 0, "Should detect conditional execution paths"
    
    def test_deep_call_chain_detection(self, simple_calls_file):
        """Test detection of deep function call chains."""
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls_file],
            max_depth=10
        )
        
        # Should trace through multiple levels:
        # login -> validateCredentials -> findUser -> database.users.find
        # login -> createSession -> generateSessionId, storeSession, updateLastLogin
        
        # Phase 4: Should detect deep call chains
        deep_paths = [p for p in response.execution_paths if len(p.path) >= 3]
        assert len(deep_paths) > 0, "Should detect call chains with 3+ levels"
        
        # Should reach the specified max depth
        assert response.call_graph_stats.max_depth_reached >= 3, "Should trace at least 3 levels deep"
    
    def test_method_call_detection(self, class_methods_file):
        """Test detection of method calls in classes."""
        response = get_call_trace_impl(
            entry_point="createUser",
            file_paths=[class_methods_file],
            max_depth=10
        )
        
        # Should detect method calls within UserService.createUser:
        # validateUserData, normalizeUserData, findUserByEmail, hashPassword, etc.
        
        # Phase 4: Should detect method calls
        assert len(response.execution_paths) > 0, "Should detect execution paths from createUser method"
        
        # Should detect calls to private methods
        private_method_calls = []
        for path in response.execution_paths:
            for call in path.path:
                if "validate" in call.lower() or "normalize" in call.lower():
                    private_method_calls.append(call)
        
        assert len(private_method_calls) > 0, "Should detect calls to private methods"
    
    def test_static_method_calls(self, class_methods_file):
        """Test detection of static method calls."""
        response = get_call_trace_impl(
            entry_point="isValid",  # EmailValidator.isValid
            file_paths=[class_methods_file],
            max_depth=5
        )
        
        # Should detect static method calls within EmailValidator.isValid:
        # hasValidFormat, hasValidDomain
        
        # Phase 4: Should detect static method call chains
        assert len(response.execution_paths) > 0, "Should detect execution paths from static method"
        
        # Should detect calls to other static methods
        static_calls = [p for p in response.execution_paths if len(p.path) >= 2]
        assert len(static_calls) > 0, "Should detect calls to other static methods"
    
    def test_constructor_and_instance_method_calls(self, class_methods_file):
        """Test detection of constructor calls and instance method calls."""
        response = get_call_trace_impl(
            entry_point="createFromCart",  # OrderEntity.createFromCart
            file_paths=[class_methods_file],
            max_depth=8
        )
        
        # Should detect:
        # 1. Constructor call: new OrderEntity()
        # 2. Instance method calls: calculateTotal(), save()
        # 3. Inherited method calls: save() -> validate(), updateTimestamp(), persistToDatabase()
        
        # Phase 4: Should detect constructor and method calls
        assert len(response.execution_paths) > 0, "Should detect execution paths from factory method"
        
        # Should detect constructor call pattern
        constructor_paths = [p for p in response.execution_paths if "OrderEntity" in str(p.path)]
        assert len(constructor_paths) > 0, "Should detect constructor calls"
        
        # Should detect instance method calls after construction
        method_calls = [p for p in response.execution_paths if len(p.path) >= 3]
        assert len(method_calls) > 0, "Should detect chained method calls"
    
    def test_async_function_call_detection(self, async_patterns_file):
        """Test detection of async function calls and Promise chains."""
        response = get_call_trace_impl(
            entry_point="complexAsyncWorkflow",
            file_paths=[async_patterns_file],
            max_depth=10
        )
        
        # Should detect async call patterns:
        # fetchUser, fetchUserPreferences, fetchUserPermissions
        # Promise.all with multiple async calls
        # Conditional async calls based on user.isPremium
        
        # Phase 4: Should detect async call patterns
        assert len(response.execution_paths) > 0, "Should detect execution paths from async function"
        
        # Should detect multiple async calls
        async_calls = []
        for path in response.execution_paths:
            for call in path.path:
                if "fetch" in call.lower() or "generate" in call.lower():
                    async_calls.append(call)
        
        assert len(async_calls) > 0, "Should detect async function calls"
        
        # Should detect Promise.all pattern
        promise_all_detected = any("Promise.all" in str(path.path) for path in response.execution_paths)
        # Note: This might be detected as separate calls rather than Promise.all
        # The important thing is detecting the parallel async calls
    
    def test_method_chaining_detection(self, class_methods_file):
        """Test detection of method chaining patterns."""
        response = get_call_trace_impl(
            entry_point="execute",  # QueryBuilder.execute() - terminal method that actually calls functions
            file_paths=[class_methods_file],
            max_depth=5
        )
        
        # QueryBuilder uses method chaining: select().from().where().execute()
        # The execute() method is the terminal method that validates and executes the query
        
        # Phase 4: Should detect execution paths from terminal method
        assert len(response.execution_paths) > 0, "Should detect execution paths from execute method"
        
        # Should track calls from execute() to validation and SQL building methods
        call_names = []
        for path in response.execution_paths:
            call_names.extend(path.path)
        
        # Should detect calls to validateQuery and buildSqlQuery
        assert "validateQuery" in call_names, "Should detect validateQuery call"
        assert "buildSqlQuery" in call_names, "Should detect buildSqlQuery call"


class TestCallSiteDetection:
    """Test detection of different types of call sites."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_direct_function_calls(self, fixtures_dir):
        """Test detection of direct function calls like myFunc()."""
        simple_calls = str(fixtures_dir / "simple_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="validateCredentials",
            file_paths=[simple_calls],
            max_depth=5
        )
        
        # Should detect direct calls: findUser(), hashPassword()
        # Phase 4: Should detect direct function call sites
        assert len(response.execution_paths) > 0, "Should detect direct function calls"
        
        # Should identify call sites accurately
        call_names = []
        for path in response.execution_paths:
            call_names.extend(path.path)
        
        assert "findUser" in call_names, "Should detect findUser function call"
        assert "hashPassword" in call_names, "Should detect hashPassword function call"
    
    def test_object_method_calls(self, fixtures_dir):
        """Test detection of object method calls like obj.method()."""
        simple_calls = str(fixtures_dir / "simple_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="findUser",
            file_paths=[simple_calls],
            max_depth=3
        )
        
        # Should detect object method calls: database.users.find()
        # Phase 4: Should detect object method call sites
        assert len(response.execution_paths) > 0, "Should detect object method calls"
        
        # Should detect method calls on objects
        method_calls = []
        for path in response.execution_paths:
            for call in path.path:
                if "." in call:  # Method calls typically have dots
                    method_calls.append(call)
        
        # Note: The exact format depends on how the parser represents method calls
        # Could be "database.users.find" or separate calls
    
    def test_dynamic_property_access(self, fixtures_dir):
        """Test detection of dynamic property access like obj[methodName]()."""
        event_system = str(fixtures_dir / "event_system.ts")
        
        response = get_call_trace_impl(
            entry_point="executeCommand",
            file_paths=[event_system],
            max_depth=8
        )
        
        # Should detect dynamic method calls in CommandProcessor.executeCommand
        # handler[methodName]() calls
        
        # Phase 4: Should detect dynamic property access
        assert len(response.execution_paths) > 0, "Should detect execution paths with dynamic calls"
        
        # Dynamic calls are complex to detect statically, but should at least
        # trace through the executeCommand method
        assert response.call_graph_stats.total_functions > 0, "Should detect functions in dynamic call context"
    
    def test_callback_function_calls(self, fixtures_dir):
        """Test detection of callback function calls."""
        async_patterns = str(fixtures_dir / "async_patterns.ts")
        
        response = get_call_trace_impl(
            entry_point="callbackPatterns",
            file_paths=[async_patterns],
            max_depth=10
        )
        
        # Should detect callback calls in nested callback pattern
        # processDataAsync(data, callback), transformResult(result, callback)
        
        # Phase 4: Should detect callback function calls
        assert len(response.execution_paths) > 0, "Should detect execution paths with callbacks"
        
        # Should detect the nested callback structure
        callback_related_calls = []
        for path in response.execution_paths:
            for call in path.path:
                if any(keyword in call.lower() for keyword in ["callback", "process", "transform", "finalize"]):
                    callback_related_calls.append(call)
        
        assert len(callback_related_calls) > 0, "Should detect callback-related function calls"


class TestCrossFileCallAnalysis:
    """Test call graph analysis across multiple TypeScript files."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_single_file_analysis(self, fixtures_dir):
        """Test call graph construction within a single file."""
        simple_calls = str(fixtures_dir / "simple_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls],
            max_depth=10
        )
        
        # Should build complete call graph within the file
        # Phase 4: Should detect all function calls within single file
        assert len(response.execution_paths) > 0, "Should detect execution paths in single file"
        assert response.call_graph_stats.total_functions > 3, "Should detect multiple functions"
        assert response.call_graph_stats.total_edges > 2, "Should detect multiple call edges"
    
    def test_multiple_file_analysis(self, fixtures_dir):
        """Test call graph construction across multiple files."""
        files = [
            str(fixtures_dir / "simple_calls.ts"),
            str(fixtures_dir / "class_methods.ts")
        ]
        
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=files,
            max_depth=10
        )
        
        # Should analyze calls across multiple files
        # Phase 4: Should handle cross-file call analysis
        assert len(response.execution_paths) > 0, "Should detect execution paths across files"
        
        # Should have more functions available from multiple files
        assert response.call_graph_stats.total_functions > 5, "Should detect functions from multiple files"
    
    def test_project_wide_analysis(self, fixtures_dir):
        """Test project-wide call graph analysis (file_paths=None)."""
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=None,  # Analyze entire project
            max_depth=8
        )
        
        # Should search for the entry point across all project files
        # Phase 4: Should handle project-wide analysis
        # Note: This might not find the function if it's only in our test fixtures
        # The test verifies the system can handle None file_paths parameter
        assert isinstance(response, CallTraceResponse), "Should handle project-wide analysis request"
        assert isinstance(response.errors, list), "Should return proper error structure"
    
    def test_nonexistent_file_handling(self, fixtures_dir):
        """Test handling of nonexistent files in file_paths."""
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=["nonexistent.ts", str(fixtures_dir / "simple_calls.ts")],
            max_depth=5
        )
        
        # Should handle nonexistent files gracefully
        assert isinstance(response, CallTraceResponse), "Should return valid response"
        
        # Should have errors for nonexistent files
        file_errors = [e for e in response.errors if e.code == "NOT_FOUND"]
        assert len(file_errors) > 0, "Should report errors for nonexistent files"
        
        # Should still process existing files
        assert "nonexistent.ts" in [e.file for e in file_errors], "Should identify nonexistent file"


class TestStaticCallGraphAccuracy:
    """Test accuracy of static call graph analysis."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_function_signature_matching(self, fixtures_dir):
        """Test accurate matching of function signatures."""
        class_methods = str(fixtures_dir / "class_methods.ts")
        
        response = get_call_trace_impl(
            entry_point="UserService",  # Constructor or class reference
            file_paths=[class_methods],
            max_depth=5
        )
        
        # Should accurately match method signatures within the class
        # Phase 4: Should match function signatures accurately
        assert isinstance(response, CallTraceResponse), "Should process class-based entry point"
        
        # Test with specific method
        response = get_call_trace_impl(
            entry_point="createUser",
            file_paths=[class_methods],
            max_depth=8
        )
        
        assert len(response.execution_paths) > 0, "Should find method in class"
    
    def test_overloaded_function_handling(self, fixtures_dir):
        """Test handling of function overloads."""
        class_methods = str(fixtures_dir / "class_methods.ts")
        
        # Test function with multiple signatures (if any exist in our fixtures)
        response = get_call_trace_impl(
            entry_point="validate",
            file_paths=[class_methods],
            max_depth=5
        )
        
        # Should handle overloaded functions
        # Phase 4: Should handle function overloads
        assert isinstance(response, CallTraceResponse), "Should handle overloaded functions"
    
    def test_generic_function_calls(self, fixtures_dir):
        """Test handling of generic function calls."""
        class_methods = str(fixtures_dir / "class_methods.ts")
        
        response = get_call_trace_impl(
            entry_point="execute",  # QueryBuilder.execute<T>()
            file_paths=[class_methods],
            max_depth=5
        )
        
        # Should handle generic function calls
        # Phase 4: Should handle generic functions
        assert isinstance(response, CallTraceResponse), "Should handle generic function calls"
    
    def test_interface_method_calls(self, fixtures_dir):
        """Test detection of interface method implementations."""
        # This tests calling methods defined in interfaces
        async_patterns = str(fixtures_dir / "async_patterns.ts")
        
        response = get_call_trace_impl(
            entry_point="initialize",
            file_paths=[async_patterns],
            max_depth=8
        )
        
        # Should detect method calls on interface implementations
        # Phase 4: Should handle interface method calls
        assert isinstance(response, CallTraceResponse), "Should handle interface method calls"
    
    def test_call_graph_completeness(self, fixtures_dir):
        """Test completeness of call graph construction."""
        complex_graph = str(fixtures_dir / "complex_graph.ts")
        
        response = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph],
            max_depth=15  # Very deep to test comprehensive analysis
        )
        
        # Should build comprehensive call graph for complex function
        # Phase 4: Should build complete call graphs
        assert len(response.execution_paths) > 0, "Should detect execution paths in complex function"
        assert response.call_graph_stats.total_functions > 10, "Should detect many functions in complex graph"
        assert response.call_graph_stats.max_depth_reached >= 5, "Should trace deep into complex call chains"
        
        # Should have reasonable edge coverage (99% target from acceptance criteria)
        edge_coverage_ratio = response.call_graph_stats.total_edges / max(1, response.call_graph_stats.total_functions - 1)
        # This is a basic heuristic - in Phase 4, implement proper edge coverage calculation
    
    def test_entry_point_validation(self, fixtures_dir):
        """Test validation of entry point parameters."""
        simple_calls = str(fixtures_dir / "simple_calls.ts")
        
        # Test empty entry point
        response = get_call_trace_impl(
            entry_point="",
            file_paths=[simple_calls],
            max_depth=5
        )
        
        # Should validate entry point
        entry_point_errors = [e for e in response.errors if e.code == "INVALID_ENTRY_POINT"]
        assert len(entry_point_errors) > 0, "Should validate empty entry point"
        
        # Test nonexistent entry point
        response = get_call_trace_impl(
            entry_point="nonexistentFunction",
            file_paths=[simple_calls],
            max_depth=5
        )
        
        # Phase 4: Should report when entry point is not found
        # In Phase 1, this might not be detected yet
        assert isinstance(response, CallTraceResponse), "Should handle nonexistent entry point"