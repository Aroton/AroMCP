# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as intelligent utilities for AI-driven development workflows. AroMCP provides both deterministic operations and AI-orchestrated processes, enabling Claude Code to perform complex development tasks efficiently while maintaining token optimization.

## 🚀 Key Features

### ✅ Production Ready
- **[FileSystem Tools](documentation/usage/filesystem_tools.md)** - File I/O, git integration, code parsing, and document loading
- **[Build Tools](documentation/usage/build_tools.md)** - Build, lint, test, and validation commands
- **[Code Analysis Tools](documentation/usage/analysis_tools.md)** - Standards management, security analysis, and code quality checks
- **[ESLint Rule Generation](documentation/commands/generate-eslint-rules.md)** - AI-orchestrated generation of project-specific ESLint rules from markdown standards

### 🔄 Planned
- **State Management Tools** - Persistent state for long-running processes
- **Context Window Management** - Token usage tracking and optimization
- **Interactive Debugging Tools** - Advanced debugging utilities

## ⚡ Quick Start

### Installation
```bash
# Clone and install
git clone <repository-url>
cd AroMCP
uv sync --dev

# Start the server
uv run python main.py
```

### Development Commands
```bash
# Testing and quality checks
uv run pytest                              # Run tests
uv run black src/ tests/                   # Format code
uv run ruff check src/ tests/              # Lint
uv run ruff check --fix src/ tests/        # Auto-fix linting
```

## 🔧 Core Capabilities

### Orchestrated ESLint Rule Generation
Generate project-specific ESLint rules from markdown coding standards:

```python
# MCP orchestrator analyzes project and creates action plan
action_plan = aromcp.generate_eslint_rules(
    target_project_root="/path/to/project",
    standards_dir=".aromcp/standards"
)

# Claude Code follows the structured plan to generate rules
# Result: Complete ESLint ruleset + AI context tailored to your project
```

### Comprehensive File Operations
```python
# Efficient file discovery and batch operations
files = aromcp.get_target_files(patterns=["**/*.ts"])
content = aromcp.read_files_batch(file_paths=["src/main.ts", "src/utils.ts"])
aromcp.write_files_batch(files={"output.json": json.dumps(analysis)})
```

### Build & Quality Automation
```python
# Integrated build, lint, and test workflows
aromcp.run_eslint(file_paths=["src/**/*.ts"])
aromcp.parse_typescript_errors(run_tsc_first=True)
aromcp.run_test_suite(test_pattern="**/*.test.ts")
```

### Standards-Driven Development
```python
# Context-aware coding standards
standards = aromcp.get_relevant_standards("src/api/routes/user.ts")
aromcp.detect_security_patterns(file_paths=["src/**/*.ts"])
aromcp.find_dead_code()
```

## 🔗 Claude Code Integration

AroMCP integrates seamlessly with Claude Code for enhanced AI-driven development.

### Setup Steps
1. **Install AroMCP** (see Quick Start above)
2. **Configure Claude Code** - Add AroMCP to your MCP servers
3. **Set Environment** - `export MCP_FILE_ROOT=/path/to/your/project`
4. **Add to CLAUDE.md** - Include AroMCP usage patterns in your project

### Essential CLAUDE.md Integration
```markdown
## AroMCP Development Tools

### Workflow Patterns
- **File Operations**: Use `get_target_files` → `read_files_batch` → `write_files_batch`
- **Code Quality**: After changes run `run_eslint` and `parse_typescript_errors`
- **Standards**: Load with `get_relevant_standards` before editing files
- **ESLint Generation**: Use orchestrated `generate_eslint_rules` for project-specific rules
```

**[Complete Integration Guide →](documentation/claude_code.md)**

## 📚 Documentation

### Integration & Setup
- **[Claude Code Integration](documentation/claude_code.md)** - Complete setup and configuration guide

### Tool Usage Guides
- **[FileSystem Tools](documentation/usage/filesystem_tools.md)** - File operations, git integration, document loading
- **[Build Tools](documentation/usage/build_tools.md)** - Build automation, linting, testing
- **[Code Analysis Tools](documentation/usage/analysis_tools.md)** - Standards management, security analysis

### Advanced Features
- **[ESLint Rule Generation](documentation/commands/generate-eslint-rules.md)** - AI-orchestrated rule generation from standards
- **[Technical Architecture](documentation/simplify-workflow.md)** - Detailed design and implementation

### Implementation Guides
- **[Code Analysis V2](documentation/implementation/code-analysis-tool-v2.md)** - Orchestrated rule generation architecture

## 🏗️ Architecture

### Unified Server Design
```
src/aromcp/
├── main_server.py                 # Unified FastMCP server
├── filesystem_server/
│   └── tools/                     # File operations, git, parsing
├── build_server/
│   └── tools/                     # Build, lint, test automation
├── analysis_server/
│   ├── tools/                     # Standards, security, quality analysis
│   │   ├── generate_eslint_rules.py    # 🆕 Orchestrator tool
│   │   ├── analyze_project_structure.py # 🆕 Project analysis
│   │   └── write_eslint_rule_file.py    # 🆕 Action execution
│   ├── standards_management/      # Standards parsing and matching
│   └── eslint_integration/        # ESLint rule generation support
```

### Key Design Principles
- **Orchestrated Intelligence**: MCP coordinates analysis, AI generates content
- **Atomic Operations**: Each action is independent and recoverable
- **Project-Agnostic**: Dynamic analysis works with any project structure
- **Token Efficient**: Batch operations minimize context usage
- **Security First**: Path validation and input sanitization throughout

## 🛠️ Development

### Contributing Guidelines
1. **Modular Architecture** - Each tool has its own implementation file
2. **Comprehensive Validation** - Input validation and security checks required
3. **Structured Errors** - Use consistent error response format with codes
4. **Test Coverage** - Write tests for all functionality
5. **Documentation** - Update relevant usage guides for new features

### Standards Compliance
- **Type Safety**: Full type annotations with modern Python syntax
- **Error Handling**: Structured error responses with appropriate codes
- **Security**: Path traversal protection and input validation
- **Performance**: Batch operations and efficient file handling

## 📄 License

[License information]