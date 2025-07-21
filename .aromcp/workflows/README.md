# MCP Workflow System Documentation

This directory contains workflow definitions for the MCP Workflow System. Workflows are defined in YAML format and provide a declarative way to orchestrate complex tasks with state management, control flow, and parallel execution capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Workflow Structure](#workflow-structure)
3. [State Management](#state-management)
4. [Step Types](#step-types)
5. [Expressions and Templates](#expressions-and-templates)
6. [Sub-Agent Tasks](#sub-agent-tasks)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

## Overview

The MCP Workflow System allows you to:
- Define complex multi-step workflows in YAML
- Manage state across workflow execution
- Execute steps conditionally and in loops
- Run tasks in parallel using sub-agents
- Integrate with MCP tools and shell commands
- Handle errors and retries gracefully

## Workflow Structure

Every workflow YAML file must contain these top-level fields:

```yaml
name: "namespace:workflow-name"  # Required: Unique identifier
description: "What this workflow does"  # Required: Human-readable description
version: "1.0.0"  # Required: Semantic version

# Optional configuration
config:
  max_retries: 3
  timeout_seconds: 3600

# Input parameter definitions
inputs:
  parameter_name:
    type: "string"  # string, number, boolean, object, array
    description: "What this parameter is for"
    required: false
    default: "default value"

# Initial state values
default_state:
  raw:
    counter: 0
    results: {}

# Computed state fields
state_schema:
  computed:
    field_name:
      from: "raw.counter"
      transform: "input * 2"

# Workflow steps (required)
steps:
  - id: "step1"
    type: "user_message"
    message: "Starting workflow..."

# Sub-agent task definitions
sub_agent_tasks:
  task_name:
    description: "Process a single item"
    # ... task definition
```

## State Management

The workflow system uses a three-tier state model:

### 1. Raw State (`raw`)
- Directly writable by agents and steps
- Persists throughout workflow execution
- Access via `raw.field_name`

### 2. Computed State (`computed`)
- Automatically derived from other state values
- Updated when dependencies change
- Defined using JavaScript expressions
- Access via `computed.field_name`

### 3. Legacy State (`state`)
- For backward compatibility
- Similar to raw state
- Access via `state.field_name`

### Computed Field Definition

```yaml
state_schema:
  computed:
    # Simple transformation
    doubled_value:
      from: "raw.value"
      transform: "input * 2"
    
    # Multiple dependencies
    total_count:
      from: ["raw.success_count", "raw.failure_count"]
      transform: "input[0] + input[1]"
    
    # Complex transformation with filtering
    code_files:
      from: "raw.all_files"
      transform: |
        input.filter(file => {
          const codeExts = ['.py', '.js', '.ts'];
          return codeExts.some(ext => file.endsWith(ext));
        })
    
    # Error handling
    safe_division:
      from: ["raw.numerator", "raw.denominator"]
      transform: "input[0] / input[1]"
      on_error: "use_fallback"
      fallback: 0
```

## Step Types

### Client-Executed Steps (require agent/client interaction)

#### `user_message`
Display a message to the user.

```yaml
- id: "welcome"
  type: "user_message"
  message: "Welcome to the workflow!"
  message_type: "info"  # info, warning, error, success
  format: "markdown"    # text, markdown, code
```

#### `mcp_call`
Execute an MCP tool call.

```yaml
- id: "list_files"
  type: "mcp_call"
  tool: "aromcp.list_files"
  parameters:
    path: "/src"
  state_update:
    path: "raw.files"
    value: "data.files"  # Access result.data.files
  store_result: "raw.full_result"  # Store entire result
  timeout: 30
```

#### `user_input`
Collect input from the user.

```yaml
- id: "get_choice"
  type: "user_input"
  prompt: "Select an option:"
  type: "string"
  choices: ["option1", "option2", "option3"]
  default: "option1"
  state_update:
    path: "raw.user_choice"
    value: "input"
  max_retries: 3
```

#### `parallel_foreach`
Execute sub-agents in parallel for each item.

```yaml
- id: "process_files"
  type: "parallel_foreach"
  items: "{{ computed.code_files }}"
  sub_agent_task: "process_single_file"
  max_parallel: 5
  timeout_seconds: 300
```

#### `agent_shell_command`
Have the agent execute a shell command.

```yaml
- id: "run_tests"
  type: "agent_shell_command"
  command: "npm test"
  reason: "Running test suite to verify changes"
  working_directory: "/project"
  state_update:
    path: "raw.test_output"
    value: "stdout"
```

#### `agent_task`
Give the agent a task to complete.

```yaml
- id: "fix_errors"
  type: "agent_task"
  prompt: "Fix any linting errors found in {{ file_path }}"
  context:
    errors: "{{ raw.lint_errors }}"
```

### Server-Executed Steps (processed internally)

#### `shell_command`
Execute a shell command on the server.

```yaml
- id: "git_status"
  type: "shell_command"
  command: "git status --porcelain"
  working_directory: "/repo"
  timeout: 10
  state_update:
    path: "raw.git_output"
    value: "stdout"
```

#### `state_update`
Update a single state value.

```yaml
- id: "increment_counter"
  type: "state_update"
  path: "raw.counter"
  value: "{{ raw.counter + 1 }}"
  operation: "set"  # set, increment, decrement, append, multiply
```

#### `batch_state_update`
Update multiple state values at once.

```yaml
- id: "reset_counters"
  type: "batch_state_update"
  updates:
    - path: "raw.success_count"
      value: 0
    - path: "raw.failure_count"
      value: 0
    - path: "raw.results"
      value: {}
```

### Control Flow Steps

#### `conditional`
Execute steps based on a condition.

```yaml
- id: "check_files"
  type: "conditional"
  condition: "{{ computed.has_files }}"
  then_steps:
    - id: "process_files"
      type: "user_message"
      message: "Processing {{ computed.total_files }} files..."
  else_steps:
    - id: "no_files"
      type: "user_message"
      message: "No files to process"
    - id: "exit"
      type: "break"
```

#### `while_loop`
Repeat steps while a condition is true.

```yaml
- id: "retry_loop"
  type: "while_loop"
  condition: "{{ raw.attempts < 3 && !raw.success }}"
  max_iterations: 10
  body:
    - id: "attempt"
      type: "state_update"
      path: "raw.attempts"
      value: "{{ raw.attempts + 1 }}"
    # ... more steps
```

#### `foreach`
Iterate over items in an array.

```yaml
- id: "process_each"
  type: "foreach"
  items: "{{ computed.failed_files }}"
  variable_name: "file"
  body:
    - id: "show_file"
      type: "user_message"
      message: "Failed: {{ file }}"
```

#### `break` and `continue`
Control loop execution.

```yaml
- id: "exit_loop"
  type: "break"  # Exit current loop

- id: "skip_iteration"
  type: "continue"  # Skip to next iteration
```

## Expressions and Templates

### Template Variables

Use `{{ expression }}` to reference state values and evaluate expressions:

```yaml
# Simple references
message: "Processing {{ raw.file_name }}"

# Expressions
value: "{{ raw.count + 1 }}"

# Conditional expressions
message: "{{ raw.count > 0 ? 'Found items' : 'No items found' }}"

# Array operations
items: "{{ computed.files.filter(f => f.endsWith('.py')) }}"

# Input parameters
value: "{{ compare_to || 'main' }}"  # Use input or default
```

### JavaScript Expressions

Computed fields and conditions support full JavaScript expressions:

```yaml
# Array methods
transform: "input.map(x => x.toUpperCase())"

# Complex logic
transform: |
  input.filter(file => {
    const excluded = ['node_modules', '.git'];
    return !excluded.some(dir => file.includes(dir));
  })

# Object manipulation
transform: "Object.entries(input).map(([k, v]) => ({key: k, value: v}))"
```

## Sub-Agent Tasks

Sub-agent tasks allow parallel processing of items:

```yaml
sub_agent_tasks:
  process_file:
    description: "Process a single file"
    
    # Input parameters for the task
    inputs:
      file_path:
        type: "string"
        description: "File to process"
        required: true
      max_attempts:
        type: "number"
        description: "Maximum attempts"
        default: 3
    
    # Initial state for sub-agent
    default_state:
      raw:
        attempts: 0
        success: false
    
    # Computed fields for sub-agent
    state_schema:
      computed:
        can_retry:
          from: ["raw.attempts", "{{ max_attempts }}"]
          transform: "input[0] < input[1]"
    
    # Either provide a prompt template...
    prompt_template: |
      Process the file: {{ file_path }}
      You are processing item {{ index }} of {{ total }}.
      
      Your task is to...
    
    # ...or define explicit steps
    steps:
      - id: "process"
        type: "mcp_call"
        tool: "process_tool"
        parameters:
          file: "{{ file_path }}"
```

## Best Practices

### 1. Naming Conventions
- Use `namespace:name` format for workflow names
- Use descriptive `snake_case` for step IDs
- Use clear, action-oriented step descriptions

### 2. State Management
- Keep raw state flat when possible
- Use computed fields for derived values
- Document state structure in comments

### 3. Error Handling
- Set appropriate timeouts for long-running operations
- Use `max_iterations` for loops to prevent infinite loops
- Provide fallback values for computed fields

### 4. Performance
- Use `parallel_foreach` for independent operations
- Batch related `user_message` steps
- Limit `max_parallel` based on resource constraints

### 5. Debugging
- Use descriptive messages at key points
- Store intermediate results in state for inspection
- Use `debug_task_completion` and `debug_step_advance` for debugging

## Examples

### Simple Linear Workflow

```yaml
name: "example:hello-world"
description: "A simple greeting workflow"
version: "1.0.0"

steps:
  - id: "greet"
    type: "user_message"
    message: "Hello, World!"
  
  - id: "get_name"
    type: "user_input"
    prompt: "What's your name?"
    state_update:
      path: "raw.user_name"
      value: "input"
  
  - id: "personalized_greeting"
    type: "user_message"
    message: "Nice to meet you, {{ raw.user_name }}!"
```

### Conditional Workflow

```yaml
name: "example:file-processor"
description: "Process files based on type"
version: "1.0.0"

default_state:
  raw:
    file_path: ""

state_schema:
  computed:
    is_python:
      from: "raw.file_path"
      transform: "input.endsWith('.py')"
    is_javascript:
      from: "raw.file_path"
      transform: "input.endsWith('.js') || input.endsWith('.ts')"

steps:
  - id: "check_file_type"
    type: "conditional"
    condition: "{{ computed.is_python }}"
    then_steps:
      - id: "process_python"
        type: "mcp_call"
        tool: "python_linter"
        parameters:
          file: "{{ raw.file_path }}"
    else_steps:
      - id: "check_js"
        type: "conditional"
        condition: "{{ computed.is_javascript }}"
        then_steps:
          - id: "process_js"
            type: "mcp_call"
            tool: "eslint"
            parameters:
              file: "{{ raw.file_path }}"
```

### Parallel Processing Workflow

```yaml
name: "example:batch-processor"
description: "Process multiple files in parallel"
version: "1.0.0"

default_state:
  raw:
    files: []
    results: {}

steps:
  - id: "get_files"
    type: "shell_command"
    command: "find . -name '*.py' -type f"
    state_update:
      path: "raw.files"
      value: "stdout.split('\\n').filter(f => f)"
  
  - id: "process_files"
    type: "parallel_foreach"
    items: "{{ raw.files }}"
    sub_agent_task: "analyze_file"
    max_parallel: 5

sub_agent_tasks:
  analyze_file:
    description: "Analyze a single Python file"
    inputs:
      file_path:
        type: "string"
        required: true
    
    prompt_template: |
      Analyze the Python file: {{ file_path }}
      Check for:
      1. Code style issues
      2. Potential bugs
      3. Performance improvements
      
      Report your findings.
```

## Validation

Use the validation script to check your workflow files:

```bash
python scripts/validate_workflow.py .aromcp/workflows/my-workflow.yaml
```

The validator checks for:
- Required fields
- Valid step types
- Proper field types
- Reference consistency
- Schema compliance

## Schema Reference

The complete JSON Schema for workflow files is available at `.aromcp/workflows/schema.json`. This schema defines all valid fields, step types, and their constraints.