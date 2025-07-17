# Complex Dependency Flow Example

## Dependency Management Workflow

```yaml
name: "complex:dependency-flow"
description: "Workflow with complex task dependencies"

# Default state initialization
default_state:
  raw:
    tasks: {}
    config:
      skip_tests: false
      parallel_limit: 3

state_schema:
  raw:
    tasks: object  # {task_id: {status, result, started_at, completed_at}}
    config: object  # Configuration options

  computed:
    task_dependencies:
      static: true  # Computed once at start
      value:
        analyze: []
        lint: ["analyze"]
        compile: ["lint"]
        test: ["compile"]
        package: ["test", "compile"]
        deploy: ["package"]

    ready_tasks:
      from: ["raw.tasks", "computed.task_dependencies"]
      transform: |
        Object.entries(input[1])
          .filter(([taskId, deps]) => {
            const taskStatus = input[0][taskId]?.status || 'pending';
            if (taskStatus !== 'pending') return false;
            return deps.every(dep => input[0][dep]?.status === 'complete');
          })
          .map(([taskId]) => taskId)

    all_complete:
      from: ["raw.tasks", "computed.task_dependencies"]
      transform: |
        Object.keys(input[1]).every(taskId =>
          input[0][taskId]?.status === 'complete'
        )

steps:
  - id: "process_loop"
    type: "while"
    condition: "{{ !all_complete }}"  # MCP resolves to computed.all_complete
    body:
      - id: "process_ready"
        type: "parallel_foreach"
        items: "{{ ready_tasks }}"  # MCP resolves to computed.ready_tasks
        wait_for_all: true
        sub_agent_task: "execute_task"
        # Uses MCP server's default parallel_foreach prompt

sub_agent_tasks:
  execute_task:
    inputs:
      task_id: "{{ item }}"
    steps:
      - id: "mark_running"
        type: "state_update"
        path: "raw.tasks.{{ task_id }}"
        value:
          status: "running"
          started_at: "{{ now() }}"

      - id: "execute"
        type: "shell_command"  # Executed internally by MCP
        command: "npm run {{ task_id }}"
        output_format: "json"
        state_update:
          path: "raw.tasks.{{ task_id }}.result"

      - id: "mark_complete"
        type: "state_update"
        path: "raw.tasks.{{ task_id }}"
        operation: "merge"
        value:
          status: "complete"
          completed_at: "{{ now() }}"
```

## How This Works

### 1. **Dependency Graph**
The workflow defines a static dependency graph where:
- `analyze` has no dependencies (runs first)
- `lint` depends on `analyze`
- `compile` depends on `lint`
- `test` depends on `compile`
- `package` depends on both `test` and `compile`
- `deploy` depends on `package`

### 2. **Dynamic Task Readiness**
The `ready_tasks` computed field continuously evaluates which tasks can run:
- Checks if task is still pending
- Verifies all dependencies are complete
- Returns list of tasks ready to execute

### 3. **Parallel Execution**
When multiple tasks are ready (e.g., after `compile` finishes, both `test` and initial `package` prep could run), they execute in parallel.

### 4. **Execution Flow Example**

Initial state:
```
ready_tasks: ["analyze"]
```

After `analyze` completes:
```
ready_tasks: ["lint"]
```

After `lint` completes:
```
ready_tasks: ["compile"]
```

After `compile` completes:
```
ready_tasks: ["test"]  // package waits for test too
```

After `test` completes:
```
ready_tasks: ["package"]
```

After `package` completes:
```
ready_tasks: ["deploy"]
```

After `deploy` completes:
```
ready_tasks: []
all_complete: true  // Workflow exits
```

## Advanced Dependency Patterns

### Conditional Dependencies

```yaml
computed:
  task_dependencies:
    from: ["raw.config"]
    transform: |
      {
        analyze: [],
        lint: ["analyze"],
        compile: ["lint"],
        test: input[0].skip_tests ? [] : ["compile"],
        package: input[0].skip_tests ? ["compile"] : ["test", "compile"],
        deploy: ["package"]
      }
```

### Dynamic Task Generation

```yaml
computed:
  # Generate tasks based on discovered modules
  module_tasks:
    from: "raw.discovered_modules"
    transform: |
      input.reduce((tasks, module) => {
        tasks[`test_${module}`] = ["compile"];
        tasks[`build_${module}`] = [`test_${module}`];
        return tasks;
      }, {})

  # Merge with static tasks
  all_dependencies:
    from: ["computed.static_dependencies", "computed.module_tasks"]
    transform: "Object.assign({}, input[0], input[1])"
```

### Priority-Based Execution

```yaml
computed:
  # Add priority to ready tasks
  prioritized_ready_tasks:
    from: ["computed.ready_tasks", "raw.task_priorities"]
    transform: |
      input[0]
        .map(taskId => ({
          id: taskId,
          priority: input[1][taskId] || 999
        }))
        .sort((a, b) => a.priority - b.priority)
        .map(t => t.id)
```

## Error Handling in Dependencies

```yaml
computed:
  # Check if dependencies failed
  blocked_tasks:
    from: ["raw.tasks", "computed.task_dependencies"]
    transform: |
      Object.entries(input[1])
        .filter(([taskId, deps]) => {
          return deps.some(dep => 
            input[0][dep]?.status === 'failed'
          );
        })
        .map(([taskId]) => taskId)

  # Skip blocked tasks
  ready_tasks:
    from: ["raw.tasks", "computed.task_dependencies", "computed.blocked_tasks"]
    transform: |
      Object.entries(input[1])
        .filter(([taskId, deps]) => {
          const taskStatus = input[0][taskId]?.status || 'pending';
          if (taskStatus !== 'pending') return false;
          if (input[2].includes(taskId)) return false;  // Skip if blocked
          return deps.every(dep => input[0][dep]?.status === 'complete');
        })
        .map(([taskId]) => taskId)
```

## Visualization Support

```yaml
computed:
  # Generate mermaid diagram of current state
  dependency_diagram:
    from: ["raw.tasks", "computed.task_dependencies"]
    transform: |
      const lines = ["graph TD"];
      Object.entries(input[1]).forEach(([task, deps]) => {
        const status = input[0][task]?.status || 'pending';
        const style = {
          complete: 'fill:#9f9',
          running: 'fill:#ff9',
          failed: 'fill:#f99',
          pending: 'fill:#fff'
        }[status];
        lines.push(`  ${task}[${task}]:::${status}`);
        lines.push(`  style ${task} ${style}`);
        deps.forEach(dep => {
          lines.push(`  ${dep} --> ${task}`);
        });
      });
      return lines.join('\\n');
```

## Interactive Deployment Example

```yaml
steps:
  - id: "get_deploy_config"
    type: "user_input"
    prompt: "Configure deployment:\n1. Environment (dev/staging/prod)\n2. Version tag\n3. Enable rollback (yes/no)"
    validation:
      pattern: "^(dev|staging|prod)\\s+v\\d+\\.\\d+\\.\\d+\\s+(yes|no)$"
      error_message: "Format: <env> v<x.y.z> <yes|no>"
    state_update:
      path: "raw.deploy_config"
      transform: |
        const parts = result.split(/\\s+/);
        { environment: parts[0], version: parts[1], rollback: parts[2] === 'yes' }

  - id: "deploy_interactive"
    type: "agent_shell_command"  # Requires agent execution
    command: "./deploy.sh --env {{ deploy_config.environment }} --version {{ deploy_config.version }}"
    reason: "Interactive deployment script with progress bars and confirmation prompts"
    timeout: 600000  # 10 minutes
    state_update:
      path: "raw.deploy_result"
```