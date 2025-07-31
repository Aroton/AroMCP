# Error Categorization System Acceptance Criteria

## Overview
Implement comprehensive error categorization system for TypeScript analysis that provides specific, actionable error codes for different types of analysis failures. The current system generates generic errors but lacks specific categorization for complex type resolution scenarios.

## Test Case Reference
- **Test File**: `test_focused_advanced_type_resolution.py`
- **Test Method**: `test_error_categorization_in_complex_scenarios`
- **Current Status**: FAILING
- **Current Issue**: Missing specific error codes like `CIRCULAR_REFERENCE_DETECTED`
- **Expected Behavior**: Detect and categorize complex type resolution errors with specific codes

## Core Requirements

### CR-ECS-001: Specific Error Code Generation
**Requirement**: Generate specific error codes for different categories of analysis failures
- **Required Error Codes**:
  - `CIRCULAR_REFERENCE_DETECTED`: For circular type references
  - `COMPLEXITY_LIMIT_EXCEEDED`: For overly complex type resolution
  - `TYPE_RESOLUTION_TIMEOUT`: For time-consuming type analysis
  - `CONSTRAINT_DEPTH_EXCEEDED`: For deeply nested generic constraints
  - `TYPE_RESOLUTION_ERROR`: Fallback for unspecified type errors
- **Current Gap**: Generic errors without specific categorization
- **Detection Context**: Complex type resolution scenarios with multiple error types

### CR-ECS-002: Circular Reference Detection
**Requirement**: Detect and properly categorize circular type reference patterns
- **Detection Patterns**:
  - Self-referencing interfaces: `interface A<T extends A<A<T>>>`
  - Mutual circular references: `A extends B, B extends A`
  - Complex circular chains: `A → B → C → A`
- **Expected Error**: `CIRCULAR_REFERENCE_DETECTED` with descriptive message
- **Current Issue**: Circular references detected but not properly categorized
- **Error Message**: Should include reference chain information

### CR-ECS-003: Complexity Limit Detection  
**Requirement**: Identify and categorize overly complex type resolution scenarios
- **Complexity Triggers**:
  - Deeply nested mapped types with multiple transformations
  - Excessive generic constraint depth (> configured limit)
  - Complex conditional type chains
  - Large union/intersection type combinations
- **Expected Error**: `COMPLEXITY_LIMIT_EXCEEDED` with complexity metrics
- **Threshold Configuration**: Configurable complexity limits

### CR-ECS-004: Timeout Detection
**Requirement**: Detect and categorize analysis operations that exceed time limits
- **Timeout Scenarios**:
  - Long-running type inference operations
  - Complex constraint resolution
  - Expensive conditional type evaluation
- **Expected Error**: `TYPE_RESOLUTION_TIMEOUT` with timing information
- **Timeout Limits**: Configurable per-operation timeouts

## Implementation Requirements

### IR-ECS-001: Error Detection Integration
**Requirement**: Integrate error detection into type resolution pipeline
- **Integration Points**:
  - `TypeResolver.resolve_type()`: Core type resolution
  - `FunctionAnalyzer._extract_types()`: Function-level analysis
  - `SymbolResolver.resolve_symbols()`: Symbol resolution
- **Detection Strategy**:
  - Proactive monitoring during resolution
  - Post-analysis error classification
  - Context-aware error message generation

### IR-ECS-002: Circular Reference Detection Algorithm
**Requirement**: Implement robust circular reference detection
- **Detection Method**:
  - Maintain resolution stack/path tracking
  - Detect when type appears in its own resolution chain
  - Support different circular reference patterns
- **Performance Considerations**:
  - Minimal overhead for non-circular cases
  - Efficient stack management
  - Early termination on detection

### IR-ECS-003: Complexity Measurement System
**Requirement**: Implement complexity measurement and thresholds
- **Complexity Metrics**:
  - Generic nesting depth
  - Conditional branch count
  - Type reference graph size
  - Resolution operation count
- **Configurable Limits**:
  - Maximum constraint depth (default: 5)
  - Maximum resolution operations (default: 1000)
  - Maximum type graph nodes (default: 500)

### IR-ECS-004: Error Message Enhancement
**Requirement**: Generate informative error messages with context
- **Message Components**:
  - Specific error code
  - Descriptive error message
  - Location information (file, line, column)
  - Context information (involved types, resolution path)
- **Message Quality**:
  - Actionable guidance where possible
  - Clear explanation of what went wrong
  - Suggestions for resolution when applicable

## Error Categories and Detection

### EC-001: CIRCULAR_REFERENCE_DETECTED
**Detection Scenarios**:
```typescript
// Self-referencing interface
interface CircularRef<T extends CircularRef<CircularRef<T>>> {
    self: T;
}

// Mutual circular references  
interface A<T extends B<T>> { value: T; }
interface B<T extends A<T>> { value: T; }
```
**Detection Logic**:
- Track type resolution chain
- Detect when type appears in own resolution path
- Generate error with circular chain information

### EC-002: COMPLEXITY_LIMIT_EXCEEDED
**Detection Scenarios**:
```typescript
// Complex mapped type
type VeryComplexMapped<T> = {
    [K in keyof T]: T[K] extends infer U
        ? U extends Record<string, any>
            ? VeryComplexMapped<U>
            : U extends any[]
            ? VeryComplexMapped<U[0]>[]
            : U
        : never;
};

// Deeply nested generics
function useVeryComplex<T extends Record<string, any>>(
    input: T
): VeryComplexMapped<VeryComplexMapped<VeryComplexMapped<T>>> {
    return {} as any;
}
```
**Detection Logic**:
- Count nesting levels during resolution
- Track resolution operation count
- Measure type graph complexity
- Trigger when limits exceeded

### EC-003: TYPE_RESOLUTION_TIMEOUT
**Detection Scenarios**:
- Long-running constraint satisfaction
- Expensive conditional type evaluation  
- Complex type inference operations
**Detection Logic**:
- Set operation timeouts (default: 100ms per type)
- Monitor resolution duration
- Interrupt and categorize on timeout

### EC-004: CONSTRAINT_DEPTH_EXCEEDED
**Detection Scenarios**:
```typescript
interface TimeoutProneType<
    T extends VeryComplexConstraint<T, U, V>, 
    U, 
    V
> {
    value: T;
}

function complexTimeout<
    T extends TimeoutProneType<T, U, V>,
    U extends TimeoutProneType<U, T, V>, 
    V extends TimeoutProneType<V, T, U>
>(input: T): V {
    return {} as V;
}
```
**Detection Logic**:
- Track generic constraint nesting depth
- Count constraint resolution levels
- Generate error when depth limit exceeded

## Edge Cases and Error Conditions

### EC-ECS-001: Multiple Simultaneous Errors
**Scenario**: Type resolution triggers multiple error conditions
- **Expected Behavior**: 
  - Categorize primary error cause
  - Include secondary error information
  - Prioritize specific over generic errors
- **Error Priority**: Circular > Timeout > Complexity > Generic

### EC-ECS-002: False Positive Prevention
**Scenario**: Complex but valid types incorrectly flagged as errors
- **Expected Behavior**:
  - Accurate detection without false positives
  - Configurable sensitivity thresholds
  - Validation against known-good complex types
- **Quality Assurance**: Test against real-world TypeScript library types

### EC-ECS-003: Performance Impact
**Scenario**: Error detection adds significant overhead
- **Expected Behavior**:
  - Minimal performance impact (< 5% overhead)
  - Efficient detection algorithms
  - Optional detailed analysis mode
- **Performance Monitoring**: Track detection overhead

### EC-ECS-004: Error Recovery
**Scenario**: Continuing analysis after detecting errors
- **Expected Behavior**:
  - Graceful degradation to simpler analysis
  - Partial results where possible
  - Clear indication of analysis limitations
- **Recovery Strategy**: Fallback to basic type analysis

## Success Criteria

### Functional Success
1. **Test Passage**: `test_error_categorization_in_complex_scenarios` passes consistently
2. **Error Code Coverage**: All required error codes generated appropriately
3. **Detection Accuracy**: Correct categorization of complex error scenarios
4. **Message Quality**: Clear, actionable error messages with context

### Quality Success
1. **Precision**: High accuracy in error categorization (> 95%)
2. **Recall**: Detect all instances of categorizable errors
3. **Performance**: Error detection overhead < 5% of analysis time
4. **Usability**: Error messages provide actionable guidance

### Integration Success
1. **Backward Compatibility**: Existing error handling continues to work
2. **Configuration**: Configurable error detection thresholds
3. **Extensibility**: Easy to add new error categories

## Validation Tests

### Test Coverage Requirements
1. **Circular References**: Various circular reference patterns
2. **Complexity Limits**: Different types of complex scenarios
3. **Timeout Conditions**: Time-consuming resolution operations
4. **Constraint Depth**: Deeply nested generic constraints
5. **Mixed Scenarios**: Files with multiple error types
6. **False Positive Testing**: Complex but valid type patterns

### Test Data Scenarios
1. **Simple Error Cases**: Clear single-error scenarios
2. **Complex Mixed Cases**: Multiple error types in one file
3. **Edge Cases**: Boundary conditions for each error type
4. **Real-world Examples**: Error patterns from actual TypeScript projects
5. **Performance Cases**: Error detection under load

## Implementation Priority

### Phase 1: Core Infrastructure (High Priority)
1. **Error Code System**: Implement error code enumeration
2. **Detection Framework**: Basic error detection integration
3. **Message System**: Enhanced error message generation

### Phase 2: Specific Detection (High Priority)
1. **Circular Detection**: Implement circular reference detection
2. **Complexity Measurement**: Build complexity measurement system
3. **Timeout Handling**: Add timeout detection and handling

### Phase 3: Advanced Features (Medium Priority)
1. **Constraint Depth**: Implement constraint depth tracking
2. **Context Enhancement**: Add detailed context information
3. **Configuration**: Make thresholds configurable

### Phase 4: Polish and Optimization (Low Priority)
1. **Performance Optimization**: Minimize detection overhead
2. **Message Improvement**: Enhance error message quality
3. **Documentation**: Comprehensive error code documentation

## Configuration Options

### Error Detection Thresholds
- `max_constraint_depth`: Maximum generic constraint nesting (default: 5)
- `complexity_limit`: Maximum type resolution operations (default: 1000)
- `resolution_timeout_ms`: Timeout per type resolution (default: 100)
- `circular_detection_enabled`: Enable circular reference detection (default: true)

### Error Reporting Options
- `detailed_error_context`: Include detailed context in errors (default: true)
- `error_suggestion_enabled`: Provide resolution suggestions (default: false)
- `error_location_precision`: Precision of error location reporting (default: 'line')