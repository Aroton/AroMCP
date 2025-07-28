# Acceptance Criteria: Sub-Agent Management
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The sub-agent management system orchestrates parallel execution of sub-agent tasks, manages isolated state contexts, and coordinates communication between main workflow and sub-agent instances. It enables scalable parallel processing while maintaining data isolation and result aggregation.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises basic sub-agent concepts but does not use parallel_foreach - more complex parallel processing remains untested in production
**Current Test Coverage**: 
- `test_complete_subagent_flow.py` - end-to-end sub-agent task execution
- `test_parallel_execution.py` - parallel processing coordination
- `test_serial_debug_mode.py` - serial debug mode behavior
- `test_subagent_state_isolation.py` - state isolation validation
**Key Implementation Files**: 
- `src/aromcp/workflow_server/workflow/subagent_manager.py` - sub-agent coordination
- `src/aromcp/workflow_server/workflow/steps/parallel_foreach.py` - parallel execution logic
- `src/aromcp/workflow_server/state/manager.py` - isolated state context management
**Identified Gaps**: Missing sub-agent timeout handling, error aggregation across parallel instances, resource management

## Acceptance Criteria

### Feature: Sub-Agent Task Definitions

#### AC-SAM-001: Sub-agent tasks are properly parsed and validated
**Given**: A workflow with sub_agent_tasks definitions
**When**: The workflow is loaded
**Then**: Task definitions must be validated for required fields (description, inputs, steps/prompt_template)

**Test Coverage**:
- ✓ Covered by: test_complete_subagent_flow.py::test_task_definition_parsing
- ✓ Covered by: test_subagent_manager_prompts.py::test_task_validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:45-67

#### AC-SAM-002: Task input definitions support proper typing
**Given**: A sub-agent task with input parameter definitions
**When**: Task inputs are validated
**Then**: Input types (string, number, boolean, object, array) must be validated correctly

**Test Coverage**:
- ✓ Covered by: test_complete_subagent_flow.py::test_task_input_validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:89-111

#### AC-SAM-003: Task default_state initialization works correctly
**Given**: A sub-agent task with default_state configuration
**When**: Sub-agent contexts are created
**Then**: Default state values must be properly initialized in each sub-agent instance

**Test Coverage**:
- ✓ Covered by: test_complete_subagent_flow.py::test_default_state_initialization

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:134-156

#### AC-SAM-004: Task state_schema supports computed fields
**Given**: A sub-agent task with state_schema containing computed field definitions
**When**: Sub-agent execution processes computed fields
**Then**: Computed field transformations must be applied within sub-agent context

**Test Coverage**:
- ✓ Covered by: test_complete_subagent_flow.py::test_computed_field_processing

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:178-205

#### AC-SAM-005: Both step-based and prompt-based task definitions are supported
**Given**: Sub-agent tasks defined with either explicit steps or prompt_template
**When**: Tasks are executed
**Then**: Both definition types must be processed correctly with appropriate context

**Test Coverage**:
- ✓ Covered by: test_complete_subagent_flow.py::test_step_vs_prompt_based_tasks

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:234-267

---

### Feature: Parallel Sub-Agent Execution

#### AC-SAM-006: Isolated state contexts are created for each sub-agent
**Given**: A parallel_foreach step with multiple work items
**When**: Sub-agents are created for parallel execution
**Then**: Each sub-agent must have completely isolated state context

**Test Coverage**:
- ✓ Covered by: test_subagent_state_isolation.py::test_context_isolation
- ✓ Covered by: test_parallel_execution.py::test_isolated_contexts

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:289-311

#### AC-SAM-007: Concurrent execution respects max_parallel limits
**Given**: A parallel_foreach step with max_parallel configuration
**When**: More work items exist than max_parallel allows
**Then**: Execution must be throttled to respect the concurrency limit

**Test Coverage**:
- ✓ Covered by: test_parallel_execution.py::test_max_parallel_throttling

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:345-367

#### AC-SAM-008: Sub-agent status and completion are tracked
**Given**: Multiple sub-agents executing in parallel
**When**: Sub-agents complete or fail
**Then**: Status tracking must accurately reflect completion state across all instances

**Test Coverage**:
- ✓ Covered by: test_parallel_execution.py::test_status_tracking

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:389-411

#### AC-SAM-009: Sub-agent results are collected and aggregated
**Given**: Sub-agents completing with results
**When**: All sub-agents finish execution
**Then**: Results must be collected and aggregated back to main workflow state

**Test Coverage**:
- ✓ Covered by: test_parallel_execution.py::test_result_aggregation

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:434-456

#### AC-SAM-010: Sub-agent timeouts are handled gracefully
**Given**: A parallel_foreach step with timeout_seconds configuration
**When**: Individual sub-agents exceed timeout limits
**Then**: Timeouts must be handled gracefully without affecting other sub-agents

**Test Coverage**:
- ✗ Missing: Sub-agent timeout handling tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:478-505

---

### Feature: Serial Debug Mode

#### AC-SAM-011: Serial debug mode converts parallel to sequential execution
**Given**: A parallel_foreach step with AROMCP_WORKFLOW_DEBUG=serial environment variable
**When**: The step is executed
**Then**: Execution must be sequential while maintaining identical behavior to parallel mode

**Test Coverage**:
- ✓ Covered by: test_serial_debug_mode.py::test_parallel_to_serial_conversion

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/parallel_foreach.py:67-89

#### AC-SAM-012: Debug mode provides agent instructions for serial execution
**Given**: Serial debug mode is active
**When**: Sub-agent contexts are created
**Then**: Debug hint must be provided: "DO NOT create subtasks - execute all work in main thread"

**Test Coverage**:
- ✓ Covered by: test_serial_debug_mode.py::test_debug_agent_instructions

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:567-589

#### AC-SAM-013: Serial mode maintains identical state updates and results
**Given**: The same workflow executed in both parallel and serial modes
**When**: Both executions complete
**Then**: Final workflow state and outputs must be identical between modes

**Test Coverage**:
- ✓ Covered by: test_serial_debug_mode.py::test_behavioral_consistency

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/parallel_foreach.py:112-145

#### AC-SAM-014: Serial mode processes items with same isolated context per item
**Given**: Serial debug mode execution
**When**: Each work item is processed
**Then**: Same isolated state context must be maintained per item as in parallel mode

**Test Coverage**:
- ✓ Covered by: test_serial_debug_mode.py::test_context_isolation_consistency

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:612-634

#### AC-SAM-015: Serial mode applies same timeout and limits for consistency
**Given**: Serial debug mode with timeout_seconds and max_parallel settings
**When**: Items are processed sequentially
**Then**: Same timeout and limit configurations must be applied for testing consistency

**Test Coverage**:
- ✓ Covered by: test_serial_debug_mode.py::test_timeout_limit_consistency

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/parallel_foreach.py:167-189

---

### Feature: Sub-Agent Communication

#### AC-SAM-016: Data passing from main workflow to sub-agents works
**Given**: A parallel_foreach step with task inputs from main workflow state
**When**: Sub-agents are created
**Then**: Task input data must be properly passed from main workflow to sub-agent contexts

**Test Coverage**:
- ✓ Covered by: test_subagent_state_updates.py::test_data_passing_to_subagents

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:656-678

#### AC-SAM-017: Sub-agent state updates don't affect other instances
**Given**: Multiple sub-agents with isolated state contexts
**When**: One sub-agent modifies its state
**Then**: State changes must not affect other sub-agent instances or main workflow

**Test Coverage**:
- ✓ Covered by: test_subagent_state_isolation.py::test_state_update_isolation

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:701-723

#### AC-SAM-018: Sub-agent prompt templates support variable substitution
**Given**: Sub-agent tasks with prompt_template containing variable placeholders
**When**: Sub-agents are created with task contexts
**Then**: Variable substitution must be applied using sub-agent's isolated state

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_prompt_template_substitution

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:745-767

#### AC-SAM-019: Sub-agent status tracking and monitoring works
**Given**: Sub-agents executing with various completion states
**When**: Status is queried during execution
**Then**: Accurate status information must be provided for monitoring capabilities

**Test Coverage**:
- ✗ Missing: Comprehensive sub-agent monitoring tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:789-811

---

### Feature: Error Handling and Resource Management

#### AC-SAM-020: Sub-agent failures are handled without affecting others
**Given**: Multiple sub-agents executing where some fail
**When**: Individual sub-agents encounter errors
**Then**: Failures must be isolated and not affect other sub-agent execution

**Test Coverage**:
- ✗ Missing: Sub-agent failure isolation tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:834-856

#### AC-SAM-021: Resource cleanup occurs after sub-agent completion
**Given**: Sub-agents that have completed execution
**When**: All sub-agents finish (successfully or with failure)
**Then**: Proper resource cleanup must be performed for all sub-agent contexts

**Test Coverage**:
- ✗ Missing: Resource management and cleanup tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/subagent_manager.py:878-895

## Integration Points
- **Workflow Execution Engine**: Receives parallel_foreach steps from workflow engine and coordinates sub-agent execution
- **State Management**: Creates isolated state contexts for sub-agents and manages result aggregation
- **Step Processing**: Delegates individual step execution within sub-agent contexts to step processors
- **Error Handling**: Coordinates with error handling system for sub-agent-level error recovery

## Schema Compliance
Governed by workflow schema sections:
- `$.properties.sub_agent_tasks` - Sub-agent task definitions and specifications
- `$.definitions.parallel_foreach_step` - Parallel foreach step configuration
- `$.definitions.sub_agent_task` - Individual sub-agent task structure
- `$.definitions.task_input` - Sub-agent task input parameter definitions