# Acceptance Criteria: State Management
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The state management system implements a three-tier architecture (inputs/state/computed) with scoped variable resolution, atomic state updates, and computed field processing. It provides the foundation for all workflow data storage and retrieval operations.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises state initialization, variable scoping, and state updates through shell command outputs and conditional logic
**Current Test Coverage**: 
- `test_three_tier_state_model.py` - three-tier architecture validation
- `test_state_manager.py` - state tier management and operations
- `test_scoped_state_management.py` - scoped variable access patterns
**Key Implementation Files**: 
- `src/aromcp/workflow_server/state/manager.py` - state management coordination
- `src/aromcp/workflow_server/state/concurrent.py` - thread-safe state operations
- `src/aromcp/workflow_server/workflow/models.py` - state data models
**Identified Gaps**: Missing cascading computed field updates, comprehensive state validation tests

## Acceptance Criteria

### Feature: Three-Tier State Architecture

#### AC-SM-001: State tier precedence is maintained
**Given**: A workflow with data in multiple state tiers (inputs, state, computed)
**When**: Variables are accessed during step execution
**Then**: Precedence order computed > inputs > state must be applied for read operations

**Test Coverage**:
- ✓ Covered by: test_three_tier_state_model.py::test_state_tier_precedence
- ✓ Covered by: test_state_manager.py::test_tier_access_priority

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:124-145

#### AC-SM-002: Inputs tier is read-only after initialization
**Given**: A workflow with initialized input parameters
**When**: Steps attempt to modify values in the inputs tier
**Then**: Modifications must be rejected and appropriate error messages provided

**Test Coverage**:
- ✓ Covered by: test_three_tier_state_model.py::test_inputs_readonly
- ✓ Covered by: test_state_manager.py::test_inputs_tier_immutability

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:167-185

#### AC-SM-003: State tier allows mutable operations
**Given**: A workflow with mutable state data
**When**: State update operations are performed
**Then**: Only the state tier must allow modifications (set, increment, decrement, append, multiply)

**Test Coverage**:
- ✓ Covered by: test_state_manager.py::test_mutable_state_operations

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:203-245

#### AC-SM-004: Flattened views are generated for step execution
**Given**: State data distributed across multiple tiers
**When**: A step requires access to the complete state context
**Then**: A flattened view combining all tiers must be provided with proper precedence

**Test Coverage**:
- ✓ Covered by: test_three_tier_state_model.py::test_flattened_view_generation

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:276-298

---

### Feature: Scoped Variable Resolution

#### AC-SM-005: Scoped syntax resolves correctly
**Given**: Variable references using scoped syntax (this.field, global.var, inputs.param)
**When**: Variables are resolved during step execution
**Then**: Correct tier-specific values must be returned based on scope prefix

**Test Coverage**:
- ✓ Covered by: test_scoped_state_management.py::test_scoped_variable_resolution
- ✓ Covered by: test_scoped_expressions.py::test_scope_prefix_resolution

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:345-378

#### AC-SM-006: Loop context variables are supported
**Given**: Steps executing within loop contexts (foreach, while_loop)
**When**: Loop variables (loop.item, loop.index, loop.iteration) are accessed
**Then**: Current loop context values must be provided correctly

**Test Coverage**:
- ✓ Covered by: test_scoped_state_management.py::test_loop_context_variables

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:412-435

#### AC-SM-007: Nested property access works with dot notation
**Given**: Complex state objects with nested properties
**When**: Variables are accessed using dot notation (object.nested.property)
**Then**: Deep property access must be resolved correctly

**Test Coverage**:
- ✓ Covered by: test_scoped_state_management.py::test_nested_property_access

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:389-410

#### AC-SM-008: Missing variable references use appropriate fallbacks
**Given**: Variable references to non-existent properties
**When**: Variables are resolved
**Then**: Appropriate fallback values or error handling must be applied

**Test Coverage**:
- ✓ Covered by: test_scoped_state_management.py::test_missing_variable_fallbacks

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:456-478

---

### Feature: State Update Operations

#### AC-SM-009: Atomic state updates are applied
**Given**: Multiple state update operations in a single transaction
**When**: Updates are processed
**Then**: All updates must be applied atomically or none at all

**Test Coverage**:
- ✓ Covered by: test_state_manager.py::test_atomic_state_updates

**Implementation Reference**: src/aromcp/workflow_server/state/concurrent.py:89-115

#### AC-SM-010: State update operations are validated
**Given**: State update specifications with various operations (set, increment, append, etc.)
**When**: Updates are applied
**Then**: Update paths must be validated against scoped syntax rules

**Test Coverage**:
- ✓ Covered by: test_state_manager.py::test_state_update_validation

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:512-545

#### AC-SM-011: Value expressions with variable substitution work
**Given**: State update values containing variable references
**When**: Updates are processed
**Then**: Variable substitution must be applied before setting values

**Test Coverage**:
- ✓ Covered by: test_scoped_set_variable_integration.py::test_variable_substitution_in_updates

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:567-589

#### AC-SM-012: Update conflicts are handled gracefully
**Given**: Concurrent state update operations on the same data
**When**: Updates are applied simultaneously
**Then**: Conflicts must be detected and appropriate error messages provided

**Test Coverage**:
- ✗ Missing: Comprehensive update conflict handling tests

**Implementation Reference**: src/aromcp/workflow_server/state/concurrent.py:145-167

---

### Feature: Computed Field Processing

#### AC-SM-013: Computed field dependencies are tracked
**Given**: Computed fields with dependency specifications in state schema
**When**: Dependencies change during workflow execution
**Then**: Dependent computed fields must be identified for recalculation

**Test Coverage**:
- ✓ Covered by: test_transformer.py::test_dependency_tracking

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:623-645

#### AC-SM-014: Computed values are recalculated when dependencies change
**Given**: State changes that affect computed field dependencies
**When**: State updates are processed
**Then**: All affected computed fields must be recalculated with new values

**Test Coverage**:
- ✓ Covered by: test_transformer.py::test_computed_field_recalculation
- ✗ Missing: Cascading computed field updates

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:678-702

#### AC-SM-015: JavaScript transformations are applied with error handling
**Given**: Computed fields with JavaScript transformation expressions
**When**: Transformations are executed
**Then**: Proper error handling must be applied with fallback values when transformations fail

**Test Coverage**:
- ✓ Covered by: test_transformer.py::test_transformation_error_handling

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:734-756

#### AC-SM-016: Cascading updates for dependent computed fields work
**Given**: Computed fields that depend on other computed fields
**When**: A root computed field changes
**Then**: All dependent computed fields must be updated in proper dependency order

**Test Coverage**:
- ✗ Missing: Cascading computed field dependency tests

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:789-812

---

### Feature: Legacy Compatibility

#### AC-SM-017: Legacy "raw" field mapping to "inputs" works
**Given**: Workflow definitions using legacy "raw" field syntax
**When**: Workflows are loaded and executed
**Then**: "raw" field values must be mapped to "inputs" tier for backward compatibility

**Test Coverage**:
- ✓ Covered by: test_three_tier_state_model.py::test_legacy_raw_field_mapping

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:856-875

## Integration Points
- **Variable Resolution**: Provides variable resolution services to step processors and expression evaluator
- **Workflow Execution Engine**: Supplies state context for step execution and receives state updates
- **Sub-Agent Management**: Manages isolated state contexts for parallel sub-agent execution
- **Error Handling**: Coordinates with error handling system for state-related error recovery

## Schema Compliance
Governed by workflow schema sections:
- `$.properties.inputs` - Input parameter definitions and validation
- `$.properties.default_state` - Initial state tier values
- `$.properties.state_schema` - Computed field definitions and dependencies
- `$.definitions.state_update` - State update operation specifications