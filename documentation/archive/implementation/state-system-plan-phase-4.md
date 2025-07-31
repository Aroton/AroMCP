# MCP Workflow System Implementation Plan - Phase 4: Parallel Execution and Sub-Agents

## Phase Overview
Implement parallel task execution with sub-agent delegation. This phase enables workflows to distribute work across multiple agents for improved performance and scalability.

## Objectives
1. Implement parallel_foreach with sub-agent delegation
2. Create sub-agent context management
3. Build MCP standard prompt system
4. Support workflow composition
5. Enable concurrent state updates

## Components to Implement

### 1. Parallel Execution Models (`src/aromcp/workflow_server/workflow/parallel.py`)
```python
@dataclass
class ParallelForEachStep:
    items: str  # Expression returning array
    max_parallel: int
    wait_for_all: bool
    sub_agent_task: str
    sub_agent_prompt_override: str | None

@dataclass
class SubAgentContext:
    task_id: str
    workflow_id: str
    context: dict[str, Any]
    parent_step_id: str
```

### 2. Standard Prompts (`src/aromcp/workflow_server/prompts/standards.py`)
```python
class StandardPrompts:
    PARALLEL_FOREACH = """You are a workflow sub-agent. Your role is to execute a specific task by following the workflow system.

Process:
1. Call workflow.get_next_step with your task_id to get the next atomic action
2. Execute the action exactly as instructed
3. Update state as directed in the step
4. Mark the step complete
5. Repeat until get_next_step returns null

The workflow will guide you through all necessary steps. Simply follow the instructions
provided by each step. Do not make assumptions about what needs to be done - the 
workflow will tell you everything."""
```

### 3. Sub-Agent Manager (`src/aromcp/workflow_server/workflow/sub_agents.py`)
- Sub-agent task registration
- Context isolation per sub-agent
- Parallel task distribution
- Completion tracking
- Result aggregation

### 4. Concurrent State Manager (`src/aromcp/workflow_server/state/concurrent.py`)
- Thread-safe state operations
- Conflict resolution strategies
- Atomic batch updates
- Optimistic locking
- Change notification system

### 5. Workflow Composition (`src/aromcp/workflow_server/workflow/composition.py`)
- Include workflow steps
- State namespace isolation
- Input/output mapping
- Shared workflow cache
- Version compatibility

### 6. Enhanced MCP Tools
```python
@mcp.tool
@json_convert
def workflow_get_next_step(
    workflow_id: str, 
    sub_agent_context: dict[str, Any] | str | None = None
) -> dict[str, Any]:
    """Get next step, with sub-agent context support"""

@mcp.tool
@json_convert
def workflow_checkpoint(
    workflow_id: str,
    step_id: str,
    reason: str
) -> dict[str, Any]:
    """Create workflow checkpoint for recovery"""

@mcp.tool
@json_convert
def workflow_resume(workflow_id: str) -> dict[str, Any]:
    """Resume from checkpoint"""
```

## Acceptance Criteria

### Functional Requirements
1. **Parallel ForEach**
   - [ ] Distributes items to sub-agents correctly
   - [ ] Respects max_parallel limit
   - [ ] Waits for all agents when specified
   - [ ] Sub-agents receive proper context
   - [ ] Standard prompt used by default
   - [ ] Custom prompts override when specified

2. **Sub-Agent Execution**
   - [ ] Sub-agents get filtered steps
   - [ ] Task context available in steps
   - [ ] State updates scoped correctly
   - [ ] Sub-agent completion tracked
   - [ ] Errors propagated to parent

3. **Concurrent State**
   - [ ] Multiple agents can update different paths
   - [ ] Conflicts on same path handled gracefully
   - [ ] Transformations remain consistent
   - [ ] No race conditions in computed fields
   - [ ] Performance scales with agents

4. **Workflow Composition**
   - [ ] Include_workflow loads and executes
   - [ ] Input mapping works correctly
   - [ ] State isolation maintained
   - [ ] Output values accessible
   - [ ] Recursive includes prevented

5. **Checkpoint/Resume**
   - [ ] Checkpoint captures full state
   - [ ] Resume restores execution point
   - [ ] Sub-agent progress preserved
   - [ ] Computed state reconstructed
   - [ ] Context limits considered

### Test Requirements
1. **Unit Tests** (`tests/workflow_server/test_parallel_execution.py`)
   - [ ] Test task distribution
   - [ ] Test context isolation
   - [ ] Test concurrent state
   - [ ] Test checkpoint/resume

2. **Integration Tests** (`tests/workflow_server/test_parallel_workflows.py`)
   - [ ] Test standards:fix workflow
   - [ ] Test multiple sub-agents
   - [ ] Test workflow composition
   - [ ] Test error scenarios

3. **Performance Tests**
   - [ ] Measure scaling with agent count
   - [ ] Test state contention handling
   - [ ] Verify memory usage
   - [ ] Check checkpoint size

## Implementation Steps

### Week 1: Parallel Execution Core
1. Implement parallel_foreach processor
2. Create sub-agent context system
3. Build task distribution logic
4. Add standard prompt support
5. Test basic parallel execution

### Week 2: Concurrent State
1. Add thread-safe state operations
2. Implement conflict resolution
3. Ensure transformation consistency
4. Add performance optimizations
5. Test concurrent scenarios

### Week 3: Composition and Recovery
1. Implement workflow inclusion
2. Add checkpoint/resume functionality
3. Build state reconstruction
4. Create comprehensive tests
5. Optimize for production use

## Success Metrics
- standards:fix workflow runs with parallel batches
- 10+ sub-agents work without conflicts
- Checkpoint/resume handles complex state
- Performance scales linearly with agents
- No data races or inconsistencies

## Dependencies
- Phases 1-3 completed
- Thread-safe data structures
- Serialization for checkpoints

## Risks and Mitigations
1. **State Consistency**
   - Risk: Race conditions in concurrent updates
   - Mitigation: Proper locking, atomic operations, comprehensive testing

2. **Memory Usage**
   - Risk: Large state with many agents
   - Mitigation: Efficient data structures, state pruning

3. **Deadlocks**
   - Risk: Complex locking causing deadlocks
   - Mitigation: Lock ordering, timeout mechanisms

## Example Parallel Workflow
```yaml
name: "test:parallel"
description: "Test parallel execution"

state_schema:
  raw:
    file_batches: array
    results: object

steps:
  - type: "parallel_foreach"
    items: "{{ file_batches }}"
    max_parallel: 5
    sub_agent_task: "process_batch"

sub_agent_tasks:
  process_batch:
    steps:
      - type: "state_update"
        path: "raw.results.{{ task_id }}"
        value:
          status: "processing"
          started_at: "{{ now() }}"
      
      - type: "foreach"
        items: "{{ context.files }}"
        steps:
          - type: "mcp_call"
            method: "lint_project"
            params:
              target_files: "{{ item }}"
      
      - type: "state_update"
        path: "raw.results.{{ task_id }}.status"
        value: "complete"
```

## Protocol Extensions
New atomic step type for parallel execution:
```typescript
{
  step: {
    id: "process_batches",
    type: "parallel_tasks",
    instructions: "Create sub-agents for ALL tasks. Execute in parallel.",
    definition: {
      tasks: [
        {
          task_id: "batch_0",
          context: { files: [...] }
        },
        {
          task_id: "batch_1", 
          context: { files: [...] }
        }
      ],
      sub_agent_prompt: "..." // Standard prompt included
    }
  }
}
```

## Next Phase Preview
Phase 5 will add:
- Error handling strategies
- Retry mechanisms
- Failure recovery
- Workflow debugging tools
- Performance monitoring