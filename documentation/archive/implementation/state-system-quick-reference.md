# MCP Workflow System - Quick Reference Guide

## Key Architecture Decisions

### State Management
- **Three-tier model**: raw (writable), computed (derived), state (legacy)
- **Flattened reading**: Agents see unified view
- **Explicit writing**: Must use "raw." or "state." prefixes
- **Reactive updates**: Changes cascade automatically

### Workflow Execution
- **MCP controls flow**: All conditionals, loops evaluated server-side
- **Agents execute atomically**: Each step is immediately executable
- **Shell commands internal**: MCP executes most bash commands internally
- **Parallel via delegation**: Sub-agents handle parallel work

### File Organization
```
.aromcp/workflows/{name}.yaml    # Project-specific (checked first)
~/.aromcp/workflows/{name}.yaml  # User global (fallback)
```

## Common Code Patterns

### MCP Tool Definition
```python
@mcp.tool
@json_convert  # ALWAYS use for list/dict parameters
def workflow_tool(
    workflow: str,
    inputs: dict[str, Any] | str | None = None  # Union type required!
) -> dict[str, Any]:
    """Tool description"""
    return {"data": result}  # or {"error": {"code": "ERROR", "message": "..."}}
```

### State Update Patterns
```python
# Reading state (flattened)
state = manager.read(workflow_id)
value = state["my_field"]  # No prefix needed

# Writing state (explicit paths)
manager.update(workflow_id, [
    {"path": "raw.my_field", "value": 10},      # OK
    {"path": "computed.field", "value": 5}      # ERROR!
])
```

### Workflow Step Types
```yaml
# Executed by MCP internally
- type: "shell_command"
  command: "git status"
  
# Executed by agent (rare)
- type: "agent_shell_command"
  command: "./interactive.sh"
  reason: "Requires TTY"

# Other agent-executed types
- type: "mcp_call"
- type: "state_update"
- type: "user_input"
- type: "parallel_tasks"
```

## State Schema Syntax

### Basic Computed Field
```yaml
computed:
  double_value:
    from: "raw.value"
    transform: "input * 2"
```

### Multiple Dependencies
```yaml
computed:
  summary:
    from: ["raw.count", "raw.total"]
    transform: |
      {
        average: input[1] / input[0],
        formatted: `${input[0]} items, total ${input[1]}`
      }
```

### Error Handling
```yaml
computed:
  safe_parse:
    from: "raw.json_string"
    transform: "JSON.parse(input)"
    on_error: "use_fallback"
    fallback: {}
```

## Control Flow Patterns

### Conditional (MCP evaluates)
```yaml
- type: "conditional"
  condition: "{{ file_count > 0 }}"  # Flattened path
  then:
    - type: "state_update"
  else:
    - type: "user_message"
```

### While Loop (MCP controls)
```yaml
- type: "while"
  condition: "{{ !is_complete }}"
  max_iterations: 50
  body:
    - type: "state_update"
```

### Parallel Tasks (Agent delegates)
```yaml
- type: "parallel_foreach"
  items: "{{ ready_batches }}"
  max_parallel: 10
  sub_agent_task: "process_batch"
  # Uses MCP standard prompt automatically
```

## Variable Resolution

### In Workflow YAML
```yaml
# Flattened paths for reading
message: "Count is {{ counter }}"  # Not {{ raw.counter }}
condition: "{{ is_ready }}"        # Not {{ computed.is_ready }}

# Full paths for writing
state_update:
  path: "raw.counter"              # Must specify tier
```

### What Agents Receive
```javascript
// Variables already replaced
{
  step: {
    id: "show_message",
    type: "user_message",
    definition: {
      message: "Count is 5"  // {{ counter }} replaced
    }
  }
}
```

## Error Response Format

### Success
```json
{
  "data": {
    "workflow_id": "wf_123",
    "state": {...}
  }
}
```

### Error
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Workflow 'missing:flow' not found"
  }
}
```

## Common Error Codes
- `INVALID_INPUT`: Parameter validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Security check failed
- `OPERATION_FAILED`: Operation failed to complete
- `TIMEOUT`: Operation timed out

## JavaScript Expression Rules

### Supported
- Property access: `user.name`, `items[0]`
- Operators: `+`, `-`, `*`, `/`, `%`
- Comparisons: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Logical: `&&`, `||`, `!`
- Ternary: `condition ? true_val : false_val`
- Template literals: `` `Hello ${name}` ``
- Array methods: `.filter()`, `.map()`, `.reduce()`
- String methods: `.includes()`, `.split()`, `.trim()`

### Not Supported
- Function declarations
- Async/await
- Import/require
- Global access (except allowed: JSON, Math)

## Testing Patterns

### Test Structure
```python
# Given - Arrange
state = {"value": 5}
transform = "input * 2"

# When - Act
result = transformer.execute(transform, state["value"])

# Then - Assert
assert result == 10
```

### Mock MCP Tools
```python
@patch('aromcp.workflow_server.tools.mcp')
def test_workflow_start(mock_mcp):
    mock_mcp.tool.return_value = lambda f: f
    # Test tool implementation
```

## Performance Guidelines

### State Updates
- Batch updates when possible
- Use atomic operations
- Minimize transformation chains

### Parallel Execution
- Default max_parallel: 10
- Consider state size with many agents
- Use checkpoints for long workflows

### Memory Management
- State size limits: ~10MB recommended
- Checkpoint large states periodically
- Clean up completed workflow state

## Security Considerations

### Path Validation
- Always validate file paths
- Prevent directory traversal
- Use project root constraints

### Command Execution
- Whitelist allowed commands
- Validate command arguments
- Consider sandboxing

### State Isolation
- Sub-agents see filtered state
- Tenant isolation in production
- Audit state access

## Debugging Tips

### Enable Trace Mode
```python
result = workflow.trace_transformations(
    workflow_id="wf_123",
    include_timing=True
)
```

### Check Dependencies
```python
deps = workflow_state.dependencies(
    workflow_id="wf_123",
    field="computed.summary"
)
print(f"Depends on: {deps['all_deps']}")
```

### Test Transformations
```python
result = workflow.test_transformation(
    transform="input.filter(x => x > 5)",
    input=[1, 5, 10, 3, 8]
)
# Returns: {"output": [10, 8], "execution_time_ms": 0.5}
```

## Common Gotchas

1. **Forgetting @json_convert**: Tool fails with "invalid type"
2. **Wrong state path**: Using "counter" instead of "raw.counter" for writes
3. **Missing union types**: Using `list[str]` instead of `list[str] | str`
4. **Circular dependencies**: Computed fields depending on each other
5. **Infinite loops**: Forgetting max_iterations on while loops

## Phase Implementation Order

1. **State Engine** → 2. **Basic Execution** → 3. **Control Flow** → 
4. **Parallel** → 5. **Error Handling** → 6. **Advanced Features**

**Don't skip phases!** Each builds on the previous.