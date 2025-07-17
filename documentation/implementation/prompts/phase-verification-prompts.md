# MCP Workflow System - Phase Verification Prompts

## Phase 1: Core State Engine Verification

```
I need you to verify that Phase 1 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-1.md (acceptance criteria)
- @documentation/implementation/state-examples/simple-examples.md (validation examples)

Run these verification steps:

1. **State Structure Tests**:
   - Verify three-tier state model works (raw, computed, state)
   - Test state initialization with defaults
   - Confirm state persists during execution

2. **Transformation Engine Tests**:
   - Test simple transformations: from: "raw.value", transform: "input * 2"
   - Test multiple dependencies: from: ["raw.a", "raw.b"]
   - Verify cascading updates work correctly
   - Confirm circular dependencies are detected
   - Test error handling with on_error strategies

3. **State Operations Tests**:
   - Verify flattened view merges all tiers correctly
   - Test that computed values override raw with same name
   - Confirm only "raw.*" and "state.*" paths can be written
   - Test all update operations (set, append, increment, merge)

4. **Example Validation**:
   - Run the simple dependency example from simple-examples.md
   - Verify the cascading computed fields work
   - Test the multiple dependency transformations

5. **Performance Tests**:
   - Measure typical state update time (target: <10ms)
   - Test with large state objects
   - Verify memory usage is reasonable

Create a verification report showing:
- Which acceptance criteria passed/failed
- Test coverage percentage
- Performance metrics
- Any issues found
```

## Phase 2: Workflow Loading and Basic Execution Verification

```
I need you to verify that Phase 2 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-2.md (acceptance criteria)
- @documentation/implementation/state-examples/simple-examples.md (test workflows)

Run these verification steps:

1. **Workflow Loading Tests**:
   - Create test workflows in .aromcp/workflows/ and ~/.aromcp/workflows/
   - Verify project workflows load first
   - Test fallback to user directory
   - Confirm clear errors for missing workflows
   - Test YAML syntax error reporting

2. **Workflow Parsing Tests**:
   - Verify default_state values parse correctly
   - Test state_schema validation
   - Confirm input definitions work
   - Test step parsing into executable format
   - Verify invalid step types are rejected

3. **Workflow Execution Tests**:
   - Test workflow.start initializes with defaults
   - Verify sequential step execution
   - Test variable replacement ({{ value }})
   - Confirm step completion advances correctly
   - Test workflow completion detection

4. **Step Type Tests**:
   - shell_command: Verify internal execution and state update
   - state_update: Test raw state modifications
   - mcp_call: Verify parameter formatting
   - user_message: Test variable interpolation

5. **Integration Tests**:
   - Run the "analyze:dependencies" example
   - Verify state transformations trigger
   - Test that computed values are available in steps

Report all test results with pass/fail status.
```

## Phase 3: Control Flow and Advanced Steps Verification

```
I need you to verify that Phase 3 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-3.md (acceptance criteria)
- @documentation/implementation/state-examples/workflow-execution-example.md (standards:fix workflow)

Run these verification steps:

1. **Conditional Execution Tests**:
   - Test simple conditions: {{ value > 5 }}
   - Test complex expressions: {{ a && (b || c) }}
   - Verify then branch executes when true
   - Verify else branch executes when false
   - Test nested conditionals
   - Confirm variables resolve in conditions

2. **While Loop Tests**:
   - Test loop executes while condition true
   - Verify max_iterations limit enforced
   - Test loop variable updates
   - Verify break exits early
   - Test nested loops
   - Confirm infinite loop protection

3. **ForEach Loop Tests**:
   - Test iteration over arrays
   - Verify item variable available
   - Test index variable access
   - Test with computed arrays
   - Verify empty array handling

4. **Expression Evaluation Tests**:
   - Test property access (state.value, state['value'])
   - Verify comparison operators
   - Test logical operators
   - Verify string methods (.includes, .startsWith)
   - Test array methods (.length, .filter)

5. **standards:fix Validation**:
   - Run the workflow control flow sections
   - Verify conditional file detection works
   - Test while loop for fixes
   - Confirm user input validation

Document any expression compatibility issues found.
```

## Phase 4: Parallel Execution and Sub-Agents Verification

```
I need you to verify that Phase 4 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-4.md (acceptance criteria)
- @documentation/implementation/state-examples/workflow-execution-example.md (full standards:fix)

Run these verification steps:

1. **Parallel ForEach Tests**:
   - Test item distribution to sub-agents
   - Verify max_parallel limit respected
   - Test wait_for_all behavior
   - Verify sub-agent context delivery
   - Confirm standard prompt usage
   - Test custom prompt override

2. **Sub-Agent Execution Tests**:
   - Verify sub-agents get filtered steps
   - Test task context availability
   - Confirm state updates scoped correctly
   - Test sub-agent completion tracking
   - Verify error propagation

3. **Concurrent State Tests**:
   - Test multiple agents updating different paths
   - Verify conflict handling on same path
   - Test transformation consistency
   - Check for race conditions
   - Measure performance scaling

4. **Workflow Composition Tests**:
   - Test include_workflow functionality
   - Verify input mapping
   - Test state isolation
   - Confirm output accessibility
   - Test recursive include prevention

5. **standards:fix Full Test**:
   - Run complete workflow with parallel batches
   - Verify all sub-agents complete
   - Test with 10+ concurrent agents
   - Measure total execution time
   - Verify final state consistency

Report concurrent execution metrics and any race conditions.
```

## Phase 5: Error Handling and Debugging Verification

```
I need you to verify that Phase 5 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-5.md (acceptance criteria)
- @documentation/implementation/state-system.md (error handling examples)

Run these verification steps:

1. **Error Handling Tests**:
   - Test each error strategy (fail, continue, retry, fallback)
   - Verify retry with exponential backoff
   - Test fallback value application
   - Confirm error state tracking
   - Test sub-agent error bubbling
   - Verify graceful degradation

2. **Recovery Mechanism Tests**:
   - Test failed step retry
   - Verify workflow resume from failure
   - Test partial state preservation
   - Confirm cleanup operations
   - Test circuit breaker behavior

3. **Debug Tool Tests**:
   - Test transformation tracing with timing
   - Verify step execution history
   - Test performance metric collection
   - Confirm state size warnings
   - Test bottleneck identification

4. **Testing Support Tests**:
   - Test transformation isolation testing
   - Verify workflow plan explanation
   - Test mock tool functionality
   - Confirm state assertions work
   - Run performance benchmarks

5. **Production Feature Tests**:
   - Test memory limit enforcement
   - Verify execution timeouts
   - Test automatic cleanup
   - Confirm monitoring exports
   - Test health check endpoints

Create error scenario test report with recovery rates.
```

## Phase 6: Advanced Features and Production Verification

```
I need you to verify that Phase 6 of the MCP Workflow System meets all acceptance criteria.

Please read these documents:
- @documentation/implementation/state-system-plan-phase-6.md (acceptance criteria)
- @documentation/implementation/state-examples/dependency-flow-example.md (complex patterns)

Run these verification steps:

1. **Advanced Pattern Tests**:
   - Test complex dependency graphs
   - Verify priority-based scheduling
   - Test dynamic task generation
   - Confirm conditional dependencies
   - Test fan-out/fan-in patterns

2. **Event-Driven Tests**:
   - Test file change triggers
   - Verify scheduled execution
   - Test webhook processing
   - Confirm event filtering
   - Test multiple subscribers

3. **External Integration Tests**:
   - Test external state persistence
   - Verify webhook receipt
   - Test metric exports
   - Confirm notifications
   - Test external tool calls

4. **Versioning Tests**:
   - Test version compatibility
   - Verify breaking change detection
   - Test migration scripts
   - Confirm rollback capability
   - Test deprecation warnings

5. **Production Readiness Tests**:
   - Test multi-tenant isolation
   - Verify rate limiting
   - Test audit logging
   - Confirm hot reload
   - Test resource quotas

6. **Full System Test**:
   - Run dependency-flow-example.md
   - Test event-driven patterns
   - Verify external integrations
   - Measure system performance
   - Confirm production deployment

Generate final system verification report with all metrics.
```

## Verification Report Template

For each phase verification, create a report with:

```markdown
# Phase X Verification Report

## Test Summary
- Total Acceptance Criteria: X
- Passed: X
- Failed: X
- Coverage: X%

## Acceptance Criteria Results

### Criterion 1: [Name]
- **Status**: ✅ PASS / ❌ FAIL
- **Evidence**: [Test results]
- **Notes**: [Any issues]

### Performance Metrics
- Average operation time: Xms
- Memory usage: XMB
- Throughput: X ops/sec

## Issues Found
1. [Issue description and severity]

## Recommendations
- [Next steps or fixes needed]
```