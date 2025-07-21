"""Shared test fixtures and utilities for workflow server tests."""

import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with workflow directory structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True)
        yield temp_dir, workflows_dir


@pytest.fixture
def workflow_executor():
    """Create a fresh workflow executor instance."""
    return QueueBasedWorkflowExecutor()


@pytest.fixture
def workflow_loader(temp_workspace):
    """Create a workflow loader with temporary workspace."""
    temp_dir, workflows_dir = temp_workspace
    return WorkflowLoader(project_root=temp_dir)


@pytest.fixture
def simple_workflow_definition():
    """Return the test:simple.yaml workflow definition."""
    return """
name: "test:simple"
description: "Test basic sequential execution"
version: "1.0.0"

default_state:
  raw:
    counter: 0
    message: ""

state_schema:
  computed:
    doubled:
      from: "raw.counter"
      transform: "input * 2"

inputs:
  name:
    type: "string"
    description: "User name"
    required: true

steps:
  - type: "state_update"
    path: "raw.counter"
    value: 5
    
  - type: "user_message"
    message: "Counter is {{ raw.counter }}, doubled is {{ computed.doubled }}"
    
  - type: "shell_command"
    command: "echo 'Hello from workflow'"
    state_update:
      path: "raw.message"
      value: "stdout"
"""


@pytest.fixture
def subagent_workflow_definition():
    """Return the test:sub-agents.yaml workflow definition."""
    return """
name: "test:sub-agents"
description: "Test workflow demonstrating sub-agent parallel execution with complex computed fields"
version: "1.0.0"

inputs:
  git_output:
    type: "string"
    description: "Raw git output with file paths (newline separated)"
    required: false
    default: "src/test.ts\\nsrc/another.js\\nREADME.md\\nnode_modules/test.js\\n.git/config\\ndist/build.js"
  
  file_list:
    type: "array"
    description: "Direct list of files to process (alternative to git_output)"
    required: false
    default: []

default_state:
  raw:
    git_output: ""
    file_list: []
    results: {}
    processed_count: 0

# Complex computed state fields similar to code-standards:enforce
state_schema:
  computed:
    # First: Parse git output into individual files
    changed_files:
      from: "raw.git_output"
      transform: "input.split('\\\\n').filter(line => line.trim() !== '')"
    
    # Second: Filter for code files only, excluding certain directories
    code_files:
      from: "computed.changed_files"
      transform: |
        input.filter(file => {
          const codeExts = ['.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.java', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.cs', '.rb'];
          const excludeDirs = ['node_modules', '__pycache__', '.git', 'dist', 'build', 'target', 'bin', 'obj', 'out', '.venv', 'venv', 'env', '.pytest_cache', '.mypy_cache', 'vendor'];
          const parts = file.split('/');
          const hasExcluded = parts.some(part => excludeDirs.includes(part));
          const isCode = codeExts.some(ext => file.endsWith(ext));
          return !hasExcluded && isCode;
        })
    
    # Third: Fallback to direct file list if no git output
    final_files:
      from: ["computed.code_files", "raw.file_list"]
      transform: "input[0].length > 0 ? input[0] : input[1]"
    
    # Statistics
    total_files:
      from: "computed.final_files"
      transform: "input.length"
    
    has_files:
      from: "computed.final_files"
      transform: "input.length > 0"
    
    typescript_files:
      from: "computed.final_files"
      transform: "input.filter(f => f.endsWith('.ts') || f.endsWith('.tsx'))"
    
    javascript_files:
      from: "computed.final_files"
      transform: "input.filter(f => f.endsWith('.js') || f.endsWith('.jsx'))"
    
    # Processing status
    all_processed:
      from: ["raw.processing_results", "computed.final_files"]
      transform: "Object.keys(input[0] || {}).length === input[1].length"
    
    failed_files:
      from: "raw.processing_results"
      transform: "Object.entries(input || {}).filter(([_, result]) => !result.success).map(([file, _]) => file)"

steps:
  # Step 1: Initialize with git output or file list
  - id: "initialize_git_output"
    type: "state_update"
    path: "raw.git_output"
    value: "{{ git_output }}"

  - id: "initialize_file_list"
    type: "state_update"
    path: "raw.file_list"
    value: "{{ file_list }}"

  # Step 2: Show what files were found
  - id: "files_found_message"
    type: "user_message"
    message: |
      Found {{ computed.total_files }} files to process:
      - Changed files: {{ computed.changed_files.length }}
      - Code files: {{ computed.code_files.length }}
      - TypeScript files: {{ computed.typescript_files.length }}
      - JavaScript files: {{ computed.javascript_files.length }}
      - Final list: {{ computed.final_files.slice(0, 5).join(', ') }}{{ computed.final_files.length > 5 ? '...' : '' }}

  # Step 3: Check if we have files to process
  - id: "check_has_files"
    type: "conditional"
    condition: "{{ computed.has_files }}"
    then_steps:
      - id: "start_processing_message"
        type: "user_message"
        message: "Starting parallel processing of {{ computed.total_files }} files..."
    else_steps:
      - id: "no_files_message"
        type: "user_message"
        message: "No files found to process. Workflow complete."
      - id: "exit_early"
        type: "break"

  # Step 4: Process files in parallel using computed.final_files
  - id: "process_files_parallel"
    type: "parallel_foreach"
    items: "{{ computed.final_files }}"
    max_parallel: 3
    sub_agent_task: "process_file"

  # Step 5: Finalize with computed field reference
  - id: "finalize"
    type: "state_update"
    path: "raw.processed_count"
    value: "{{ computed.total_files }}"

  - id: "completion_message"
    type: "user_message"
    message: |
      ✅ Processing complete!
      - Total files: {{ computed.total_files }}
      - Processed: {{ raw.processed_count }}
      - Failed: {{ computed.failed_files.length }}

sub_agent_tasks:
  process_file:
    description: "Process a single file through comprehensive code standards enforcement"
    inputs:
      file_path:
        type: "string"
        description: "Path to the file to process"
        required: true
      
      max_attempts:
        type: "number"
        description: "Maximum fix attempts"
        required: false
        default: 5

    prompt_template: |
      You are processing file: {{ file_path }} (item {{ index }} of {{ total }})
      
      Your task is to enforce code standards on this file through the following steps:
      1. Get hints for the file using hints_for_files
      2. Apply suggested improvements
      3. Run linting checks
      4. Fix any issues found
      5. Verify all checks pass
      
      Continue until all standards are met or max attempts ({{ max_attempts }}) reached.

    steps:
      - id: "mark_processing"
        type: "state_update"
        path: "raw.processing_results.{{ task_id }}"
        value:
          status: "processing"
          file: "{{ item }}"
          started_at: "{{ now() }}"
          attempts: 0

      - id: "get_hints"
        type: "mcp_call"
        tool: "hints_for_files"
        parameters:
          file_paths: ["{{ item }}"]
        state_update:
          path: "raw.processing_results.{{ task_id }}.hints"

      - id: "initial_lint"
        type: "mcp_call"
        tool: "lint_project"
        parameters:
          target_files: ["{{ item }}"]
          use_eslint_standards: true
        state_update:
          path: "raw.processing_results.{{ task_id }}.initial_lint"

      - id: "check_typescript"
        type: "conditional"
        condition: "{{ item.endsWith('.ts') || item.endsWith('.tsx') }}"
        then_steps:
          - id: "run_typescript_check"
            type: "mcp_call"
            tool: "check_typescript"
            parameters:
              file_paths: ["{{ item }}"]
            state_update:
              path: "raw.processing_results.{{ task_id }}.typescript_check"

      - id: "analyze_issues"
        type: "state_update"
        path: "raw.processing_results.{{ task_id }}.has_issues"
        value: "{{ (initial_lint && initial_lint.issues && initial_lint.issues.length > 0) || (typescript_check && typescript_check.errors && typescript_check.errors.length > 0) }}"

      - id: "mark_success"
        type: "conditional"
        condition: "{{ !raw.processing_results[task_id].has_issues }}"
        then_steps:
          - id: "mark_completed_success"
            type: "state_update"
            path: "raw.processing_results.{{ task_id }}.status"
            value: "completed"
          
          - id: "mark_success_flag"
            type: "state_update"
            path: "raw.processing_results.{{ task_id }}.success"
            value: true
        else_steps:
          - id: "mark_completed_with_issues"
            type: "state_update"
            path: "raw.processing_results.{{ task_id }}.status"
            value: "completed_with_issues"
          
          - id: "mark_needs_work"
            type: "state_update"
            path: "raw.processing_results.{{ task_id }}.success"
            value: false
          
          - id: "record_issues"
            type: "state_update"
            path: "raw.processing_results.{{ task_id }}.last_error"
            value: "File has linting or TypeScript issues that need manual attention"
"""


def create_workflow_file(workflows_dir: Path, workflow_name: str, content: str):
    """Create a workflow file in the workflows directory."""
    workflow_file = workflows_dir / f"{workflow_name}.yaml"
    workflow_file.write_text(content)
    return workflow_file


def assert_tool_response_format(response: Dict[str, Any], success: bool = True):
    """Assert that a tool response follows the expected format."""
    if success:
        assert "data" in response, f"Success response missing 'data' field: {response}"
        assert "error" not in response, f"Success response should not have 'error' field: {response}"
    else:
        assert "error" in response, f"Error response missing 'error' field: {response}"
        assert "code" in response["error"], f"Error missing 'code' field: {response['error']}"
        assert "message" in response["error"], f"Error missing 'message' field: {response['error']}"


def assert_workflow_state_structure(state: Dict[str, Any]):
    """Assert that workflow state follows the expected three-tier structure."""
    assert "raw" in state, f"State missing 'raw' tier: {state.keys()}"
    assert "computed" in state, f"State missing 'computed' tier: {state.keys()}"
    # The 'state' tier is optional and may not be present in all workflows


def assert_step_response_format(step_response: Dict[str, Any]):
    """Assert that a step response follows the expected batched format."""
    if step_response is None:
        return  # Workflow complete

    # Should have either single step or batched format
    if "step" in step_response:
        # Single step format
        step = step_response["step"]
        assert "id" in step, f"Step missing 'id': {step}"
        assert "type" in step, f"Step missing 'type': {step}"
        assert "definition" in step, f"Step missing 'definition': {step}"
    elif "steps" in step_response:
        # Batched format
        assert isinstance(step_response["steps"], list), f"Steps should be list: {step_response['steps']}"
        for step in step_response["steps"]:
            assert "id" in step, f"Step missing 'id': {step}"
            assert "type" in step, f"Step missing 'type': {step}"
            assert "definition" in step, f"Step missing 'definition': {step}"
        
        # Check for server completed steps
        if "server_completed_steps" in step_response:
            assert isinstance(step_response["server_completed_steps"], list)
            for completed_step in step_response["server_completed_steps"]:
                assert "id" in completed_step
                assert "type" in completed_step
                assert "result" in completed_step
    else:
        assert False, f"Step response missing 'step' or 'steps': {step_response}"