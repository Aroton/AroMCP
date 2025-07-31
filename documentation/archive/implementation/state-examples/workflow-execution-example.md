# Complete Workflow Example: standards:fix
# This file contains the full workflow definition and console execution example

## MCP Server Standard Prompts

The MCP server provides standard prompts for common workflow patterns. These prompts are not defined in workflows but are controlled by the MCP server to ensure consistency.

### Standard parallel_foreach Sub-agent Prompt

```
You are a workflow sub-agent. Your role is to execute a specific task by following the workflow system.

Process:
1. Call workflow.get_next_step with your task_id to get the next atomic action
2. Execute the action exactly as instructed
3. Update state as directed in the step
4. Mark the step complete
5. Repeat until get_next_step returns null

The workflow will guide you through all necessary steps. Simply follow the instructions
provided by each step. Do not make assumptions about what needs to be done - the 
workflow will tell you everything.
```

This prompt is automatically used for all `parallel_foreach` steps unless explicitly overridden.

## Workflow Definition

```yaml
name: "standards:fix"
description: "Apply coding standards to changed files using parallel processing"

config:
  max_parallel_agents: 10
  files_per_batch: 3

# Default state initialization (automatically applied by MCP on workflow.start)
default_state:
  raw:
    start_time: "{{ now() }}"
    batch_status: {}
    file_results: {}
    git_files: []
    final_typescript_result: null
    final_lint_result: null
    user_target_input: null  # Store user's input choice

state_schema:
  raw:
    # User inputs
    user_target_input: string  # branch name, commit guid, file path, or HEAD
    
    # Command outputs
    git_files: array
    command_output: string

    # Task tracking
    batch_status: object  # {batch_0: 'pending', batch_1: 'complete', ...}
    file_results: object  # {file_path: {status, fixes, errors}}

    # Results
    start_time: timestamp
    final_typescript_result: object
    final_lint_result: object

  computed:
    # Filter out unwanted files
    valid_files:
      from: "raw.git_files"
      transform: |
        input
          .filter(f => !f.includes('node_modules'))
          .filter(f => !f.includes('.min.'))
          .filter(f => !f.includes('/dist/'))
          .filter(f => !f.endsWith('.d.ts'))
          .filter(f => f.match(/\.(ts|tsx|js|jsx)$/))

    # Create batches from valid files
    file_batches:
      from: "computed.valid_files"
      transform: |
        input.reduce((batches, file, index) => {
          const batchIndex = Math.floor(index / 3);
          if (!batches[batchIndex]) batches[batchIndex] = [];
          batches[batchIndex].push(file);
          return batches;
        }, []).map((files, idx) => ({
          id: `batch_${idx}`,
          files: files
        }))

    # Find batches ready to process
    ready_batches:
      from: ["computed.file_batches", "raw.batch_status"]
      transform: |
        input[0].filter(batch => {
          const status = input[1][batch.id] || 'pending';
          return status === 'pending';
        })

    # Summary statistics
    summary:
      from: ["raw.file_results", "computed.valid_files"]
      transform: |
        {
          total_files: input[1].length,
          completed: Object.values(input[0]).filter(r => r.status === 'complete').length,
          failed: Object.values(input[0]).filter(r => r.status === 'failed').length,
          modified: Object.values(input[0]).filter(r => r.modified).length,
          total_fixes: Object.values(input[0]).reduce((sum, r) =>
            sum + (r.fixes?.hints || 0) + (r.fixes?.lint || 0) + (r.fixes?.typescript || 0), 0
          )
        }

    # Check if workflow is complete
    is_complete:
      from: ["computed.ready_batches", "computed.file_batches", "raw.batch_status"]
      transform: |
        input[0].length === 0 &&
        Object.keys(input[2]).length === input[1].length

steps:
  # First, ask the user what they want to compare against
  - id: "get_user_input"
    type: "user_input"
    prompt: |
      What files do you want to do a comparison against?
      
      Options:
      - branch <branch name> - Compare against a branch
      - commit <commit-guid> - Compare against a specific commit
      - file-path <file-path> - Process files matching a path pattern
      - HEAD - Process current uncommitted changes
    validation:
      pattern: "^(branch .+|commit [a-f0-9]{7,40}|file-path .+|HEAD)$"
      error_message: "Please provide a valid option: 'branch <name>', 'commit <guid>', 'file-path <path>', or 'HEAD'"
    state_update:
      path: "raw.user_target_input"

  # These shell commands are executed internally by MCP
  - id: "detect_files"
    type: "conditional"
    condition: "{{ user_target_input == 'HEAD' }}"
    then:
      - type: "shell_command"  # MCP executes internally
        command: "git diff --name-only HEAD"
        output_format: "lines"
        state_update:
          path: "raw.git_files"
    else:
      - type: "conditional"
        condition: "{{ user_target_input.startsWith('commit ') }}"
        then:
          - type: "shell_command"  # MCP executes internally
            command: "git diff-tree --no-commit-id --name-only -r {{ user_target_input.substring(7) }}"
            output_format: "lines"
            state_update:
              path: "raw.git_files"
        else:
          - type: "conditional"
            condition: "{{ user_target_input.startsWith('file-path ') }}"
            then:
              - type: "mcp_call"
                mcp:
                  method: "list_files"
                  params:
                    patterns: "{{ user_target_input.substring(10) }}/**/*.{ts,tsx,js,jsx}"
                state_update:
                  path: "raw.git_files"
            else:
              # Must be a branch
              - type: "shell_command"  # MCP executes internally
                command: "git diff --name-only {{ user_target_input.substring(7) }}"
                output_format: "lines"
                state_update:
                  path: "raw.git_files"

  # Example of a shell command that MUST be run by the agent (rare case)
  - id: "optional_agent_command"
    type: "conditional"
    condition: "{{ config.run_custom_script }}"
    then:
      - type: "agent_shell_command"  # Agent must execute this
        command: "./custom-analysis.sh {{ valid_files.join(' ') }}"
        reason: "Requires interactive terminal or special permissions"
        output_format: "json"
        state_update:
          path: "raw.custom_analysis"

  - id: "orchestration_loop"
    type: "while"
    condition: "{{ !is_complete }}"  # MCP resolves to computed.is_complete
    max_iterations: 50
    body:
      # Process all ready batches in parallel
      - id: "process_batches"
        type: "parallel_foreach"
        items: "{{ ready_batches }}"
        max_parallel: 10
        wait_for_all: true
        sub_agent_task: "process_standards_batch"
        # Uses MCP server's default parallel_foreach prompt (see top of file)

  - id: "final_validation"
    type: "sequential"
    steps:
      - id: "run_full_typescript_check"
        type: "mcp_call"
        mcp:
          method: "check_typescript"
        state_update:
          path: "raw.final_typescript_result"

      - id: "run_full_lint_check"
        type: "mcp_call"
        mcp:
          method: "lint_project"
          params:
            use_standards: true
        state_update:
          path: "raw.final_lint_result"

  - id: "report_results"
    type: "user_message"
    message: |
      ## Standards Fix Complete!

      **Summary:**
      - Files processed: {{ summary.completed }}/{{ summary.total_files }}
      - Files modified: {{ summary.modified }}
      - Total fixes applied: {{ summary.total_fixes }}
      - Exit code: {{ final_typescript_result.check_again ? 2 : final_lint_result.check_again ? 1 : 0 }}

# Sub-agent task definitions
sub_agent_tasks:
  process_standards_batch:
    steps:
      # First mark batch as processing
      - id: "mark_batch_processing_{{ task_id }}"
        type: "state_update"
        path: "raw.batch_status.{{ task_id }}"
        value: "processing"

      - id: "process_each_file_{{ task_id }}"
        type: "foreach"
        items: "{{ context.files }}"
        steps:
          - id: "update_file_processing"
            type: "state_update"
            path: "raw.file_results.{{ item | path_to_key }}"
            value:
              status: "processing"
              path: "{{ item }}"
              iteration: 0
              total_fixes: 0

          - id: "fix_until_clean"
            type: "while"
            condition: "{{ file_results[item].iteration < 5 }}"  # Safety limit
            max_iterations: 5
            body:
              # Check lint issues
              - id: "check_lint"
                type: "mcp_call"
                mcp:
                  method: "lint_project"
                  params:
                    use_standards: true
                    target_files: "{{ item }}"
                state_update:
                  path: "raw.file_results.{{ item | path_to_key }}.lint_check"

              # Fix lint issues if any
              - id: "fix_lint"
                type: "conditional"
                condition: "{{ file_results[item].lint_check?.fixable > 0 }}"
                then:
                  - type: "mcp_call"
                    mcp:
                      method: "lint_project"
                      params:
                        use_standards: true
                        target_files: "{{ item }}"
                        fix: true
                    state_update:
                      path: "raw.file_results.{{ item | path_to_key }}.lint_fixed"
                  - type: "state_update"
                    path: "raw.file_results.{{ item | path_to_key }}.total_fixes"
                    operation: "increment"
                    value: "{{ file_results[item].lint_fixed.fixed }}"

              # Check TypeScript issues
              - id: "check_typescript"
                type: "mcp_call"
                mcp:
                  method: "check_typescript"
                  params:
                    files: ["{{ item }}"]
                state_update:
                  path: "raw.file_results.{{ item | path_to_key }}.ts_check"

              # Fix TypeScript issues if any
              - id: "fix_typescript"
                type: "conditional"
                condition: "{{ file_results[item].ts_check?.errors?.length > 0 }}"
                then:
                  - type: "mcp_call"
                    mcp:
                      method: "hints_for_file"
                      params:
                        file_path: "{{ item }}"
                        session_id: "{{ parent.workflow.id }}"
                    state_update:
                      path: "raw.file_results.{{ item | path_to_key }}.hints"
                  - type: "apply_hints"
                    file: "{{ item }}"
                    hints: "{{ file_results[item].hints.data.hints }}"
                    state_update:
                      path: "raw.file_results.{{ item | path_to_key }}.hints_applied"
                      value: "{{ applied_count }}"
                  - type: "state_update"
                    path: "raw.file_results.{{ item | path_to_key }}.total_fixes"
                    operation: "increment"
                    value: "{{ file_results[item].hints_applied }}"

              # Update iteration count
              - id: "increment_iteration"
                type: "state_update"
                path: "raw.file_results.{{ item | path_to_key }}.iteration"
                operation: "increment"

              # Exit loop if no errors remain
              - id: "check_if_clean"
                type: "conditional"
                condition: |
                  (!file_results[item].lint_check?.check_again && 
                   !file_results[item].ts_check?.check_again)
                then:
                  - type: "break"  # Exit the while loop

          - id: "finalize_file"
            type: "state_update"
            path: "raw.file_results.{{ item | path_to_key }}"
            operation: "merge"
            value:
              status: |
                {{ (file_results[item].lint_check?.check_again || 
                    file_results[item].ts_check?.check_again) ? 'failed' : 'complete' }}
              modified: "{{ file_results[item].total_fixes > 0 }}"
              final_iteration: "{{ file_results[item].iteration }}"

      - id: "mark_batch_complete_{{ task_id }}"
        type: "state_update"
        path: "raw.batch_status.{{ task_id }}"
        value: "complete"
```

## Full Execution Example: Agent Console View

### Orchestrator Agent Console (With MCP Internal Execution)

```
USER: /workflow standards:fix start

ORCHESTRATOR: Getting workflow info...

MCP CALL: workflow.get_info
  params: {
    workflow: "standards:fix"  // MCP will look for:
                              // 1. ./.aromcp/workflows/standards:fix.yaml
                              // 2. ~/.aromcp/workflows/standards:fix.yaml
  }
RESULT: {
  name: "standards:fix",
  description: "Apply coding standards to changed files using parallel processing",
  version: "1.0.0"
}

Starting workflow standards:fix...

MCP CALL: workflow.start
  params: {
    workflow: "standards:fix"
  }

RESULT: {
  workflow_id: "wf_abc123",
  state: {
    // Flattened view - agent doesn't see raw/computed/state distinction
    start_time: "2024-01-20T10:00:00Z",
    batch_status: {},
    file_results: {},
    git_files: [],
    final_typescript_result: null,
    final_lint_result: null,
    user_target_input: null,
    valid_files: [],
    file_batches: [],
    ready_batches: [],
    summary: { total_files: 0, completed: 0, failed: 0, modified: 0, total_fixes: 0 },
    is_complete: false
  }
}

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }

RESULT: {
  step: {
    id: "get_user_input",
    type: "user_input",
    instructions: "Ask the user for input and validate the response. Store the validated input in state.",
    definition: {
      prompt: "What files do you want to do a comparison against?\n\nOptions:\n- branch <branch name> - Compare against a branch\n- commit <commit-guid> - Compare against a specific commit\n- file-path <file-path> - Process files matching a path pattern\n- HEAD - Process current uncommitted changes",
      validation: {
        pattern: "^(branch .+|commit [a-f0-9]{7,40}|file-path .+|HEAD)$",
        error_message: "Please provide a valid option: 'branch <name>', 'commit <guid>', 'file-path <path>', or 'HEAD'"
      },
      state_update: {
        path: "raw.user_target_input"
      }
    }
  }
}

What files do you want to do a comparison against?

Options:
- branch <branch name> - Compare against a branch
- commit <commit-guid> - Compare against a specific commit
- file-path <file-path> - Process files matching a path pattern
- HEAD - Process current uncommitted changes

USER: HEAD

Validating input... ✓

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_abc123",
    updates: [{
      path: "raw.user_target_input",
      value: "HEAD"
    }]
  }

RESULT: {
  success: true
}

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "get_user_input" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }

// NOTE: MCP server internally executed the shell command "git diff --name-only HEAD"
// and updated the state with the results. The agent skips directly to the next meaningful step.

RESULT: {
  step: {
    id: "orchestration_loop.process_batches",
    type: "parallel_tasks",
    instructions: "Create sub-agents for ALL tasks listed. Execute them in parallel. Wait for ALL to complete before calling get_next_step again.",
    definition: {
      // sub_agent_prompt provided by MCP server's default parallel_foreach prompt
      tasks: [
        {
          task_id: "batch_0",
          context: {
            files: ["src/index.ts", "src/utils/helper.ts", "src/components/Button.tsx"],
            workflow_id: "wf_abc123"
          }
        },
        {
          task_id: "batch_1",
          context: {
            files: ["src/components/Card.tsx", "src/api/users.ts", "src/api/auth.ts"],
            workflow_id: "wf_abc123"
          }
        },
        {
          task_id: "batch_2",
          context: {
            files: ["tests/utils.test.ts"],
            workflow_id: "wf_abc123"
          }
        }
      ]
    }
  },
  // Optional debug info showing what MCP did internally
  _internal_executions: [
    {
      step_id: "detect_files.then.shell_command",
      command: "git diff --name-only HEAD",
      result: ["src/index.ts", "src/utils/helper.ts", "src/components/Button.tsx", 
               "src/components/Card.tsx", "src/api/users.ts", "src/api/auth.ts", 
               "tests/utils.test.ts", "node_modules/some-lib/index.js", "dist/bundle.min.js"],
      state_updates: [
        { path: "raw.git_files", value: [/* 9 files */] }
      ]
    }
  ]
}

Executing step: orchestration_loop.process_batches
Following instructions: "Create sub-agents for ALL tasks listed..."

CLAUDE CODE: Creating sub-agent for batch_0
CLAUDE CODE: Creating sub-agent for batch_1
CLAUDE CODE: Creating sub-agent for batch_2

[WAITING FOR ALL 3 SUB-AGENTS TO COMPLETE...]

CLAUDE CODE: Sub-agent batch_0 returned: complete
CLAUDE CODE: Sub-agent batch_1 returned: complete
CLAUDE CODE: Sub-agent batch_2 returned: complete

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "orchestration_loop.process_batches" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }

RESULT: {
  step: {
    id: "final_validation.run_full_typescript_check",
    type: "mcp_call",
    instructions: "Run TypeScript check on entire project and store result.",
    definition: {
      method: "check_typescript",
      params: {},
      state_update: {
        path: "raw.final_typescript_result"
      }
    }
  }
}

Executing step: final_validation.run_full_typescript_check

MCP CALL: check_typescript
RESULT: { errors: [], check_again: false }

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_abc123",
    updates: [{
      path: "raw.final_typescript_result",
      value: { errors: [], check_again: false }
    }]
  }
RESULT: { success: true }

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "final_validation.run_full_typescript_check" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }

RESULT: {
  step: {
    id: "final_validation.run_full_lint_check",
    type: "mcp_call",
    instructions: "Run lint check with standards and store result.",
    definition: {
      method: "lint_project",
      params: { use_standards: true },
      state_update: {
        path: "raw.final_lint_result"
      }
    }
  }
}

Executing step: final_validation.run_full_lint_check

MCP CALL: lint_project
  params: { use_standards: true }
RESULT: { issues: [], check_again: false }

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_abc123",
    updates: [{
      path: "raw.final_lint_result",
      value: { issues: [], check_again: false }
    }]
  }
RESULT: { success: true }

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "final_validation.run_full_lint_check" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }

RESULT: {
  step: {
    id: "report_results",
    type: "user_message",
    instructions: "Display this message to the user.",
    definition: {
      message: "## Standards Fix Complete!\n\n**Summary:**\n- Files processed: 7/7\n- Files modified: 5\n- Total fixes applied: 23\n- Exit code: 0"
    }
  }
}

## Standards Fix Complete!

**Summary:**
- Files processed: 7/7
- Files modified: 5
- Total fixes applied: 23
- Exit code: 0

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "report_results" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_abc123" }
RESULT: null

Workflow complete!

MCP CALL: workflow.complete
  params: { workflow_id: "wf_abc123", status: "success" }
RESULT: {
  success: true,
  final_state: {
    // Final flattened state with all results
    start_time: "2024-01-20T10:00:00Z",
    user_target_input: "HEAD",
    git_files: [9 files],
    valid_files: [7 files],
    file_batches: [3 batches],
    batch_status: {
      batch_0: "complete",
      batch_1: "complete",
      batch_2: "complete"
    },
    file_results: { /* detailed results per file */ },
    summary: {
      total_files: 7,
      completed: 7,
      failed: 0,
      modified: 5,
      total_fixes: 23
    },
    is_complete: true
  }
}

## Workflow Summary

The standards:fix workflow completed successfully:
- Started at: 2024-01-20T10:00:00Z
- Target: HEAD (current uncommitted changes)
- Processed 7 TypeScript/JavaScript files
- Modified 5 files that needed fixes
- Applied 23 total fixes:
  - Lint fixes: 15
  - TypeScript hints: 8
- All files now pass TypeScript and lint checks
- No errors encountered during processing
```

### Alternative Example: When Agent Must Execute Command

```
# Example workflow snippet showing agent_shell_command
USER: /workflow custom:analyze start --with-interactive

MCP CALL: workflow.get_next_step
  params: { workflow_id: "wf_xyz789" }

RESULT: {
  step: {
    id: "run_interactive_analysis",
    type: "agent_shell_command",
    instructions: "This command requires interactive terminal access. Execute it and capture the output.",
    definition: {
      command: "./analyze-interactive.sh src/",
      reason: "Requires TTY for progress bars and user prompts",
      output_format: "json",
      timeout: 300000,  // 5 minutes
      state_update: {
        path: "raw.interactive_analysis",
        value: "{{ result }}"
      }
    }
  }
}

Executing step: run_interactive_analysis
Following instructions: "This command requires interactive terminal access..."

SHELL: ./analyze-interactive.sh src/
[Interactive progress bar showing...]
Analyzing file 1/50: src/index.ts
Analyzing file 2/50: src/utils/helper.ts
...
Analysis complete!

STDOUT:
{
  "analyzed": 50,
  "issues": 12,
  "suggestions": 45
}

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_xyz789",
    updates: [{
      path: "raw.interactive_analysis",
      value: {
        "analyzed": 50,
        "issues": 12,
        "suggestions": 45
      }
    }]
  }
RESULT: { success: true }
```

### Sub-Agent Console (batch_0)

```
SUB-AGENT: Starting workflow task

Initial prompt: [MCP Server Default parallel_foreach Prompt]
"You are a workflow sub-agent. Your role is to execute a specific task by following the workflow system..."

Context: {
  task_id: "batch_0",
  files: ["src/index.ts", "src/utils/helper.ts", "src/components/Button.tsx"],
  workflow_id: "wf_abc123"
}

Following the workflow process - calling get_next_step...

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "mark_batch_processing_batch_0",
    type: "state_update",
    instructions: "Mark this batch as 'processing' to indicate work has begun. This prevents other agents from picking up the same batch.",
    definition: {
      updates: [{
        path: "raw.batch_status.batch_0",
        operation: "set",
        value: "processing"
      }]
    }
  }
}

Following instructions: "Mark this batch as 'processing' to indicate work has begun..."

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_abc123",
    updates: [{
      path: "raw.batch_status.batch_0",
      value: "processing"
    }]
  }
RESULT: { success: true }

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "mark_batch_processing_batch_0" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

// Processing first file: src/index.ts
RESULT: {
  step: {
    id: "update_file_processing",
    type: "state_update",
    instructions: "Initialize processing state for src/index.ts with iteration counter and fix tracker.",
    definition: {
      updates: [{
        path: "raw.file_results.src_index_ts",
        value: {
          status: "processing",
          path: "src/index.ts",
          iteration: 0,
          total_fixes: 0
        }
      }]
    }
  }
}

[State update executed...]

// Start fix loop - Iteration 1
MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "check_lint",
    type: "mcp_call",
    instructions: "Check src/index.ts for lint issues. This is the first step of the fix cycle.",
    definition: {
      method: "lint_project",
      params: {
        use_standards: true,
        target_files: "src/index.ts"
      },
      state_update: {
        path: "raw.file_results.src_index_ts.lint_check"
      }
    }
  }
}

Following instructions: "Check src/index.ts for lint issues..."

MCP CALL: lint_project
  params: {
    use_standards: true,
    target_files: "src/index.ts"
  }
RESULT: {
  issues: 3,
  fixable: 2,
  check_again: true,
  errors: [
    { line: 10, rule: "semi", message: "Missing semicolon" },
    { line: 12, rule: "quotes", message: "Strings must use single quotes" },
    { line: 30, rule: "no-unused-vars", message: "Variable 'temp' is never used" }
  ]
}

[State update completed...]

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "fix_lint",
    type: "mcp_call",
    instructions: "Lint found 2 fixable issues. Apply automatic fixes for semicolon and quotes issues.",
    definition: {
      method: "lint_project",
      params: {
        use_standards: true,
        target_files: "src/index.ts",
        fix: true
      },
      state_update: {
        path: "raw.file_results.src_index_ts.lint_fixed"
      }
    }
  }
}

Following instructions: "Lint found 2 fixable issues. Apply automatic fixes..."

MCP CALL: lint_project
  params: {
    use_standards: true,
    target_files: "src/index.ts",
    fix: true
  }
RESULT: { fixed: 2, remaining: 1 }

[State updates: lint_fixed result and increment total_fixes by 2...]

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "check_typescript",
    type: "mcp_call",
    instructions: "Check src/index.ts for TypeScript errors now that lint issues are fixed.",
    definition: {
      method: "check_typescript",
      params: {
        files: ["src/index.ts"]
      },
      state_update: {
        path: "raw.file_results.src_index_ts.ts_check"
      }
    }
  }
}

Following instructions: "Check src/index.ts for TypeScript errors..."

MCP CALL: check_typescript
  params: {
    files: ["src/index.ts"]
  }
RESULT: {
  errors: [
    { line: 15, message: "Function lacks return type annotation", code: "TS7006" },
    { line: 23, message: "Variable 'config' implicitly has 'any' type", code: "TS7005" }
  ],
  check_again: true
}

[State update completed...]

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "get_hints_for_typescript_fixes",
    type: "mcp_call",
    instructions: "TypeScript found 2 errors. Get hints to fix these type annotation issues.",
    definition: {
      method: "hints_for_file",
      params: {
        file_path: "src/index.ts",
        session_id: "wf_abc123"
      },
      state_update: {
        path: "raw.file_results.src_index_ts.hints"
      }
    }
  }
}

Following instructions: "TypeScript found 2 errors. Get hints..."

MCP CALL: hints_for_file
  params: {
    file_path: "src/index.ts",
    session_id: "wf_abc123"
  }
RESULT: {
  data: {
    hints: [
      {
        line: 15,
        hint: "Add return type annotation: ': Promise<User[]>'",
        severity: "error"
      },
      {
        line: 23,
        hint: "Variable 'config' implicitly has 'any' type. Add type annotation: ': ConfigOptions'",
        severity: "error"
      }
    ]
  }
}

[State update completed...]

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "apply_typescript_hints",
    type: "apply_hints",
    instructions: "Apply the 2 TypeScript hints to add missing type annotations.",
    definition: {
      file: "src/index.ts",
      hints: [/* hints from previous step */],
      state_update: {
        path: "raw.file_results.src_index_ts.hints_applied",
        value: "{{ applied_count }}"
      }
    }
  }
}

Following instructions: "Apply the 2 TypeScript hints..."

[Agent applies hints to fix TypeScript errors]

[State updates: hints_applied = 2, increment total_fixes by 2, increment iteration...]

// Iteration 2 - Check again
MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "check_lint",
    type: "mcp_call",
    instructions: "Re-check lint after TypeScript fixes. Iteration 2 of fix cycle.",
    definition: {
      method: "lint_project",
      params: {
        use_standards: true,
        target_files: "src/index.ts"
      },
      state_update: {
        path: "raw.file_results.src_index_ts.lint_check"
      }
    }
  }
}

Following instructions: "Re-check lint after TypeScript fixes..."

MCP CALL: lint_project
  params: {
    use_standards: true,
    target_files: "src/index.ts"
  }
RESULT: {
  issues: 1,
  fixable: 0,
  check_again: false,  // Only unfixable issue remains (unused variable)
  errors: [
    { line: 30, rule: "no-unused-vars", message: "Variable 'temp' is never used" }
  ]
}

[Continue checking TypeScript - finds no errors]

// Exit condition met - no more fixable issues
MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "finalize_file",
    type: "state_update",
    instructions: "File processing complete. One unfixable lint issue remains (unused variable). Mark file as complete with 4 total fixes applied.",
    definition: {
      updates: [{
        path: "raw.file_results.src_index_ts",
        operation: "merge",
        value: {
          status: "complete",  // Would be "failed" if fixable issues remained
          modified: true,
          final_iteration: 2
        }
      }]
    }
  }
}

[Process repeats for remaining files: src/utils/helper.ts and src/components/Button.tsx]

// After all files are processed
MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }

RESULT: {
  step: {
    id: "mark_batch_complete_batch_0",
    type: "state_update",
    instructions: "All 3 files in this batch have been processed. Mark the batch as complete. Total fixes applied: 12 (4 per file average).",
    definition: {
      updates: [{
        path: "raw.batch_status.batch_0",
        operation: "set",
        value: "complete"
      }]
    }
  }
}

Following instructions: "All files in this batch have been processed..."

MCP CALL: workflow_state.update
  params: {
    workflow_id: "wf_abc123",
    updates: [{
      path: "raw.batch_status.batch_0",
      value: "complete"
    }]
  }
RESULT: { success: true }

MCP CALL: workflow.step_complete
  params: { workflow_id: "wf_abc123", step_id: "mark_batch_complete_batch_0" }
RESULT: { success: true }

MCP CALL: workflow.get_next_step
  params: { 
    workflow_id: "wf_abc123", 
    sub_agent_context: { task_id: "batch_0" } 
  }
RESULT: null

Workflow task complete. Returning to orchestrator.
```

## Key Benefits of MCP Internal Execution

1. **Reduced Context Usage**: Agent never sees intermediate bash commands or their outputs
2. **Fewer Round Trips**: No back-and-forth for simple command execution
3. **Cleaner Agent Flow**: Agent jumps from meaningful step to meaningful step
4. **Better Error Handling**: MCP can retry commands internally without agent involvement
5. **Optional Debug Info**: `_internal_executions` field can show what happened (for debugging)

## Step Type Comparison

| Step Type | Executed By | When to Use |
|-----------|-------------|-------------|
| `shell_command` | MCP Server | Default for all bash commands - data collection, git operations, etc. |
| `agent_shell_command` | Agent | Only when requiring: interactive TTY, special permissions, user environment |
| `mcp_call` | Agent | All MCP tool calls that aren't built into workflow system |
| `state_update` | Agent | Direct state modifications |
| `user_input` | Agent | User interaction required |
| `user_message` | Agent | Display output to user |
| `parallel_tasks` | Agent | Delegate to sub-agents |

## MCP-Controlled Standard Prompts

The MCP server maintains standard prompts for common workflow patterns:

### Benefits:
1. **Consistency**: All workflows using `parallel_foreach` get the same sub-agent behavior
2. **Centralized Updates**: Improve the prompt once, all workflows benefit
3. **Simplified Workflows**: No need to repeat prompts in every workflow
4. **Future Evolution**: Can add new prompt types as patterns emerge

### Standard Prompt Types:
- `parallel_foreach`: Default sub-agent prompt for parallel task execution
- `sequential_task`: (Future) For sequential sub-task delegation
- `retry_handler`: (Future) For error recovery sub-agents
- `validation_agent`: (Future) For quality check sub-agents

### Override Capability:
Workflows can still provide custom prompts when needed:
```yaml
- type: "parallel_foreach"
  sub_agent_prompt_override: "Custom prompt for special handling..."
```

This design ensures workflows remain clean and focused on logic while the MCP server handles the operational details of agent coordination.

## Simplified Fix Loop Benefits

The updated fix loop (check lint → fix lint → check TypeScript → fix TypeScript → repeat) provides:

1. **Clear Logic**: Simple pattern that's easy to understand and debug
2. **Atomic Operations**: Each step does one thing well
3. **No Redundant Checks**: Loop continues until clean, eliminating need for final validation
4. **Efficient Processing**: Only fetches hints when TypeScript errors are found
5. **Natural Exit**: Loop exits when both lint and TypeScript report no fixable issues

This approach reduces complexity while ensuring thorough error resolution.