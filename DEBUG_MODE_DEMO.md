# Sub-Agent Tasks Debug Mode - TODO Implementation

## Problems Solved

The workflow system had two main issues:
1. **Crash Issue**: Sub-agents calling `get_next_step` crashed due to API mismatch and thread safety issues
2. **Debugging Challenge**: Parallel sub-agent execution was hard to debug and follow

## Root Problems Addressed:
1. **API Mismatch**: Missing `workflow_id` parameter in sub-agent step retrieval
2. **Thread Safety**: Race conditions in sub-agent context management  
3. **Debug Visibility**: Difficult to follow parallel execution flow
4. **Sub-Agent Complexity**: Multiple agents running simultaneously made debugging confusing

## Solution Implemented

### 1. Fixed Critical Bug ✅
- **API Fix**: Updated `workflow_tools.py:395` to pass both `workflow_id` and `task_id`
- **Thread Safety**: Added proper locking around sub-agent context access
- **Error Context**: Enhanced error messages with available task information

### 2. Added TODO-Based Debug Mode ✅
- **Environment Control**: Set `AROMCP_WORKFLOW_DEBUG=serial` to enable debug mode
- **TODO Conversion**: Parallel workflows convert to TODO lists in main agent
- **No Sub-Agents**: All execution stays in main agent for full visibility
- **Serial Processing**: Tasks execute one at a time with TodoWrite progress tracking

## Usage

### Normal Parallel Execution (Default)
```bash
# Sub-agents spawn and run in parallel (may be hard to debug)
uv run python -m aromcp.workflow_server.main
```

### TODO Debug Mode
```bash
# NO sub-agents - everything runs as TODOs in main agent
AROMCP_WORKFLOW_DEBUG=serial uv run python -m aromcp.workflow_server.main
```

### Debug Output Example
```
🐛 DEBUG: Parallel_foreach converted to TODO mode (AROMCP_WORKFLOW_DEBUG=serial)
🐛 DEBUG: Created 3 TODO items for serial execution in main agent

Instructions received:
"🚨 DEBUG MODE: Execute as TODOs in main agent. DO NOT spawn sub-agents. 
Use TodoWrite to track progress. Process each task serially by executing 
sub-agent steps directly in main agent context."

Main agent execution:
1. TodoWrite: ["Process file1.py (hints + lint)", "Process file2.py (hints + lint)", "Process file3.py (hints + lint)"]
2. Mark "Process file1.py..." as in_progress
3. Execute: aromcp.hints_for_files(file_paths=["file1.py"])
4. Execute: aromcp.lint_project(target_files=["file1.py"])  
5. Mark "Process file1.py..." as completed
6. Mark "Process file2.py..." as in_progress
7. Execute: aromcp.hints_for_files(file_paths=["file2.py"])
8. Execute: aromcp.lint_project(target_files=["file2.py"])
9. Mark "Process file2.py..." as completed
... and so on
```

## API Changes

### Before (Broken)
```python
# This would crash with "Sub-agent task not found"
next_step = executor.get_next_sub_agent_step(task_id)
```

### After (Fixed)
```python  
# Now works correctly
next_step = executor.get_next_sub_agent_step(workflow_id, task_id)
```

## Benefits

1. **🐛 Debug Visibility**: See exactly what each sub-agent is doing step-by-step
2. **🔒 Thread Safety**: No more race conditions or concurrent access issues  
3. **🛠️ Easy Toggle**: Switch between parallel and serial execution with environment variable
4. **📋 Better Errors**: Clear error messages with context when things go wrong
5. **🔄 Backward Compatible**: Existing workflows continue to work unchanged
6. **📝 TODO-Based Execution**: Tasks convert to TODO items instead of sub-agents
7. **🎯 Main Agent Control**: Everything executes in main agent context for full visibility  
8. **💬 Clear Instructions**: Explicit instructions to use TODOs instead of spawning sub-agents

## Files Modified

- `src/aromcp/workflow_server/tools/workflow_tools.py` - Fixed API mismatch
- `src/aromcp/workflow_server/workflow/queue_executor.py` - Updated method signature  
- `src/aromcp/workflow_server/workflow/subagent_manager.py` - Added thread safety + debug mode
- `src/aromcp/workflow_server/prompts/standards.py` - Added debug note support
- `shared-claude/commands/workflow.md` - Updated documentation for debug mode
- `tests/workflow_server/test_complete_subagent_flow.py` - Fixed API usage
- `tests/workflow_server/test_missing_coverage.py` - Fixed API usage

## Testing

All 278 workflow tests pass ✅

The fix resolves the original crash issue and provides an easy way to debug parallel workflows by running them serially with detailed logging.