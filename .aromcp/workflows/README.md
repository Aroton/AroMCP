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
  state:
    counter: 0
    results: {}

# Computed state fields
state_schema:
  state:
    counter: "number"
    results: "object"
  computed:
    field_name:
      from: "state.counter"
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

The workflow system uses a four-scope variable model with modern scoped syntax:

### Scoped Variable Syntax (NEW)

Variables are now accessed using scoped prefixes for better clarity and conflict prevention:

```yaml
# Current workflow state and computed values
message: "Processing {{ this.file_name }}"
condition: "{{ this.total_count > 0 }}"

# Global variables shared across workflow contexts  
value: "{{ global.retry_count }}"

# Workflow input parameters (read-only)
path: "{{ inputs.project_path }}"

# Loop context variables (automatic)
message: "Processing item {{ loop.item }}"
condition: "{{ loop.iteration < 5 }}"
```

### The Four Variable Scopes

#### 1. `this` Scope - Current Context
- Contains both state and computed fields from the current workflow context
- Combines what was previously `state.field` and `computed.field`
- Access via `{{ this.field_name }}`
- Updated through `state_update` paths like `this.field_name`

#### 2. `global` Scope - Shared Variables  
- Global variables persisted across workflow execution contexts
- Useful for counters, caches, and shared state
- Access via `{{ global.variable_name }}`
- Updated through `state_update` paths like `global.variable_name`

#### 3. `inputs` Scope - Input Parameters
- Read-only parameters passed to the workflow
- Defined at workflow start, cannot be modified during execution
- Access via `{{ inputs.parameter_name }}`
- Cannot be updated (read-only)

#### 4. `loop` Scope - Loop Context (Automatic)
- Automatically managed loop variables
- Available only within loop contexts (while_loop, foreach)
- Access via `{{ loop.item }}`, `{{ loop.index }}`, `{{ loop.iteration }}`
- Cannot be manually updated (automatically managed)

### Computed Field Definition (Updated Syntax)

```yaml
state_schema:
  computed:
    # Simple transformation (NEW: uses 'this' scope)
    doubled_value:
      from: "this.value"
      transform: "input * 2"
    
    # Multiple dependencies (NEW: updated scope references)
    total_count:
      from: ["this.success_count", "this.failure_count"]
      transform: "input[0] + input[1]"
    
    # Complex transformation with filtering
    code_files:
      from: "this.all_files"
      transform: |
        input.filter(file => {
          const codeExts = ['.py', '.js', '.ts'];
          return codeExts.some(ext => file.endsWith(ext));
        })
    
    # Using global variables and inputs
    retry_decision:
      from: ["global.max_retries", "inputs.retry_enabled", "this.current_attempt"]
      transform: "input[1] && input[2] < input[0]"
    
    # Error handling
    safe_division:
      from: ["this.numerator", "this.denominator"]
      transform: "input[0] / input[1]"
      on_error: "use_fallback"
      fallback: 0
```

### Legacy Syntax Migration

⚠️ **Breaking Change**: The old `state.` and `computed.` prefixes have been replaced:

```yaml
# OLD (deprecated)
from: "state.value"
condition: "{{ computed.total_count > 0 }}"
state_update:
  path: "state.result"

# NEW (required)
from: "this.value"
condition: "{{ this.total_count > 0 }}"
state_update:
  path: "this.result"
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
    path: "this.files"
    value: "data.files"  # Access result.data.files
  store_result: "this.full_result"  # Store entire result
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
    path: "this.user_choice"
    value: "input"
  max_retries: 3
```

#### `parallel_foreach`
Execute sub-agents in parallel for each item.

```yaml
- id: "process_files"
  type: "parallel_foreach"
  items: "{{ this.code_files }}"
  sub_agent_task: "process_single_file"
  max_parallel: 5
  timeout_seconds: 300
```

#### `agent_prompt`
Provide a task instruction for the agent.

```yaml
- id: "fix_errors"
  type: "agent_prompt"
  prompt: "Fix any linting errors found in {{ inputs.file_path }}"
  context:
    errors: "{{ this.lint_errors }}"
  expected_response:
    type: "object"
    required: ["success", "changes_made"]
  timeout: 300
  max_retries: 3
```

#### `agent_response`
Process and validate agent response.

```yaml
- id: "process_response"
  type: "agent_response"
  response_schema:
    type: "object"
    required: ["analysis", "recommendations"]
  state_updates:
    - path: "this.analysis"
      value: "response.analysis"
    - path: "this.recommendations"
      value: "response.recommendations"
  store_response: "this.full_response"
```

### Server-Executed Steps (processed internally)

#### `shell_command`
Execute a shell command.

```yaml
- id: "git_status"
  type: "shell_command"
  command: "git status --porcelain"
  working_directory: "/repo"
  timeout: 10
  state_update:
    path: "this.git_output"
    value: "stdout"
  execution_context: "server"  # "server" (default) or "client"
```

**Note: Standalone state update steps have been removed. State updates are now embedded within other step types using the `state_update` or `state_updates` field.**

Examples of state updates in other steps:

```yaml
# In mcp_call
- id: "get_data"
  type: "mcp_call"
  tool: "fetch_data"
  state_update:
    path: "this.data"
    value: "result"

# In user_input
- id: "get_choice"
  type: "user_input"
  prompt: "Choose an option:"
  state_update:
    path: "this.choice"
    value: "input"

# In agent_response with multiple updates
- id: "process_response"
  type: "agent_response"
  state_updates:
    - path: "this.field1"
      value: "response.data1"
    - path: "this.field2"
      value: "response.data2"
```

### Control Flow Steps

#### `conditional`
Execute steps based on a condition.

```yaml
- id: "check_files"
  type: "conditional"
  condition: "{{ this.has_files }}"
  then_steps:
    - id: "process_files"
      type: "user_message"
      message: "Processing {{ this.total_files }} files..."
  else_steps:
    - id: "no_files"
      type: "user_message"
      message: "No files to process"
    - id: "exit"
      type: "break"
```

#### `while_loop`
Repeat steps while a condition is true. The loop automatically tracks iteration count via `{{ loop.iteration }}`.

```yaml
- id: "retry_loop"
  type: "while_loop"
  condition: "{{ loop.iteration < 3 && !this.success }}"
  max_iterations: 10
  body:
    # The iteration count is automatically managed by the loop
    - id: "show_attempt"
      type: "user_message"
      message: "Attempt {{ loop.iteration }}"
    # ... more steps
```

**Important**: While loops automatically provide `{{ loop.iteration }}` (1-based counter) for loop control. No initialization needed in `default_state`.

#### `foreach`
Iterate over items in an array. The current item and index are available via loop scope variables.

```yaml
- id: "process_each"
  type: "foreach"
  items: "{{ this.failed_files }}"
  body:
    - id: "show_file"
      type: "user_message"
      message: "Failed: {{ loop.item }} (index {{ loop.index }})"
```

**Loop Variables**: Use `{{ loop.item }}` for the current item and `{{ loop.index }}` for the 0-based index.

#### `break` and `continue`
Control loop execution.

```yaml
- id: "exit_loop"
  type: "break"  # Exit current loop

- id: "skip_iteration"
  type: "continue"  # Skip to next iteration
```

## Expressions and Templates

### Template Variables (Updated Scoped Syntax)

Use `{{ expression }}` to reference scoped variables and evaluate expressions:

```yaml
# Current workflow context (combines state + computed)
message: "Processing {{ this.file_name }}"
condition: "{{ this.count > 0 }}"

# Input parameters (read-only)
value: "{{ inputs.compare_to || 'main' }}"  # Use input or default

# Global variables (persistent across contexts)
message: "Retry {{ global.attempt_count }}"

# Current workflow values with expressions
value: "{{ this.count + 1 }}"

# Conditional expressions
message: "{{ this.count > 0 ? 'Found items' : 'No items found' }}"

# Array operations using scoped syntax
items: "{{ this.files.filter(f => f.endsWith('.py')) }}"

# Loop variables (automatic in loop contexts)
message: "Processing: {{ loop.item }} at index {{ loop.index }}"
condition: "{{ loop.iteration < 5 }}"
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
      state:
        attempt_number: 0
        success: false
    
    # Computed fields for sub-agent
    state_schema:
      computed:
        can_retry:
          from: ["loop.iteration", "inputs.max_attempts"]
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
      path: "this.user_name"
      value: "input"
  
  - id: "personalized_greeting"
    type: "user_message"
    message: "Nice to meet you, {{ this.user_name }}!"
```

### Conditional Workflow

```yaml
name: "example:file-processor"
description: "Process files based on type"
version: "1.0.0"

default_state:
  state:
    file_path: ""

state_schema:
  computed:
    is_python:
      from: "this.file_path"
      transform: "input.endsWith('.py')"
    is_javascript:
      from: "this.file_path"
      transform: "input.endsWith('.js') || input.endsWith('.ts')"

steps:
  - id: "check_file_type"
    type: "conditional"
    condition: "{{ this.is_python }}"
    then_steps:
      - id: "process_python"
        type: "mcp_call"
        tool: "python_linter"
        parameters:
          file: "{{ this.file_path }}"
    else_steps:
      - id: "check_js"
        type: "conditional"
        condition: "{{ this.is_javascript }}"
        then_steps:
          - id: "process_js"
            type: "mcp_call"
            tool: "eslint"
            parameters:
              file: "{{ this.file_path }}"
```

### Parallel Processing Workflow

```yaml
name: "example:batch-processor"
description: "Process multiple files in parallel"
version: "1.0.0"

default_state:
  state:
    files: []
    results: {}

steps:
  - id: "get_files"
    type: "shell_command"
    command: "find . -name '*.py' -type f"
    state_update:
      path: "this.files"
      value: "stdout.split('\\n').filter(f => f)"
  
  - id: "process_files"
    type: "parallel_foreach"
    items: "{{ this.files }}"
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

### Recent Schema Changes (2025 - Variable Scoping System)

The workflow schema has been completely updated with a new scoped variable system:

1. **New Scoped Variable System** ⚠️ **BREAKING CHANGE**:
   - **`this` scope**: Replaces `state.field` and `computed.field` → use `{{ this.field }}`
   - **`global` scope**: New persistent global variables → use `{{ global.variable }}`
   - **`inputs` scope**: Unchanged input parameters → use `{{ inputs.parameter }}`
   - **`loop` scope**: New automatic loop variables → use `{{ loop.item }}`, `{{ loop.index }}`, `{{ loop.iteration }}`

2. **Migration Required**:
   - `{{ state.field }}` → `{{ this.field }}`
   - `{{ computed.field }}` → `{{ this.field }}`
   - `state_update: { path: "state.field" }` → `state_update: { path: "this.field" }`
   - `from: "state.field"` → `from: "this.field"`

3. **Enhanced Loop Management**: 
   - While loops: `{{ loop.iteration }}` (1-based counter, no initialization needed)
   - Foreach loops: `{{ loop.item }}` and `{{ loop.index }}` (0-based index)
   - Legacy `state.attempt_number` is deprecated

4. **Backward Compatibility**: Legacy syntax still works but shows deprecation warnings. All examples have been updated to use the new scoped syntax.

5. **Validation Updates**: The validator now checks scoped variable references and provides helpful error messages for invalid scope usage.