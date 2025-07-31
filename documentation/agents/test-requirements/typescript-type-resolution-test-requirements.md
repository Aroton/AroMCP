# TypeScript Type Resolution Test Requirements

## Overview

This document provides comprehensive test requirements documentation for implementing the missing advanced TypeScript type resolution functionality in the AroMCP analysis server. The tests are designed to follow Test-Driven Development (TDD) principles, starting with failing tests that define exact expectations.

## Test Status Summary

**Total Test Files Analyzed**: 3
**Total Test Methods**: 42
**Currently Failing**: 13 specific tests requiring implementation

## Critical Issues Identified

### 1. DataClass Access Pattern Inconsistency

**Problem**: Tests expect dictionary-style access (`obj['key']`) but models are dataclasses requiring attribute access (`obj.key`)

**Affected Models**:
- `TypeResolutionMetadata` - Tests use `result.resolution_metadata['max_constraint_depth_reached']`
- `TypeInstantiation` - Tests use `inst['type_args'][0]` and `inst.get('type_args')`
- `TypeGuardInfo` - Tests use `info['narrows_to']` and `info['from_type']`

**Required Fix**: Either implement `__getitem__` methods on dataclasses or update tests to use attribute access.

### 2. Missing Advanced Parameters

**Problem**: Advanced parameters are accepted but not implemented in the analysis logic

**Missing Parameters**:
- `max_constraint_depth`: Limits generic constraint resolution depth (tests expect ≤5 levels)
- `track_instantiations`: Collects generic type instantiations (Repository<User>, Repository<Product>)
- `resolve_conditional_types`: Handles TypeScript conditional types (T extends U ? A : B)
- `fallback_on_complexity`: Graceful degradation when analysis becomes complex
- `analyze_type_guards`: Identifies TypeScript type guard functions
- `resolve_class_methods`: Handles class method analysis
- `resolve_imports`: Cross-file type resolution
- `handle_recursive_types`: Manages recursive type definitions

### 3. Specific Error Code Implementation

**Problem**: Tests expect specific error codes but only receive generic "UNKNOWN_TYPE"

**Expected Error Codes**:
- `CIRCULAR_CONSTRAINT`: Circular generic constraints
- `TYPE_RESOLUTION_ERROR`: General type resolution failures
- `CONSTRAINT_DEPTH_EXCEEDED`: When constraint depth exceeds limit
- `CIRCULAR_REFERENCE_DETECTED`: Circular type references
- `COMPLEXITY_LIMIT_EXCEEDED`: Type analysis too complex
- `TYPE_RESOLUTION_TIMEOUT`: Analysis timeout
- `PERFORMANCE_LIMIT_EXCEEDED`: Performance limits exceeded

## Detailed Test Requirements

### A. Progressive Type Resolution (test_type_resolution.py)

#### A1. Conditional Type Resolution (FAILING)
```python
# Expected: Complex conditional types preserved in signatures
# File: test_generic_type_resolution_with_conditional_types()
# Current: Returns None for format_value.types
```

**Requirements**:
- Preserve conditional return types: `T extends string ? string : T extends number ? string : never`
- Include conditional type information in `types` dictionary
- Support `resolve_conditional_types` parameter

#### A2. Resolution Depth Content Differences (FAILING)
```python
# Expected: Progressive depth provides more type information
# File: test_resolution_depth_content_differences()
# Current: Missing resolution_metadata and fallback tracking
```

**Requirements**:
- Track `fallbacks_used` in `TypeResolutionMetadata`
- Progressive type information: `generic_type_count >= basic_type_count`
- Implement `fallback_on_complexity` parameter

#### A3. Error Handling with Specific Codes (FAILING)
```python
# Expected: Specific error codes for different error types
# File: test_type_resolution_error_handling()
# Current: Only "UNKNOWN_TYPE" errors returned
```

**Requirements**:
- `TYPE_RESOLUTION_ERROR` for invalid constraints
- `UNKNOWN_TYPE` for undefined types
- `CIRCULAR_CONSTRAINT` for circular references
- Proper error categorization based on failure type

#### A4. Depth Fallback with Metadata (FAILING)
```python
# Expected: Fallback metadata when depth limits exceeded
# File: test_type_resolution_depth_fallback()
# Current: Missing fallback tracking in metadata
```

**Requirements**:
- Track `fallbacks_used > 0` when fallback occurs
- Include `resolution_metadata` with fallback information
- Support `fallback_on_complexity=True` parameter

#### A5. Nested Type Resolution (FAILING)
```python
# Expected: All nested types (Profile, Address) resolved
# File: test_nested_type_resolution()
# Current: Missing Profile and Address types
```

**Requirements**:
- Resolve all referenced types transitively
- Include nested interface relationships
- Support deep type dependency chains

#### A6. Generic Constraint Depth Tracking (FAILING)
```python
# Expected: DataClass attribute access for max_constraint_depth_reached
# File: test_generic_constraint_resolution_depth_5_levels()
# Current: TypeError on dictionary access
```

**Requirements**:
- Fix access pattern: `result.resolution_metadata.max_constraint_depth_reached`
- Track actual constraint depth reached
- Enforce `max_constraint_depth` parameter (≤5 levels)

#### A7. Generic Instantiation Tracking (FAILING)
```python
# Expected: Track Repository<User>, Repository<Product> instantiations
# File: test_generic_instantiation_tracking()
# Current: AttributeError on TypeInstantiation.get()
```

**Requirements**:
- Fix access pattern: `inst.type_args[0]` instead of `inst['type_args'][0]`
- Track all generic type instantiations
- Support `track_instantiations=True` parameter

#### A8. Type Guard Analysis (FAILING)
```python
# Expected: Identify type guard functions with narrowing info
# File: test_inference_with_type_guards()
# Current: TypeError on TypeGuardInfo dictionary access
```

**Requirements**:
- Fix access pattern: `info.narrows_to` instead of `info['narrows_to']`
- Identify `person is User` type guard patterns
- Include `type_guard_info` with narrowing information

#### A9. Performance Under Complexity (FAILING)
```python
# Expected: Graceful handling of complex type hierarchies
# File: test_type_inference_performance_under_complexity()
# Current: Complete analysis failure with tuple error
```

**Requirements**:
- Handle complex interdependent type hierarchies (50+ types)
- Maintain reasonable performance (<30s for complex scenarios)
- Resolve at least 75% of functions in complex scenarios

### B. Focused Advanced Features (test_focused_advanced_type_resolution.py)

#### B1. Specific Error Code Implementation (FAILING)
```python
# Expected: CIRCULAR_CONSTRAINT and TYPE_RESOLUTION_ERROR codes
# Current: Only UNKNOWN_TYPE returned for all errors
```

**Requirements**:
- Detect circular constraint patterns: `CircularA<T extends CircularB<T>>`
- Return `CIRCULAR_CONSTRAINT` error code for circular references
- Return `TYPE_RESOLUTION_ERROR` for malformed generic constraints

#### B2. Max Constraint Depth Enforcement (FAILING)
```python
# Expected: CONSTRAINT_DEPTH_EXCEEDED when depth > limit
# Current: No depth limit enforcement
```

**Requirements**:
- Implement `max_constraint_depth` parameter processing
- Generate `CONSTRAINT_DEPTH_EXCEEDED` error when limit exceeded
- Support constraint hierarchies up to specified depth

#### B3. Conditional Type Parameter (FAILING)
```python
# Expected: Complex conditional types in function signatures
# Current: Conditional types not preserved in signatures
```

**Requirements**:
- Support `resolve_conditional_types=True` parameter
- Preserve conditional type expressions: `ComplexConditional<T>`
- Include all conditional type definitions in response

#### B4. Complex Error Categorization (FAILING)
```python
# Expected: CIRCULAR_REFERENCE_DETECTED for circular types
# Current: Generic error codes only
```

**Requirements**:
- Detect circular type references in interfaces
- Return `CIRCULAR_REFERENCE_DETECTED` for recursive type patterns
- Support additional error categories for complexity and timeouts

### C. Advanced Type Resolution Failures (test_advanced_type_resolution_failures.py)

#### C1. Resolution Depth Content Differences (FAILING)
```python
# Expected: Progressive type information increase by depth
# Current: Missing fallback_on_complexity parameter support
```

**Requirements**:
- Implement `fallback_on_complexity` parameter
- Track fallback usage in `TypeResolutionMetadata`
- Provide progressively more detailed type information

#### C2. Error Handling with Specific Codes (FAILING)
```python
# Expected: Categorized errors (TYPE_RESOLUTION_ERROR, CIRCULAR_CONSTRAINT)
# Current: Generic error handling only
```

**Requirements**:
- Implement error classification based on failure type
- Support all expected error codes from the error codes list above
- Proper error message generation for each category

#### C3. Advanced Parameter Implementation (FAILING)
```python
# Expected: Support for all advanced parameters
# Current: Parameters accepted but not processed
```

**Parameters Requiring Implementation**:
- `max_constraint_depth`: Generic constraint depth limits
- `track_instantiations`: Generic type instantiation tracking
- `resolve_conditional_types`: TypeScript conditional type handling
- `handle_recursive_types`: Recursive type definition support
- `resolve_class_methods`: Class method signature resolution
- `resolve_imports`: Cross-file type resolution
- `analyze_type_guards`: Type guard function identification

## Implementation Priority

### Phase 1: Critical Fixes (High Priority)
1. **Fix DataClass Access Patterns**
   - Update TypeResolutionMetadata access to use attributes
   - Fix TypeInstantiation and TypeGuardInfo access patterns
   - Ensure all model classes support expected access methods

2. **Implement Basic Error Categorization**
   - Add `CIRCULAR_CONSTRAINT` detection and error code
   - Implement `TYPE_RESOLUTION_ERROR` for general failures
   - Add `CONSTRAINT_DEPTH_EXCEEDED` error handling

3. **Basic Parameter Support**
   - Implement `max_constraint_depth` parameter enforcement
   - Add basic `fallback_on_complexity` tracking
   - Support `track_instantiations` parameter

### Phase 2: Advanced Features (Medium Priority)
1. **Conditional Type Support**
   - Implement `resolve_conditional_types` parameter
   - Preserve conditional type expressions in signatures
   - Support infer keyword and complex conditional patterns

2. **Type Guard Analysis**
   - Implement `analyze_type_guards` parameter
   - Identify type guard functions (`x is Type` patterns)
   - Track type narrowing information

3. **Advanced Error Codes**
   - Add `CIRCULAR_REFERENCE_DETECTED` for recursive types
   - Implement `COMPLEXITY_LIMIT_EXCEEDED` and timeout handling
   - Add performance-related error categorization

### Phase 3: Performance and Edge Cases (Low Priority)
1. **Performance Optimization**
   - Handle complex type hierarchies (50+ interdependent types)
   - Implement timeout handling for long-running analysis
   - Memory usage optimization for large codebases

2. **Advanced Type Features**
   - Support `handle_recursive_types` parameter
   - Implement `resolve_class_methods` for method signatures
   - Add `resolve_imports` for cross-file type resolution

## Test File Locations

```
tests/analysis_server/test_type_resolution.py                    # 9 failing tests
tests/analysis_server/test_focused_advanced_type_resolution.py   # 4 failing tests  
tests/analysis_server/test_advanced_type_resolution_failures.py  # All should fail initially
```

## Expected Behavior Examples

### Successful Constraint Depth Tracking
```python
result = get_function_details_impl(
    functions="processDeepGeneric",
    max_constraint_depth=5
)
# Should succeed with: result.resolution_metadata.max_constraint_depth_reached <= 5
```

### Successful Type Instantiation Tracking
```python
result = get_function_details_impl(
    functions="setupRepositories", 
    track_instantiations=True
)
# Should return: result.type_instantiations["Repository"] with User, Product instantiations
```

### Successful Error Categorization
```python
result = get_function_details_impl(functions="circularConstraint")
# Should return: error.code == "CIRCULAR_CONSTRAINT" for circular references
```

## Validation Criteria

Each implemented feature must:
1. **Pass Corresponding Tests**: All related test methods must pass
2. **Maintain Backward Compatibility**: Existing functionality must continue working
3. **Follow Model Conventions**: Use proper dataclass patterns and access methods
4. **Handle Edge Cases**: Graceful degradation for complex scenarios
5. **Performance Requirements**: Meet specified time limits for analysis operations

## Notes for Implementation

- **DataClass vs Dictionary Access**: Consider implementing `__getitem__` and `get` methods on relevant dataclasses to support both access patterns
- **Error Code Consistency**: Ensure error codes match exactly what tests expect
- **Parameter Validation**: Advanced parameters should be validated and have appropriate defaults
- **Memory Management**: Large type hierarchies should not cause memory issues
- **Test Fixture Dependencies**: Tests rely on specific fixture files in `tests/analysis_server/fixtures/phase3_types/`

This documentation provides the TDD Code Writer with comprehensive requirements to implement the missing TypeScript type resolution functionality systematically.