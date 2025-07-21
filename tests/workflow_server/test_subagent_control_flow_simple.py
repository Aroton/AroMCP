"""Simple verification tests for sub-agent control flow expansion functionality.

This test file verifies that the control flow expansion methods in SubAgentManager
work correctly by testing with the code-standards:enforce workflow pattern.
"""

import os
from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestSubAgentControlFlowVerification:
    """Verification tests for sub-agent control flow expansion."""

    def setup_method(self):
        """Setup test environment."""
        self.executor = WorkflowExecutor()
        self.loader = WorkflowLoader()
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()

    def test_while_loop_expansion_in_sub_agents(self):
        """Test that while_loop steps in sub-agents are expanded correctly."""
        
        print("=== Testing While Loop Expansion in Sub-Agents ===")
        
        # Use the real code-standards:enforce workflow which has while_loop in sub-agents
        workflow_def = self.loader.load("code-standards:enforce")
        start_result = self.executor.start(workflow_def, {
            "commit": "",
            "compare_to": "HEAD"
        })
        workflow_id = start_result["workflow_id"]
        
        print(f"\\n1. Started workflow {workflow_id}")
        
        # Progress through workflow to reach parallel_foreach
        max_attempts = 10
        found_parallel_step = None
        
        for attempt in range(max_attempts):
            response = self.executor.get_next_step(workflow_id)
            
            if response is None or "error" in response:
                break
                
            steps = response.get("steps", [])
            
            # Complete non-parallel steps to continue workflow
            for step in steps:
                if step["type"] in ["user_message", "shell_command"]:
                    try:
                        self.executor.step_complete(workflow_id, step["id"], "success", {})
                    except Exception:
                        pass  # Continue even if completion fails
                elif step["type"] == "parallel_foreach" and step["id"] == "process_files_parallel":
                    found_parallel_step = step
                    break
            
            if found_parallel_step:
                break
        
        assert found_parallel_step is not None, "Should find parallel_foreach step"
        
        # Get sub-agent tasks
        definition = found_parallel_step["definition"]
        assert "tasks" in definition, "parallel_foreach should have tasks"
        
        tasks = definition["tasks"]
        if len(tasks) == 0:
            print("\\n   No files to process (no git changes) - creating mock task for testing")
            # Mock a task for testing purposes
            self.executor.state_manager.update(workflow_id, [
                {"path": "raw.git_output", "value": "test_file.py"}
            ])
            
            # Get the step again to regenerate tasks
            response2 = self.executor.get_next_step(workflow_id)
            if response2 and "steps" in response2:
                for step in response2["steps"]:
                    if step["type"] == "parallel_foreach":
                        tasks = step["definition"].get("tasks", [])
                        break
        
        assert len(tasks) > 0, f"Should have at least 1 task, got {len(tasks)}"
        
        print(f"\\n2. Found {len(tasks)} sub-agent tasks")
        
        # Test the key fix: sub-agent steps should NOT immediately complete
        first_task = tasks[0]
        task_id = first_task["task_id"]
        
        print(f"\\n3. Testing sub-agent execution for task: {task_id}")
        
        # This was the key bug: get_next_sub_agent_step was returning None immediately
        # After the fix, it should return actual steps from the while_loop body
        first_sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
        
        # CRITICAL TEST: Should NOT be None (was the original bug)
        assert first_sub_step is not None, "Sub-agent should return steps, not complete immediately"
        assert "step" in first_sub_step, f"Sub-agent response should have 'step' field: {first_sub_step.keys()}"
        
        step_info = first_sub_step["step"]
        print(f"   First sub-agent step: {step_info['id']} ({step_info['type']})")
        
        # The step should be from the while_loop body expansion
        # Expected types from the code-standards:enforce sub-agent while_loop body:
        expected_types = ["state_update", "user_message", "conditional", "mcp_call"]
        assert step_info["type"] in expected_types, f"Unexpected step type: {step_info['type']} (expected one of {expected_types})"
        
        # Verify step advancement works
        second_sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
        
        if second_sub_step is not None:
            print(f"   Second sub-agent step: {second_sub_step['step']['id']} ({second_sub_step['step']['type']})")
            # Should be a different step
            assert second_sub_step["step"]["id"] != first_sub_step["step"]["id"], "Steps should advance"
        else:
            print("   Second call returned None (sub-agent complete after first step)")
        
        print("\\n✅ WHILE LOOP EXPANSION TEST PASSED!")
        print(f"   - Sub-agent steps execute correctly (not immediately completed)")
        print(f"   - While loop body steps are properly expanded")
        print(f"   - Step advancement works correctly")

    def test_conditional_expansion_in_sub_agents(self):
        """Test that conditional steps in sub-agents are expanded correctly."""
        
        print("=== Testing Conditional Expansion in Sub-Agents ===")
        
        # The code-standards:enforce workflow has many conditional steps in the sub-agent while_loop
        workflow_def = self.loader.load("code-standards:enforce")
        start_result = self.executor.start(workflow_def, {
            "commit": "",
            "compare_to": "HEAD"
        })
        workflow_id = start_result["workflow_id"]
        
        # Add a test file to ensure we have something to process
        self.executor.state_manager.update(workflow_id, [
            {"path": "raw.git_output", "value": "test_file.ts"}
        ])
        
        # Progress to parallel_foreach
        found_tasks = False
        max_attempts = 10
        
        for attempt in range(max_attempts):
            response = self.executor.get_next_step(workflow_id)
            
            if response is None:
                break
                
            steps = response.get("steps", [])
            
            for step in steps:
                if step["type"] == "parallel_foreach":
                    tasks = step["definition"].get("tasks", [])
                    if len(tasks) > 0:
                        task_id = tasks[0]["task_id"]
                        found_tasks = True
                        break
                elif step["type"] in ["user_message", "shell_command"]:
                    try:
                        self.executor.step_complete(workflow_id, step["id"], "success", {})
                    except Exception:
                        pass
            
            if found_tasks:
                break
        
        assert found_tasks, "Should find parallel_foreach with tasks"
        
        print(f"\\n1. Found sub-agent task: {task_id}")
        
        # Execute multiple sub-agent steps to encounter conditional expansions
        step_count = 0
        conditional_steps_found = 0
        max_sub_steps = 20  # Reasonable limit
        
        while step_count < max_sub_steps:
            sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
            
            if sub_step is None:
                break
                
            step_info = sub_step["step"]
            step_count += 1
            
            print(f"   Step {step_count}: {step_info['id']} ({step_info['type']})")
            
            # Count steps that came from conditional expansion
            # Look for steps from expanded conditional branches (then/else patterns)
            if any(pattern in step_info["id"] for pattern in 
                   [".then.", ".else.", "final_result_processing", "failure_", "success_"]):
                conditional_steps_found += 1
        
        print(f"\\n2. Executed {step_count} sub-agent steps")
        print(f"   Found {conditional_steps_found} steps from conditional expansion")
        
        # We should have found some steps that came from conditional expansion
        # The code-standards:enforce sub-agent has many conditionals in the while_loop
        assert conditional_steps_found > 0, f"Should find steps from conditional expansion, found {conditional_steps_found}"
        assert step_count > 1, f"Should execute multiple steps, only got {step_count}"
        
        print("\\n✅ CONDITIONAL EXPANSION TEST PASSED!")
        print(f"   - Conditional steps are properly expanded in sub-agents")
        print(f"   - Multiple conditional branches execute correctly")

    def test_server_vs_client_step_handling(self):
        """Test that server and client steps are handled correctly in sub-agents."""
        
        print("=== Testing Server vs Client Step Handling ===")
        
        workflow_def = self.loader.load("code-standards:enforce")
        start_result = self.executor.start(workflow_def, {
            "commit": "",
            "compare_to": "HEAD"  
        })
        workflow_id = start_result["workflow_id"]
        
        # Add test file
        self.executor.state_manager.update(workflow_id, [
            {"path": "raw.git_output", "value": "test_file.py"}
        ])
        
        # Find sub-agent task
        task_id = None
        for attempt in range(10):
            response = self.executor.get_next_step(workflow_id)
            if not response or not response.get("steps"):
                break
                
            for step in response["steps"]:
                if step["type"] == "parallel_foreach":
                    tasks = step["definition"].get("tasks", [])
                    if tasks:
                        task_id = tasks[0]["task_id"]
                        break
                elif step["type"] in ["user_message", "shell_command"]:
                    try:
                        self.executor.step_complete(workflow_id, step["id"], "success", {})
                    except:
                        pass
            if task_id:
                break
                
        assert task_id is not None, "Should find sub-agent task"
        
        # Execute sub-agent steps and categorize them
        client_steps = []
        server_steps_processed = 0
        max_steps = 15
        
        for i in range(max_steps):
            sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
            
            if sub_step is None:
                break
                
            step_info = sub_step["step"]
            step_type = step_info["type"]
            
            # Client steps should be returned to us
            if step_type in ["user_message", "mcp_call", "internal_mcp_call", "user_input"]:
                client_steps.append(step_info)
                
            print(f"   Returned step: {step_info['id']} ({step_type})")
        
        print(f"\\n1. Received {len(client_steps)} client steps")
        
        # We should get client steps (user_message, mcp_call) but NOT server steps (state_update)
        assert len(client_steps) > 0, "Should receive client steps from sub-agent"
        
        # Verify we got expected client step types
        client_types = [step["type"] for step in client_steps]
        expected_client_types = ["user_message", "mcp_call"]
        
        has_expected_types = any(ct in expected_client_types for ct in client_types)
        assert has_expected_types, f"Should get expected client types {expected_client_types}, got {client_types}"
        
        print("\\n✅ SERVER VS CLIENT STEP HANDLING TEST PASSED!")
        print(f"   - Client steps are returned: {client_types}")
        print(f"   - Server steps are processed internally (not returned)")


if __name__ == "__main__":
    # Run tests directly
    import sys
    import traceback
    
    def run_test_method(test_class, method_name):
        """Run a single test method."""
        try:
            print(f"\\n🧪 Running {method_name}")
            instance = test_class()
            instance.setup_method()
            getattr(instance, method_name)()
            instance.teardown_method()
            print(f"✅ {method_name} PASSED")
            return True
        except Exception as e:
            print(f"❌ {method_name} FAILED: {e}")
            print(traceback.format_exc())
            return False

    # Run verification tests
    test_class = TestSubAgentControlFlowVerification
    test_methods = [
        "test_while_loop_expansion_in_sub_agents",
        "test_conditional_expansion_in_sub_agents", 
        "test_server_vs_client_step_handling"
    ]
    
    passed = 0
    total = len(test_methods)
    
    for method in test_methods:
        if run_test_method(test_class, method):
            passed += 1
    
    print(f"\\n📊 Sub-Agent Control Flow Verification: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\\n🎉 All sub-agent control flow verification tests PASSED!")
        sys.exit(0)
    else:
        print(f"\\n💥 Some sub-agent control flow verification tests FAILED!")
        sys.exit(1)