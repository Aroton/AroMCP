# Implementation Plan: Knip Integration for Unused Code Detection

## Phase 1: Core Knip Tool Implementation (Day 1-2)

### Executive Summary
- Phase objective: Create `find_unused_code` MCP tool that wraps Knip CLI
- Duration estimate: 1-2 days
- Critical dependencies: Knip installation detection, JSON output parsing
- Deliverables: Working tool with error handling and structured responses

### Technical Approach
Based on existing analysis server patterns, leverage:
- FastMCP standards with `@json_convert` and typed responses
- Response models in `models/typescript_models.py`
- Tool registration in `tools/__init__.py`
- Implementation function in separate file `tools/find_unused_code.py`
- Comprehensive error handling following existing patterns

### Task Breakdown

1. **Response Model Creation**
   - Add `UnusedCodeInfo` dataclass to `typescript_models.py`
   - Add `FindUnusedCodeResponse` with pagination support
   - Include Knip-specific metadata (configuration, filters)
   - Estimated effort: 2-3 hours, low complexity

2. **Core Tool Implementation**
   - Create `tools/find_unused_code.py` with `find_unused_code_impl()`
   - Implement Knip CLI execution with subprocess
   - Parse Knip JSON output into structured response
   - Handle common Knip exit codes and error scenarios
   - Estimated effort: 4-6 hours, medium complexity

3. **Tool Registration**
   - Add tool registration to `tools/__init__.py`
   - Follow existing pattern with `@mcp.tool` and `@json_convert`
   - Include comprehensive docstring with "Use this tool when" section
   - Support core parameters: include/exclude patterns, config file
   - Estimated effort: 1-2 hours, low complexity

4. **Knip Installation Detection**
   - Check for local vs global Knip installation
   - Clear error messages for missing Knip
   - Fallback strategies (npx knip, global knip)
   - Guide users on Knip installation
   - Estimated effort: 2-3 hours, medium complexity

### Dependencies & Integration Points
- Existing analysis server infrastructure (tools registration, models)
- No upstream dependencies from previous phases
- Integration with MCP_PROJECT_ROOT resolution
- Compatible with existing pagination system

### Risk Analysis & Mitigation
- **Technical Risk**: Knip JSON output changes
  - Mitigation: Version detection and format validation
- **Installation Risk**: Users without Knip installed
  - Mitigation: Clear error messages with installation instructions
- **Performance Risk**: Large projects with many unused exports
  - Mitigation: Built-in pagination support, configurable filters

### Success Criteria
- Tool successfully wraps Knip CLI commands
- Structured response with unused files, exports, dependencies
- Clear error handling for missing Knip or invalid configuration
- Passes basic functionality tests

## Phase 2: Advanced Features & Configuration (Day 3)

### Executive Summary
- Phase objective: Add Knip configuration support and advanced filtering
- Duration estimate: 1 day
- Prerequisites: Phase 1 core tool working
- Deliverables: Production-ready tool with full Knip feature support

### Technical Approach
Extend Phase 1 implementation with:
- Knip configuration file support (knip.json, knip.config.js)
- Framework-specific presets (React, Next.js, Vue, etc.)
- Advanced filtering options (file patterns, dependency types)
- Performance optimizations for large codebases

### Task Breakdown

1. **Configuration File Support**
   - Detect and use existing knip.json/knip.config.js
   - Allow override with custom configuration
   - Validate configuration before execution
   - Estimated effort: 3-4 hours, medium complexity

2. **Framework Presets Integration**
   - Support common framework presets
   - Auto-detect framework from package.json
   - Allow manual framework specification
   - Estimated effort: 2-3 hours, low-medium complexity

3. **Advanced Filtering Options**
   - File inclusion/exclusion patterns
   - Dependency type filtering (devDependencies, etc.)
   - Workspace support for monorepos
   - Estimated effort: 2-3 hours, medium complexity

4. **Performance Optimizations**
   - Streaming output for large results
   - Configurable timeouts
   - Memory usage monitoring
   - Estimated effort: 2-3 hours, medium complexity

### Dependencies & Integration Points
- Phase 1 core implementation must be complete
- Integration with existing project detection patterns
- Compatible with monorepo workspace patterns

### Risk Analysis & Mitigation
- **Configuration Risk**: Invalid Knip configurations
  - Mitigation: Configuration validation before execution
- **Framework Risk**: Unsupported frameworks
  - Mitigation: Fallback to generic analysis
- **Performance Risk**: Timeout on large projects
  - Mitigation: Configurable timeouts and chunked execution

### Success Criteria
- Supports all major Knip configuration options
- Works with popular frameworks out-of-the-box
- Handles large projects without timeout issues
- Configuration validation prevents runtime errors

## Phase 3: Testing & Documentation (Day 4)

### Executive Summary
- Phase objective: Comprehensive testing and production readiness
- Duration estimate: 1 day
- Prerequisites: Phases 1-2 complete
- Deliverables: Full test coverage, documentation, integration validation

### Technical Approach
Following existing analysis server testing patterns:
- Unit tests for core functionality and error cases
- Integration tests with real Knip installations
- Performance tests for large codebases
- Security validation for path handling

### Task Breakdown

1. **Core Functionality Tests**
   - Basic unused code detection scenarios
   - Configuration file handling
   - Error condition handling
   - Estimated effort: 3-4 hours, medium complexity

2. **Integration Testing**
   - Test with real TypeScript projects
   - Framework-specific scenarios
   - Monorepo workspace testing
   - Estimated effort: 2-3 hours, medium complexity

3. **Security & Edge Case Testing**
   - Path traversal protection
   - Invalid configuration handling
   - Large output handling
   - Estimated effort: 2-3 hours, medium complexity

4. **Documentation Updates**
   - Tool usage examples
   - Configuration reference
   - Troubleshooting guide
   - Estimated effort: 1-2 hours, low complexity

### Dependencies & Integration Points
- All previous phases must be complete
- Update `tests/test_individual_servers.py` to include new tool
- Integration with existing test infrastructure

### Risk Analysis & Mitigation
- **Test Coverage Risk**: Missing edge cases
  - Mitigation: Systematic test scenarios based on Knip documentation
- **Integration Risk**: Inconsistent behavior across environments
  - Mitigation: Multiple environment testing (local vs CI)

### Success Criteria
- 90%+ test coverage for new functionality
- All tests pass in CI environment
- Documentation provides clear usage guidance
- Tool included in server registration tests

## Implementation Timeline

**Day 1**: Phase 1 Tasks 1-2 (Response models, core implementation)
**Day 2**: Phase 1 Tasks 3-4 (Tool registration, installation detection)
**Day 3**: Phase 2 (Advanced features and configuration)
**Day 4**: Phase 3 (Testing and documentation)

## Technical Implementation Details

### Response Model Structure
```python
@dataclass
class UnusedCodeInfo:
    file_path: str
    unused_exports: list[str]
    unused_files: list[str]
    unused_dependencies: list[str]
    issue_type: str  # "file", "export", "dependency", "type"
    severity: str    # "error", "warning", "info"

@dataclass
class FindUnusedCodeResponse:
    unused_items: list[UnusedCodeInfo]
    total_issues: int
    knip_version: str
    configuration_used: dict[str, Any]
    errors: list[AnalysisError]
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None
```

### Tool Registration Pattern
```python
@mcp.tool
@json_convert
def find_unused_code(
    include_patterns: str | list[str] | None = None,
    exclude_patterns: str | list[str] | None = None,
    config_file: str | None = None,
    include_entry_files: bool = True,
    include_dependencies: bool = True,
    include_devDependencies: bool = False,
    workspace: str | None = None,
    page: int = 1,
    max_tokens: int = 20000,
) -> FindUnusedCodeResponse:
```

### CLI Integration Strategy
- Use `subprocess.run()` with proper error handling
- Parse JSON output with fallback for text output
- Validate Knip installation before execution
- Support both local (`npx knip`) and global (`knip`) installations

## Success Metrics

1. **Functionality**: Tool successfully detects unused code in TypeScript projects
2. **Reliability**: Handles missing Knip installation gracefully
3. **Performance**: Processes large projects within reasonable time limits
4. **Usability**: Clear error messages and comprehensive documentation
5. **Integration**: Seamlessly integrates with existing analysis server patterns

This simplified approach leverages proven Knip technology instead of building custom unused code detection, reducing implementation time from weeks to days while providing production-ready functionality.