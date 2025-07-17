# Test-Driven Development Guide for MCP Workflow System

## Overview

This guide provides specific TDD instructions for implementing the MCP Workflow System. Each phase should be implemented test-first, with acceptance criteria validated through automated tests.

## General TDD Process

1. **Red**: Write a failing test for the next bit of functionality
2. **Green**: Write the minimal code to make the test pass
3. **Refactor**: Clean up the code while keeping tests green
4. **Repeat**: Continue until all acceptance criteria are met

## Phase 1: Core State Engine - Test Specifications

### Test File: `tests/workflow_server/test_state_models.py`

```python
def test_workflow_state_initialization():
    """Test that WorkflowState initializes with three tiers"""
    # Given
    initial_state = {
        "raw": {"counter": 0},
        "computed": {},
        "state": {"version": "1.0"}
    }
    
    # When
    workflow_state = WorkflowState(**initial_state)
    
    # Then
    assert workflow_state.raw["counter"] == 0
    assert workflow_state.computed == {}
    assert workflow_state.state["version"] == "1.0"

def test_computed_field_definition():
    """Test computed field definition structure"""
    # Given
    field_def = ComputedFieldDefinition(
        from_paths=["raw.value"],
        transform="input * 2",
        on_error="use_fallback",
        fallback=0
    )
    
    # Then
    assert field_def.from_paths == ["raw.value"]
    assert field_def.transform == "input * 2"
```

### Test File: `tests/workflow_server/test_transformer.py`

```python
def test_simple_transformation():
    """Test basic JavaScript transformation"""
    # Given
    transformer = TransformationEngine()
    state = {"raw": {"value": 5}}
    transform = "input * 2"
    
    # When
    result = transformer.execute(transform, 5)
    
    # Then
    assert result == 10

def test_transformation_with_dependencies():
    """Test transformation with multiple dependencies"""
    # Given
    transformer = TransformationEngine()
    transform = "input[0] + input[1]"
    inputs = [5, 3]
    
    # When
    result = transformer.execute(transform, inputs)
    
    # Then
    assert result == 8

def test_circular_dependency_detection():
    """Test that circular dependencies are detected"""
    # Given
    schema = {
        "computed": {
            "a": {"from": "computed.b", "transform": "input"},
            "b": {"from": "computed.a", "transform": "input"}
        }
    }
    
    # When/Then
    with pytest.raises(CircularDependencyError):
        DependencyResolver(schema).resolve()
```

### Test File: `tests/workflow_server/test_state_manager.py`

```python
def test_flattened_view():
    """Test state flattening for read operations"""
    # Given
    state = WorkflowState(
        raw={"counter": 5, "name": "test"},
        computed={"double": 10, "name": "computed"},
        state={"version": "1.0"}
    )
    manager = StateManager()
    
    # When
    flattened = manager.get_flattened_view(state)
    
    # Then
    assert flattened["counter"] == 5
    assert flattened["double"] == 10
    assert flattened["name"] == "computed"  # computed takes precedence
    assert flattened["version"] == "1.0"

def test_state_update_validation():
    """Test that only raw/state paths can be written"""
    # Given
    manager = StateManager()
    
    # When/Then - Valid updates
    assert manager.validate_update_path("raw.counter") == True
    assert manager.validate_update_path("state.version") == True
    
    # When/Then - Invalid updates
    assert manager.validate_update_path("computed.value") == False
    assert manager.validate_update_path("invalid.path") == False

def test_cascading_updates():
    """Test that updates trigger dependent transformations"""
    # Given
    schema = StateSchema(
        raw={"value": "number"},
        computed={
            "double": {"from": "raw.value", "transform": "input * 2"},
            "quadruple": {"from": "computed.double", "transform": "input * 2"}
        }
    )
    manager = StateManager(schema)
    
    # When
    manager.update("wf_123", [{"path": "raw.value", "value": 5}])
    state = manager.read("wf_123")
    
    # Then
    assert state["value"] == 5
    assert state["double"] == 10
    assert state["quadruple"] == 20
```

## Phase 2: Workflow Loading - Test Specifications

### Test File: `tests/workflow_server/test_workflow_loader.py`

```python
def test_workflow_name_resolution():
    """Test workflow loading from correct locations"""
    # Given
    loader = WorkflowLoader()
    mock_files = {
        ".aromcp/workflows/test:workflow.yaml": "project_workflow",
        "~/.aromcp/workflows/test:workflow.yaml": "global_workflow"
    }
    
    # When
    workflow = loader.load("test:workflow")
    
    # Then
    assert workflow.source == "project"  # Project takes precedence

def test_workflow_not_found():
    """Test error when workflow doesn't exist"""
    # Given
    loader = WorkflowLoader()
    
    # When/Then
    with pytest.raises(WorkflowNotFoundError) as exc:
        loader.load("missing:workflow")
    
    assert "missing:workflow" in str(exc.value)
    assert ".aromcp/workflows/missing:workflow.yaml" in str(exc.value)

def test_yaml_parsing():
    """Test YAML workflow definition parsing"""
    # Given
    yaml_content = """
    name: "test:simple"
    description: "Test workflow"
    version: "1.0.0"
    
    default_state:
      raw:
        counter: 0
    
    steps:
      - type: "state_update"
        path: "raw.counter"
        value: 10
    """
    
    # When
    workflow = WorkflowParser.parse(yaml_content)
    
    # Then
    assert workflow.name == "test:simple"
    assert workflow.default_state["raw"]["counter"] == 0
    assert len(workflow.steps) == 1
```

### Test File: `tests/workflow_server/test_basic_execution.py`

```python
def test_workflow_start():
    """Test workflow initialization"""
    # Given
    executor = WorkflowExecutor()
    workflow_def = load_test_workflow("simple")
    
    # When
    result = executor.start(workflow_def, inputs={"name": "test"})
    
    # Then
    assert result["workflow_id"].startswith("wf_")
    assert result["state"]["counter"] == 0  # Default state
    assert result["state"]["name"] == "test"  # Input applied

def test_get_next_step_sequential():
    """Test sequential step execution"""
    # Given
    executor = WorkflowExecutor()
    workflow_id = "wf_123"
    steps = [
        {"id": "step1", "type": "state_update"},
        {"id": "step2", "type": "mcp_call"},
        {"id": "step3", "type": "user_message"}
    ]
    
    # When/Then
    next_step = executor.get_next_step(workflow_id)
    assert next_step["id"] == "step1"
    
    executor.step_complete(workflow_id, "step1")
    next_step = executor.get_next_step(workflow_id)
    assert next_step["id"] == "step2"

def test_variable_replacement():
    """Test variable interpolation in steps"""
    # Given
    state = {"counter": 5, "name": "test"}
    step = {
        "type": "user_message",
        "message": "Hello {{ name }}, count is {{ counter }}"
    }
    
    # When
    replaced = VariableReplacer.replace(step, state)
    
    # Then
    assert replaced["message"] == "Hello test, count is 5"
```

## Phase 3: Control Flow - Test Specifications

### Test File: `tests/workflow_server/test_expressions.py`

```python
def test_boolean_expressions():
    """Test expression evaluation"""
    # Given
    evaluator = ExpressionEvaluator()
    context = {"value": 5, "flag": True}
    
    # When/Then
    assert evaluator.evaluate("value > 3", context) == True
    assert evaluator.evaluate("value == 5 && flag", context) == True
    assert evaluator.evaluate("value < 3 || flag", context) == True

def test_property_access():
    """Test nested property access"""
    # Given
    evaluator = ExpressionEvaluator()
    context = {
        "user": {"name": "Alice", "age": 30},
        "items": ["a", "b", "c"]
    }
    
    # When/Then
    assert evaluator.evaluate("user.name", context) == "Alice"
    assert evaluator.evaluate("items.length", context) == 3
    assert evaluator.evaluate("items[1]", context) == "b"
```

### Test File: `tests/workflow_server/test_control_flow.py`

```python
def test_conditional_execution():
    """Test if/then/else branching"""
    # Given
    executor = WorkflowExecutor()
    state = {"value": 5}
    conditional = ConditionalStep(
        condition="value > 3",
        then_steps=[{"id": "then1", "type": "state_update"}],
        else_steps=[{"id": "else1", "type": "state_update"}]
    )
    
    # When
    next_step = executor.process_conditional(conditional, state)
    
    # Then
    assert next_step["id"] == "then1"

def test_while_loop():
    """Test while loop execution"""
    # Given
    executor = WorkflowExecutor()
    loop = WhileLoopStep(
        condition="counter < 5",
        max_iterations=10,
        body=[
            {"type": "state_update", "path": "raw.counter", "operation": "increment"}
        ]
    )
    
    # When - Execute loop
    state = {"counter": 0}
    iterations = 0
    while executor.evaluate_condition(loop.condition, state):
        iterations += 1
        # Execute body
        state["counter"] += 1
    
    # Then
    assert iterations == 5
    assert state["counter"] == 5

def test_foreach_expansion():
    """Test foreach loop expansion"""
    # Given
    executor = WorkflowExecutor()
    state = {"items": ["a", "b", "c"]}
    foreach = ForEachStep(
        items="items",
        body=[{"type": "state_update", "path": "raw.{{ item }}"}]
    )
    
    # When
    expanded = executor.expand_foreach(foreach, state)
    
    # Then
    assert len(expanded) == 3
    assert expanded[0]["definition"]["path"] == "raw.a"
    assert expanded[1]["definition"]["path"] == "raw.b"
```

## Phase 4: Parallel Execution - Test Specifications

### Test File: `tests/workflow_server/test_parallel_execution.py`

```python
def test_parallel_task_distribution():
    """Test task distribution to sub-agents"""
    # Given
    executor = ParallelExecutor()
    items = [
        {"id": "batch_0", "files": ["a.ts", "b.ts"]},
        {"id": "batch_1", "files": ["c.ts", "d.ts"]}
    ]
    
    # When
    tasks = executor.create_parallel_tasks(items, "process_batch")
    
    # Then
    assert len(tasks) == 2
    assert tasks[0]["task_id"] == "batch_0"
    assert tasks[0]["context"]["files"] == ["a.ts", "b.ts"]

def test_concurrent_state_updates():
    """Test thread-safe state updates"""
    # Given
    manager = ConcurrentStateManager()
    workflow_id = "wf_123"
    
    # When - Simulate concurrent updates
    import threading
    def update_path(path, value):
        manager.update(workflow_id, [{"path": path, "value": value}])
    
    threads = [
        threading.Thread(target=update_path, args=("raw.thread1", 1)),
        threading.Thread(target=update_path, args=("raw.thread2", 2)),
        threading.Thread(target=update_path, args=("raw.thread3", 3))
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Then
    state = manager.read(workflow_id)
    assert state["thread1"] == 1
    assert state["thread2"] == 2
    assert state["thread3"] == 3

def test_sub_agent_context_isolation():
    """Test sub-agents have isolated contexts"""
    # Given
    executor = WorkflowExecutor()
    parent_id = "wf_parent"
    
    # When
    context1 = executor.create_sub_agent_context(parent_id, "task_1")
    context2 = executor.create_sub_agent_context(parent_id, "task_2")
    
    # Then
    assert context1["task_id"] == "task_1"
    assert context2["task_id"] == "task_2"
    assert context1["workflow_id"] == parent_id
    
    # When - Sub-agent requests steps
    step1 = executor.get_next_step(parent_id, context1)
    step2 = executor.get_next_step(parent_id, context2)
    
    # Then - Each gets appropriate steps
    assert step1 != step2
```

## Test Execution Strategy

### Running Tests During Development

```bash
# Run specific test file
uv run pytest tests/workflow_server/test_state_models.py -v

# Run specific test
uv run pytest tests/workflow_server/test_state_models.py::test_workflow_state_initialization -v

# Run with coverage
uv run pytest tests/workflow_server/ --cov=src/aromcp/workflow_server --cov-report=html

# Run in watch mode during development
uv run pytest-watch tests/workflow_server/ -- -v
```

### Test Organization

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions
3. **Example Tests**: Validate documentation examples work
4. **Performance Tests**: Ensure performance requirements met

### Coverage Requirements

- Core logic: 95%+ coverage
- Error paths: 90%+ coverage
- Integration points: 85%+ coverage
- Overall: 90%+ coverage

## Validation Against Examples

Each phase should validate against the example workflows:

### Phase 1 Validation
```python
def test_simple_transformation_example():
    """Validate simple-examples.md transformation"""
    # Test the exact example from documentation
    schema = {
        "raw": {"git_output": "string"},
        "computed": {
            "parsed_files": {
                "from": "raw.git_output",
                "transform": "input.split('\\n').filter(l => l.trim())"
            }
        }
    }
    # ... implement and verify
```

### Phase 2 Validation
```python
def test_simple_workflow_example():
    """Validate simple sequential workflow from docs"""
    # Load and execute test:simple workflow
    # Verify each step executes correctly
```

### Phase 3 Validation
```python
def test_standards_fix_control_flow():
    """Validate standards:fix workflow control flow"""
    # Test conditional file detection
    # Test while loop for fixes
    # Test user input validation
```

## Common Test Patterns

### Mock External Dependencies
```python
@patch('subprocess.run')
def test_shell_command_execution(mock_run):
    """Test shell command with mocked subprocess"""
    mock_run.return_value.stdout = "file1.ts\nfile2.ts"
    # ... test shell command step
```

### Test Error Scenarios
```python
def test_transformation_error_handling():
    """Test all error handling strategies"""
    strategies = ["use_fallback", "propagate", "ignore"]
    for strategy in strategies:
        # Test each strategy behavior
```

### Test Async/Concurrent Behavior
```python
@pytest.mark.asyncio
async def test_parallel_execution():
    """Test async parallel execution"""
    # Use asyncio for testing concurrent behavior
```

## Success Criteria Validation

Each phase has specific acceptance criteria. Create explicit tests for each:

```python
class TestPhase1AcceptanceCriteria:
    """Explicit tests for Phase 1 acceptance criteria"""
    
    def test_three_tier_state_model(self):
        """AC: Three-tier state model implemented"""
        pass
    
    def test_state_initialization_with_defaults(self):
        """AC: State can be initialized with default values"""
        pass
    
    def test_javascript_expressions_evaluate(self):
        """AC: JavaScript expressions evaluate correctly"""
        pass
    
    # ... one test per acceptance criterion
```

This approach ensures that acceptance criteria are met through automated validation rather than manual checking.