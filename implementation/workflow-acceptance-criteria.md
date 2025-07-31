# MCP Workflow System Acceptance Criteria

## Overview
This document defines the acceptance criteria for the MCP Workflow System implementation, focusing on validation, execution, and documentation as primary priorities. The system should work reliably while minimizing AI token usage through efficient state management and clear error reporting.

## 1. Core Validation & Schema Compliance

### 1.1 Schema Validation
- **MUST** validate all workflows against the JSON schema defined in `.aromcp/workflows/schema.json`
- **MUST** provide both strict schema-only validation and enhanced validation with helpful error messages
- **MUST** automatically discover and load schema from standard locations

### 1.2 Required Fields
- **MUST** enforce presence of all required top-level fields: `name`, `description`, `version`, `steps`
- **MUST** validate field formats:
  - `name`: Must follow "namespace:name" pattern
  - `version`: Must follow semantic versioning (e.g., "1.0.0")
  - `steps`: Must be non-empty array

### 1.3 Error Reporting
- **MUST** provide clear, actionable error messages with exact paths (e.g., "steps[2].then_steps[0]")
- **MUST** include "Did you mean?" suggestions for undefined variable references
- **MUST** distinguish between errors (blocking) and warnings (non-blocking)

## 2. State Management & Variable Resolution

### 2.1 State Hierarchy
- **MUST** support three-tier state model:
  - `state`: Mutable workflow state
  - `inputs`: Read-only input parameters
  - `computed`: Automatically derived values
- **MUST** remove deprecated `raw` namespace entirely

### 2.2 Variable References
- **MUST** validate all variable references resolve to defined values
- **MUST** support template syntax: `{{ expression }}`
- **MUST** validate references in correct context:
  - `item` only valid in foreach loops
  - `loop.index` only valid in loop contexts
  - State paths must exist in `default_state` or be created by prior steps

### 2.3 Computed Fields
- **MUST** support JavaScript expressions for transformations
- **MUST** handle dependencies correctly (single value or array)
- **MUST** prevent circular dependencies
- **MUST** support error handling strategies: `use_fallback`, `propagate`, `ignore`

## 3. Step Execution & Control Flow

### 3.1 Step Types
- **MUST** support all defined step types:
  - Client-executed: `user_message`, `mcp_call`, `user_input`, `agent_prompt`, `agent_response`, `parallel_foreach`
  - Server-executed: `shell_command`
  - Control flow: `conditional`, `while_loop`, `foreach`, `break`, `continue`
- **MUST** remove deprecated `state_update` and `batch_state_update` step types

### 3.2 Control Flow Execution
- **MUST** properly scope variables within control structures
- **MUST** support nested control structures
- **MUST** enforce `break`/`continue` only within loop contexts
- **MUST** automatically manage `attempt_number` counter for while loops

### 3.3 State Updates
- **MUST** support embedded state updates within steps using `state_update` or `state_updates` fields
- **MUST** support update operations: `set`, `increment`, `decrement`, `append`, `multiply`
- **MUST** validate state paths exist before updates

## 4. Client-Server Execution Model

### 4.1 Execution Context
- **MUST** categorize steps correctly as client or server executed
- **MUST** support `execution_context` only on `shell_command` steps ("client" or "server")
- **MUST** pass client-executed steps to AI agent for processing

### 4.2 Agent Communication
- **MUST** support bi-directional communication through `agent_prompt` and `agent_response`
- **MUST** validate agent responses against defined schemas
- **MUST** handle response validation failures according to retry settings

## 5. Error Handling & Recovery

### 5.1 Error Strategies
- **MUST** implement error handling strategies per step:
  - `retry`: Retry up to max_retries
  - `continue`: Continue workflow despite error
  - `fail`: Stop workflow execution
  - `fallback`: Use fallback value

### 5.2 Validation Failures
- **MUST** provide detailed validation errors before execution
- **MUST** fail fast on invalid workflow definitions
- **MUST** include diagnostic information for debugging

## 6. Sub-Agent Task Management

### 6.1 Task Definition
- **MUST** support sub-agent tasks with either `prompt_template` or `steps`
- **MUST** validate sub-agent task references in `parallel_foreach`
- **MUST** support passing inputs to sub-agents from foreach items

### 6.2 State Isolation
- **MUST** maintain isolated state contexts for sub-agents
- **MUST** prevent sub-agent state from affecting parent workflow
- **MUST** properly collect and return sub-agent results

### 6.3 Context Variables
- **MUST** provide context variables to sub-agents:
  - `item`: Current item being processed
  - `index`: Current item index
  - `total`: Total number of items

## 7. Performance & Token Optimization

### 7.1 Token Efficiency
- **MUST** minimize token usage through efficient state representation
- **MUST** avoid redundant state in error messages
- **MUST** use concise progress reporting

### 7.2 Resource Limits
- **MUST** enforce `max_iterations` on loops
- **MUST** respect `max_parallel` limits on parallel execution

## 8. Documentation & Developer Experience

### 8.1 Validation Messages
- **MUST** provide helpful error messages with examples
- **MUST** suggest corrections for common mistakes
- **MUST** clearly indicate deprecated features have been removed

### 8.2 Workflow Documentation
- **MUST** validate workflows match documented schema
- **MUST** support all examples in workflows/README.md
- **MUST** provide clear execution flow for debugging

## Acceptance Test Scenarios

### Scenario 1: Basic Workflow Execution
- Create a simple linear workflow with user messages and state updates
- Verify all steps execute in order
- Confirm state updates are applied correctly

### Scenario 2: Complex Control Flow
- Create workflow with nested conditionals and loops
- Include break/continue statements
- Verify proper variable scoping and flow control

### Scenario 3: Sub-Agent Parallel Processing
- Create workflow using parallel_foreach with sub-agent tasks
- Verify state isolation between sub-agents
- Confirm results are properly collected

### Scenario 4: Error Handling
- Create workflow with intentional failures
- Test each error handling strategy
- Verify appropriate error messages and recovery

### Scenario 5: State Management
- Create workflow with complex computed fields
- Test dependency updates and transformations
- Verify no circular dependencies

### Scenario 6: Validation Edge Cases
- Test workflows with missing required fields
- Test invalid variable references
- Verify helpful error messages with suggestions

## Success Criteria

1. All test scenarios pass without errors
2. Validation provides clear, actionable error messages
3. Token usage is minimized through efficient state management
4. No deprecated features remain in the system
5. All examples in documentation execute successfully