# Acceptance Criteria: User Interaction
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The user interaction system manages communication between workflow execution and human users through message display, input collection, and wait operations. It provides the interface for workflows to present information and gather user input with proper validation and retry mechanisms.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises user_message steps for displaying validation results and status updates to users during the quality assurance process
**Current Test Coverage**: 
- `test_user_input_step.py` - user input collection and validation
- `test_wait_step.py` - wait step behavior and state preservation
- `test_client_step_processors.py` - user message formatting and batching
**Key Implementation Files**: 
- `src/aromcp/workflow_server/workflow/steps/user_message.py` - message display logic
- `src/aromcp/workflow_server/workflow/steps/user_input.py` - input collection and validation
- `src/aromcp/workflow_server/workflow/steps/wait_step.py` - workflow pause/resume logic
**Identified Gaps**: Missing message format validation, complex input validation scenarios, user interaction timeout handling

## Acceptance Criteria

### Feature: User Message Display

#### AC-UI-001: Message types are displayed with proper formatting
**Given**: A user_message step with message type (info, warning, error, success)
**When**: The message is presented to the user
**Then**: Message must be formatted appropriately for the specified type with visual indicators

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_user_message_type_formatting
- ✗ Missing: Message format and type validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:23-45

#### AC-UI-002: Message formats support text, markdown, and code display
**Given**: A user_message step with format specification (text, markdown, code)
**When**: The message content is processed
**Then**: Content must be formatted according to the specified format type

**Test Coverage**:
- ✗ Missing: Message format validation and rendering tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:67-89

#### AC-UI-003: Variable substitution works in message content
**Given**: A user_message step with variable placeholders in message content
**When**: The message is processed for display
**Then**: Variable references must be resolved from current workflow state

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_message_variable_substitution

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:112-134

#### AC-UI-004: Message batching optimizes client communication
**Given**: Multiple consecutive user_message steps
**When**: Messages are queued for client delivery
**Then**: Messages must be batched together for efficient communication

**Test Coverage**:
- ✓ Covered by: test_client_step_processors.py::test_user_message_batching

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:156-178

#### AC-UI-005: Long messages are handled appropriately
**Given**: User messages with content exceeding display limits
**When**: Long messages are processed
**Then**: Appropriate handling must be applied (truncation, pagination, or full display)

**Test Coverage**:
- ✗ Missing: Long message handling tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_message.py:200-222

---

### Feature: User Input Collection

#### AC-UI-006: Input types are validated correctly
**Given**: A user_input step with input type specification (string, number, boolean, choice)
**When**: User provides input
**Then**: Input must be validated against the specified type with appropriate error messages

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_input_type_validation

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:34-56

#### AC-UI-007: Required vs optional inputs are handled properly
**Given**: User input steps with required and optional input configurations
**When**: User provides or omits input values
**Then**: Required inputs must be enforced and optional inputs must allow empty values

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_required_optional_input_handling

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:78-100

#### AC-UI-008: Input validation rules are applied correctly
**Given**: A user_input step with validation rules (min/max length, pattern, range)
**When**: User input is validated
**Then**: All specified validation rules must be applied with clear error messages

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_input_validation_rules
- ✗ Missing: Complex validation rule scenarios

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:123-145

#### AC-UI-009: Choice-based inputs provide proper selection interface
**Given**: A user_input step with input type "choice" and available choices
**When**: User is presented with input options
**Then**: All available choices must be displayed and selection must be validated

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_choice_input_selection

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:167-189

#### AC-UI-010: Default values are applied for optional inputs
**Given**: A user_input step with default value configuration
**When**: User does not provide input (for optional inputs)
**Then**: Default value must be used and stored in workflow state

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_default_value_application

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:212-234

---

### Feature: Input Validation and Retry Logic

#### AC-UI-011: Validation failures trigger retry logic with max_retries
**Given**: A user_input step with max_retries configuration
**When**: User provides invalid input
**Then**: User must be reprompted up to max_retries times with clear error messages

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_validation_retry_logic

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:256-278

#### AC-UI-012: Retry attempts provide incremental guidance
**Given**: Multiple retry attempts for invalid input
**When**: Each retry occurs
**Then**: Progressively more detailed guidance should be provided to help user succeed

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_incremental_retry_guidance

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:300-322

#### AC-UI-013: Retry exhaustion follows configured error handling strategy
**Given**: A user_input step where max_retries is exceeded
**When**: All retry attempts are exhausted
**Then**: Configured error_handling strategy must be applied (fail, continue, fallback)

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_retry_exhaustion_error_handling

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:345-367

#### AC-UI-014: Input validation supports custom validation expressions
**Given**: A user_input step with custom JavaScript validation expressions
**When**: User input is validated
**Then**: Custom validation logic must be executed with proper error reporting

**Test Coverage**:
- ✗ Missing: Custom validation expression tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:389-411

---

### Feature: Wait Step Behavior

#### AC-UI-015: Wait step pauses workflow execution for client polling
**Given**: A wait_step in workflow execution
**When**: The wait step is encountered
**Then**: Workflow execution must pause until client calls get_next_step

**Test Coverage**:
- ✓ Covered by: test_wait_step.py::test_wait_step_pause_behavior

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:23-41

#### AC-UI-016: Wait message is displayed to user during pause
**Given**: A wait_step with optional wait message configuration
**When**: The workflow pauses at the wait step
**Then**: Wait message must be displayed to inform user of pause reason

**Test Coverage**:
- ✓ Covered by: test_wait_step.py::test_wait_message_display

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:56-78

#### AC-UI-017: Workflow state is preserved during wait period
**Given**: A workflow paused at a wait_step
**When**: The workflow is waiting for client action
**Then**: Complete workflow state must be preserved and accessible when resumed

**Test Coverage**:
- ✓ Covered by: test_wait_step.py::test_state_preservation_during_wait

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:89-111

#### AC-UI-018: Wait step timeout handling works when configured
**Given**: A wait_step with optional timeout configuration
**When**: Client does not poll within timeout period
**Then**: Appropriate timeout handling must be applied (future enhancement)

**Test Coverage**:
- ✗ Missing: Wait step timeout handling tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/wait_step.py:134-156

---

### Feature: State Updates from User Interaction

#### AC-UI-019: User input is stored in workflow state correctly
**Given**: A user_input step with state_update configuration
**When**: Valid user input is collected
**Then**: Input value must be stored in specified workflow state location

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_input_state_storage

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:434-456

#### AC-UI-020: Multiple state updates from single input work correctly
**Given**: A user_input step with multiple state_update configurations
**When**: User input is processed
**Then**: All specified state updates must be applied in correct order

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_multiple_state_updates_from_input

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:478-500

#### AC-UI-021: Input validation affects state update behavior
**Given**: User input that fails validation
**When**: Validation failure occurs
**Then**: State updates must not be applied until valid input is provided

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_validation_prevents_state_updates

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:523-545

---

### Feature: User Interaction Timeouts and Error Handling

#### AC-UI-022: User interaction timeouts are configurable
**Given**: User interaction steps with timeout configuration
**When**: User does not respond within timeout period
**Then**: Configured timeout handling must be applied with appropriate error strategy

**Test Coverage**:
- ✗ Missing: User interaction timeout handling tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:567-589

#### AC-UI-023: User interaction errors follow step error handling strategies
**Given**: User interaction steps with error_handling configuration
**When**: Interaction errors occur (timeout, validation failure, etc.)
**Then**: Configured error handling strategy must be applied (retry, continue, fail, fallback)

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_interaction_error_handling_strategies

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:612-634

#### AC-UI-024: User interaction context is preserved across retries
**Given**: User interaction that requires multiple retry attempts
**When**: Retries occur due to validation failures
**Then**: Interaction context (prompt, choices, previous attempts) must be preserved

**Test Coverage**:
- ✓ Covered by: test_user_input_step.py::test_context_preservation_across_retries

**Implementation Reference**: src/aromcp/workflow_server/workflow/steps/user_input.py:656-678

## Integration Points
- **Step Processing**: Implements user interaction step types within the broader step processing framework
- **State Management**: Stores user input and interaction results in workflow state with proper validation
- **Workflow Execution Engine**: Coordinates with workflow engine for pause/resume behavior and blocking execution
- **Error Handling**: Uses error handling system for validation failures, timeouts, and retry logic

## Schema Compliance
Governed by workflow schema sections:
- `$.definitions.user_message_step` - User message step specification and properties
- `$.definitions.user_input_step` - User input step configuration and validation rules
- `$.definitions.wait_step` - Wait step specification and message configuration
- `$.definitions.input_validation` - Input validation rule specifications
- `$.definitions.choice_input` - Choice-based input configuration