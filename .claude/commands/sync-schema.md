# /sync-schema

**Purpose**: Synchronize MCP workflow schema changes across the entire server codebase after any schema update.

**Use this command when**: The workflow schema (`.aromcp/workflows/schema.json`) has been modified and you need to propagate these changes throughout the codebase.

## Usage
- `/sync-schema` - Analyze schema changes and update all affected files

## Execution Process

### Phase 1: Schema Analysis
1. **Load Current Schema**
   - Read `.aromcp/workflows/schema.json`
   - Parse and validate the schema structure
   - Identify all defined elements (step types, state structure, validation rules)

2. **Detect Changes**
   - Compare with previous known structure
   - Identify:
     - New step types added to the enum
     - Modified state tier names or structure
     - New validation rules or patterns
     - Changed field definitions
     - Deprecated elements

3. **Impact Analysis**
   - Scan codebase for references to changed elements
   - Build dependency map of affected files
   - Prioritize updates by criticality

### Phase 2: Systematic Updates

#### 1. Core Validation & Registration
**Files to check:**
- `src/aromcp/workflow_server/workflow/validator.py`
- `src/aromcp/workflow_server/workflow/step_registry.py`

**Updates needed:**
- Add new step types to `VALID_STEP_TYPES`
- Add validation methods for new step types (e.g., `_validate_<step_type>_step()`)
- Update schema validation logic
- Register new step processors

#### 2. State Management
**Files to check:**
- `src/aromcp/workflow_server/state/manager.py`
- `src/aromcp/workflow_server/state/models.py`
- `src/aromcp/workflow_server/tools/state_tools.py`

**Updates needed:**
- Update path validation for new state tiers
- Modify state structure in models
- Update flattened view generation
- Adjust state update logic
- Update documentation and examples

#### 3. Step Processing
**Files to check:**
- `src/aromcp/workflow_server/workflow/step_processors.py`
- `src/aromcp/workflow_server/workflow/steps/*.py`
- `src/aromcp/workflow_server/workflow/executor.py`

**Updates needed:**
- Add processors for new step types
- Update existing processors for schema changes
- Handle new fields (e.g., `execution_context`)
- Update step execution logic

#### 4. Workflow Tools
**Files to check:**
- `src/aromcp/workflow_server/tools/workflow_tools.py`
- `src/aromcp/workflow_server/tools/debug_tools.py`
- All files in `src/aromcp/workflow_server/tools/`

**Updates needed:**
- Update tool documentation
- Modify examples to reflect schema changes
- Update state inspection tools
- Adjust tool parameter handling

#### 5. Documentation
**Files to check:**
- `.aromcp/workflows/README.md`
- `shared-claude/commands/workflow.md`
- `.claude/commands/workflow:generate.md`
- `src/aromcp/workflow_server/prompts/standards.py`

**Updates needed:**
- Update all workflow examples
- Document new step types with examples
- Update state structure documentation
- Revise variable template references
- Update command documentation

#### 6. Test Infrastructure
**Files to check:**
- All files in `src/aromcp/workflow_server/testing/`
- Test workflows in `.aromcp/workflows/test:*.yaml`
- Integration test files

**Updates needed:**
- Update test fixtures
- Modify mock implementations
- Update example workflows
- Add tests for new features
- Ensure backward compatibility tests

### Phase 3: Validation & Testing

1. **Schema Validation**
   ```bash
   # Validate all workflow files against new schema
   uv run python scripts/validate_workflow.py .aromcp/workflows/*.yaml
   ```

2. **Unit Tests**
   ```bash
   # Run all unit tests
   uv run pytest tests/workflow_server/
   ```

3. **Integration Tests**
   ```bash
   # Run integration tests
   uv run pytest tests/workflow_server/test_*_integration.py
   ```

4. **Backward Compatibility**
   - Test existing workflows still function
   - Verify deprecation warnings work correctly
   - Ensure migration paths are clear

## Generic Update Patterns

### For State Structure Changes
When state tiers are renamed or restructured:
1. Update path validation logic in `validate_update_path()`
2. Modify state models with backward compatibility properties
3. Update all path references in code and documentation
4. Add migration logic if needed

### For New Step Types
When adding new step types to the schema:
1. Add to `VALID_STEP_TYPES` in validator
2. Create validation method `_validate_<type>_step()`
3. Add processor in step_processors or create new file
4. Update step execution logic in executor
5. Document with examples in all relevant files

### For Field Additions
When adding new fields to existing structures:
1. Update validation to handle optional/required status
2. Modify processors to use new fields
3. Update documentation with field descriptions
4. Add default values where appropriate

### For Deprecations
When deprecating elements:
1. Add deprecation warnings in validation
2. Maintain backward compatibility temporarily
3. Document migration path
4. Update all examples to use new approach

## Verification Checklist

### Code Updates
- [ ] All validator step types match schema enum
- [ ] New validation methods added for new step types
- [ ] Step processors implemented for new types
- [ ] State management handles new structure
- [ ] Path validation reflects current state tiers
- [ ] Tool documentation is updated
- [ ] Examples use correct syntax

### Testing
- [ ] All test workflows validate successfully
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Backward compatibility maintained
- [ ] New features have test coverage

### Documentation
- [ ] README reflects current schema
- [ ] Command documentation is updated
- [ ] Examples are correct and functional
- [ ] Migration guide provided if needed

## Common Patterns to Search For

Use these patterns to find code that needs updating:

1. **State paths**: Search for string patterns like `"raw."`, `"state."`, `"computed."`
2. **Step type checks**: Search for `step["type"] ==` or `step.type ==`
3. **State structure**: Search for `{raw:`, `{computed:`, `{state:`
4. **Validation patterns**: Search for `VALID_STEP_TYPES`, `_validate_.*_step`
5. **Documentation**: Search for ````yaml` blocks in markdown files

## Important Notes

- **Maintain Backward Compatibility**: Use property decorators or migration logic
- **Test Thoroughly**: Each change should be validated with tests
- **Update Incrementally**: Make changes in logical groups and test between
- **Document Changes**: Update all relevant documentation with examples
- **Communicate Breaking Changes**: If compatibility cannot be maintained

This generic approach ensures any schema change can be properly synchronized across the codebase.