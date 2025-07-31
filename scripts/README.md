# AroMCP Scripts

Utility scripts for working with AroMCP workflows and tools.

## validate_workflow.py

A comprehensive workflow validation script that checks MCP workflow YAML files for correctness and completeness.

### Usage

```bash
# Validate a single workflow
python scripts/validate_workflow.py .aromcp/workflows/code-standards:enforce.yaml

# Validate multiple workflows
python scripts/validate_workflow.py .aromcp/workflows/*.yaml

# Run with uv
uv run python scripts/validate_workflow.py .aromcp/workflows/code-standards:enforce.yaml
```

### Features

- **YAML Syntax Validation**: Ensures the file is valid YAML
- **Schema Validation**: Checks required fields and structure
- **Step Type Validation**: Verifies all step types are valid
- **Parameter Validation**: Checks input parameters and types
- **Cross-Reference Validation**: Ensures referenced elements exist
- **Best Practice Warnings**: Suggests improvements

### Validation Checks

1. **Required Fields**
   - name, description, version, steps

2. **Step Types**
   - All 14 supported step types
   - Required fields for each step type
   - Nested step validation (conditionals, loops)

3. **State Management**
   - State path validation
   - Computed field validation
   - State update operations

4. **Input Parameters**
   - Type validation
   - Default value checks
   - Required field validation

5. **Sub-Agent Tasks**
   - Task definition validation
   - Prompt template checks
   - Reference validation

### Exit Codes

- `0`: All workflows valid
- `1`: One or more workflows invalid

### Running Tests

```bash
# Run validation tests
uv run pytest tests/test_workflow_validation.py -v
```

### Example Output

```
Validating: .aromcp/workflows/code-standards:enforce.yaml
=======================================================
✅ Validation PASSED

Workflow is valid and follows best practices!
```