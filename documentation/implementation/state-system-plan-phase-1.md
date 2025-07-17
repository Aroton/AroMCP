# MCP Workflow System Implementation Plan - Phase 1: Core State Engine

## Phase Overview
Build the foundational state management system with reactive transformations. This phase establishes the core data structures and transformation engine that all workflow features will build upon.

## Objectives
1. Implement the three-tier state model (raw, computed, state)
2. Create the reactive transformation engine
3. Build state reading with flattened view
4. Implement state writing with path validation
5. Create comprehensive test coverage

## Components to Implement

### 1. State Model (`src/aromcp/workflow_server/state/models.py`)
```python
@dataclass
class WorkflowState:
    raw: dict[str, Any]      # Agent-writable values
    computed: dict[str, Any] # MCP-computed values
    state: dict[str, Any]    # Legacy/manual values
    
@dataclass
class ComputedFieldDefinition:
    from_paths: list[str]    # Dependencies
    transform: str           # JavaScript expression
    on_error: str           # "use_fallback" | "propagate" | "ignore"
    fallback: Any           # Default value on error
```

### 2. Transformation Engine (`src/aromcp/workflow_server/state/transformer.py`)
- JavaScript expression evaluator (using `py_mini_racer` or similar)
- Dependency graph builder
- Cascading update calculator
- Error handling for transformations
- Circular dependency detection

### 3. State Manager (`src/aromcp/workflow_server/state/manager.py`)
- State initialization with defaults
- Flattened view generation for reading
- Path validation for writing (must start with "raw." or "state.")
- Atomic state updates
- Change tracking and notifications

### 4. MCP Tools (`src/aromcp/workflow_server/tools/state_tools.py`)
```python
@mcp.tool
@json_convert
def workflow_state_read(workflow_id: str, paths: list[str] | None = None) -> dict[str, Any]:
    """Read workflow state with flattened view"""
    
@mcp.tool
@json_convert
def workflow_state_update(workflow_id: str, updates: list[dict[str, Any]] | str) -> dict[str, Any]:
    """Update raw state values and trigger transformations"""
    
@mcp.tool
@json_convert
def workflow_state_dependencies(workflow_id: str, field: str) -> dict[str, Any]:
    """Get computed field dependency information"""
```

## Acceptance Criteria

### Functional Requirements
1. **State Structure**
   - [ ] Three-tier state model implemented (raw, computed, state)
   - [ ] State can be initialized with default values
   - [ ] State persists in memory during workflow execution

2. **Transformation Engine**
   - [ ] JavaScript expressions evaluate correctly
   - [ ] Single dependencies work: `from: "raw.value"`
   - [ ] Multiple dependencies work: `from: ["raw.a", "raw.b"]`
   - [ ] Cascading transformations update in correct order
   - [ ] Circular dependencies are detected and rejected
   - [ ] Transformation errors are handled gracefully

3. **State Reading**
   - [ ] Flattened view merges all three tiers correctly
   - [ ] Computed values take precedence over raw values
   - [ ] Specific paths can be read efficiently
   - [ ] Reading non-existent paths returns None/undefined

4. **State Writing**  
   - [ ] Only paths starting with "raw." or "state." can be written
   - [ ] Writing to computed paths is rejected with clear error
   - [ ] Updates trigger dependent transformations
   - [ ] Multiple updates are applied atomically
   - [ ] Operations (set, append, increment, merge) work correctly

5. **Error Handling**
   - [ ] Invalid JavaScript expressions fail gracefully
   - [ ] Transformation errors respect on_error strategy
   - [ ] Clear error messages for debugging
   - [ ] State remains consistent after errors

### Test Requirements
1. **Unit Tests** (`tests/workflow_server/test_state_manager.py`)
   - [ ] Test state initialization
   - [ ] Test transformation execution
   - [ ] Test dependency resolution
   - [ ] Test error scenarios
   - [ ] Test all update operations

2. **Integration Tests** (`tests/workflow_server/test_state_integration.py`)
   - [ ] Test cascading transformations
   - [ ] Test complex dependency graphs
   - [ ] Test real-world transformation examples
   - [ ] Test performance with large state

3. **Example Validation**
   - [ ] Simple dependency example works (from simple-examples.md)
   - [ ] Cascading computed fields work
   - [ ] Multiple dependency transformations work

## Implementation Steps

### Week 1: Core Models and Basic Transformation
1. Create state model classes
2. Implement basic JavaScript evaluator
3. Build dependency graph resolver
4. Create simple transformation executor
5. Write comprehensive unit tests

### Week 2: State Manager and MCP Tools  
1. Implement state manager with read/write
2. Add flattened view generation
3. Create MCP tool wrappers
4. Implement all update operations
5. Add integration tests

### Week 3: Advanced Features and Testing
1. Add error handling strategies
2. Implement cascading updates
3. Optimize performance
4. Create example workflows for testing
5. Document the API

## Success Metrics
- All unit tests pass (100% coverage of core logic)
- All integration tests pass
- Example transformations from documentation work correctly
- Performance: <10ms for typical state updates
- Clear error messages for all failure scenarios

## Dependencies
- Python 3.12+
- fastmcp SDK
- JavaScript engine (py_mini_racer or similar)
- Existing MCP infrastructure (json_parameter_middleware)

## Risks and Mitigations
1. **JavaScript Engine Complexity**
   - Risk: Integration issues with Python
   - Mitigation: Start with simple expressions, consider Python-based expression language as fallback

2. **Performance with Large State**
   - Risk: Slow transformations with many dependencies
   - Mitigation: Implement caching, optimize dependency graph

3. **Complex Error Scenarios**
   - Risk: Difficult to debug transformation errors
   - Mitigation: Comprehensive logging, transformation tracing

## Next Phase Preview
Phase 2 will build on this foundation to add:
- Workflow definition loading and parsing
- Basic workflow execution (sequential steps only)
- Simple state persistence
- Initial workflow.get_info and workflow.start tools