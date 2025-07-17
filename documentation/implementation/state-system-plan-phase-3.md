# MCP Workflow System Implementation Plan - Phase 3: Control Flow and Advanced Steps

## Phase Overview
Add control flow constructs (conditionals, loops) and advanced step types to enable complex workflow logic. This phase transforms the basic sequential executor into a full workflow engine.

## Objectives
1. Implement conditional execution (if/then/else)
2. Add loop constructs (while, foreach)
3. Support nested control structures
4. Implement break/continue operations
5. Add user input validation

## Components to Implement

### 1. Control Flow Models (`src/aromcp/workflow_server/workflow/control_flow.py`)
```python
@dataclass
class ConditionalStep:
    condition: str  # Expression to evaluate
    then_steps: list[WorkflowStep]
    else_steps: list[WorkflowStep] | None

@dataclass
class WhileLoopStep:
    condition: str
    max_iterations: int
    body: list[WorkflowStep]

@dataclass
class ForEachStep:
    items: str  # Expression returning array
    variable_name: str  # Default: "item"
    body: list[WorkflowStep]
```

### 2. Expression Evaluator (`src/aromcp/workflow_server/workflow/expressions.py`)
- Boolean expression evaluation
- Comparison operators (==, !=, <, >, <=, >=)
- Logical operators (&&, ||, !)
- Property access (dots and brackets)
- Array/string methods (.length, .includes, etc.)

### 3. Execution Context (`src/aromcp/workflow_server/workflow/context.py`)
- Step execution stack
- Loop iteration tracking
- Break/continue handling
- Variable scoping for loops
- Nested structure support

### 4. Advanced Step Processors (`src/aromcp/workflow_server/workflow/steps/`)
- `conditional.py` - Evaluate conditions and choose branch
- `while_loop.py` - Execute loop with iteration limit
- `foreach.py` - Iterate over arrays
- `user_input.py` - Prompt with validation
- `break_continue.py` - Loop control operations

### 5. Enhanced Executor (`src/aromcp/workflow_server/workflow/executor_v2.py`)
- Stack-based execution for nested structures
- Condition evaluation with state context
- Loop state management
- Early exit handling
- Expression result caching

## Acceptance Criteria

### Functional Requirements
1. **Conditional Execution**
   - [ ] Simple conditions evaluate correctly
   - [ ] Complex boolean expressions work
   - [ ] Then branch executes when true
   - [ ] Else branch executes when false
   - [ ] Nested conditionals work properly
   - [ ] Variables in conditions resolve correctly

2. **While Loops**
   - [ ] Loop executes while condition is true
   - [ ] Max iterations limit is enforced
   - [ ] Loop variables update correctly
   - [ ] Break exits the loop early
   - [ ] Nested loops work properly
   - [ ] Infinite loop protection works

3. **ForEach Loops**
   - [ ] Iterates over array values
   - [ ] Item variable is available in body
   - [ ] Index variable is accessible
   - [ ] Works with computed arrays
   - [ ] Handles empty arrays gracefully
   - [ ] Nested foreach works

4. **Expression Evaluation**
   - [ ] Property access works (state.value, state['value'])
   - [ ] Comparison operators work correctly
   - [ ] Logical operators follow precedence
   - [ ] String methods work (.includes, .startsWith)
   - [ ] Array methods work (.length, .filter)
   - [ ] Type coercion follows JavaScript rules

5. **User Input**
   - [ ] Prompts display correctly
   - [ ] Validation patterns work
   - [ ] Error messages show on invalid input
   - [ ] Retry on validation failure
   - [ ] Input stored in state correctly

### Test Requirements
1. **Unit Tests** (`tests/workflow_server/test_control_flow.py`)
   - [ ] Test condition evaluation
   - [ ] Test loop execution
   - [ ] Test break/continue
   - [ ] Test expression parser
   - [ ] Test validation patterns

2. **Integration Tests** (`tests/workflow_server/test_complex_workflows.py`)
   - [ ] Test nested conditionals
   - [ ] Test nested loops
   - [ ] Test condition with computed state
   - [ ] Test foreach with transformations
   - [ ] Test user input flows

3. **Example Validation**
   - [ ] standards:fix workflow executes correctly
   - [ ] While loop with ready_batches works
   - [ ] Conditional file processing works
   - [ ] User input validation works

## Implementation Steps

### Week 1: Expression System
1. Build expression parser and evaluator
2. Support JavaScript-like syntax
3. Integrate with state flattened view
4. Add comprehensive expression tests
5. Handle edge cases and errors

### Week 2: Control Flow Structures
1. Implement conditional step processor
2. Add while loop with safety limits
3. Create foreach iterator
4. Build execution context stack
5. Test nested structures

### Week 3: Integration and Polish
1. Enhance executor for control flow
2. Add break/continue support
3. Implement user input with validation
4. Write complex integration tests
5. Optimize performance

## Success Metrics
- Complex workflows with nested logic execute correctly
- Expression evaluation matches JavaScript behavior
- Loop safety mechanisms prevent infinite loops
- User input validation provides good UX
- Performance remains good with deep nesting

## Dependencies
- Phase 1 & 2 completed
- JavaScript-like expression parser
- Regex library for validation patterns

## Risks and Mitigations
1. **Complex Expression Parsing**
   - Risk: Edge cases in JavaScript compatibility
   - Mitigation: Comprehensive test suite, clear documentation of limitations

2. **Infinite Loops**
   - Risk: Workflows hanging forever
   - Mitigation: Mandatory iteration limits, timeout mechanisms

3. **Deep Nesting Performance**
   - Risk: Stack overflow or slow execution
   - Mitigation: Iteration limits, execution depth limits

## Example Workflow Test
```yaml
name: "test:control-flow"
description: "Test control flow features"

state_schema:
  raw:
    files: array
    process_count: number
  computed:
    needs_processing:
      from: "raw.files"
      transform: "input.filter(f => !f.processed)"

steps:
  - type: "conditional"
    condition: "{{ files.length > 0 }}"
    then:
      - type: "foreach"
        items: "{{ needs_processing }}"
        steps:
          - type: "while"
            condition: "{{ !item.valid && item.attempts < 3 }}"
            body:
              - type: "state_update"
                path: "raw.files[{{ index }}].attempts"
                operation: "increment"
              
              - type: "conditional"
                condition: "{{ item.type == 'typescript' }}"
                then:
                  - type: "mcp_call"
                    method: "check_typescript"
                    params:
                      files: ["{{ item.path }}"]
    else:
      - type: "user_message"
        message: "No files to process"
```

## MCP Protocol Updates
The `workflow.get_next_step` response now includes expanded control flow information:
```typescript
{
  step: {
    id: "process_loop.condition",
    type: "conditional",
    instructions: "Condition evaluated to true by MCP. Execute then branch.",
    definition: {
      condition_result: true,
      original_condition: "files.length > 0",
      evaluated_values: {
        "files.length": 5
      }
    }
  }
}
```

## Next Phase Preview
Phase 4 will add:
- Parallel execution (parallel_foreach)
- Sub-agent task delegation
- Workflow composition (include_workflow)
- Advanced error handling