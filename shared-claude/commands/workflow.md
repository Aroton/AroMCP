# /workflow

**Purpose**: Execute and manage MCP workflows through the unified workflow server system.

**Execution Pattern**: Main agent interacts with the workflow engine through MCP tools to execute workflow steps sequentially or delegate to sub-agents for parallel execution.

## Usage
- `/workflow list` - List all available workflows
- `/workflow {workflow_name} info` - Get detailed information about a workflow
- `/workflow {workflow_name} start [--input key=value ...]` - Start a new workflow instance
- `/workflow resume {workflow_id}` - Resume a previously started workflow
- `/workflow status {workflow_id}` - Check the status of a running workflow

## Main Agent Workflow

### Critical Constraints
- ALWAYS use the MCP workflow tools, never directly manipulate workflow files
- RESPECT the workflow's defined steps and control flow
- UPDATE state only through workflow_update_state tool
- HANDLE errors gracefully and report them clearly
- For parallel steps, delegate to sub-agents appropriately

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
        - mcp_call: Execute the specified MCP tool
        - shell_command: (Handled internally by server - skip to next step)
        - state_update: Call workflow_update_state
        - user_message: Display message to user
        - user_input: Prompt user for input
        - parallel_foreach: Create sub-agents
        - Other types: Follow step instructions
     4. Call workflow_step_complete(workflow_id, step_id, result)
     5. Handle any errors and report status
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
  tool: "list_files",
  parameters: {
    patterns: ["*.ts", "*.tsx"],
    page: 1
  },
  output_path: "files"  // Where to store result in state
};
```
1. Extract tool name and parameters
2. Interpolate any template variables ({{ variable }})
3. Call the specified MCP tool
4. Store result in state at output_path if specified
5. Mark step complete with result

### State Updates (`state_update`)
```javascript
const step = {
  type: "state_update",
  updates: [
    { path: "raw.counter", value: 10 },
    { path: "state.status", value: "processing" }
  ]
};
```
1. Call workflow_update_state with the updates
2. Verify state was updated successfully
3. Mark step complete

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
  task_template: "process_file",
  max_parallel: 10
};
```
1. Call workflow_create_sub_agent for each item (up to max_parallel)
2. Provide sub-agent with:
   - Task ID
   - Item to process
   - Workflow context
   - Instructions to use workflow_get_next_step
3. Monitor sub-agent completion
4. Aggregate results
5. Mark step complete when all sub-agents finish

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

**When delegated as a sub-agent for parallel execution:**

1. Receive your task context:
   - workflow_id
   - task_id
   - item to process
   - Any additional context

2. Execute your assigned task:
   ```
   while task not complete:
     1. Call workflow_get_next_step(workflow_id, task_id)
     2. Execute the step following main agent patterns
     3. Call workflow_step_complete with your task_id
     4. Continue until no more steps
   ```

3. Focus only on your assigned item/task
4. Update state only through workflow tools
5. Report completion when done

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