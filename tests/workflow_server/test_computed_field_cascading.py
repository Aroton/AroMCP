"""
Comprehensive cascading computed field testing for state management.

Covers missing acceptance criteria:
- AC-SM-014: Computed values are recalculated when dependencies change
- AC-SM-016: Cascading updates for dependent computed fields work

Focus: Cascading computed field dependencies and recalculation
Pillar: State Management
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List
import json

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowInstance
from aromcp.workflow_server.state.concurrent import ConcurrentStateManager


class TestComputedFieldCascading:
    """Test cascading computed field dependencies and recalculation logic."""

    @pytest.fixture
    def mock_js_evaluator(self):
        """Mock JavaScript expression evaluator."""
        evaluator = Mock()
        # Reset call count for each test
        self._call_count = 0  # Track calls
        # Default to simple string concatenation for testing
        evaluator.execute = Mock(side_effect=self._mock_js_evaluation)
        return evaluator

    def _mock_js_evaluation(self, expression: str, context: Dict[str, Any]) -> Any:
        """Mock JavaScript evaluation with realistic computed field logic."""
        self._call_count += 1
        call_id = self._call_count
        
        # Match exact expressions instead of substring matching
        if expression == "this.firstName + ' ' + this.lastName":
            # fullName expression
            first = context.get("firstName", "")
            last = context.get("lastName", "")
            result = f"{first} {last}"
            return result
        elif expression == "this.fullName + ' (' + this.email + ')'":
            # displayName expression
            full_name = context.get("fullName", "")
            email = context.get("email", "")
            result = f"{full_name} ({email})" if email else full_name
            return result
        elif expression == "this.firstName && this.lastName && this.email":
            # isComplete expression
            result = bool(context.get("firstName") and context.get("lastName") and context.get("email"))
            return result
        elif expression == "this.isComplete ? 'Complete' : 'Incomplete'":
            # status expression
            result = "Complete" if context.get("isComplete") else "Incomplete"
            return result
        elif expression == "this.status + ': ' + this.displayName":
            # summary expression
            status = context.get("status", "Unknown")
            display = context.get("displayName", "No Name")
            result = f"{status}: {display}"
            return result
        elif expression == "this.score >= 90 ? 'Excellent' : this.score >= 70 ? 'Good' : 'Needs Improvement'":
            # scoreCategory expression
            score = context.get("score", 0)
            if score >= 90:
                return "Excellent"
            elif score >= 70:
                return "Good"
            else:
                return "Needs Improvement"
        elif expression == "this.scoreCategory + ' (' + this.score + '/100)'":
            # finalGrade expression
            category = context.get("scoreCategory", "Unknown")
            score = context.get("score", 0)
            return f"{category} ({score}/100)"
        elif expression == "this.score >= 60 ? 'PASS' : 'FAIL'":
            # passStatus expression
            score = context.get("score", 0)
            return "PASS" if score >= 60 else "FAIL"
        elif expression == "this.passStatus === 'PASS' && this.attendanceRate >= 0.8":
            # canGraduate expression
            pass_status = context.get("passStatus", "")
            attendance = context.get("attendanceRate", 0)
            return pass_status == "PASS" and attendance >= 0.8
        elif expression == "this.finalGrade + ' - ' + (this.canGraduate ? 'Eligible' : 'Not Eligible')":
            # academicSummary expression
            final_grade = context.get("finalGrade", "Unknown")
            can_graduate = context.get("canGraduate", False)
            eligibility = "Eligible" if can_graduate else "Not Eligible"
            return f"{final_grade} - {eligibility}"
        else:
            # Default evaluation for simple expressions
            try:
                return eval(expression.replace("this.", ""), {"__builtins__": {}}, context)
            except:
                return expression

    @pytest.fixture
    def state_manager(self, mock_js_evaluator):
        """Create state manager with mocked JavaScript evaluator."""
        with patch('aromcp.workflow_server.state.manager.TransformationEngine', return_value=mock_js_evaluator):
            manager = StateManager()
            return manager

    @pytest.fixture
    def cascading_state_schema(self):
        """State schema with cascading computed field dependencies."""
        return {
            "computed": {
                # Level 1: Direct dependency on inputs/state
                "fullName": {
                    "expression": "this.firstName + ' ' + this.lastName",
                    "dependencies": ["firstName", "lastName"]
                },
                "isComplete": {
                    "expression": "this.firstName && this.lastName && this.email",
                    "dependencies": ["firstName", "lastName", "email"]
                },
                # Level 2: Depends on Level 1 computed fields
                "displayName": {
                    "expression": "this.fullName + ' (' + this.email + ')'",
                    "dependencies": ["fullName", "email"]
                },
                "status": {
                    "expression": "this.isComplete ? 'Complete' : 'Incomplete'",
                    "dependencies": ["isComplete"]
                },
                # Level 3: Depends on Level 2 computed fields
                "summary": {
                    "expression": "this.status + ': ' + this.displayName",
                    "dependencies": ["status", "displayName"]
                }
            }
        }

    @pytest.fixture
    def multi_level_schema(self):
        """State schema with deep cascading dependencies."""
        return {
            "computed": {
                # Level 1: Base calculations
                "scoreCategory": {
                    "expression": "this.score >= 90 ? 'Excellent' : this.score >= 70 ? 'Good' : 'Needs Improvement'",
                    "dependencies": ["score"]
                },
                # Level 2: Depends on Level 1
                "finalGrade": {
                    "expression": "this.scoreCategory + ' (' + this.score + '/100)'",
                    "dependencies": ["scoreCategory", "score"]
                },
                # Also Level 1: Independent calculation
                "passStatus": {
                    "expression": "this.score >= 60 ? 'PASS' : 'FAIL'",
                    "dependencies": ["score"]
                },
                # Level 2: Depends on passStatus
                "canGraduate": {
                    "expression": "this.passStatus === 'PASS' && this.attendanceRate >= 0.8",
                    "dependencies": ["passStatus", "attendanceRate"]
                },
                # Level 3: Depends on Level 2 fields
                "academicSummary": {
                    "expression": "this.finalGrade + ' - ' + (this.canGraduate ? 'Eligible' : 'Not Eligible')",
                    "dependencies": ["finalGrade", "canGraduate"]
                }
            }
        }

    def test_single_dependency_change_triggers_cascading_updates(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-014: Computed values are recalculated when dependencies change
        Focus: Single input change triggers multiple computed field updates
        """
        # Initialize state with schema
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        # Get initial computed values
        initial_state = state_manager.get_flattened_state()
        assert initial_state["fullName"] == "John Doe"
        assert initial_state["displayName"] == "John Doe (john@example.com)"
        assert initial_state["isComplete"] == True
        assert initial_state["status"] == "Complete"
        assert initial_state["summary"] == "Complete: John Doe (john@example.com)"

        # Change firstName - should trigger cascading updates
        state_manager.update_state([{
            "path": "state.firstName",
            "operation": "set",
            "value": "Jane"
        }])

        # Verify cascading updates occurred
        updated_state = state_manager.get_flattened_state()
        assert updated_state["firstName"] == "Jane"  # Direct change
        assert updated_state["fullName"] == "Jane Doe"  # Level 1 cascade
        assert updated_state["displayName"] == "Jane Doe (john@example.com)"  # Level 2 cascade
        assert updated_state["summary"] == "Complete: Jane Doe (john@example.com)"  # Level 3 cascade
        
        # Status should remain the same since all required fields are still present
        assert updated_state["isComplete"] == True
        assert updated_state["status"] == "Complete"

    def test_dependency_removal_cascades_correctly(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-016: Cascading updates for dependent computed fields work
        Focus: Removing a dependency cascades through all dependent fields
        """
        # Initialize complete state
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        # Remove email - should cascade through isComplete, status, displayName, summary
        state_manager.update_state([{
            "path": "state.email",
            "operation": "set", 
            "value": ""
        }])

        updated_state = state_manager.get_flattened_state()
        
        # Direct change
        assert updated_state["email"] == ""
        
        # Level 1 cascades
        assert updated_state["fullName"] == "John Doe"  # Unchanged, doesn't depend on email
        assert updated_state["isComplete"] == False  # Changed due to missing email
        
        # Level 2 cascades  
        assert updated_state["displayName"] == "John Doe"  # Changed, no email to show
        assert updated_state["status"] == "Incomplete"  # Changed due to isComplete change
        
        # Level 3 cascade
        assert updated_state["summary"] == "Incomplete: John Doe"  # Fully cascaded change

    def test_multiple_dependency_changes_optimize_recalculation(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-016: Cascading updates optimize for multiple simultaneous changes
        Focus: Multiple changes should trigger efficient single recalculation pass
        """
        # Initialize state
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        # Track recalculation calls
        recalculation_count = 0
        original_update_computed = state_manager._update_computed_fields
        
        def counting_update_computed(*args, **kwargs):
            nonlocal recalculation_count
            recalculation_count += 1
            return original_update_computed(*args, **kwargs)
            
        state_manager._update_computed_fields = counting_update_computed

        # Make multiple changes simultaneously
        state_manager.update_state([
            {"path": "state.firstName", "operation": "set", "value": "Jane"},
            {"path": "state.lastName", "operation": "set", "value": "Smith"},
            {"path": "state.email", "operation": "set", "value": "jane.smith@example.com"}
        ])

        # Should have triggered only one recalculation pass for efficiency
        assert recalculation_count == 1

        # Verify all cascading updates completed correctly
        final_state = state_manager.get_flattened_state()
        assert final_state["fullName"] == "Jane Smith"
        assert final_state["displayName"] == "Jane Smith (jane.smith@example.com)"
        assert final_state["isComplete"] == True
        assert final_state["status"] == "Complete"
        assert final_state["summary"] == "Complete: Jane Smith (jane.smith@example.com)"

    def test_deep_cascading_dependencies_five_levels(self, state_manager, multi_level_schema):
        """
        Test AC-SM-016: Deep cascading works through multiple dependency levels
        Focus: 5-level dependency chain updates correctly
        """
        # Initialize state with score-based schema
        state_manager.initialize_state(
            inputs={},
            default_state={"score": 85, "attendanceRate": 0.9},
            state_schema=multi_level_schema
        )

        # Get initial state - score of 85 should result in "Good" category
        initial_state = state_manager.get_flattened_state()
        assert initial_state["scoreCategory"] == "Good"  # Level 1
        assert initial_state["finalGrade"] == "Good (85/100)"  # Level 2
        assert initial_state["passStatus"] == "PASS"  # Level 1
        assert initial_state["canGraduate"] == True  # Level 2
        assert initial_state["academicSummary"] == "Good (85/100) - Eligible"  # Level 3

        # Change score to 95 - should cascade through all levels
        state_manager.update_state([{
            "path": "state.score",
            "operation": "set",
            "value": 95
        }])

        updated_state = state_manager.get_flattened_state()
        assert updated_state["score"] == 95  # Direct change
        assert updated_state["scoreCategory"] == "Excellent"  # Level 1 cascade
        assert updated_state["finalGrade"] == "Excellent (95/100)"  # Level 2 cascade
        assert updated_state["passStatus"] == "PASS"  # Level 1, unchanged
        assert updated_state["canGraduate"] == True  # Level 2, unchanged
        assert updated_state["academicSummary"] == "Excellent (95/100) - Eligible"  # Level 3 cascade

        # Change score to 45 - should cascade through all levels differently
        state_manager.update_state([{
            "path": "state.score", 
            "operation": "set",
            "value": 45
        }])

        final_state = state_manager.get_flattened_state()
        assert final_state["score"] == 45
        assert final_state["scoreCategory"] == "Needs Improvement"  # Level 1
        assert final_state["finalGrade"] == "Needs Improvement (45/100)"  # Level 2
        assert final_state["passStatus"] == "FAIL"  # Level 1
        assert final_state["canGraduate"] == False  # Level 2
        assert final_state["academicSummary"] == "Needs Improvement (45/100) - Not Eligible"  # Level 3

    def test_circular_dependency_detection_and_prevention(self, state_manager):
        """
        Test AC-SM-016: Circular dependencies are detected and prevented
        Focus: System handles circular computed field dependencies gracefully
        """
        # Schema with circular dependency
        circular_schema = {
            "computed": {
                "fieldA": {
                    "expression": "this.fieldB + '_A'",
                    "dependencies": ["fieldB"]
                },
                "fieldB": {
                    "expression": "this.fieldC + '_B'", 
                    "dependencies": ["fieldC"]
                },
                "fieldC": {
                    "expression": "this.fieldA + '_C'",  # Circular back to fieldA
                    "dependencies": ["fieldA"]
                }
            }
        }

        # Should detect circular dependency during initialization
        from aromcp.workflow_server.state.models import CircularDependencyError
        with pytest.raises(CircularDependencyError) as exc_info:
            state_manager.initialize_state(
                inputs={},
                default_state={"baseValue": "start"},
                state_schema=circular_schema
            )

        assert "circular dependency" in str(exc_info.value).lower()

    def test_partial_dependency_resolution_handles_missing_fields(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-014: Computed fields handle missing dependencies gracefully
        Focus: Partial state should not crash cascading calculations
        """
        # Initialize with partial state (missing lastName)
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        state = state_manager.get_flattened_state()
        
        # Should handle missing lastName gracefully
        assert state["fullName"] == "John "  # Space but no last name
        assert state["isComplete"] == False  # Missing lastName
        assert state["status"] == "Incomplete"
        assert "john@example.com" in state["displayName"]
        assert "Incomplete" in state["summary"]

        # Add missing dependency
        state_manager.update_state([{
            "path": "state.lastName",
            "operation": "set",
            "value": "Doe"
        }])

        # Should now cascade to complete state
        complete_state = state_manager.get_flattened_state()
        assert complete_state["fullName"] == "John Doe"
        assert complete_state["isComplete"] == True
        assert complete_state["status"] == "Complete"

    def test_dependency_tracking_accuracy(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-016: Dependency tracking accurately identifies affected fields
        Focus: Only fields that actually depend on changed values are recalculated
        """
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        # Track which fields get recalculated
        recalculated_fields = []
        original_compute = state_manager._compute_field
        
        def tracking_compute(state, field_name, *args, **kwargs):
            recalculated_fields.append(field_name)
            return original_compute(state, field_name, *args, **kwargs)
            
        state_manager._compute_field = tracking_compute

        # Change only firstName
        recalculated_fields.clear()
        state_manager.update_state([{
            "path": "state.firstName",
            "operation": "set", 
            "value": "Jane"
        }])

        # Should recalculate fields that depend on firstName (directly or transitively)
        expected_recalculated = {"fullName", "isComplete", "displayName", "status", "summary"}  
        # fullName: depends on firstName directly
        # isComplete: depends on firstName directly
        # displayName: depends on fullName (which depends on firstName)
        # status: depends on isComplete (which depends on firstName)
        # summary: depends on both displayName and status (both transitively depend on firstName)
        actual_recalculated = set(recalculated_fields)
        
        # Verify all expected fields were recalculated
        assert expected_recalculated == actual_recalculated

    def test_concurrent_cascading_updates_thread_safety(self, state_manager, cascading_state_schema):
        """
        Test AC-SM-016: Cascading updates are thread-safe under concurrent access
        Focus: Multiple threads updating dependencies don't corrupt cascading calculations
        """
        import threading
        import time
        
        state_manager.initialize_state(
            inputs={},
            default_state={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            state_schema=cascading_state_schema
        )

        errors = []
        results = {}

        def update_first_name(name_suffix):
            try:
                state_manager.update_state([{
                    "path": "state.firstName",
                    "operation": "set",
                    "value": f"John{name_suffix}"
                }])
                # Small delay to encourage race conditions
                time.sleep(0.01)
                state = state_manager.get_flattened_state()
                results[name_suffix] = state["fullName"]
            except Exception as e:
                errors.append(str(e))

        def update_last_name(name_suffix):
            try:  
                state_manager.update_state([{
                    "path": "state.lastName",
                    "operation": "set",
                    "value": f"Doe{name_suffix}"
                }])
                time.sleep(0.01)
                state = state_manager.get_flattened_state()
                results[f"last_{name_suffix}"] = state["fullName"]
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads updating concurrently
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=update_first_name, args=(i,))
            t2 = threading.Thread(target=update_last_name, args=(i,))
            threads.extend([t1, t2])

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent update errors: {errors}"

        # Verify final state is consistent (no corrupted computed fields)
        final_state = state_manager.get_flattened_state()
        assert "fullName" in final_state
        assert len(final_state["fullName"].split()) == 2  # Should have first and last name
        assert final_state["isComplete"] == True  # Should still be complete
        

class TestComputedFieldPerformance:
    """Test performance characteristics of cascading computed fields."""

    @pytest.fixture
    def performance_schema(self):
        """Large schema with many cascading dependencies for performance testing."""
        schema = {"computed": {}}
        
        # Create 50 computed fields with various dependency patterns
        for i in range(50):
            if i == 0:
                # First field depends on base state
                schema["computed"][f"field_{i}"] = {
                    "expression": f"this.baseValue + '_{i}'",
                    "dependencies": ["baseValue"]
                }
            elif i < 25:
                # First 25 fields create a linear dependency chain
                schema["computed"][f"field_{i}"] = {
                    "expression": f"this.field_{i-1} + '_{i}'",
                    "dependencies": [f"field_{i-1}"]
                }
            else:
                # Remaining fields depend on multiple earlier fields
                deps = [f"field_{j}" for j in range(max(0, i-5), i)]
                schema["computed"][f"field_{i}"] = {
                    "expression": f"'{i}:' + this.{deps[0]} if deps else 'empty'",
                    "dependencies": deps
                }
                
        return schema

    def test_large_cascading_update_performance(self, performance_schema):
        """
        Test AC-SM-016: Large cascading updates complete within reasonable time
        Focus: Performance doesn't degrade exponentially with cascade depth
        """
        mock_evaluator = Mock()
        mock_evaluator.execute = Mock(return_value="computed_value")
        
        with patch('aromcp.workflow_server.state.manager.TransformationEngine', return_value=mock_evaluator):
            state_manager = StateManager()
            
            # Initialize with performance schema
            state_manager.initialize_state(
                inputs={},
                default_state={"baseValue": "start"},
                state_schema=performance_schema,
                workflow_id="wf_perf_test"
            )

            # Time a cascading update
            import time
            start_time = time.time()
            
            state_manager.update_state([{
                "path": "state.baseValue",
                "operation": "set",
                "value": "updated_start"
            }], workflow_id="wf_perf_test")
            
            elapsed_time = time.time() - start_time
            
            # Should complete within reasonable time (< 1 second for 50 fields)
            assert elapsed_time < 1.0, f"Cascading update took too long: {elapsed_time:.2f}s"
            
            # Verify some recalculations occurred
            assert mock_evaluator.execute.call_count > 0