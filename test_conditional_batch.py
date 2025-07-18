#!/usr/bin/env python3
"""Test conditional processing in batching."""

from aromcp.workflow_server.workflow.executor import WorkflowExecutor
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.state.models import StateSchema

# Test workflow: user_message, shell_command, conditional
steps = [
    WorkflowStep(id="msg1", type="user_message", definition={"message": "Starting..."}),
    WorkflowStep(id="cmd1", type="shell_command", definition={"command": "echo 'Pre-conditional'"}),
    WorkflowStep(
        id="check",
        type="conditional", 
        definition={
            "condition": "{{ value > 5 }}",
            "then_steps": [
                {"id": "then1", "type": "user_message", "message": "Value is high"},
                {"id": "then2", "type": "mcp_call", "tool": "test_tool", "parameters": {}}
            ],
            "else_steps": [
                {"id": "else1", "type": "user_message", "message": "Value is low"},
                {"id": "else2", "type": "state_update", "path": "raw.status", "value": "low"},
                {"id": "else3", "type": "mcp_call", "tool": "other_tool", "parameters": {}}
            ]
        }
    ),
    WorkflowStep(id="final", type="user_message", definition={"message": "Done"})
]

workflow_def = WorkflowDefinition(
    name="test:batch",
    description="Test batching with conditional",
    version="1.0.0",
    default_state={"raw": {"value": 3}},  # Will trigger else branch
    state_schema=StateSchema(),
    inputs={},
    steps=steps,
)

executor = WorkflowExecutor()
result = executor.start(workflow_def)
workflow_id = result["workflow_id"]

print("=== Getting next step (should batch everything) ===")
next_step = executor.get_next_step(workflow_id)

if next_step and "steps" in next_step:
    print(f"\nAgent-visible steps ({len(next_step['steps'])}):")
    for step in next_step["steps"]:
        print(f"  - {step['id']} ({step['type']})")
    
    print(f"\nServer-completed steps ({len(next_step['server_completed_steps'])}):")
    for step in next_step["server_completed_steps"]:
        print(f"  - {step['id']} ({step['type']})")
        
    print("\nExpected: msg1, else1, else3 (mcp_call) in steps")
    print("Expected: cmd1, else2 (state_update) in server_completed_steps")
    print("(final comes after completing the mcp_call)")
    
    # Complete the mcp_call and check next step
    print("\n=== Completing mcp_call and getting next ===")
    executor.step_complete(workflow_id, "check.else.2", "success")
    next_step = executor.get_next_step(workflow_id)
    
    if next_step and "steps" in next_step:
        print(f"Next batch has {len(next_step['steps'])} steps:")
        for step in next_step["steps"]:
            print(f"  - {step['id']} ({step['type']})")
    elif next_step is None:
        print("Workflow complete")
    else:
        print("Unexpected format:", next_step)
else:
    print("ERROR: Unexpected response format")
    print(next_step)