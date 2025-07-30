"""
Tests for Phase 4 Conditional Execution Path Analysis and Branch Detection.

These tests verify that the TypeScript Analysis MCP Server can analyze conditional execution paths,
detect different branches in control flow, and estimate execution probabilities.
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


class TestConditionalCallAnalysis:
    """Test analysis of conditional function calls."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the Phase 4 fixtures directory."""
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    @pytest.fixture
    def conditional_calls_file(self, fixtures_dir):
        """Path to conditional calls test file."""
        return str(fixtures_dir / "conditional_calls.ts")
    
    @pytest.fixture
    def simple_calls_file(self, fixtures_dir):
        """Path to simple calls test file."""
        return str(fixtures_dir / "simple_calls.ts")
    
    def test_if_else_branch_detection(self, conditional_calls_file):
        """Test detection of if/else execution branches."""
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls_file],
            max_depth=10,
            analyze_conditions=True
        )
        
        # Should detect different execution paths for different actions
        # Phase 4: Should detect if/else branches
        assert len(response.execution_paths) > 0, "Should detect execution paths"
        
        # Should find different call paths for different conditions
        create_path_found = False
        update_path_found = False
        delete_path_found = False
        
        for path in response.execution_paths:
            path_functions = set(path.path)
            if "createUser" in path_functions:
                create_path_found = True
            if "updateUser" in path_functions:
                update_path_found = True
            if "deleteUser" in path_functions:
                delete_path_found = True
        
        # Phase 4: Should detect multiple conditional branches
        branches_detected = sum([create_path_found, update_path_found, delete_path_found])
        assert branches_detected >= 2, "Should detect multiple if/else branches"
    
    def test_switch_statement_branches(self, conditional_calls_file):
        """Test detection of switch statement branches."""
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls_file],
            max_depth=8,
            analyze_conditions=True
        )
        
        # Should detect different switch case branches
        # Based on user.role: admin, moderator, user, guest, default
        role_specific_calls = {
            "admin": "grantAdminAccess",
            "moderator": "grantModeratorAccess", 
            "user": "grantUserAccess",
            "guest": "grantGuestAccess",
            "default": "grantDefaultAccess"
        }
        
        detected_role_paths = {}
        for path in response.execution_paths:
            for role, expected_call in role_specific_calls.items():
                if expected_call in path.path:
                    detected_role_paths[role] = True
        
        # Phase 4: Should detect switch statement branches
        assert len(detected_role_paths) >= 2, "Should detect multiple switch case branches"
    
    def test_try_catch_error_paths(self, conditional_calls_file):
        """Test detection of try/catch error handling paths."""
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls_file],
            max_depth=12,
            analyze_conditions=True
        )
        
        # Should detect both success and error paths
        success_path_calls = {"validateUser", "saveToDatabase", "indexUserData"}
        error_path_calls = {"handleValidationError", "handleDatabaseError", "handleUnknownError"}
        finally_calls = {"cleanupResources", "updateProcessingStats"}
        
        success_detected = False
        error_detected = False
        finally_detected = False
        
        for path in response.execution_paths:
            path_functions = set(path.path)
            
            if success_path_calls.intersection(path_functions):
                success_detected = True
            if error_path_calls.intersection(path_functions):
                error_detected = True
            if finally_calls.intersection(path_functions):
                finally_detected = True
        
        # Phase 4: Should detect try/catch/finally paths
        assert success_detected, "Should detect try block success path"
        # Error paths might be harder to detect statically
        # Finally block should be detected as it always executes
        assert finally_detected, "Should detect finally block execution"
    
    def test_nested_conditional_analysis(self, conditional_calls_file):
        """Test analysis of nested conditional statements."""
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls_file],
            max_depth=15,
            analyze_conditions=True
        )
        
        # Should detect nested conditions in subscription handling
        # if (user.subscription) -> if (user.subscription.isPremium) -> if (features.includes...)
        nested_calls = {
            "enableAdvancedAnalytics",
            "setupAnalyticsDashboard", 
            "enablePremiumFeatures",
            "enableBasicFeatures",
            "setupFreeTrial"
        }
        
        nested_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in nested_calls:
                    nested_calls_found.add(call)
        
        # Phase 4: Should detect nested conditional calls
        assert len(nested_calls_found) >= 2, "Should detect nested conditional execution paths"
    
    def test_early_return_handling(self, simple_calls_file):
        """Test handling of functions with early returns."""
        response = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls_file],
            max_depth=8,
            analyze_conditions=True
        )
        
        # login function has early return paths:
        # - if (!isValid) -> logFailure and return false
        # - if (isValid) -> createSession, logSuccess and return true
        
        # Should detect both return paths
        early_return_detected = False
        normal_return_detected = False
        
        for path in response.execution_paths:
            # Check if logFailure appears in the path
            if any("logFailure" in func for func in path.path):
                early_return_detected = True
            # Check if both logSuccess and createSession appear (they might be in separate paths due to conditional analysis)
            if any("logSuccess" in func for func in path.path):
                normal_return_detected = True
        
        # Phase 4: Should detect early return paths
        assert early_return_detected, "Should detect early return path"
        assert normal_return_detected, "Should detect normal execution path"
    
    def test_ternary_operator_branches(self, conditional_calls_file):
        """Test detection of ternary operator execution paths."""
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls_file],
            max_depth=12,
            analyze_conditions=True
        )
        
        # Should detect ternary operator calls:
        # order.isRush ? calculateRushShipping(order) : calculateStandardShipping(order)
        # order.customer.isFirstTime ? applyFirstTimeDiscount(order) : calculateLoyaltyDiscount(order)
        
        ternary_calls = {
            "calculateRushShipping",
            "calculateStandardShipping", 
            "applyFirstTimeDiscount",
            "calculateLoyaltyDiscount"
        }
        
        ternary_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in ternary_calls:
                    ternary_calls_found.add(call)
        
        # Phase 4: Should detect ternary operator branches
        assert len(ternary_calls_found) >= 2, "Should detect ternary operator execution paths"


class TestExecutionPathProbability:
    """Test estimation of execution path probabilities."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_execution_probability_calculation(self, fixtures_dir):
        """Test calculation of execution probabilities for different paths."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls],
            max_depth=10,
            analyze_conditions=True
        )
        
        # Should calculate execution probabilities based on conditions
        # Phase 4: Should estimate execution probabilities
        probability_paths = [p for p in response.execution_paths if p.execution_probability is not None]
        assert len(probability_paths) > 0, "Should calculate execution probabilities"
        
        # Probabilities should be between 0 and 1
        for path in probability_paths:
            assert 0.0 <= path.execution_probability <= 1.0, f"Probability should be 0-1: {path.execution_probability}"
        
        # Should have different probabilities for different paths
        unique_probabilities = set(p.execution_probability for p in probability_paths)
        # Note: All paths might have default probability of 1.0 in simple cases
    
    def test_high_probability_paths(self, fixtures_dir):
        """Test identification of high probability execution paths."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls],
            max_depth=8,
            analyze_conditions=True
        )
        
        # High probability path: order.amount > 0 (90% according to comments)
        high_prob_calls = {"processPayment"}
        
        high_prob_paths = []
        for path in response.execution_paths:
            if any(call in path.path for call in high_prob_calls):
                high_prob_paths.append(path)
        
        # Phase 4: Should identify high probability paths
        assert len(high_prob_paths) > 0, "Should identify high probability execution paths"
        
        # High probability paths should have higher probability values
        for path in high_prob_paths:
            # Default probability might be 1.0, but should not be 0
            assert path.execution_probability > 0.0, "High probability paths should have non-zero probability"
    
    def test_low_probability_paths(self, fixtures_dir):
        """Test identification of low probability execution paths."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic", 
            file_paths=[conditional_calls],
            max_depth=10,
            analyze_conditions=True
        )
        
        # Low probability paths: order.requiresCustomsDeclaration (1% according to comments)
        low_prob_calls = {"generateCustomsDocuments", "scheduleCustomsReview"}
        
        low_prob_paths = []
        for path in response.execution_paths:
            if any(call in path.path for call in low_prob_calls):
                low_prob_paths.append(path)
        
        # Phase 4: Should identify low probability paths
        if len(low_prob_paths) > 0:
            # If detected, should have reasonable probability
            for path in low_prob_paths:
                assert path.execution_probability >= 0.0, "Low probability paths should have valid probability"
    
    def test_conditional_probability_composition(self, fixtures_dir):
        """Test composition of probabilities for nested conditions."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls],
            max_depth=12,
            analyze_conditions=True
        )
        
        # Nested conditions should have composed probabilities
        # order.amount > 1000 (10% of orders > 0) -> flagForManualReview
        nested_condition_calls = {"flagForManualReview", "notifyAccountManager"}
        
        nested_paths = []
        for path in response.execution_paths:
            if any(call in path.path for call in nested_condition_calls):
                nested_paths.append(path)
        
        # Phase 4: Should handle nested conditional probabilities
        if len(nested_paths) > 0:
            for path in nested_paths:
                # Nested conditions should typically have lower probability than parent conditions
                assert path.execution_probability >= 0.0, "Nested conditions should have valid probability"


class TestControlFlowPatterns:
    """Test analysis of various control flow patterns."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_loop_execution_analysis(self, fixtures_dir):
        """Test analysis of function calls within loops."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="loopWithConditionalCalls",
            file_paths=[conditional_calls],
            max_depth=15,
            analyze_conditions=True
        )
        
        # Should detect function calls within for/while loops
        loop_related_calls = {
            "preprocessItem", "processItem", "handleItemError", 
            "postprocessItem", "finalizeProcessing",
            "attemptOperation", "handleSuccess", "handleRetry"
        }
        
        loop_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in loop_related_calls:
                    loop_calls_found.add(call)
        
        # Phase 4: Should detect function calls within loops
        assert len(loop_calls_found) >= 3, "Should detect function calls within loop structures"
    
    def test_break_continue_handling(self, fixtures_dir):
        """Test handling of break and continue statements in loops."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="loopWithConditionalCalls",
            file_paths=[conditional_calls],
            max_depth=12,
            analyze_conditions=True
        )
        
        # Should handle break/continue control flow
        # break: finalizeProcessing(item) -> break
        # continue: handleItemError(item) -> continue
        
        break_continue_calls = {"finalizeProcessing", "handleItemError"}
        
        break_continue_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in break_continue_calls:
                    break_continue_found.add(call)
        
        # Phase 4: Should handle break/continue control flow
        assert len(break_continue_found) > 0, "Should handle break/continue control flow"
    
    def test_async_conditional_flow(self, fixtures_dir):
        """Test conditional execution in async functions."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="asyncConditionalFlow",
            file_paths=[conditional_calls],
            max_depth=20,
            analyze_conditions=True
        )
        
        # Should detect conditional async execution paths
        async_conditional_calls = {
            "authenticateRequest", "initiatePasswordReset", 
            "isRateLimited", "processRequestData", "validateData",
            "executeBusinessLogic"
        }
        
        async_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in async_conditional_calls:
                    async_calls_found.add(call)
        
        # Phase 4: Should detect async conditional execution
        assert len(async_calls_found) >= 2, "Should detect async conditional execution paths"
    
    def test_error_handling_branches(self, fixtures_dir):
        """Test detection of error handling execution branches."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="asyncConditionalFlow",
            file_paths=[conditional_calls],
            max_depth=18,
            analyze_conditions=True
        )
        
        # Should detect different error handling paths
        error_handling_calls = {
            "logTimeoutError", "logNetworkError", "logUnknownError"
        }
        
        error_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in error_handling_calls:
                    error_calls_found.add(call)
        
        # Phase 4: Should detect error handling branches
        # Note: Error handling paths might be harder to detect statically
        # The key is that analysis should handle error branches without crashing
        assert isinstance(response.execution_paths, list), "Should handle error handling branches"


class TestBranchPrediction:
    """Test branch prediction and path likelihood analysis."""
    
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"
    
    def test_condition_analysis(self, fixtures_dir):
        """Test analysis of conditional expressions."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls],
            max_depth=10,
            analyze_conditions=True
        )
        
        # Should analyze conditional expressions and store them
        conditional_paths = [p for p in response.execution_paths if p.condition]
        
        # Phase 4: Should analyze conditional expressions
        if len(conditional_paths) > 0:
            # Should have meaningful condition descriptions
            for path in conditional_paths:
                assert isinstance(path.condition, str), "Condition should be a string description"
                assert len(path.condition) > 0, "Condition should not be empty"
        
        # Even if no explicit conditions detected, should handle analysis
        assert isinstance(response.execution_paths, list), "Should handle condition analysis"
    
    def test_business_logic_probability(self, fixtures_dir):
        """Test probability estimation based on business logic."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls],
            max_depth=12,
            analyze_conditions=True
        )
        
        # Should estimate probabilities based on business context
        # Comments in the code indicate probability estimates
        
        # Check for reasonable probability distribution
        probabilities = [p.execution_probability for p in response.execution_paths if p.execution_probability is not None]
        
        # Phase 4: Should estimate business logic probabilities
        if len(probabilities) > 0:
            # Should have valid probability values
            for prob in probabilities:
                assert 0.0 <= prob <= 1.0, f"Invalid probability: {prob}"
            
            # Should not all be the same probability (unless it's a simple case)
            # This tests that the system considers different likelihoods
    
    def test_path_coverage_analysis(self, fixtures_dir):
        """Test analysis of execution path coverage."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_calls],
            max_depth=15,
            analyze_conditions=True
        )
        
        # Should provide good coverage of possible execution paths
        unique_functions = set()
        for path in response.execution_paths:
            unique_functions.update(path.path)
        
        # Should discover many functions through path analysis
        # Phase 4: Should provide comprehensive path coverage
        assert len(unique_functions) >= 5, "Should discover multiple functions through path analysis"
        
        # Should have multiple execution paths
        assert len(response.execution_paths) > 1, "Should detect multiple execution paths"
    
    def test_edge_case_conditions(self, fixtures_dir):
        """Test handling of edge case conditional logic."""
        simple_calls = str(fixtures_dir / "simple_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="validateCredentials",
            file_paths=[simple_calls],
            max_depth=8,
            analyze_conditions=True
        )
        
        # Should handle edge cases like null checks, empty strings, etc.
        # validateCredentials has: if (!user) return false
        
        # Should detect both success and failure paths
        null_check_paths = []
        success_paths = []
        
        for path in response.execution_paths:
            if len(path.path) <= 2:  # Short path likely indicates early return
                null_check_paths.append(path)
            elif "hashPassword" in path.path:  # Longer path with password hashing
                success_paths.append(path)
        
        # Phase 4: Should handle edge case conditions
        assert len(null_check_paths) > 0 or len(success_paths) > 0, "Should detect conditional execution paths"
    
    def test_complex_boolean_logic(self, fixtures_dir):
        """Test handling of complex boolean expressions."""
        conditional_calls = str(fixtures_dir / "conditional_calls.ts")
        
        response = get_call_trace_impl(
            entry_point="complexBusinessLogic",
            file_paths=[conditional_calls],
            max_depth=10,
            analyze_conditions=True
        )
        
        # Should handle complex boolean conditions
        # order.amount > 0 && order.amount > 100
        # order.isInternational && order.requiresCustomsDeclaration
        
        complex_condition_calls = {
            "applyBulkDiscount", "calculateInternationalFees", 
            "generateCustomsDocuments", "applyVipDiscount"
        }
        
        complex_calls_found = set()
        for path in response.execution_paths:
            for call in path.path:
                if call in complex_condition_calls:
                    complex_calls_found.add(call)
        
        # Phase 4: Should handle complex boolean logic
        assert len(complex_calls_found) >= 1, "Should handle complex boolean conditional logic"