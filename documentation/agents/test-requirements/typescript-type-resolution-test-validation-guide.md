# TypeScript Type Resolution Test Validation Guide

## Overview

This guide provides specific test commands, expected outcomes, and validation steps for implementing the TypeScript type resolution functionality. Use this guide to validate each implementation phase systematically.

## Quick Test Commands

### Run All Type Resolution Tests
```bash
# Full test suite (will show overall progress)
uv run pytest tests/analysis_server/test_type_resolution.py tests/analysis_server/test_focused_advanced_type_resolution.py -v

# Stop on first failure (good for iterative development)
uv run pytest tests/analysis_server/test_type_resolution.py tests/analysis_server/test_focused_advanced_type_resolution.py -x
```

### Run Individual Test Categories
```bash
# Progressive type resolution tests
uv run pytest tests/analysis_server/test_type_resolution.py::TestProgressiveTypeResolution -v

# Advanced features tests  
uv run pytest tests/analysis_server/test_focused_advanced_type_resolution.py::TestFocusedAdvancedTypeResolution -v

# Generic constraint tests
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution -v
```

## Phase-by-Phase Validation

### Phase 1: Infrastructure Fixes

#### 1.1 Fix DataClass Access Patterns

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution::test_generic_constraint_resolution_depth_5_levels -v --tb=short
```

**Before Fix** (Current State):
```
TypeError: 'TypeResolutionMetadata' object is not subscriptable
```

**After Fix** (Expected):
```
AssertionError: Missing resolution_metadata
# OR
AssertionError: Expected constraint depth >= 1, got X
```

**Success Criteria**: Error changes from `TypeError` to `AssertionError` (infrastructure working)

#### 1.2 Fix Error Code Classification

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_focused_advanced_type_resolution.py::TestFocusedAdvancedTypeResolution::test_specific_error_codes_implementation -v --tb=short
```

**Before Fix** (Current State):
```
AssertionError: Expected CIRCULAR_CONSTRAINT in ['UNKNOWN_TYPE', 'UNKNOWN_TYPE', ...]
```

**After Fix** (Expected):
```
PASSED  # Should pass completely once error codes are implemented
```

**Success Criteria**: Test passes with proper error code classification

#### 1.3 Fix TypeInstantiation Access

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution::test_generic_instantiation_tracking -v --tb=short
```

**Before Fix** (Current State):
```
AttributeError: 'TypeInstantiation' object has no attribute 'get'
```

**After Fix** (Expected):
```
AssertionError: Missing type_instantiations attribute
# OR test passes if instantiation tracking is implemented
```

**Success Criteria**: Error changes from `AttributeError` to logic-based `AssertionError`

### Phase 2: Core Functionality Implementation

#### 2.1 Constraint Depth Tracking

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution::test_generic_constraint_resolution_depth_5_levels -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `result.resolution_metadata.max_constraint_depth_reached <= 5`
- Proper constraint depth tracking in metadata
- All 5 levels of generic constraints handled

#### 2.2 Type Instantiation Tracking

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution::test_generic_instantiation_tracking -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `result.type_instantiations["Repository"]` contains instantiations
- Type args include "User", "Product", "string", "number"
- Proper TypeInstantiation objects created

#### 2.3 Fallback Tracking

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestProgressiveTypeResolution::test_type_resolution_depth_fallback -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `result.resolution_metadata.fallbacks_used > 0`
- `fallback_on_complexity=True` parameter respected
- Metadata properly populated

### Phase 3: Advanced Features

#### 3.1 Conditional Type Resolution

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_focused_advanced_type_resolution.py::TestFocusedAdvancedTypeResolution::test_resolve_conditional_types_parameter -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `"ComplexConditional<T>"` in function signature
- `"IsString<T>"` in function signature
- All conditional types included in response

#### 3.2 Type Guard Analysis

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeInferenceAccuracy::test_inference_with_type_guards -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `"person is User"` in function signature
- `type_guard_info.is_type_guard == True`
- `type_guard_info.narrows_to == 'User'`

#### 3.3 Nested Type Resolution

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeDefinitionExtraction::test_nested_type_resolution -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- All expected types present: ["User", "Profile", "Address", "Partial"]
- Nested relationships preserved
- Transitive type resolution working

### Phase 4: Performance and Complex Scenarios

#### 4.1 Complex Type Hierarchy Handling

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeInferenceAccuracy::test_type_inference_performance_under_complexity -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `result.success == True`
- Analysis time < 30 seconds
- At least 15 out of 20 functions resolved successfully

#### 4.2 Progressive Resolution Differences

**Test Command**:
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestProgressiveTypeResolution::test_resolution_depth_content_differences -v
```

**Expected After Implementation**:
```
PASSED
```

**Validation Points**:
- `generic_type_count >= basic_type_count`
- `full_type_count >= generic_type_count`
- Progressive type information increase

## Comprehensive Test Validation

### Run All Tests by Category

#### Basic Type Resolution (Should Pass Early)
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeDefinitionExtraction -v
```
**Expected**: Most tests pass (these are simpler)

#### Generic Type Resolution (Moderate Complexity)
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution -v
```
**Expected**: Pass after Phase 2 implementation

#### Advanced Type Features (High Complexity)
```bash
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeInferenceAccuracy -v
```
**Expected**: Pass after Phase 3 implementation

### Performance Benchmarks

#### Timing Validation
```bash
# Run with timing output
uv run pytest tests/analysis_server/test_type_resolution.py::TestProgressiveTypeResolution::test_progressive_resolution_performance_comparison -v --durations=10
```

**Expected Timing Requirements**:
- Basic resolution: < 1.0 seconds
- Generic resolution: < 3.0 seconds  
- Full inference: < 10.0 seconds

#### Memory Usage Validation
```bash
# Monitor memory during complex tests
uv run pytest tests/analysis_server/test_type_resolution.py::TestTypeInferenceAccuracy::test_type_inference_performance_under_complexity -v -s
```

**Expected**: No memory errors, reasonable memory usage

## Debugging Failed Tests

### Get Detailed Error Information
```bash
# Full traceback for debugging
uv run pytest tests/analysis_server/test_type_resolution.py::TestSpecificFailingTest -vvv --tb=long

# Show local variables in traceback
uv run pytest tests/analysis_server/test_type_resolution.py::TestSpecificFailingTest -vvv --tb=long --showlocals
```

### Check Specific Assertion Details
```bash
# Print detailed assertion output
uv run pytest tests/analysis_server/test_type_resolution.py::TestSpecificFailingTest -vvv -s
```

### Isolate Single Test Cases
```bash
# Run just one test method for focused debugging
uv run pytest tests/analysis_server/test_type_resolution.py::TestGenericTypeResolution::test_generic_constraint_resolution_depth_5_levels -vvv --tb=short
```

## Validation Checklists

### Phase 1 Complete Checklist
- [ ] No more `TypeError: 'TypeResolutionMetadata' object is not subscriptable`
- [ ] No more `AttributeError: 'TypeInstantiation' object has no attribute 'get'`
- [ ] No more `TypeError: 'TypeGuardInfo' object is not subscriptable`
- [ ] Error codes other than "UNKNOWN_TYPE" appear in test failures

### Phase 2 Complete Checklist
- [ ] `test_generic_constraint_resolution_depth_5_levels` passes
- [ ] `test_generic_instantiation_tracking` passes  
- [ ] `test_type_resolution_depth_fallback` passes
- [ ] `test_specific_error_codes_implementation` passes

### Phase 3 Complete Checklist
- [ ] `test_resolve_conditional_types_parameter` passes
- [ ] `test_inference_with_type_guards` passes
- [ ] `test_nested_type_resolution` passes
- [ ] Complex conditional types preserved in signatures

### Phase 4 Complete Checklist
- [ ] `test_type_inference_performance_under_complexity` passes
- [ ] `test_resolution_depth_content_differences` passes
- [ ] All timing requirements met
- [ ] All memory usage requirements met

## Success Criteria Summary

### Immediate Success (Phase 1)
- **Infrastructure Working**: Error types change from TypeError to AssertionError
- **Error Classification**: Specific error codes returned instead of generic "UNKNOWN_TYPE"

### Partial Success (Phase 2)  
- **Core Tracking**: At least 50% of failing tests now pass
- **Metadata Working**: `resolution_metadata` properly populated
- **Basic Parameters**: `max_constraint_depth` and similar parameters functional

### Near Complete (Phase 3)
- **Advanced Features**: 80% of failing tests now pass
- **Complex Types**: Conditional types and type guards working
- **Type Resolution**: Nested type resolution functional

### Full Success (Phase 4)
- **All Tests Pass**: 100% test success rate
- **Performance**: All timing and memory requirements met
- **Robustness**: Complex scenarios handled gracefully

## Quick Status Check Commands

### Current Status
```bash
# See how many tests are currently failing
uv run pytest tests/analysis_server/test_type_resolution.py tests/analysis_server/test_focused_advanced_type_resolution.py --tb=no -q
```

### Progress Tracking
```bash
# Count passing vs failing tests
uv run pytest tests/analysis_server/test_type_resolution.py tests/analysis_server/test_focused_advanced_type_resolution.py --tb=no | grep -E "(PASSED|FAILED)" | sort | uniq -c
```

### Specific Error Types
```bash
# See what types of errors are occurring
uv run pytest tests/analysis_server/test_type_resolution.py tests/analysis_server/test_focused_advanced_type_resolution.py --tb=line | grep -E "(TypeError|AttributeError|AssertionError)"
```

This validation guide ensures systematic verification of each implementation phase, making it easy to track progress and identify when each phase is successfully completed.