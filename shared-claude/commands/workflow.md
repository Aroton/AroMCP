# /workflow

**Purpose**: Execute and manage MCP workflows through the unified workflow server system.

**Execution Pattern**: Main agent interacts with the workflow engine through MCP tools to execute workflow steps sequentially or delegate to sub-agents for parallel execution.

## Usage
- `/workflow list` - List all available workflows
- `/workflow {workflow_name} info` - Get detailed information about a workflow
- `/workflow {workflow_name} start [--input key=value ...]` - Start a new workflow instance
- `/workflow resume {workflow_id}` - Resume a previously started workflow
- `/workflow status {workflow_id}` - Check the status of a running workflow

## Debug Mode
To enable serial execution for easier debugging of parallel workflows, set the environment variable:
```bash
AROMCP_WORKFLOW_DEBUG=serial
```

When enabled:
- All `parallel_foreach` steps convert to TODO mode in the main agent
- NO sub-agents are spawned - everything executes in the main agent context  
- Tasks are processed serially using the TodoWrite tool for progress tracking
- Sub-agent steps are executed directly by the main agent with item context
- The workflow logic remains identical - only execution method changes

## Main Agent Workflow

### Critical Constraints
- ALWAYS use the MCP workflow tools, never directly manipulate workflow files
- RESPECT the workflow's defined steps and control flow
- UPDATE state only through workflow_update_state tool
- HANDLE errors gracefully and report them clearly
- For parallel steps, delegate to sub-agents appropriately
- STEP COMPLETION is implicit - simply call workflow_get_next_step to advance

### Command: `/workflow list`
1. Call `workflow_list` tool to get available workflows
2. Display in a formatted table showing:
   - Workflow name (with namespace if present)
   - Version
   - Brief description
   - Number of input parameters
3. Group by namespace if multiple namespaces exist

### Command: `/workflow {workflow_name} info`
1. Call `workflow_get_info` with the workflow name
2. Display comprehensive information:
   - Full name and version
   - Detailed description
   - Input parameters with types and descriptions
   - Required vs optional parameters
   - Initial state structure
   - Number of steps
   - Whether it uses sub-agents
3. Provide example start command with required inputs

### Command: `/workflow {workflow_name} start`
1. Parse input parameters from command line:
   - Format: `--input key=value` for each parameter
   - Support JSON values: `--input config='{"debug": true}'`
   - Validate required parameters are provided
2. Call `workflow_get_info` to verify inputs
3. Call `workflow_start` with validated inputs
4. Store workflow_id for execution
5. Begin workflow execution loop:
   ```
   while workflow not complete:
     1. Call workflow_get_next_step(workflow_id)
     2. If no step returned, workflow is complete
     3. Execute the step based on its type:
        - mcp_call: Execute MCP tool, store result if needed
        - agent_task: Execute the prompt instruction
        - shell_command: (Server handles - just continue)
        - user_message: Display message to user
        - user_input: Prompt user for input
        - parallel_foreach: Create sub-agents
        - Other types: Follow step instructions
     4. Handle any errors and report status
   ```
   
   **MCP Call Pattern with store_result**:
   ```javascript
   // When step.type === "mcp_call" && step.store_result:
   const result = await execute_mcp_tool(step.tool, step.parameters);
   await workflow_update_state(workflow_id, [{
     path: step.store_result,
     value: result
   }]);
   ```
6. Report workflow completion status and final state

### Command: `/workflow resume {workflow_id}`
1. Call `workflow_resume` with the workflow_id
2. If successful, continue execution loop from step 5 of start command
3. If workflow not found or already complete, report status

### Command: `/workflow status {workflow_id}`
1. Call workflow tools to check instance status
2. Display:
   - Workflow name and ID
   - Current status (pending/running/completed/failed)
   - Progress (current step / total steps)
   - Current state summary
   - Execution duration
   - Any error messages if failed

## Step Execution Details

### MCP Tool Calls (`mcp_call`)
```javascript
const step = {
  type: "mcp_call",
  tool: "aromcp.lint_project",
  parameters: {
    use_eslint_standards: true,
    target_files: ["{{ file_path }}"]
  },
  store_result: "raw.lint_output"  // Where to store tool result in state
};
```
1. Extract tool name and parameters
2. Interpolate any template variables ({{ variable }})
3. Call the specified MCP tool
4. **CRITICAL**: If step has `store_result`, use `workflow_update_state` to store the result at that path
5. Continue with `workflow_get_next_step()` to advance

**Important**: Steps with `store_result` require you to manually store the result:
```javascript
// When you see store_result in a step definition:
const step = {
  type: "mcp_call", 
  tool: "aromcp.lint_project",
  parameters: {...},
  store_result: "state.lint_tool_output"  // <- You must store result here
};

// Execute like this:
// 1. Call the MCP tool and get result
const result = aromcp.lint_project(parameters);

// 2. Store the result at the specified path
workflow_update_state(workflow_id, [{
  path: "state.lint_tool_output",  // Use the store_result path
  value: result
}]);

// 3. Continue with next step
workflow_get_next_step(workflow_id);
```

### Agent Tasks (`agent_task`)
```javascript
const step = {
  type: "agent_task",
  prompt: "Fix any linting errors found in {{ file_path }}. Use the file editing tools to make changes.",
  context: {
    file_path: "src/component.ts"
  }
};
```
1. Read the prompt instruction for the agent
2. Interpolate any template variables in prompt and context
3. Execute the task directly using available tools
4. Mark step complete when task is finished

### State Updates (via other steps)
State updates are now embedded within other step types using the `state_update` or `state_updates` field:
- `mcp_call`: Use `state_update` field to store tool results
- `user_input`: Use `state_update` field to store user input
- `agent_response`: Use `state_updates` field for multiple updates
- `shell_command`: Use `state_update` field to store command output

### User Interaction (`user_input`, `user_message`)
```javascript
const step = {
  type: "user_input",
  prompt: "Enter the target directory:",
  variable: "target_dir",
  validation: "path"  // optional
};
```
1. Display prompt to user
2. Collect input
3. Validate if validation specified
4. Store in state at specified variable
5. Mark step complete

### Parallel Execution (`parallel_foreach`)
```javascript
const step = {
  type: "parallel_foreach",
  items: "{{ files }}",
  sub_agent_task: "process_file",
  max_parallel: 10,
  instructions: "Create sub-agents for ALL tasks listed. Execute them in parallel. Wait for ALL to complete before calling get_next_step again.",
  subagent_prompt: "You are a workflow sub-agent. Your role is to execute a specific task by following the workflow system...",
  definition: {
    tasks: [
      {
        task_id: "process_file.item0",
        context: {
          item: "file1.ts",
          index: 0,
          total: 3,
          task_id: "process_file.item0",
          parent_step_id: "step_3",
          workflow_id: "wf_abc123"
        }
      }
      // ... more tasks
    ]
  }
};
```

#### Normal Execution Mode
**Client-Side Sub-Agent Creation**:
1. **Client orchestrator** receives parallel_foreach step with task list
2. **For each task** (up to `max_parallel`), spawn a new sub-agent using the provided `subagent_prompt`
3. **Sub-agents** call `workflow_get_next_step(workflow_id, task_id)` to get their specific steps
4. **Sub-agents** execute steps defined in workflow's `sub_agent_tasks` section
5. **Sub-agents** continue until `workflow_get_next_step` returns null (task complete)
6. **Wait for ALL sub-agents** to complete before main agent continues

#### Debug Serial Mode (`AROMCP_WORKFLOW_DEBUG=serial`)
When you see this debug note in a parallel_foreach step:
```
🐛 DEBUG MODE: Execute as TODOs in main agent instead of spawning sub-agents. Process each item serially for easier debugging.
```

**🚨 CRITICAL: TODO Mode - NOT Sub-Agent Mode**:
1. **DO NOT spawn any sub-agents** - stay in the main agent
2. **Convert each task to a TODO item** in your task list
3. **Process TODOs serially one at a time** using the sub-agent steps inline
4. **Use TodoWrite tool** to track progress through each item
5. **Execute sub-agent steps directly** in the main agent context

**TODO Mode Execution Pattern**:
```javascript
// When you see debug_serial: true in parallel_foreach definition
const step = {
  type: "parallel_foreach",
  definition: {
    debug_serial: true,  // 🚨 This means TODO mode!
    tasks: [
      {task_id: "process_file.item0", context: {item: "file1.ts", ...}},
      {task_id: "process_file.item1", context: {item: "file2.ts", ...}},
      {task_id: "process_file.item2", context: {item: "file3.ts", ...}}
    ]
  }
};

// Execute as:
// 1. TodoWrite: Add all items to TODO list  
// 2. For each TODO item:
//    - Mark as in_progress
//    - Execute sub-agent steps directly in main agent
//    - Use item context (file_path, etc.) for step execution
//    - Mark as completed when done
// 3. Continue to next workflow step
```

**Key Differences**:
- **Production Mode**: Spawn sub-agents for parallel execution
- **Debug Mode**: Execute as TODOs in main agent for visibility and control

**Concrete TODO Mode Example**:
```javascript
// When you receive this in debug mode:
{
  "type": "parallel_foreach",  
  "definition": {
    "debug_serial": true,
    "instructions": "🚨 DEBUG MODE: Execute as TODOs in main agent. DO NOT spawn sub-agents...",
    "tasks": [
      {"task_id": "process_file.item0", "context": {"item": "file1.ts", "file_path": "file1.ts"}},
      {"task_id": "process_file.item1", "context": {"item": "file2.ts", "file_path": "file2.ts"}}
    ],
    "sub_agent_steps": [
      {"id": "get_hints", "type": "mcp_call", "definition": {"tool": "aromcp.hints_for_files", "parameters": {"file_paths": ["{{ file_path }}"]}, "store_result": "raw.hints_output"}},
      {"id": "apply_fixes", "type": "agent_task", "definition": {"prompt": "Apply the hints to fix {{ file_path }}"}},
      {"id": "lint_check", "type": "mcp_call", "definition": {"tool": "aromcp.lint_project", "parameters": {"target_files": ["{{ file_path }}"]}, "store_result": "raw.lint_output"}}
    ]
  }
}

// Execute like this:
// 1. TodoWrite: ["Process file1.ts with hints and lint", "Process file2.ts with hints and lint"] 
// 2. Mark "Process file1.ts..." as in_progress
// 3. Execute: aromcp.hints_for_files with file_paths=["file1.ts"] (result stored in raw.hints_output)
// 4. Execute: agent_task "Apply the hints to fix file1.ts" (use available tools)
// 5. Execute: aromcp.lint_project with target_files=["file1.ts"] (result stored in raw.lint_output)
// 6. Mark "Process file1.ts..." as completed
// 7. Mark "Process file2.ts..." as in_progress  
// 8. Execute: aromcp.hints_for_files with file_paths=["file2.ts"] (result stored in raw.hints_output)
// 9. Execute: agent_task "Apply the hints to fix file2.ts" (use available tools)
// 10. Execute: aromcp.lint_project with target_files=["file2.ts"] (result stored in raw.lint_output)
// 11. Mark "Process file2.ts..." as completed
// 12. Continue to next workflow step
```

### Shell Commands (`shell_command`)
```javascript
const step = {
  type: "shell_command",
  command: "npm test",
  state_update: {
    path: "test_results",
    value: "stdout"  // or "stderr", "returncode", "full_output"
  }
};
```
**Note**: Shell commands are executed internally by the MCP server with a 30-second timeout. The agent simply waits for the next step after server execution completes.

**Server-side execution**: No action needed by agent - the workflow engine handles this internally

## Sub-Agent Instructions

**When spawned as a sub-agent for parallel execution:**

1. **Receive your task context** from the orchestrator:
   - `workflow_id`: Parent workflow instance
   - `task_id`: Your unique task identifier (e.g., "process_file.item0")
   - `item`: The specific item you're processing
   - `index`, `total`: Your position in the batch
   - Additional context variables

2. **Execute your assigned task** using the workflow system:
   ```
   while task not complete:
     1. Call workflow_get_next_step(workflow_id, task_id)
     2. If step returned, execute it following main agent patterns:
        - mcp_call: Execute MCP tool, then if store_result exists:
          • Get the tool result
          • Call workflow_update_state to store at the specified path
        - agent_task: Execute the prompt instruction using available tools
        - conditional: Follow branch logic
        - Other types: Follow step instructions
     3. Continue until workflow_get_next_step returns null
   ```
   
   **Critical for Sub-Agents**: Always store MCP results when `store_result` is present:
   ```javascript
   // Sub-agent example with store_result:
   if (step.store_result) {
     const result = await mcp_tool(step.parameters);
     await workflow_update_state(workflow_id, [{
       path: step.store_result,
       value: result
     }]);
   }
   ```

3. **Key principles for sub-agents:**
   - Use your specific `task_id` for all workflow operations
   - Focus only on your assigned item/task
   - Update state only through workflow tools
   - Follow the same step execution patterns as main agents
   - Variables like `{{ item }}`, `{{ index }}`, `{{ task_id }}` are available in your context

## Error Handling

### Common Errors and Solutions

1. **Workflow not found**
   - Verify workflow name and namespace
   - Use `/workflow list` to see available workflows

2. **Missing required input**
   - Check `/workflow {name} info` for required parameters
   - Provide all required inputs with --input flags

3. **State update failed**
   - Verify path exists in state schema
   - Check value type matches schema

4. **Step execution failed**
   - Check step parameters are correctly interpolated
   - Verify MCP tool exists and is accessible
   - Review error message for specific issues

5. **Workflow stuck**
   - Use `/workflow status` to check current state
   - Resume with `/workflow resume` if appropriate
   - Check for infinite loops in workflow definition

## Best Practices

1. **Start Simple**: Test workflows with minimal inputs first
2. **Monitor Progress**: Use status command to track execution
3. **Save Workflow IDs**: Keep track of running workflows for resume capability
4. **Validate Inputs**: Always check required inputs before starting
5. **Handle Interruptions**: Use resume capability for long-running workflows
6. **Delegate Wisely**: Use sub-agents for parallel work to improve performance

## Example Workflow Executions

### Simple Linear Workflow
```
/workflow code-standards:enforce start --input directory=./src --input fix=true

Workflow 'code-standards:enforce' started with ID: wf_123456
Step 1/5: Listing files... ✓
Step 2/5: Checking standards... ✓
Step 3/5: Applying fixes... ✓
Step 4/5: Validating changes... ✓
Step 5/5: Generating report... ✓
Workflow completed successfully!
```

### Parallel Processing Workflow
```
/workflow batch:processor start --input files='["a.ts", "b.ts", "c.ts"]'

Workflow 'batch:processor' started with ID: wf_789012
Step 1/3: Initializing... ✓
Step 2/3: Processing files in parallel...
  - Creating 3 sub-agents...
  - Sub-agent 1 processing a.ts... ✓
  - Sub-agent 2 processing b.ts... ✓
  - Sub-agent 3 processing c.ts... ✓
Step 3/3: Aggregating results... ✓
Workflow completed successfully!
```

### Interactive Workflow
```
/workflow project:setup start

Workflow 'project:setup' started with ID: wf_345678
Step 1/4: Checking environment... ✓
Step 2/4: User input required
> Enter project name: my-awesome-project
Step 3/4: Creating project structure... ✓
Step 4/4: Installing dependencies... ✓
Workflow completed successfully!
```

## Workflow Development Tips

When developing or debugging workflows:

1. **Use descriptive step names** in workflow YAML
2. **Include progress messages** with user_message steps
3. **Add checkpoints** for long-running workflows
4. **Test control flow** with simple conditions first
5. **Validate state schema** matches your updates
6. **Use computed fields** for derived values
7. **Plan for error recovery** with appropriate error handling steps