# Simple Workflow Examples

## Simple Command + Transform Example

```yaml
name: "analyze:dependencies"
description: "Analyze npm dependencies"

# Default state initialization
default_state:
  raw:
    package_json: ""
    npm_list: ""

state_schema:
  raw:
    package_json: string
    npm_list: string

  computed:
    dependencies:
      from: "raw.package_json"
      transform: |
        JSON.parse(input).dependencies || {}

    outdated_deps:
      from: "raw.npm_list"
      transform: |
        input.split('\n')
          .filter(line => line.includes('outdated'))
          .map(line => {
            const parts = line.split(/\s+/);
            return {
              name: parts[0],
              current: parts[1],
              wanted: parts[2],
              latest: parts[3]
            };
          })

    security_risks:
      from: ["computed.outdated_deps", "computed.dependencies"]
      transform: |
        input[0].filter(dep => {
          const current = input[1][dep.name];
          return current && dep.latest.split('.')[0] > current.split('.')[0];
        })

steps:
  - id: "read_package"
    type: "shell_command"  # Executed internally by MCP
    command: "cat package.json"
    output_format: "text"
    state_update:
      path: "raw.package_json"

  - id: "check_outdated"
    type: "shell_command"  # Executed internally by MCP
    command: "npm outdated --json || true"
    output_format: "text"
    state_update:
      path: "raw.npm_list"

  - id: "report"
    type: "user_message"
    message: |
      Found {{ outdated_deps.length }} outdated dependencies
      Major version updates needed: {{ security_risks.length }}
```

## State Schema Features Example

```yaml
# Default state values (applied automatically on workflow.start)
default_state:
  raw:
    counter: 0
    status: "initialized"
    items: []
    config:
      retries: 3
      timeout: 5000

state_schema:
  # Simple raw fields
  raw:
    git_output: string
    test_results: object

  # Computed fields with single dependency
  computed:
    parsed_files:
      from: "raw.git_output"
      transform: "input.split('\\n').filter(l => l.trim())"

    # Computed from another computed field (cascading)
    valid_files:
      from: "computed.parsed_files"
      transform: |
        input.filter(f =>
          f.endsWith('.ts') ||
          f.endsWith('.js')
        )

    # Multiple dependencies
    analysis_summary:
      from: ["computed.valid_files", "raw.test_results"]
      transform: |
        {
          total_files: input[0].length,
          failed_tests: input[1].failed || 0,
          ready_to_deploy: input[0].length > 0 && input[1].failed === 0
        }

    # Access full state in transform (MCP provides flattened view internally)
    complex_calculation:
      from: "computed.valid_files"
      transform: |
        input.map(file => ({
          path: file,
          has_test: test_results.files?.includes(file),  // MCP provides flattened access
          batch: file_batches?.findIndex(b => b.includes(file))
        }))
```

## Example State Updates

```yaml
# MCP executes shell command internally
- type: "shell_command"
  command: "find . -name '*.ts' -exec wc -l {} +"
  output_format: "lines"
  state_update:
    path: "raw.line_counts"  # Must use full path
    value: "{{ result }}"

# MCP automatically computes:
# - parsed_counts (parse the wc output)
# - large_files (files > 1000 lines)
# - summary_stats (total lines, avg, etc.)

# Agent can immediately use computed state in conditions
- type: "conditional"
  condition: "{{ large_files.length > 0 }}"  # Flattened path
  then:
    - type: "user_message"
      message: "Found {{ large_files.length }} large files"
```

## MCP Control Flow Examples

Here's how MCP handles control flow internally and returns atomic steps to agents:

```typescript
// YAML: Conditional with nested steps
- type: "conditional"
  condition: "{{ errors > 0 }}"  // Flattened path
  then:
    - type: "shell_command"
      command: "npm run fix"
    - type: "state_update"
      path: "raw.fix_attempted"  // Full path for updates
      value: true

// What agent receives (if condition is true and MCP executes shell command):
// Note: Agent skips the shell_command since MCP executes it internally
get_next_step() → {
  id: "fix_errors.then.1.state_update",
  type: "state_update",
  instructions: "Mark that fix was attempted (npm fix already executed by MCP)",
  definition: {
    updates: [{ path: "raw.fix_attempted", value: true }]
  }
}

// YAML: While loop with ready batches check
- type: "while"
  condition: "{{ !is_complete }}"
  body:
    - type: "parallel_foreach"
      items: "{{ ready_batches }}"
      sub_agent_task: "process_batch"

// What agent receives when ready_batches exist:
get_next_step() → {
  id: "orchestration_loop.process_batches",
  type: "parallel_tasks",
  instructions: "Create sub-agents for ALL tasks listed. Execute them in parallel.",
  definition: {
    // sub_agent_prompt provided by MCP server's default
    tasks: [
      { task_id: "batch_0", context: {...} },
      { task_id: "batch_1", context: {...} },
      { task_id: "batch_2", context: {...} }
    ]
  }
}

// What agent receives when no ready batches (loop exits):
get_next_step() → {
  id: "final_validation.run_full_typescript_check",
  type: "mcp_call",
  instructions: "Run TypeScript check on entire project",
  definition: {
    method: "check_typescript",
    params: {},
    state_update: { path: "raw.final_typescript_result" }
  }
}

// YAML: ForEach that becomes multiple updates
- type: "foreach"
  items: "{{ files_to_process }}"  // Flattened path
  steps:
    - type: "state_update"
      path: "raw.file_status.{{ item | path_to_key }}"  // Full path
      value: "processing"

// What agent receives (all items expanded):
get_next_step() → {
  id: "process_files.foreach.expanded",
  type: "state_update",
  instructions: "Update status for all files to 'processing'",
  definition: {
    updates: [
      { path: "raw.file_status.src_index_ts", value: "processing" },
      { path: "raw.file_status.src_utils_ts", value: "processing" },
      { path: "raw.file_status.src_main_ts", value: "processing" }
    ]
  }
}

// YAML: User input with validation
- type: "user_input"
  prompt: "Select deployment environment: dev, staging, or prod"
  validation:
    pattern: "^(dev|staging|prod)$"
    error_message: "Please enter: dev, staging, or prod"
  state_update:
    path: "raw.target_env"

// What agent receives:
get_next_step() → {
  id: "get_deployment_env",
  type: "user_input",
  instructions: "Ask the user for input and validate the response. Store in state.",
  definition: {
    prompt: "Select deployment environment: dev, staging, or prod",
    validation: {
      pattern: "^(dev|staging|prod)$",
      error_message: "Please enter: dev, staging, or prod"
    },
    state_update: {
      path: "raw.target_env"
    }
  }
}

// YAML: Agent shell command for interactive script
- type: "agent_shell_command"
  command: "./deploy-interactive.sh {{ target_env }}"
  reason: "Requires interactive prompts and progress bars"
  output_format: "json"
  timeout: 600000  # 10 minutes
  state_update:
    path: "raw.deployment_result"

// What agent receives:
get_next_step() → {
  id: "run_deployment",
  type: "agent_shell_command",
  instructions: "This command requires interactive terminal. Execute it and capture output.",
  definition: {
    command: "./deploy-interactive.sh prod",  // Variable replaced
    reason: "Requires interactive prompts and progress bars",
    output_format: "json",
    timeout: 600000,
    state_update: {
      path: "raw.deployment_result"
    }
  }
}
```