# MCP Workflow System - Phase Implementation Prompts

## Phase 1: Core State Engine Implementation

```
I need you to implement Phase 1 of the MCP Workflow System - the Core State Engine.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-1.md (requirements and design)
- @documentation/implementation/state-system-tdd-guide.md (test specifications)
- @documentation/implementation/state-system-quick-reference.md (code patterns)

Follow TDD approach:
1. Create the test files first based on the TDD guide
2. Implement models in src/aromcp/workflow_server/state/models.py
3. Build the transformation engine in transformer.py
4. Create the state manager in manager.py
5. Implement the MCP tools in tools/state_tools.py

Key requirements:
- Three-tier state model (raw, computed, state)
- JavaScript transformation engine
- Dependency resolution with circular detection
- Flattened view for reading
- Path validation for writing

Make sure all tests pass before considering the phase complete.
```

## Phase 2: Workflow Loading and Basic Execution Implementation

```
I need you to implement Phase 2 of the MCP Workflow System - Workflow Loading and Basic Execution.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-2.md (requirements and design)
- @documentation/implementation/state-system-tdd-guide.md (test specifications for Phase 2)
- @documentation/implementation/state-system-quick-reference.md (workflow patterns)

Prerequisites: Phase 1 must be complete with all tests passing.

Implement:
1. Workflow models in src/aromcp/workflow_server/workflow/models.py
2. YAML loader with name resolution in loader.py
3. Sequential executor in executor.py
4. Basic step processors in steps/ directory
5. MCP workflow tools in tools/workflow_tools.py

Key requirements:
- Name-based loading (.aromcp/workflows/ then ~/.aromcp/workflows/)
- YAML parsing with validation
- Sequential step execution
- Variable replacement
- Integration with Phase 1 state system

Test with simple sequential workflows first.
```

## Phase 3: Control Flow and Advanced Steps Implementation

```
I need you to implement Phase 3 of the MCP Workflow System - Control Flow and Advanced Steps.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-3.md (requirements and design)
- @documentation/implementation/state-system-tdd-guide.md (test specifications for Phase 3)
- @documentation/implementation/state-system-quick-reference.md (control flow patterns)

Prerequisites: Phases 1-2 must be complete with all tests passing.

Implement:
1. Control flow models in control_flow.py
2. Expression evaluator in expressions.py
3. Execution context in context.py
4. Advanced step processors (conditional, loops, user_input)
5. Enhanced executor v2

Key requirements:
- Boolean expression evaluation
- if/then/else branching
- while loops with safety limits
- foreach iteration
- User input with validation
- Nested structure support

Validate against the control flow examples in the plan.
```

## Phase 4: Parallel Execution and Sub-Agents Implementation

```
I need you to implement Phase 4 of the MCP Workflow System - Parallel Execution and Sub-Agents.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-4.md (requirements and design)
- @documentation/implementation/state-system-tdd-guide.md (test specifications for Phase 4)
- @documentation/implementation/state-system-quick-reference.md (parallel patterns)

Prerequisites: Phases 1-3 must be complete with all tests passing.

Implement:
1. Parallel execution models in parallel.py
2. Standard prompts in prompts/standards.py
3. Sub-agent manager in sub_agents.py
4. Concurrent state manager in state/concurrent.py
5. Enhanced MCP tools with sub-agent support

Key requirements:
- parallel_foreach with task distribution
- Sub-agent context isolation
- Thread-safe state operations
- Standard prompt system
- Workflow composition support

Test with multiple concurrent sub-agents.
```

## Phase 5: Error Handling and Debugging Implementation

```
I need you to implement Phase 5 of the MCP Workflow System - Error Handling and Debugging.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-5.md (requirements and design)
- @documentation/implementation/state-system-tdd-guide.md (test specifications for Phase 5)
- @documentation/implementation/state-system-quick-reference.md (error patterns)

Prerequisites: Phases 1-4 must be complete with all tests passing.

Implement:
1. Error handling framework in errors/ directory
2. Retry mechanisms in workflow/retry.py
3. Debug tools in tools/debug_tools.py
4. Monitoring system in monitoring/
5. Test framework utilities in testing/

Key requirements:
- Multi-level error handling (step, workflow, sub-agent)
- Retry with exponential backoff
- Transformation tracing
- Performance monitoring
- Test utilities for workflows

Focus on production reliability.
```

## Phase 6: Advanced Features and Production Implementation

```
I need you to implement Phase 6 of the MCP Workflow System - Advanced Features and Production.

Please read these documents first:
- @documentation/implementation/state-system-plan-phase-6.md (requirements and design)
- @documentation/implementation/state-system-quick-reference.md (advanced patterns)

Prerequisites: Phases 1-5 must be complete with all tests passing.

Implement:
1. Advanced patterns in patterns/ directory
2. External integrations in integrations/
3. Versioning system in versioning/
4. Production features in production/
5. Advanced MCP tools

Key requirements:
- Complex dependency graphs
- Event-driven workflows
- External system integration
- Workflow versioning
- Multi-tenant support

This completes the full system. Ensure all integration tests pass.
```