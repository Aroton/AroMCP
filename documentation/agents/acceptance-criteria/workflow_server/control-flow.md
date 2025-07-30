# Acceptance Criteria: Control Flow
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The control flow system implements conditional branching, loop constructs, and flow control statements that enable complex workflow logic. It supports conditional execution, while loops, foreach loops, and break/continue statements with proper nesting and context management.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises conditional steps for branch logic based on command results, demonstrating basic control flow patterns
**Current Test Coverage**: 
- `test_control_flow_implementation.py` - comprehensive control flow logic testing
- `test_acceptance_scenario_2_complex_control_flow.py` - complex nested control flow scenarios
- `test_while_loop_condition_fix.py` - while loop condition handling
**Key Implementation Files**: 
- `src/aromcp/workflow_server/workflow/steps/conditional.py` - conditional branching logic
- `src/aromcp/workflow_server/workflow/steps/while_loop.py` - while loop implementation
- `src/aromcp/workflow_server/workflow/steps/foreach.py` - foreach loop implementation
- `src/aromcp/workflow_server/workflow/steps/break.py` - break statement handling
- `src/aromcp/workflow_server/workflow/steps/continue.py` - continue statement handling
**Identified Gaps**: Missing nested loop break/continue handling, infinite loop detection improvements

## Acceptance Criteria

### Feature: Conditional Branching

#### AC-CF-001: Conditional expressions are evaluated correctly
**Given**: A conditional step with boolean condition expression
**When**: The condition is evaluated using JavaScript expression engine
**Then**: Condition must be evaluated to true or false with proper state variable access

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_conditional_evaluation
- ✓ Covered by: test_acceptance_scenario_2_complex_control_flow.py::test_complex_conditionals

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:34-56

#### AC-CF-002: Then-branch executes when condition is true
**Given**: A conditional step with condition evaluating to true
**When**: The conditional step is processed
**Then**: Steps in then_steps array must be executed in order

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_then_branch_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:78-95

#### AC-CF-003: Else-branch executes when condition is false
**Given**: A conditional step with condition evaluating to false
**When**: The conditional step is processed
**Then**: Steps in else_steps array must be executed in order

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_else_branch_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:112-129

#### AC-CF-004: Nested conditional structures are supported
**Given**: Conditional steps containing other conditional steps in then_steps or else_steps
**When**: Nested conditionals are processed
**Then**: Proper nesting behavior must be maintained with correct evaluation order

**Test Coverage**:
- ✓ Covered by: test_acceptance_scenario_2_complex_control_flow.py::test_nested_conditionals

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:145-172

#### AC-CF-005: Condition evaluation errors are handled gracefully
**Given**: A conditional step with invalid or failing condition expression
**When**: Condition evaluation is attempted
**Then**: Appropriate error handling must be applied with clear error messages

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_condition_evaluation_errors

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:189-211

---

### Feature: While Loop Implementation

#### AC-CF-006: While loop condition is evaluated before each iteration
**Given**: A while_loop step with condition expression
**When**: The loop is executed
**Then**: Condition must be evaluated before each iteration to determine continuation

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_while_loop_condition_evaluation
- ✓ Covered by: test_while_loop_condition_fix.py::test_condition_reevaluation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:45-67

#### AC-CF-007: While loop body executes when condition is true
**Given**: A while_loop with condition evaluating to true
**When**: Loop iteration is processed
**Then**: Steps in body array must be executed in defined order

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_while_loop_body_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:89-111

#### AC-CF-008: While loop terminates when condition becomes false
**Given**: A while_loop where condition changes from true to false
**When**: Condition is reevaluated
**Then**: Loop execution must terminate and continue with next step

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_while_loop_termination

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:134-151

#### AC-CF-009: While loop respects max_iterations safety limit
**Given**: A while_loop with max_iterations configuration (default: 100)
**When**: Loop executes for more than max_iterations
**Then**: Loop must terminate safely with appropriate warning or error

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_max_iterations_limit

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:167-189

#### AC-CF-010: While loop provides iteration variable in context
**Given**: A while_loop executing with multiple iterations
**When**: Loop body steps access loop context
**Then**: loop.iteration variable must be available with current iteration count

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_while_loop_iteration_context

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:203-225

---

### Feature: Foreach Loop Implementation

#### AC-CF-011: Foreach evaluates items expression to generate array
**Given**: A foreach step with items expression referencing state data
**When**: The loop is initialized
**Then**: Items expression must be evaluated to generate array of work items

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_foreach_items_evaluation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/foreach.py:34-56

#### AC-CF-012: Foreach creates loop context with item variables
**Given**: A foreach loop processing array elements
**When**: Each iteration is processed
**Then**: Loop context must include item, index, and iteration variables

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_foreach_context_variables

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/foreach.py:78-100

#### AC-CF-013: Foreach supports custom variable_name for current item
**Given**: A foreach step with custom variable_name configuration
**When**: Loop body steps access current item
**Then**: Current item must be available using specified variable name (default: "item")

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_foreach_custom_variable_name

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/foreach.py:123-145

#### AC-CF-014: Foreach executes body steps for each array element
**Given**: A foreach loop with array of items and body steps
**When**: The loop is processed
**Then**: Body steps must be executed once for each array element in order

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_foreach_body_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/foreach.py:167-189

#### AC-CF-015: Nested foreach structures are supported
**Given**: Foreach loops containing other foreach loops in body steps
**When**: Nested loops are processed
**Then**: Proper nesting behavior must be maintained with correct context isolation

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_nested_foreach_loops

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/foreach.py:203-235

---

### Feature: Flow Control Statements

#### AC-CF-016: Break statement exits current loop immediately
**Given**: A break statement within a loop context (while_loop or foreach)
**When**: The break statement is executed
**Then**: Current loop execution must terminate and resume after loop construct

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_break_statement_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/break.py:23-45

#### AC-CF-017: Break statement works in both while_loop and foreach contexts
**Given**: Break statements used within different loop types
**When**: Break is executed in each context
**Then**: Appropriate loop termination must occur regardless of loop type

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_break_in_different_loop_types

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/break.py:67-89

#### AC-CF-018: Break outside loop context generates appropriate error
**Given**: A break statement used outside any loop context
**When**: The break statement is encountered
**Then**: Clear error message must be provided indicating invalid break usage

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_break_outside_loop_error

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/break.py:103-125

#### AC-CF-019: Continue statement skips remaining steps in current iteration
**Given**: A continue statement within a loop iteration
**When**: The continue statement is executed
**Then**: Remaining steps in current iteration must be skipped, continuing with next iteration

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_continue_statement_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/continue.py:34-56

#### AC-CF-020: Continue statement works in both while_loop and foreach contexts
**Given**: Continue statements used within different loop types
**When**: Continue is executed in each context
**Then**: Appropriate iteration skipping must occur regardless of loop type

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_continue_in_different_loop_types

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/continue.py:78-100

#### AC-CF-021: Continue outside loop context generates appropriate error
**Given**: A continue statement used outside any loop context
**When**: The continue statement is encountered
**Then**: Clear error message must be provided indicating invalid continue usage

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_continue_outside_loop_error

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/continue.py:123-145

---

### Feature: Advanced Control Flow Scenarios

#### AC-CF-022: Nested loop break/continue affects only innermost loop
**Given**: Nested loops with break/continue statements in inner loop
**When**: Break or continue is executed
**Then**: Only the innermost loop must be affected, outer loops continue normally

**Test Coverage**:
- ✗ Missing: Nested loop break/continue handling tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/break.py:167-189

#### AC-CF-023: Infinite loop conditions are detected and handled
**Given**: While loops with conditions that never become false
**When**: Max iterations limit is reached
**Then**: Loop must be terminated safely with detailed diagnostic information

**Test Coverage**:
- ✗ Missing: Enhanced infinite loop detection tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/while_loop.py:234-256

#### AC-CF-024: Control flow works correctly with state updates
**Given**: Loops and conditionals that modify workflow state
**When**: State updates occur within control flow constructs
**Then**: State changes must be properly applied and visible to subsequent iterations/conditions

**Test Coverage**:
- ✓ Covered by: test_control_flow_implementation.py::test_control_flow_with_state_updates

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/conditional.py:267-289

## Integration Points
- **Variable Resolution**: Uses variable resolution system for condition and expression evaluation in control flow
- **State Management**: Accesses and modifies workflow state within control flow contexts
- **Step Processing**: Delegates execution of body steps and branch steps to step processors
- **Workflow Execution Engine**: Coordinates with workflow engine for proper control flow execution order

## Schema Compliance
Governed by workflow schema sections:
- `$.definitions.conditional_step` - Conditional branching step specification
- `$.definitions.while_loop_step` - While loop step configuration
- `$.definitions.foreach_step` - Foreach loop step specification
- `$.definitions.break_step` - Break statement specification
- `$.definitions.continue_step` - Continue statement specification