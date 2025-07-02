# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. AroMCP provides "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making while handling token-intensive operations efficiently.

## Features

- **FileSystem Tools** - File I/O operations, git integration, code parsing, and document loading ✅
- **Build Tools** - Build, lint, test, and validation commands ✅
- **Code Analysis Tools** - Standards management, security analysis, and code quality checks ✅
- **State Management Tools** - Persistent state management for long-running processes (planned)
- **Context Window Management Tools** - Token usage tracking and optimization (planned)
- **Interactive Debugging Tools** - Debugging utilities and error investigation (planned)

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd AroMCP

# Install dependencies using uv
uv sync --dev

# Run the server
uv run python main.py
```

### Development Commands

```bash
# Run tests
uv run pytest

# Code formatting
uv run black src/ tests/

# Linting
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check --fix src/ tests/
```

## Integration

### Claude Code Integration

AroMCP integrates seamlessly with Claude Code to provide enhanced filesystem operations, build automation, and code analysis capabilities during AI-driven development sessions.

#### Using AroMCP from Claude Code

1. **Install and start the server**:
```bash
# Clone and install AroMCP
git clone <repository-url>
cd AroMCP
uv sync --dev

# Start the server
uv run python main.py
```

2. **Configure in Claude Code**:
   - Add AroMCP to your MCP servers configuration
   - Set `MCP_FILE_ROOT` environment variable to your project directory
   
3. **Copy this usage guide to your project's CLAUDE.md**:

```markdown
## AroMCP Tools Usage

This project uses AroMCP for enhanced development operations. Key workflows:

### FileSystem Operations
- Use `get_target_files` with patterns like "**/*.ts" for file discovery
- Use `read_files_batch` for efficient multi-file reading (max 5 files per batch for optimal performance)
- Use `write_files_batch` for atomic multi-file writes
- Use diff tools (`apply_file_diffs`, `preview_file_changes`) for safe code changes

### Build & Validation
- After code changes, run: `run_eslint(file_paths=["modified/file.ts"])`
- For TypeScript: `parse_typescript_errors(run_tsc_first=true)`
- For tests: `run_test_suite(test_pattern="*.test.ts")`

### Code Analysis (Standards-Driven Development)
1. Before editing: `get_relevant_standards("path/to/file.ts")` to load coding standards
2. After changes: `run_eslint` to validate against standards
3. Security check: `detect_security_patterns(file_paths=["path/to/file.ts"])`
4. Find issues: `find_dead_code()`, `find_import_cycles()`
5. ESLint rule generation: Use Claude Code command (see documentation/commands/generate-eslint-rules.md)

### Standards Setup
- Place coding standards in `.aromcp/standards/` as markdown with YAML frontmatter
- Standards auto-match to files using glob patterns
- For ESLint rule generation from standards, use the AI-driven Claude Code command approach
- **IMPORTANT**: Always include `.aromcp/non-eslint-standards.md` in your project's CLAUDE.md file

### CLAUDE.md Integration (Required)
Your project's CLAUDE.md must always load the non-ESLint standards file:
```markdown
## Project Coding Standards
Load the non-ESLint coding standards that require human judgment:
@.aromcp/non-eslint-standards.md

These standards cover architecture, documentation, process, and business logic
requirements that cannot be automatically enforced via ESLint.
```
```

**[Complete Claude Code Integration Guide →](documentation/claude_code.md)**

## Documentation

### Integration Guides
- [Claude Code Integration](documentation/claude_code.md) - Complete setup guide for Claude Code integration

### Usage Guides
- [FileSystem Tools Usage](documentation/usage/filesystem_tools.md) - Comprehensive guide for all filesystem operations
- [Build Tools Usage](documentation/usage/build_tools.md) - Complete guide for build, lint, test, and validation tools
- [Code Analysis Tools Usage](documentation/usage/analysis_tools.md) - Guide for standards-driven development and code analysis

### Technical Documentation
- [Simplify Workflow](documentation/simplify-workflow.md) - Detailed technical design and architecture

## FileSystem Tools Usage (Moved)

**This section has been moved to [documentation/usage/filesystem_tools.md](documentation/usage/filesystem_tools.md) for better organization.**

## Project Structure

```
src/aromcp/
├── main_server.py                     # Unified FastMCP server
├── filesystem_server/
│   ├── tools.py                       # FastMCP tool registration
│   └── tools/                         # Individual tool implementations
│       ├── get_target_files.py
│       ├── read_files_batch.py
│       ├── write_files_batch.py
│       ├── extract_method_signatures.py
│       ├── find_imports_for_files.py
│       └── load_documents_by_pattern.py
├── build_server/                      # Build, lint, test, and validation tools
│   ├── tools.py                       # FastMCP tool registration  
│   └── tools/                         # Individual tool implementations
│       ├── run_command.py
│       ├── get_build_config.py
│       ├── check_dependencies.py
│       ├── parse_typescript_errors.py
│       ├── parse_lint_results.py
│       ├── run_test_suite.py
│       └── run_nextjs_build.py
├── state_server/                      # Planned: State management tools
├── analysis_server/                   # Code analysis and standards tools
│   ├── tools/                         # Individual tool implementations
│   │   ├── __init__.py               # FastMCP tool registration
│   │   ├── load_coding_standards.py
│   │   ├── get_relevant_standards.py
│   │   ├── parse_standard_to_rules.py
│   │   ├── detect_security_patterns.py
│   │   ├── find_dead_code.py
│   │   ├── find_import_cycles.py
│   │   ├── analyze_component_usage.py
│   │   └── extract_api_endpoints.py
│   ├── standards_management/         # Standards parsing and matching
│   └── analyzers/                    # Analysis utilities
```

## Contributing

1. Follow the existing code structure with separate implementation files
2. All tools must include comprehensive input validation and security checks
3. Use structured error responses with appropriate error codes
4. Write comprehensive tests for all functionality
5. Update documentation for any new tools or features

## License

[License information]
