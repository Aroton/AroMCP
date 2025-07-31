# MCP Workflow System Implementation Plan - Phase 2: Workflow Loading and Basic Execution

## Phase Overview
Build the workflow definition system and implement basic sequential workflow execution. This phase establishes workflow loading, parsing, and simple step execution without complex control flow.

## Objectives
1. Implement workflow YAML loading with name-based resolution
2. Parse and validate workflow definitions
3. Create workflow execution engine for sequential steps
4. Implement basic MCP workflow management tools
5. Support simple state updates and MCP calls

## Components to Implement

### 1. Workflow Models (`src/aromcp/workflow_server/workflow/models.py`)
```python
@dataclass
class WorkflowDefinition:
    name: str
    description: str
    version: str
    default_state: dict[str, Any]
    state_schema: StateSchema
    inputs: dict[str, InputDefinition]
    steps: list[WorkflowStep]
    sub_agent_tasks: dict[str, SubAgentTask]
    loaded_from: str  # File path where loaded
    source: str       # "project" | "global"

@dataclass
class WorkflowStep:
    id: str
    type: str  # "mcp_call" | "state_update" | "user_message" | "shell_command"
    definition: dict[str, Any]
```

### 2. Workflow Loader (`src/aromcp/workflow_server/workflow/loader.py`)
- Name-based resolution (.aromcp/workflows/{name}.yaml, ~/.aromcp/workflows/{name}.yaml)
- YAML parsing with validation
- Import resolution for shared workflows
- Schema validation
- Error reporting with file locations

### 3. Execution Engine (`src/aromcp/workflow_server/workflow/executor.py`)
- Workflow instance management
- Sequential step execution
- Variable replacement in step definitions
- Step completion tracking
- Basic error handling

### 4. Step Processors (`src/aromcp/workflow_server/workflow/steps/`)
- `shell_command.py` - Execute commands internally
- `state_update.py` - Update workflow state
- `mcp_call.py` - Call MCP tools
- `user_message.py` - Format messages for display

### 5. MCP Tools (`src/aromcp/workflow_server/tools/workflow_tools.py`)
```python
@mcp.tool
@json_convert
def workflow_get_info(workflow: str) -> dict[str, Any]:
    """Get workflow metadata and input requirements"""

@mcp.tool
@json_convert
def workflow_start(workflow: str, inputs: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Initialize and start a workflow instance"""

@mcp.tool
@json_convert
def workflow_list(include_global: bool = True) -> dict[str, Any]:
    """List available workflows"""

@mcp.tool
@json_convert
def workflow_get_next_step(workflow_id: str) -> dict[str, Any]:
    """Get next atomic step to execute"""

@mcp.tool
@json_convert
def workflow_step_complete(workflow_id: str, step_id: str, status: str = "success") -> dict[str, Any]:
    """Mark a step as complete"""
```

## Acceptance Criteria

### Functional Requirements
1. **Workflow Loading**
   - [ ] Workflows load from project directory first (.aromcp/workflows/)
   - [ ] Falls back to user directory (~/.aromcp/workflows/)
   - [ ] Clear error when workflow not found
   - [ ] YAML syntax errors reported with line numbers
   - [ ] Workflow names follow convention (category:action)

2. **Workflow Parsing**
   - [ ] Default state values are parsed correctly
   - [ ] State schema with computed fields is validated
   - [ ] Input definitions are validated
   - [ ] Steps are parsed into executable format
   - [ ] Invalid step types are rejected

3. **Workflow Execution**
   - [ ] workflow.start initializes state with defaults
   - [ ] workflow.get_next_step returns sequential steps
   - [ ] Variables are replaced before returning steps
   - [ ] Step completion advances to next step
   - [ ] Workflow completes when no steps remain

4. **Step Types (Basic)**
   - [ ] shell_command executes internally and updates state
   - [ ] state_update modifies raw state values
   - [ ] mcp_call parameters are properly formatted
   - [ ] user_message interpolates variables
   - [ ] All steps return consistent atomic format

5. **State Integration**
   - [ ] Default state initializes on workflow.start
   - [ ] State updates trigger transformations
   - [ ] Computed values available in variable replacement
   - [ ] State persists across step executions

### Test Requirements
1. **Unit Tests** (`tests/workflow_server/test_workflow_loader.py`)
   - [ ] Test workflow file resolution
   - [ ] Test YAML parsing
   - [ ] Test validation errors
   - [ ] Test import resolution

2. **Integration Tests** (`tests/workflow_server/test_basic_execution.py`)
   - [ ] Test simple sequential workflow
   - [ ] Test state updates and transformations
   - [ ] Test variable replacement
   - [ ] Test all basic step types

3. **Example Validation**
   - [ ] Simple command + transform example works
   - [ ] Basic state updates trigger computed fields
   - [ ] User messages show interpolated values

## Implementation Steps

### Week 1: Models and Loading
1. Define workflow model classes
2. Implement workflow loader with name resolution
3. Add YAML parsing and validation
4. Create workflow registry
5. Write unit tests for loading

### Week 2: Basic Execution Engine
1. Implement workflow instance manager
2. Create sequential step executor
3. Add variable replacement system
4. Implement step completion tracking
5. Add integration with state manager

### Week 3: Step Processors and MCP Tools
1. Implement all basic step processors
2. Create MCP tool wrappers
3. Add comprehensive error handling
4. Write integration tests
5. Validate against examples

## Success Metrics
- All unit tests pass with good coverage
- Simple sequential workflows execute correctly
- State integration works seamlessly
- Clear error messages for common mistakes
- Examples from documentation run successfully

## Dependencies
- Phase 1 completed (State Engine)
- YAML parsing library (PyYAML)
- Command execution library (subprocess)
- Existing MCP infrastructure

## Risks and Mitigations
1. **Complex YAML Structures**
   - Risk: Difficult to validate nested configurations
   - Mitigation: Use schema validation library, clear error messages

2. **Shell Command Security**
   - Risk: Arbitrary command execution
   - Mitigation: Command validation, sandboxing considerations

3. **State Synchronization**
   - Risk: State updates not properly synchronized
   - Mitigation: Atomic operations, proper locking

## Example Workflow Test
```yaml
name: "test:simple"
description: "Test basic sequential execution"

default_state:
  raw:
    counter: 0
    message: ""

state_schema:
  computed:
    doubled:
      from: "raw.counter"
      transform: "input * 2"

steps:
  - type: "state_update"
    path: "raw.counter"
    value: 5
    
  - type: "user_message"
    message: "Counter is {{ counter }}, doubled is {{ doubled }}"
    
  - type: "shell_command"
    command: "echo 'Hello from workflow'"
    state_update:
      path: "raw.message"
```

## Next Phase Preview
Phase 3 will add:
- Conditional execution (if/then/else)
- Loop constructs (while, foreach)
- Complex variable expressions
- Error handling strategies