# Acceptance Criteria: Variable Resolution
Generated: 2025-07-23
Source: Production workflow, schema.json, implementation analysis, test coverage review

## Overview
The variable resolution system handles scoped variable syntax, JavaScript expression evaluation, and template variable substitution throughout workflow execution. It provides the bridge between workflow state and dynamic content generation across all step types.

## Coverage Analysis
**Production Usage**: code-standards:enforce.yaml exercises variable resolution through state references in conditional logic and shell command parameter substitution  
**Current Test Coverage**: 
- `test_variable_resolution_expressions.py` - JavaScript expression evaluation
- `test_scoped_expressions.py` - scoped variable syntax testing
- `test_subagent_template_replacement.py` - template variable substitution
- `test_template_fallback_logic.py` - template fallback handling
**Key Implementation Files**: 
- `src/aromcp/workflow_server/workflow/expression_evaluator.py` - JavaScript expression engine
- `src/aromcp/workflow_server/state/manager.py` - scoped variable resolution
- `src/aromcp/workflow_server/workflow/template_processor.py` - template substitution
**Identified Gaps**: Missing PythonMonkey fallback behavior tests, complex nested expression evaluation

## Acceptance Criteria

### Feature: Scoped Variable Syntax

#### AC-VR-001: This-scope variable references resolve correctly
**Given**: Variable references using `this.field` syntax
**When**: Variables are resolved during step execution
**Then**: Values must be retrieved from current workflow state tier with proper precedence

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_this_scope_resolution
- ✓ Covered by: test_scoped_state_management.py::test_this_field_access

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:345-367

#### AC-VR-002: Global-scope variable references access workflow-level state
**Given**: Variable references using `global.var` syntax
**When**: Variables are resolved in any context (main workflow, sub-agent, loop)
**Then**: Values must be retrieved from main workflow state regardless of execution context

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_global_scope_resolution

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:389-411

#### AC-VR-003: Inputs-scope variable references access read-only parameters
**Given**: Variable references using `inputs.param` syntax
**When**: Variables are resolved during step execution
**Then**: Values must be retrieved from read-only inputs tier

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_inputs_scope_resolution

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:434-456

#### AC-VR-004: Loop context variables are available in loop scopes
**Given**: Steps executing within loop contexts (foreach, while_loop)
**When**: Loop variables (loop.item, loop.index, loop.iteration) are accessed
**Then**: Current loop context values must be provided correctly

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_loop_context_variables

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:478-505

#### AC-VR-005: Legacy state and computed scope syntax works with deprecation warnings
**Given**: Variable references using legacy `state.field` or `computed.field` syntax
**When**: Variables are resolved
**Then**: Values must resolve correctly but deprecation warnings should be logged

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_legacy_scope_syntax

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:523-548

#### AC-VR-006: Invalid scoped paths generate clear error messages
**Given**: Variable references with invalid scope prefixes or malformed paths
**When**: Variable resolution is attempted
**Then**: Clear, specific error messages must be provided for debugging

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_invalid_scope_error_messages

**Implementation Reference**: src/aromcp/workflow_server/state/manager.py:567-589

---

### Feature: JavaScript Expression Engine

#### AC-VR-007: PythonMonkey engine supports full ES6+ evaluation
**Given**: JavaScript expressions using modern ES6+ syntax (arrow functions, const/let, template literals)
**When**: Expressions are evaluated
**Then**: Full JavaScript semantics must be maintained with proper syntax support

**Test Coverage**:
- ✓ Covered by: test_variable_resolution_expressions.py::test_es6_syntax_support
- ✗ Missing: Comprehensive ES6+ feature testing

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:34-67

#### AC-VR-008: Python-based evaluation fallback works for basic expressions
**Given**: Environments where PythonMonkey is not available
**When**: Basic expressions (comparisons, arithmetic) are evaluated
**Then**: Python-based fallback must provide equivalent results

**Test Coverage**:
- ✗ Missing: PythonMonkey fallback behavior tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:89-111

#### AC-VR-009: Boolean expressions and comparisons evaluate correctly
**Given**: Conditional expressions with boolean logic, comparisons, and arithmetic
**When**: Expressions are evaluated in conditional steps or while loops
**Then**: Proper boolean results must be returned with correct operator precedence

**Test Coverage**:
- ✓ Covered by: test_variable_resolution_expressions.py::test_boolean_expression_evaluation

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:134-156

#### AC-VR-010: Property access with dot and bracket notation works
**Given**: Expressions accessing object properties using dot notation (obj.prop) or bracket notation (obj['prop'])
**When**: Property access is evaluated
**Then**: Correct property values must be retrieved with support for both notation types

**Test Coverage**:
- ✓ Covered by: test_variable_resolution_expressions.py::test_property_access_notation

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:178-200

#### AC-VR-011: Function calls and method invocations are supported
**Given**: Expressions containing function calls or method invocations
**When**: Functions are evaluated within expression context
**Then**: Function execution must work correctly with proper parameter passing

**Test Coverage**:
- ✓ Covered by: test_variable_resolution_expressions.py::test_function_calls

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:223-245

#### AC-VR-012: Expression evaluation errors are handled appropriately
**Given**: JavaScript expressions with syntax errors or runtime exceptions
**When**: Expression evaluation fails
**Then**: Appropriate error handling must be applied with clear diagnostic information

**Test Coverage**:
- ✓ Covered by: test_variable_resolution_expressions.py::test_expression_error_handling

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:267-289

---

### Feature: Template Variable Substitution

#### AC-VR-013: Template variable syntax is processed correctly
**Given**: Template strings containing `{{ variable }}` syntax
**When**: Templates are processed for step parameters, messages, or prompts
**Then**: Variable placeholders must be replaced with resolved values

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_template_variable_substitution

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:23-45

#### AC-VR-014: Nested property access works within templates
**Given**: Template variables referencing nested object properties ({{ object.nested.property }})
**When**: Template substitution is performed
**Then**: Deep property access must be resolved correctly within template context

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_nested_property_templates

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:67-89

#### AC-VR-015: Missing variables use appropriate fallback behavior
**Given**: Template variables referencing non-existent properties or undefined values
**When**: Template substitution encounters missing variables
**Then**: Appropriate fallback behavior must be applied (empty string, error, or configured fallback)

**Test Coverage**:
- ✓ Covered by: test_template_fallback_logic.py::test_missing_variable_fallbacks

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:112-134

#### AC-VR-016: Template variable substitution works in all step contexts
**Given**: Templates used in step parameters, conditions, messages, and agent prompts
**When**: Variable substitution is applied across different step types
**Then**: Consistent substitution behavior must be maintained across all contexts

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_cross_step_template_consistency

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:156-178

#### AC-VR-017: Template escaping allows literal braces
**Given**: Template strings needing literal `{{` and `}}` characters
**When**: Template escaping syntax is used
**Then**: Literal braces must be preserved without variable substitution

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_template_escaping

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:200-222

#### AC-VR-018: Template syntax errors generate clear messages
**Given**: Template strings with malformed variable syntax or invalid references
**When**: Template processing is attempted
**Then**: Clear error messages must be provided with location and context information

**Test Coverage**:
- ✓ Covered by: test_template_fallback_logic.py::test_template_syntax_error_messages

**Implementation Reference**: src/aromcp/workflow_server/workflow/template_processor.py:245-267

---

### Feature: Complex Expression Scenarios

#### AC-VR-019: Expressions work correctly within loop contexts
**Given**: Expressions evaluated within foreach or while_loop contexts
**When**: Loop variables and state are accessed in expressions
**Then**: Proper scoping must be maintained with loop context variables available

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_expressions_in_loop_contexts

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:289-315

#### AC-VR-020: Complex nested expressions evaluate correctly
**Given**: Expressions with multiple levels of nesting, function calls, and property access
**When**: Complex expressions are evaluated
**Then**: Proper evaluation order and result accuracy must be maintained

**Test Coverage**:
- ✗ Missing: Complex nested expression evaluation tests

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:334-367

#### AC-VR-021: Expression evaluation respects three-tier state precedence
**Given**: Expressions accessing variables that exist in multiple state tiers
**When**: Variable resolution occurs within expressions
**Then**: Three-tier precedence (computed > inputs > state) must be maintained

**Test Coverage**:
- ✓ Covered by: test_scoped_expressions.py::test_expression_state_precedence

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:389-411

#### AC-VR-022: Variable resolution works in sub-agent contexts
**Given**: Expressions evaluated within sub-agent execution contexts
**When**: Variables are resolved in isolated sub-agent state
**Then**: Proper state isolation must be maintained while allowing global variable access

**Test Coverage**:
- ✓ Covered by: test_subagent_template_replacement.py::test_subagent_variable_resolution

**Implementation Reference**: src/aromcp/workflow_server/workflow/expression_evaluator.py:434-456

## Integration Points
- **State Management**: Retrieves variable values from three-tier state architecture with proper precedence
- **Step Processing**: Provides variable resolution services for parameter substitution across all step types
- **Control Flow**: Supports condition evaluation for conditional and loop constructs
- **Sub-Agent Management**: Handles variable resolution within isolated sub-agent contexts

## Schema Compliance
Governed by workflow schema sections:
- Variable references are used throughout step definitions but not explicitly defined in schema
- Template syntax is used in `prompt_template` fields in sub-agent tasks
- Expression syntax is used in condition fields for conditional and loop steps
- Scoped variable syntax is implicitly supported across all step parameter fields