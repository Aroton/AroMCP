# Shared Workflow with Reactive State

## Check Standards Shared Workflow

```yaml
# shared/check-standards.yaml
workflow:
  name: "shared:check-standards"

  state_schema:
    raw:
      files: array
      typescript_results: object
      lint_results: object

    computed:
      files_with_errors:
        from: ["raw.typescript_results", "raw.lint_results"]
        transform: |
          Object.keys(input[0])
            .filter(f => input[0][f].errors > 0 || input[1][f].errors > 0)

      total_issues:
        from: ["raw.typescript_results", "raw.lint_results"]
        transform: |
          Object.values(input[0]).reduce((sum, r) => sum + r.errors, 0) +
          Object.values(input[1]).reduce((sum, r) => sum + r.errors, 0)

  steps:
    - id: "check_typescript"
      type: "foreach"
      items: "{{ inputs.files }}"
      steps:
        - type: "mcp_call"
          mcp:
            method: "check_typescript"
            params:
              files: ["{{ item }}"]
          state_update:
            path: "raw.typescript_results.{{ item }}"
            value: "{{ result }}"

    - id: "check_lint"
      type: "foreach"
      items: "{{ inputs.files }}"
      steps:
        - type: "mcp_call"
          mcp:
            method: "lint_project"
            params:
              target_files: "{{ item }}"
          state_update:
            path: "raw.lint_results.{{ item }}"
            value: "{{ result }}"
```

## Main Workflow Using Shared Components

```yaml
# main-workflow.yaml
imports:
  - "shared/check-standards.yaml"

steps:
  - id: "run_checks"
    type: "include_workflow"
    workflow: "shared:check-standards"
    inputs:
      files: "{{ valid_files }}"
    # Computed state from included workflow is available
```

## Check Quality Shared Workflow

```yaml
# shared/check-quality.yaml
workflow:
  name: "shared:check-quality"

  state_schema:
    raw:
      lint_output: object
      test_output: object
      coverage_output: object

    computed:
      quality_score:
        from: ["raw.lint_output", "raw.test_output", "raw.coverage_output"]
        transform: |
          {
            lint: 100 - (input[0].errorCount || 0) * 10,
            tests: input[1].success ? 100 : 50,
            coverage: input[2].percentage || 0,
            overall: (100 - (input[0].errorCount || 0) * 10 +
                     (input[1].success ? 100 : 50) +
                     (input[2].percentage || 0)) / 3
          }

      needs_improvement:
        from: "computed.quality_score"
        transform: |
          Object.entries(input)
            .filter(([metric, score]) => score < 80)
            .map(([metric, score]) => ({ metric, score }))

  steps:
    - id: "run_lint"
      type: "mcp_call"
      mcp:
        method: "lint_project"
      state_update:
        path: "raw.lint_output"

    - id: "run_tests"
      type: "mcp_call"
      mcp:
        method: "run_test_suite"
      state_update:
        path: "raw.test_output"

    - id: "check_coverage"
      type: "shell_command"  # Executed internally by MCP
      command: "npm run coverage --silent"
      output_format: "json"
      state_update:
        path: "raw.coverage_output"
```

## Workflow Composition Benefits

### 1. **Reusable Components**
- Shared workflows can be imported by multiple workflows
- Common patterns (like standards checking) defined once
- Easy to maintain and update

### 2. **State Isolation**
- Each workflow maintains its own state namespace
- Computed fields cascade within the workflow
- Clear interfaces through inputs/outputs

### 3. **Modular Testing**
- Test shared workflows independently
- Mock inputs for unit testing
- Verify computed field transformations

### 4. **Version Management**
- Version shared workflows independently
- Track changes in imports
- Backward compatibility through versioning

## Example Usage in Main Workflow

```yaml
name: "release:prepare"
description: "Prepare for release by running all quality checks"

imports:
  - "shared/check-standards.yaml"
  - "shared/check-quality.yaml"

default_state:
  raw:
    release_version: ""
    checks_passed: {}
    deployment_target: ""

state_schema:
  raw:
    release_version: string
    checks_passed: object
    deployment_target: string

  computed:
    ready_for_release:
      from: "raw.checks_passed"
      transform: |
        Object.values(input).every(check => check === true)

steps:
  - id: "get_deployment_target"
    type: "user_input"
    prompt: "Enter deployment target (dev/staging/prod):"
    validation:
      pattern: "^(dev|staging|prod)$"
      error_message: "Must be one of: dev, staging, prod"
    state_update:
      path: "raw.deployment_target"

  - id: "get_version"
    type: "shell_command"  # Executed internally by MCP
    command: "npm version --json"
    output_format: "json"
    state_update:
      path: "raw.release_version"
      transform: "{{ result.version }}"

  - id: "run_standards_check"
    type: "include_workflow"
    workflow: "shared:check-standards"
    inputs:
      files: "{{ all_source_files }}"
    on_complete:
      - type: "state_update"
        path: "raw.checks_passed.standards"
        value: "{{ total_issues === 0 }}"

  - id: "run_quality_check"
    type: "include_workflow"
    workflow: "shared:check-quality"
    on_complete:
      - type: "state_update"
        path: "raw.checks_passed.quality"
        value: "{{ quality_score.overall >= 80 }}"

  - id: "report_status"
    type: "conditional"
    condition: "{{ ready_for_release }}"
    then:
      - type: "user_message"
        message: "✅ Ready for release v{{ release_version }} to {{ deployment_target }}!"
    else:
      - type: "user_message"
        message: "❌ Not ready for release. Fix issues and try again."
```