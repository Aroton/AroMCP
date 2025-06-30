# MCP Tool Suite Technical Design

## Project Overview

This document defines a suite of MCP (Model Context Protocol) tools that serve as reusable utilities for AI-driven code operations across multiple projects. These tools are "dumb" utilities - they perform deterministic, programmatic operations without any AI/LLM logic. The AI agent (Claude) handles all intelligent decision-making.

## Core Design Principles

1. **Separation of Concerns**: Each tool category has a single, well-defined responsibility
2. **Token Efficiency**: Servers handle operations that would be token-expensive in an AI context
3. **Project Agnostic**: Servers work with any project structure without hardcoded paths
4. **Stateless Operations**: Most operations should be stateless except for the dedicated state management tools
5. **Error Resilience**: Graceful error handling with structured error responses
6. **Batch Operations**: Support batch operations where applicable to reduce round trips
7. **Security**: Validate inputs, use whitelists for commands, prevent directory traversal

## Tool Categories

The MCP server provides six categories of tools designed to handle token-intensive operations and provide structured data for AI decision-making.

### 1. FileSystem Tools

**Purpose**: Handle all file I/O operations, git operations, and code parsing tasks that would consume tokens if done in the AI agent.

**Key Tools**:
- `get_target_files`: List files based on git status (working/branch/commit) or path patterns
- `read_files_batch`: Read multiple files in one operation, return as path->content dict
- `write_files_batch`: Write multiple files atomically with automatic directory creation
- `apply_file_diffs`: Apply multiple diffs to files with validation and rollback support
- `preview_file_changes`: Show consolidated preview of all pending changes
- `validate_diffs`: Pre-validate diffs for conflicts and applicability
- `extract_method_signatures`: Parse code files to extract function/method signatures programmatically
- `find_imports_for_files`: Identify which files import the given files (dependency analysis)
- `load_documents_by_pattern`: Load multiple documents matching glob patterns (for standards, configs)

**Enhanced Diff Operations**:
The improved diff handling provides safety and predictability:
```json
// preview_file_changes response
{
  "data": {
    "total_files": 3,
    "total_changes": 45,
    "files": [
      {
        "path": "src/api/handler.ts",
        "additions": 12,
        "deletions": 5,
        "conflicts": [],
        "preview": "... diff preview ..."
      }
    ],
    "validation": {
      "all_valid": true,
      "conflicts_detected": false,
      "applicable": true
    }
  }
}
```

**Design Considerations**:
- All paths must be relative to the project root (MCP_PROJECT_ROOT)
- Prevent directory traversal attacks with strict path validation
- Support multiple file encodings (UTF-8 default, with fallbacks)
- Handle large files gracefully (streaming for files >1MB)
- Return structured data, not raw strings where possible
- Include file metadata (size, last modified) when relevant
- Support standard unified diff format for patch application
- Diff validation includes:
  - Syntax checking for valid diff format
  - Conflict detection between multiple diffs
  - Verification that source content matches
  - Atomic transactions - all succeed or all fail
  - Automatic backup before applying changes

### 2. State Management Tools

**Purpose**: Manage persistent state for AI-driven processes with YAML-based orchestration, supporting multiple process types per project with automatic state checkpointing and TODO integration.

**Key Tools**:
- `list_available_processes`: List all process definitions available for the project
- `load_process_definition`: Load a specific YAML process definition by name
- `initialize_process`: Create a new process instance from a selected definition
- `list_active_processes`: Show all running/paused processes for the project
- `get_process_steps`: Return next 10 steps with embedded state update instructions
- `get_process_state`: Retrieve current state snapshot including completed steps
- `update_step_state`: Mark step as pending/in_progress/completed with validation
- `validate_step_completion`: Check if step requirements are met before completion
- `checkpoint_state`: Force a state checkpoint at any point
- `pause_process`: Pause a process to work on another
- `resume_process`: Resume a paused process from last checkpoint
- `cleanup_process`: Archive completed process state

**Process Library Structure**:
```
project_root/
├── .mcp/
│   ├── processes/
│   │   ├── code-refactoring.yaml
│   │   ├── technical-design.yaml
│   │   ├── code-simplification.yaml
│   │   ├── bug-investigation.yaml
│   │   └── feature-implementation.yaml
│   └── state/
│       ├── active/
│       │   └── {process-id}/
│       └── archived/
```

**Example Process Definitions**:

**code-simplification.yaml**:
```yaml
version: 1
process:
  name: "code-simplification"
  description: "Simplify complex code while maintaining functionality"
  category: "refactoring"
  
  steps:
    - id: "identify_complex_code"
      description: "Find code with high complexity metrics"
      tools: ["analyze_complexity", "detect_code_smells"]
      state_checkpoint: true
      
    - id: "analyze_dependencies"
      description: "Understand code dependencies before simplification"
      depends_on: ["identify_complex_code"]
      tools: ["extract_dependencies", "find_import_cycles"]
      state_checkpoint: true
      
    - id: "create_simplification_plan"
      description: "Plan simplification approach"
      depends_on: ["analyze_dependencies"]
      validation:
        requires: ["no_breaking_changes"]
      state_checkpoint: true
```

**technical-design.yaml**:
```yaml
version: 1
process:
  name: "technical-design"
  description: "Create technical design documentation"
  category: "documentation"
  
  steps:
    - id: "analyze_requirements"
      description: "Analyze feature requirements and constraints"
      tools: ["extract_api_endpoints", "analyze_component_usage"]
      state_checkpoint: true
      
    - id: "research_patterns"
      description: "Research applicable design patterns"
      depends_on: ["analyze_requirements"]
      state_checkpoint: true
      
    - id: "draft_design"
      description: "Create initial technical design"
      depends_on: ["research_patterns"]
      validation:
        output_schema:
          design_doc: "string"
          diagrams: "array"
      state_checkpoint: true
```

**Design Considerations**:
- Process definitions stored in project's `.mcp/processes/` directory
- Multiple processes can be active simultaneously per project
- Each process instance has a unique ID and isolated state
- Schema versioning with strict no-resume on version change
- Processes can be paused/resumed to switch contexts
- Process categories help organize different workflow types
- State automatically tracks which tools were used in each step
- Process history maintained for learning and optimization

### 3. Build Tools

**Purpose**: Execute build, lint, test, and validation commands with structured output parsing, focusing on actionable error reporting.

**Key Tools**:
- `run_command`: Execute whitelisted commands with structured output
- `run_nextjs_build`: Specialized Next.js build with categorized error reporting
- `parse_typescript_errors`: Run tsc and return structured error data
- `parse_lint_results`: Run linters and return categorized issues
- `run_test_suite`: Execute tests with parsed results
- `check_dependencies`: Analyze package.json and installed deps
- `get_build_config`: Extract build configuration from various sources

**Next.js Build Tool Specifics**:
- Parses and categorizes TypeScript compilation errors
- Extracts ESLint violations with file locations and rule IDs
- Reports bundle size warnings with threshold comparisons
- Filters out verbose logs, focusing on actionable issues
- Returns structured data optimized for AI consumption:
```json
{
  "typescript_errors": [
    {
      "file": "src/components/Button.tsx",
      "line": 15,
      "column": 8,
      "severity": "error",
      "message": "Property 'onClick' is missing",
      "code": "TS2741"
    }
  ],
  "eslint_violations": [
    {
      "file": "src/utils/api.ts",
      "line": 23,
      "rule": "no-console",
      "severity": "warning",
      "message": "Unexpected console statement"
    }
  ],
  "bundle_warnings": [
    {
      "chunk": "main",
      "size": "512KB",
      "limit": "500KB",
      "severity": "warning"
    }
  ]
}
```

**Design Considerations**:
- Command whitelisting with configurable allowed lists
- Structured parsing of common output formats
- Resource limits (timeout, memory) for command execution
- Support for different package managers (npm, yarn, pnpm)
- Error deduplication to reduce noise
- Focus on actionable items only (no performance metrics or verbose logs)

### 4. Code Analysis Tools

**Purpose**: Perform deterministic code analysis operations that would be token-heavy, focusing on security, quality, and architecture insights.

**Priority Tools** (based on immediate value):

**Security & Quality**:
- `detect_security_patterns`: Find hardcoded secrets, SQL injection risks, unsafe patterns
  - Scans for API keys, passwords, connection strings in code
  - Identifies SQL concatenation, eval usage, command injection risks
  - Returns categorized findings with severity levels
  
- `find_import_cycles`: Detect circular dependencies between modules
  - Builds module dependency graph
  - Identifies cycles with full import chains
  - Suggests refactoring approaches

**Dead Code & Optimization**:
- `find_dead_code`: Comprehensive dead code detection
  - Unused exports, functions, variables
  - Unreachable code paths
  - Orphaned files with no imports
  - Returns actionable removal suggestions
  
- `analyze_component_usage`: Track component/function usage across codebase
  - Where each component/function is imported and used
  - Usage frequency statistics
  - Helps identify candidates for refactoring

**Architecture Analysis**:
- `extract_api_endpoints`: Parse and document API routes
  - Extracts HTTP methods, paths, parameters
  - Identifies middleware and authentication
  - Generates OpenAPI-compatible structure
  
**Additional Tools**:
- `detect_code_smells`: Find long methods, high complexity, parameter overload
- `analyze_test_coverage`: Parse coverage reports, identify untested paths
- `find_similar_code`: Detect near-duplicates for consolidation
- `analyze_bundle_impact`: Estimate change impact on bundle size
- `extract_configuration`: Gather all config values and their sources

**Design Considerations**:
- Use AST parsing for accurate analysis
- Support multiple languages (TypeScript, JavaScript, Python)
- Return actionable data with specific line numbers and fix suggestions
- Batch analysis to reduce overhead
- Cache results for unchanged files

### 5. Context Window Management Tools

**Purpose**: Help AI agents efficiently manage token usage and context windows during long-running operations.

**Key Tools**:
- `track_context_usage`: Monitor cumulative token consumption across operations
  - Tracks tokens used per tool call
  - Maintains running total for current session
  - Warns when approaching context limits
  
- `suggest_context_checkpoint`: Recommend optimal points to create summaries
  - Analyzes token usage patterns
  - Identifies natural breakpoints in work
  - Suggests what information to preserve
  
- `compress_context`: Create condensed summaries of completed work
  - Generates structured summaries of file changes
  - Preserves key decisions and rationale
  - Maintains critical state information
  - Returns token-efficient representation
  
- `estimate_token_budget`: Calculate remaining context for planned operations
  - Estimates tokens needed for upcoming tasks
  - Provides recommendations for context management
  - Suggests when to offload to state storage

**Example Usage**:
```json
{
  "data": {
    "current_usage": 45000,
    "estimated_limit": 100000,
    "usage_by_category": {
      "file_reading": 25000,
      "analysis": 15000,
      "state_management": 5000
    },
    "recommendations": [
      "Consider creating checkpoint before next large file read",
      "Archive completed process steps to reduce context"
    ]
  }
}
```

**Design Considerations**:
- Token counting based on tiktoken or similar libraries
- Intelligent summarization that preserves critical information
- Integration with state management for context persistence
- Configurable thresholds for different model contexts

### 6. Interactive Debugging Tools

**Purpose**: Provide debugging utilities that help AI agents investigate and resolve issues efficiently.

**Key Tools**:
- `create_debug_snapshot`: Capture comprehensive project state
  - Saves current file states, git status, process state
  - Creates restore points for experimentation
  - Includes relevant logs and error traces
  - Minimal overhead for quick snapshots
  
- `trace_execution_path`: Track code execution flow
  - Instruments code with lightweight tracing
  - Captures function calls and returns
  - Records variable values at key points
  - Returns execution graph
  
- `analyze_error_context`: Extract relevant context around errors
  - Parses stack traces to identify error locations
  - Extracts surrounding code context
  - Identifies recent changes that might be related
  - Suggests relevant files to investigate
  
- `suggest_debug_steps`: Provide debugging strategies
  - Analyzes error patterns
  - Suggests specific debugging approaches
  - Recommends relevant tools to use
  - Provides example commands

**Example Error Analysis**:
```json
{
  "data": {
    "error_location": {
      "file": "src/api/handler.ts",
      "line": 45,
      "function": "processRequest"
    },
    "related_files": [
      "src/api/validator.ts",
      "src/types/request.ts"
    ],
    "recent_changes": [
      {
        "file": "src/api/handler.ts",
        "changed": "2 hours ago",
        "diff_summary": "Added new validation logic"
      }
    ],
    "suggested_steps": [
      "Check validator.ts for schema changes",
      "Trace execution with sample request",
      "Compare with last working version"
    ]
  }
}
```

**Design Considerations**:
- Low-overhead tracing mechanisms
- Smart context extraction without overwhelming detail
- Integration with version control for change tracking
- Language-agnostic debugging strategies

## Configuration Standards

### Project Configuration
Each project is configured when initializing a connection to the MCP server. Multiple projects can use the same server instance simultaneously with isolated configurations.

**Project Initialization Parameters**:
```json
{
  "project_id": "my-nextjs-app",
  "project_root": "/path/to/project/root",
  "processes_dir": "/path/to/project/.mcp/processes",  // Directory containing process YAML files
  "state_config": {
    "backend": "file",  // file|redis|postgres
    "path": "/path/to/project/.mcp/state",
    "init_file": "/path/to/initial-state.yaml"  // optional
  },
  "security_level": "standard",  // strict|standard|permissive
  "allowed_commands": ["npm", "yarn", "pnpm", "tsc", "eslint"]
}
```

### Server-Level Environment Variables
These apply to the MCP server itself, not individual projects:
```
# Server Configuration
MCP_SERVER_PORT=3000  # Port for MCP server
MCP_MAX_PROJECTS=10  # Maximum concurrent projects
MCP_LOG_LEVEL=debug|info|warn|error

# Default State Backend (can be overridden per project)
MCP_DEFAULT_STATE_BACKEND=file
MCP_DEFAULT_STATE_PATH=./.mcp/state
```

### Project Isolation
- Each project has its own isolated workspace
- File operations are restricted to the project's root directory
- State is maintained separately per project
- Commands are executed in the project's context
- Security policies apply per project

### Tool Response Format
Optimized for LLM consumption with minimal overhead:
```
{
  "data": { ... },  // Tool-specific data, structured for easy parsing
  "error": {  // Only present on failure
    "code": "ERROR_CODE",
    "message": "Brief error description"
  }
}
```

Tools should:
- Return data directly without unnecessary wrapper objects
- Use consistent field names across similar tools
- Include only actionable information
- Omit verbose metadata unless critical for decision-making

### Error Codes Convention
- `INVALID_INPUT`: Validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Security check failed
- `OPERATION_FAILED`: Command/operation failed
- `TIMEOUT`: Operation timed out
- `UNSUPPORTED`: Feature not supported

## Implementation Guidelines

1. **Language**: Python 3.12+ using the `fastmcp` SDK
2. **Dependencies**: Minimal external dependencies, prefer stdlib
3. **Testing**: Each tool should have unit tests with mocked filesystem/commands
4. **Documentation**: Each tool must have comprehensive docstrings
5. **Logging**: Structured logging with appropriate levels
6. **Performance**: Async operations where beneficial, connection pooling for state backends

## Security Requirements

1. **Input Validation**: Validate all inputs against schemas
2. **Path Security**: Prevent directory traversal attacks
3. **Command Security**: Whitelist approach for all command execution
4. **Resource Limits**: Implement timeouts and memory limits
5. **Secrets**: Never log sensitive information

## Deployment Considerations

1. **Packaging**: Single unified server with all tools
2. **Versioning**: Semantic versioning with clear upgrade paths
3. **Compatibility**: Maintain backwards compatibility within major versions
4. **Discovery**: Tools are discoverable through FastMCP introspection
5. **Health Checks**: Server-level health checks via FastMCP

## Example Usage Patterns

The servers should support these common patterns:

1. **Batch Processing**: Process multiple files in parallel
2. **Incremental Updates**: Only process changed items
3. **Progress Tracking**: Long operations report progress
4. **Resumability**: Processes can be paused and resumed
5. **Audit Trail**: State changes are tracked with metadata

Remember: These tools are utilities that provide efficient, deterministic operations. They do not make decisions - they execute operations requested by the AI agent and return structured data for the AI to analyze and act upon.

## Implementation Phases

The implementation is organized into six phases, each focusing on a single tool category. This approach allows for incremental development, testing, and validation.

### Phase 1: FileSystem Tools (Foundation)
**Complexity**: Low-Medium  
**Dependencies**: None  
**Timeline**: 1-2 weeks

**Tools to implement**:
- `get_target_files` - Basic file listing with git integration
- `read_files_batch` - Multi-file reading
- `write_files_batch` - Atomic multi-file writing
- `extract_method_signatures` - AST-based parsing
- `find_imports_for_files` - Import dependency tracking
- `load_documents_by_pattern` - Pattern-based document loading

**Later in phase (enhanced features)**:
- `apply_file_diffs` - Diff application with validation
- `preview_file_changes` - Change preview system
- `validate_diffs` - Diff validation logic

**Deliverables**:
- Complete tool implementations in `src/aromcp/filesystem_server/tools.py`
- Comprehensive test suite in `tests/test_filesystem_tools.py`
- README section with usage examples for each tool
- Security validation tests (path traversal, encoding)

### Phase 2: Build Tools
**Complexity**: Low  
**Dependencies**: FileSystem Tools (for reading config files)  
**Timeline**: 1 week

**Tools to implement**:
- `run_command` - Basic command execution with whitelisting
- `get_build_config` - Config extraction
- `check_dependencies` - Package dependency analysis
- `parse_typescript_errors` - TypeScript error parsing
- `parse_lint_results` - Linter output parsing
- `run_test_suite` - Test execution and parsing
- `run_nextjs_build` - Specialized Next.js build handler

**Deliverables**:
- Tool implementations in `src/aromcp/build_server/tools.py`
- Test suite with mocked command outputs
- README with command whitelist configuration
- Example parsers for common tools (ESLint, Jest, tsc)

### Phase 3: Context Window Management Tools
**Complexity**: Low  
**Dependencies**: None  
**Timeline**: 3-4 days

**Tools to implement**:
- `track_context_usage` - Token counting implementation
- `estimate_token_budget` - Budget calculation
- `suggest_context_checkpoint` - Checkpoint recommendation logic
- `compress_context` - Context summarization

**Deliverables**:
- Tool implementations in `src/aromcp/context_management/tools.py`
- Token counting tests with various content types
- README with context management strategies
- Integration examples with state management

### Phase 4: Code Analysis Tools
**Complexity**: Medium-High  
**Dependencies**: FileSystem Tools (for code reading)  
**Timeline**: 2 weeks

**Priority tools to implement first**:
- `detect_security_patterns` - Security scanning
- `find_import_cycles` - Circular dependency detection
- `find_dead_code` - Dead code identification
- `analyze_component_usage` - Usage tracking
- `extract_api_endpoints` - API discovery

**Additional tools**:
- `detect_code_smells` - Code quality checks
- `analyze_test_coverage` - Coverage analysis
- `find_similar_code` - Duplication detection
- `analyze_bundle_impact` - Bundle size analysis
- `extract_configuration` - Config gathering

**Deliverables**:
- AST parsing framework for multiple languages
- Tool implementations in `src/aromcp/analysis_server/tools.py`
- Language-specific test suites
- README with analysis thresholds and customization
- Performance benchmarks for large codebases

### Phase 5: State Management Tools
**Complexity**: Medium-High  
**Dependencies**: FileSystem Tools (for YAML loading)  
**Timeline**: 2 weeks

**Tools to implement**:
- `list_available_processes` - Process discovery
- `load_process_definition` - YAML process loading
- `initialize_process` - Process instantiation
- `get_process_state` - State retrieval
- `update_step_state` - State updates
- `checkpoint_state` - Manual checkpointing
- `validate_step_completion` - Validation logic
- `get_process_steps` - Step generation with instructions
- `list_active_processes` - Active process tracking
- `pause_process` / `resume_process` - Process control
- `cleanup_process` - Process archival

**Deliverables**:
- YAML schema definition and validation
- Tool implementations in `src/aromcp/state_server/tools.py`
- Example process definitions for common workflows
- State persistence with file backend
- README with process creation guide
- Migration guide for existing TODO lists

### Phase 6: Interactive Debugging Tools
**Complexity**: High  
**Dependencies**: FileSystem Tools, Code Analysis Tools  
**Timeline**: 1-2 weeks

**Tools to implement**:
- `create_debug_snapshot` - Snapshot creation
- `analyze_error_context` - Error analysis
- `suggest_debug_steps` - Strategy generation
- `trace_execution_path` - Execution tracing

**Deliverables**:
- Tool implementations in `src/aromcp/debugging_tools/tools.py`
- Language-specific tracing mechanisms
- Test suite with various error scenarios
- README with debugging workflow examples
- Performance impact documentation

## Testing Strategy

Each phase includes:
1. **Unit tests**: Individual tool functionality
2. **Integration tests**: Tool interactions within category
3. **Security tests**: Input validation, resource limits
4. **Performance tests**: Large file/codebase handling
5. **Error handling tests**: Edge cases and failures

## Documentation Requirements

Each phase must update:
1. **README.md**: Tool descriptions and basic usage
2. **API documentation**: Detailed parameter/response docs
3. **Examples directory**: Real-world usage scenarios
4. **CHANGELOG.md**: Version history and breaking changes

## Migration Path

For teams adopting the tools:
1. Start with Phase 1-3 (core functionality)
2. Integrate with existing Claude Code workflow
3. Gradually adopt process definitions (Phase 5)
4. Add analysis and debugging as needed

## Success Metrics

Each phase is complete when:
- All tools pass comprehensive test suite
- Documentation is complete with examples
- Performance meets benchmarks (<100ms for most operations)
- Security review passes
- Integration with FastMCP server verified