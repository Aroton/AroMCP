# Acceptance Criteria: Step Processing
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The step processing system handles the execution of 13 different step types, from user interaction and agent communication to tool integration and system operations. It provides the core functionality for individual step execution within the broader workflow context.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises shell_command, user_message, conditional, and mcp_call steps through its quality assurance workflow
**Current Test Coverage**: 
- `test_client_step_processors.py` - MCP tool integration and user interaction steps
- `test_agent_step_processors.py` - agent communication step processing
- `test_shell_command_step.py` - shell command execution
- `test_user_input_step.py` - user input collection and validation
- `test_wait_step.py` - wait step behavior
**Key Implementation Files**: 
- `src/aromcp/workflow_server/workflow/step_processors.py` - step processing coordination
- `src/aromcp/workflow_server/workflow/steps/` - individual step implementations
- `src/aromcp/workflow_server/workflow/step_registry.py` - step type registration
**Identified Gaps**: Missing comprehensive timeout handling, tool error scenarios, message format validation

## Acceptance Criteria

### Feature: User Interaction Steps

#### AC-SP-001: user_message steps format messages correctly
**Given**: A user_message step with message content and type
**When**: The step is processed
**Then**: Message must be formatted with proper type (info, warning, error, success) and format (text, markdown, code)

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_user_message_formatting
- ✗ Missing: Message format and type validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:23-45

#### AC-SP-002: user_message steps support variable substitution
**Given**: A user_message step with variable placeholders in message content
**When**: Variable substitution is applied
**Then**: Variables must be resolved from current workflow state

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_message_variable_substitution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:67-89

#### AC-SP-003: user_input steps collect and validate input
**Given**: A user_input step with input type and validation rules
**When**: User provides input
**Then**: Input must be validated against specified rules and stored in workflow state

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_input_validation
- ✗ Missing: Complex validation rule scenarios

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:45-78

#### AC-SP-004: user_input steps support choice-based inputs
**Given**: A user_input step with input type "choice" and available choices
**When**: User selects from available options
**Then**: Selection must be validated against available choices and stored

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_choice_input_validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:103-125

#### AC-SP-005: user_input steps handle validation failures with retries
**Given**: A user_input step with max_retries configuration
**When**: User provides invalid input
**Then**: Retry logic must be applied up to max_retries limit

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_validation_retry_logic

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:145-167

---

### Feature: Agent Communication Steps

#### AC-SP-006: agent_prompt steps format prompts with context
**Given**: An agent_prompt step with prompt template and context data
**When**: The step is processed
**Then**: Prompt must be formatted with variable substitution and context data

**Test Coverage**:
- ✓ Covered by: test_agent_step_processors.py::test_agent_prompt_formatting
- ✓ Covered by: test_subagent_prompt_validation.py::test_prompt_template_processing

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/agent_prompt.py:34-56

#### AC-SP-007: agent_prompt steps support expected_response schema
**Given**: An agent_prompt step with expected_response schema definition
**When**: The prompt is created
**Then**: Response schema must be included in agent task context

**Test Coverage**:
- ✓ Covered by: test_agent_step_processors.py::test_expected_response_schema

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/agent_prompt.py:78-95

#### AC-SP-008: agent_response steps validate responses against schema
**Given**: An agent_response step with response_schema and response data
**When**: The response is processed
**Then**: Response must be validated against schema if specified

**Test Coverage**:
- ✓ Covered by: test_agent_step_processors.py::test_response_validation
- ✗ Missing: Response schema validation edge cases

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/agent_response.py:56-78

#### AC-SP-009: agent_response steps apply multiple state updates
**Given**: An agent_response step with state_updates array
**When**: Response processing is complete
**Then**: All state updates must be applied in specified order

**Test Coverage**:
- ✓ Covered by: test_agent_step_processors.py::test_multiple_state_updates

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/agent_response.py:89-115

---

### Feature: Tool Integration Steps

#### AC-SP-010: mcp_call steps invoke tools with parameter substitution
**Given**: An mcp_call step with tool name and parameters containing variables
**When**: The tool is invoked
**Then**: Variable substitution must be applied to parameters before tool execution

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_mcp_tool_parameter_substitution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/mcp_call.py:45-67

#### AC-SP-011: mcp_call steps handle tool results and state updates
**Given**: An mcp_call step with state_update and store_result configuration
**When**: Tool execution completes
**Then**: Results must be stored and state updates applied as specified

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_tool_result_processing

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/mcp_call.py:89-111

#### AC-SP-012: mcp_call steps handle execution context (client vs server)
**Given**: An mcp_call step with execution_context specification
**When**: The tool is invoked
**Then**: Tool must be executed in the specified context (client or server)

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_execution_context_handling

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/mcp_call.py:134-156

#### AC-SP-013: mcp_call steps handle tool timeouts and retries
**Given**: An mcp_call step with timeout and retry configuration
**When**: Tool execution exceeds timeout or fails
**Then**: Appropriate timeout handling and retry logic must be applied

**Test Coverage**:
- ✗ Missing: Tool timeout and error handling scenarios

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/mcp_call.py:178-205

---

### Feature: System Operation Steps

#### AC-SP-014: shell_command steps execute with proper security
**Given**: A shell_command step with command and working directory
**When**: The command is executed
**Then**: Execution must be secure with proper environment isolation

**Test Coverage**:
- ✓ Covered by: test_shell_command_step.py::test_secure_command_execution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/shell_command.py:34-58

#### AC-SP-015: shell_command steps capture output and exit codes
**Given**: A shell_command step that executes successfully or fails
**When**: Command execution completes
**Then**: stdout, stderr, and exit codes must be captured and stored

**Test Coverage**:
- ✓ Covered by: test_shell_command_step.py::test_output_capture

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/shell_command.py:78-102

#### AC-SP-016: shell_command steps handle timeouts gracefully
**Given**: A shell_command step with timeout configuration
**When**: Command execution exceeds timeout
**Then**: Command must be terminated gracefully with appropriate error handling

**Test Coverage**:
- ✓ Covered by: test_shell_command_step.py::test_command_timeout_handling

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/shell_command.py:125-147

#### AC-SP-017: wait_step pauses workflow for client polling
**Given**: A wait_step with optional wait message
**When**: The step is encountered
**Then**: Workflow execution must pause until client calls get_next_step

**Test Coverage**:
- ✓ Covered by: test_wait_step.py::test_wait_step_behavior

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:23-41

#### AC-SP-018: wait_step maintains workflow state during pause
**Given**: A wait_step that pauses workflow execution
**When**: The workflow is waiting
**Then**: Workflow state must be preserved and accessible during wait period

**Test Coverage**:
- ✓ Covered by: test_wait_step.py::test_state_preservation_during_wait

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:56-78

---

### Feature: Step Registry and Validation

#### AC-SP-019: Step types are properly registered and validated
**Given**: A workflow step with a specific type
**When**: The step is processed
**Then**: Step type must be registered in step registry and conform to type requirements

**Test Coverage**:
- ✓ Covered by: test_step_registry.py::test_step_type_registration

**Implementation Reference**: src/aromcp/workflow_server/workflow/step_registry.py:34-56

#### AC-SP-020: Step definitions are validated against schema requirements
**Given**: A step definition in workflow YAML
**When**: Workflow is loaded and validated
**Then**: Step must conform to step type schema requirements

**Test Coverage**:
- ✓ Covered by: test_validator.py::test_step_definition_validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/validator.py:123-145

#### AC-SP-021: Invalid step configurations generate clear error messages
**Given**: A step with invalid configuration or missing required fields
**When**: Workflow validation is performed
**Then**: Clear, specific error messages must be provided for validation failures

**Test Coverage**:
- ✓ Covered by: test_validator.py::test_step_validation_error_messages

**Implementation Reference**: src/aromcp/workflow_server/workflow/validator.py:167-189

---

### Feature: Step Batching and Queuing

#### AC-SP-022: User message steps are batched for efficiency
**Given**: Multiple consecutive user_message steps
**When**: Steps are queued for execution
**Then**: Messages must be batched together for efficient client communication

**Test Coverage**:
- ✓ Covered by: test_batched_steps.py::test_user_message_batching

**Implementation Reference**: src/aromcp/workflow_server/workflow/step_processors.py:234-256

#### AC-SP-023: Blocking steps pause execution appropriately
**Given**: Steps requiring client interaction (user_input, wait_step)
**When**: These steps are encountered
**Then**: Workflow execution must pause until client provides required input

**Test Coverage**:
- ✗ Missing: Comprehensive blocking step behavior tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/step_processors.py:178-203

## Integration Points
- **Workflow Execution Engine**: Receives step execution requests from workflow engine and reports completion status
- **State Management**: Accesses workflow state for variable resolution and applies state updates from step results
- **Variable Resolution**: Uses variable resolution system for parameter substitution and expression evaluation
- **Error Handling**: Coordinates with error handling system for step-level error recovery and retry logic

## Schema Compliance
Governed by workflow schema sections:
- `$.definitions.step` - General step structure and common properties
- `$.definitions.user_message_step` - User message step specification
- `$.definitions.user_input_step` - User input step specification
- `$.definitions.agent_prompt_step` - Agent prompt step specification
- `$.definitions.agent_response_step` - Agent response step specification
- `$.definitions.mcp_call_step` - MCP tool call step specification
- `$.definitions.shell_command_step` - Shell command step specification
- `$.definitions.wait_step` - Wait step specification