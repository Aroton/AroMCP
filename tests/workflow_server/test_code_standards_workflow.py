"""Test for code-standards:enforce workflow execution to verify sub-agent steps work correctly."""

import os
from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestCodeStandardsWorkflow:
    """Test the code-standards:enforce workflow specifically."""

    def setup_method(self):
        """Setup test environment."""
        self.executor = WorkflowExecutor()
        self.loader = WorkflowLoader()
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()

    def test_code_standards_enforce_workflow_sub_agent_steps(self):
        """Test that code-standards:enforce workflow sub-agent steps execute correctly."""
        
        print("=== Testing Code Standards Enforce Workflow ===")
        
        # Step 1: Load the actual code-standards:enforce workflow
        workflow_def = self.loader.load("code-standards:enforce")
        start_result = self.executor.start(workflow_def, {
            "commit": "",  # Use diff mode  
            "compare_to": "HEAD"  # Compare against HEAD
        })
        workflow_id = start_result["workflow_id"]
        
        print(f"\\n1. Started code-standards:enforce workflow {workflow_id}")
        
        # Step 2: Let the git commands run naturally but check what files they find
        # The workflow will run git diff commands to get real changed files
        
        # Step 3: Progress through workflow steps to reach parallel_foreach
        max_attempts = 10
        found_parallel_step = None
        
        for attempt in range(max_attempts):
            response = self.executor.get_next_step(workflow_id)
            
            if response is None:
                print(f"\\n2.{attempt+1}. Workflow completed without finding parallel_foreach step")
                break
            elif "error" in response:
                print(f"\\n2.{attempt+1}. Workflow error: {response['error']}")
                break
                
            steps = response.get("steps", [])
            print(f"\\n2.{attempt+1}. Got {len(steps)} step(s):")
            
            # Look for the parallel_foreach step
            for step in steps:
                step_id = step["id"]  
                step_type = step["type"]
                print(f"   Step: {step_id} ({step_type})")
                
                if step_type == "parallel_foreach" and step_id == "process_files_parallel":
                    found_parallel_step = step
                    print(f"   ✓ Found target parallel_foreach step!")
                    break
            
            # Complete user_message and shell_command steps to continue workflow
            for step in steps:
                if step["type"] in ["user_message", "shell_command"]:
                    try:
                        self.executor.step_complete(workflow_id, step["id"], "success", {})
                    except Exception as e:
                        print(f"   Warning: Could not complete {step['id']}: {e}")
            
            # If we found our target step, break out
            if found_parallel_step:
                break
        
        # Step 4: Verify we found the parallel_foreach step
        assert found_parallel_step is not None, f"Expected to find parallel_foreach step after {max_attempts} attempts"
        
        # Step 5: Validate the sub-agent tasks were created
        definition = found_parallel_step["definition"]
        assert "tasks" in definition, f"parallel_foreach definition missing 'tasks': {definition.keys()}"
        
        tasks = definition["tasks"]
        print(f"\\n3. Found {len(tasks)} sub-agent tasks:")
        
        # Should have tasks for whatever files git diff found
        # Since we're running in a real git repo, there may be actual changed files
        print(f"   Found tasks for files: {[task['context']['item'] for task in tasks[:5]]}{'...' if len(tasks) > 5 else ''}")
        
        # Just verify we have some tasks (the exact number depends on what's actually changed)
        assert len(tasks) > 0, f"Expected at least 1 task, got {len(tasks)}"
        
        # Verify task structure is correct
        for i, task in enumerate(tasks[:3]):  # Check first 3 tasks
            task_id = task["task_id"]
            expected_task_id = f"enforce_standards_on_file.item{i}"
            file_path = task['context']['item']
            
            print(f"   Task {i}: {task_id}")
            print(f"   - File: {file_path}")
            
            assert task_id == expected_task_id, f"Task ID mismatch: {task_id} != {expected_task_id}"
            assert "inputs" in task, f"Task missing inputs: {task.keys()}"
            assert task["inputs"]["file_path"] == file_path, f"Input file_path mismatch"
        
        # Step 6: Test getting next sub-agent step for the first task
        first_task = tasks[0]
        task_id = first_task["task_id"]
        file_path = first_task["context"]["item"]
        
        print(f"\\n4. Testing sub-agent step execution for task: {task_id}")
        print(f"   File being processed: {file_path}")
        
        # This is the key test - get the first step from the sub-agent
        first_sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
        
        # Verify we got a step back (not immediately completed)
        assert first_sub_step is not None, f"Expected first sub-agent step, got None (immediately completed)"
        assert "step" in first_sub_step, f"Expected 'step' field in sub-agent response: {first_sub_step.keys()}"
        
        step_info = first_sub_step["step"]
        print(f"   First sub-agent step: {step_info['id']} ({step_info['type']})")
        print(f"   Definition keys: {list(step_info['definition'].keys())}")
        
        # The first step should be from the while_loop body, likely a shell_command with state_update
        expected_step_types = ["shell_command with state_update", "user_message", "conditional"]  # Possible first step types
        assert step_info["type"] in expected_step_types, f"Unexpected first step type: {step_info['type']}"
        assert task_id in step_info["id"], f"Step ID should contain task_id: {step_info['id']}"
        
        # Step 7: Test getting a second sub-agent step  
        second_sub_step = self.executor.get_next_sub_agent_step(workflow_id, task_id)
        
        if second_sub_step is not None:
            print(f"   Second sub-agent step: {second_sub_step['step']['id']} ({second_sub_step['step']['type']})")
            # Should be a different step
            assert second_sub_step["step"]["id"] != first_sub_step["step"]["id"], "Steps should advance"
        else:
            print(f"   Second call returned None (sub-agent complete)")
        
        print("\\n✅ CODE-STANDARDS:ENFORCE WORKFLOW TEST PASSED!")
        print("   - Successfully loaded real workflow")
        print("   - Found parallel_foreach step with correct sub-agent tasks")
        print("   - Sub-agent tasks have expected structure and files")
        print(f"   - First sub-agent step executes correctly (not immediately completed)")
        print(f"   - Sub-agent step advancement works properly")

    def test_code_standards_enforce_with_debug_mode(self):
        """Test code-standards:enforce workflow in debug mode."""
        import os
        
        print("=== Testing Code Standards Enforce in Debug Mode ===")
        
        # Set debug mode
        original_debug = os.environ.get("AROMCP_WORKFLOW_DEBUG")
        os.environ["AROMCP_WORKFLOW_DEBUG"] = "serial"
        
        try:
            # Create new executor with debug mode
            debug_executor = WorkflowExecutor()
            
            # Load workflow  
            workflow_def = self.loader.load("code-standards:enforce")
            start_result = debug_executor.start(workflow_def, {"commit": "", "compare_to": "HEAD"})
            workflow_id = start_result["workflow_id"]
            
            print(f"\\n1. Started code-standards:enforce in DEBUG MODE: {workflow_id}")
            
            # Mock git output
            mock_git_output = "src/debug_test.ts"  # Single file for simpler debug testing
            debug_executor.state_manager.update(workflow_id, [
                {"path": "raw.git_output", "value": mock_git_output}
            ])
            
            # Progress through steps looking for expanded sub-agent steps
            expanded_steps = []
            max_attempts = 15  # More attempts for debug mode
            
            for attempt in range(max_attempts):
                response = debug_executor.get_next_step(workflow_id)
                
                if response is None:
                    print(f"\\n2.{attempt+1}. Workflow completed")
                    break
                elif "error" in response:
                    print(f"\\n2.{attempt+1}. Workflow error: {response['error']}")
                    break
                    
                steps = response.get("steps", [])
                print(f"\\n2.{attempt+1}. Got {len(steps)} step(s):")
                
                for step in steps:
                    step_id = step["id"]
                    step_type = step["type"]
                    print(f"   Step: {step_id} ({step_type})")
                    
                    # Look for expanded sub-agent steps (contain task_id pattern)
                    if "enforce_standards_on_file.item" in step_id:
                        expanded_steps.append(step)
                        print(f"     ✓ Found expanded sub-agent step!")
                
                # Log steps (implicit completion will handle them automatically)
                for step in steps:
                    if step["type"] in ["user_message", "shell_command"]:
                        print(f"     Step ready: {step['id']} ({step['type']})")
                    elif step["type"] == "parallel_foreach":
                        print(f"     Parallel foreach step ready: {step['id']}") 
                
                # Stop if we found expanded steps
                if expanded_steps:
                    break
            
            # Verify debug expansion worked
            assert len(expanded_steps) > 0, f"Debug mode should have expanded sub-agent steps after {max_attempts} attempts"
            
            print(f"\\n3. Debug expansion results:")
            print(f"   Found {len(expanded_steps)} expanded sub-agent steps")
            
            for step in expanded_steps[:3]:  # Show first 3
                print(f"   - {step['id']} ({step['type']})")
            
            print("\\n✅ DEBUG MODE TEST PASSED!")
            print("   - Workflow correctly expanded parallel_foreach into individual steps")
            print("   - Sub-agent steps are returned one at a time")
            
        finally:
            # Restore debug setting
            if original_debug is not None:
                os.environ["AROMCP_WORKFLOW_DEBUG"] = original_debug
            else:
                os.environ.pop("AROMCP_WORKFLOW_DEBUG", None)


if __name__ == "__main__":
    # Run the test directly
    test = TestCodeStandardsWorkflow()
    test.setup_method()
    try:
        test.test_code_standards_enforce_workflow_sub_agent_steps()
        test.test_code_standards_enforce_with_debug_mode()
        print("\\n🎉 ALL CODE-STANDARDS:ENFORCE TESTS PASSED!")
    finally:
        test.teardown_method()