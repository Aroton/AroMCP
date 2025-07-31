# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as intelligent utilities for AI-driven development workflows. AroMCP provides both deterministic operations and AI-orchestrated processes, enabling Claude Code to perform complex development tasks efficiently while maintaining token optimization.

## 🚀 Key Features

### ✅ Production Ready
- **[FileSystem Tools](documentation/usage/filesystem_tools.md)** - File I/O, git integration, code parsing, and document loading
- **[Build Tools](documentation/usage/build_tools.md)** - Build, lint, test, and validation commands
- **[Code Analysis Tools](documentation/usage/analysis_tools.md)** - Enhanced standards management with v2 features (70-80% token reduction, session deduplication, context-aware compression)
- **[ESLint Rule Generation](documentation/commands/generate-eslint-rules.md)** - AI-orchestrated generation of project-specific ESLint rules from markdown standards
- **🆕 [Simplified Tools](documentation/ai-agent-improvements.md)** - Intuitive aliases with 2-3 parameters for better AI agent adoption

### 🔄 Planned
- **State Management Tools** - Persistent state for long-running processes
- **Context Window Management** - Token usage tracking and optimization
- **Interactive Debugging Tools** - Advanced debugging utilities

## ⚡ Quick Start

### Installation & Setup
```bash
# Clone and install
git clone <repository-url>
cd AroMCP
uv sync --dev

# Create system-wide symlink (recommended)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP

# Verify symlink
ls -la /usr/mcp/AroMCP  # Should point to your AroMCP directory

# Install Claude Code commands (optional)
./install.sh

# Start the server (unified - deprecated)
uv run python main.py
```

### Why Use a Symlink?

Creating a symlink at `/usr/mcp/AroMCP` provides several benefits:

- **🔗 Consistent Path**: All Claude Desktop configurations use the same path regardless of where you clone AroMCP
- **📝 Simplified Config**: No need to update configurations when moving the repository
- **🔄 Easy Updates**: Pull updates to your local directory, symlink automatically points to latest code
- **👥 Team Consistency**: All team members can use identical Claude Desktop configurations

**Alternative without symlink**: If you prefer not to use a symlink, replace `/usr/mcp/AroMCP` with your actual AroMCP directory path in all configurations below.

### 🆕 Individual Servers (Recommended)

AroMCP now supports running individual MCP servers, allowing you to enable only the functionality you need:

```bash
# Run individual servers
uv run python servers/filesystem/main.py   # File operations and code analysis
uv run python servers/build/main.py        # Build, lint, and test tools
uv run python servers/analysis/main.py     # Code quality analysis
uv run python servers/standards/main.py    # ESLint rules and coding guidelines
uv run python servers/workflow/main.py     # Workflow execution and state management

# Or run all servers in background
./scripts/run-all-servers.sh

# Check server health
./scripts/health-check.py

# Stop all servers
./scripts/stop-all-servers.sh
```

**Benefits of Individual Servers:**
- 🎯 **Selective Deployment** - Enable only the servers you need
- 📦 **Minimal Dependencies** - Each server has its own minimal requirements
- 🚀 **Better Performance** - Reduced memory footprint per server
- 🔧 **Independent Development** - Work on servers in isolation

See [Individual Servers Guide](docs/INDIVIDUAL_SERVERS.md) for detailed configuration and Claude Desktop setup.

### Claude Code Commands Installation

AroMCP includes enhanced Claude Code commands for standards management. Install them to your Claude configuration:

```bash
# Run the install script to copy commands to ~/.claude
./install.sh
```

**What gets installed:**
- **Standards Commands** - `standards:create`, `standards:generate`, `standards:update`, `standards:fix`
- **Specialized Agents** - Batch processing agents for parallel workflow execution
- **Templates** - Coding standards templates and patterns
- **Safe Installation** - Automatically backs up existing configurations

**Available Commands:**
```bash
# Create new coding standards interactively
claude standards:create

# Generate AI hints and ESLint rules from standards
claude standards:generate

# Update existing standards with new content
claude standards:update

# Apply standards to changed files with parallel processing
claude standards:fix
claude standards:fix branch main  # Fix changes against specific branch
claude standards:fix --resume     # Resume interrupted workflow
```

The install script:
- ✅ **Safe installation** - Backs up existing `~/.claude` contents with timestamps
- ✅ **Smart detection** - Automatically finds standards directory via `.aromcp/.standards-dir`
- ✅ **No overrides** - Commands work with current directory as project root
- ✅ **User confirmation** - Asks before overwriting existing files

### Development Commands
```bash
# Testing and quality checks
uv run pytest                              # Run tests
uv run black src/ tests/                   # Format code
uv run ruff check src/ tests/              # Lint
uv run ruff check --fix src/ tests/        # Auto-fix linting
```

### Project Dependencies for ESLint Integration

When using AroMCP's `parse_lint_results` tool with standards ESLint rules in your target projects, ensure the following dependencies are installed:

#### Required Dependencies
```bash
# Install ESLint v9+ and TypeScript parser
npm install --save-dev eslint @typescript-eslint/parser

# Or with yarn
yarn add --dev eslint @typescript-eslint/parser
```

#### Next.js Projects
For Next.js projects, ESLint is typically pre-configured. Ensure you have:
```bash
# Usually included in Next.js by default
npm install --save-dev eslint eslint-config-next @typescript-eslint/parser
```

#### Dependencies Explained
- **`eslint`** (v9.0.0+) - Required for linting with flat config format
- **`@typescript-eslint/parser`** - Required for parsing TypeScript files in AroMCP standards rules
- **`eslint-config-next`** - Next.js ESLint configuration (Next.js projects only)

#### ESLint Configuration
AroMCP generates ESLint v9 flat config files at `.aromcp/eslint/standards-config.js` that:
- Use `@typescript-eslint/parser` for TypeScript support
- Include ignore patterns for common directories (`.aromcp/`, `node_modules/`, `dist/`, `build/`, `.next/`)
- Apply only to JavaScript/TypeScript files (`**/*.{js,jsx,ts,tsx}`)
- Run independently of existing project ESLint configuration

#### Usage Notes
- **Next.js projects**: AroMCP runs both `npm run lint` (Next.js config) and standards ESLint separately
- **Other projects**: AroMCP can run either standards ESLint or regular ESLint
- **No conflicts**: Standards ESLint uses `--no-config-lookup` to avoid conflicts with existing `.eslintrc.*` files

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

### Simplified Tools (Recommended for AI Agents)
```python
# Simple, intuitive operations with 2-3 parameters
files = aromcp.list_files(patterns=["**/*.ts"])
content = aromcp.read_files(file_paths=["src/main.ts", "src/utils.ts"])
aromcp.write_files(files={"output.json": json.dumps(analysis)})

# Quality checks made simple
aromcp.lint_project(linter="eslint")
aromcp.check_typescript()
aromcp.run_tests()

# Individual quality checks
aromcp.lint_project()
aromcp.check_typescript()
aromcp.run_tests()
```

### Advanced File Operations (Power Users)
```python
# Full-featured operations with advanced options
files = aromcp.get_target_files(patterns=["**/*.ts"], page=1, max_tokens=20000)
content = aromcp.read_files_batch(file_paths=["src/main.ts"], encoding="auto", expand_patterns=True)
aromcp.write_files_batch(files={"output.json": json.dumps(analysis)}, create_backup=True)
```

### Advanced Build & Quality Automation
```python
# Advanced workflows with full configuration
aromcp.parse_lint_results(target_files=["src/**/*.ts"], use_standards_eslint=True)
aromcp.parse_typescript_errors(include_warnings=True, use_build_command=False)
aromcp.run_test_suite(pattern="**/*.test.ts", coverage=True)
```

### Standards-Driven Development
```python
# Context-aware coding standards with smart compression and session management
standards = aromcp.hints_for_file(
    "src/api/routes/user.ts",
    session_id="dev-session-123"  # Enable cross-file deduplication
)
# Standards are compressed based on context (70-80% token reduction)
# Previously loaded rules are referenced, not repeated

# Session statistics and context analysis
stats = aromcp.get_session_stats(session_id="dev-session-123")
context = aromcp.analyze_context(file_path="src/api/routes/user.ts")

# Code quality analysis
aromcp.extract_api_endpoints(route_patterns=["src/**/*.ts"])
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
## Development Workflow with AroMCP

### The Core Principle
**The ONE mandatory requirement**: Always call `hints_for_file()` before editing any file to get project standards.

### Essential Tools
1. **`hints_for_file(filepath, session_id?)`** - Get project standards and coding rules (MANDATORY before edits)
2. **`lint_project(use_standards=True)`** - Check code style using generated rules (ALWAYS use generated rules)
3. **`check_typescript()`** - Validate TypeScript compilation
4. **`standards:fix`** - Automated parallel standards application with architectural intelligence

### Required Workflow Order
```python
# 1. Get standards before editing
hints = hints_for_file("src/api/user.ts", session_id="fix-user-api-123")

# 2. Make your edits following the standards...

# 3. Run linter with generated rules (REQUIRED)
lint_results = lint_project(use_standards=True)

# 4. Check TypeScript errors (REQUIRED)
ts_errors = check_typescript()
```

### Automated Standards Application
```bash
# Apply standards to all changed files with intelligent batching
claude standards:fix

# The command uses architectural analysis to:
# - Group related files (Frontend UI, Backend API, Data Schema, etc.)
# - Process up to 5 files per batch with specialized agents
# - Run 3 parallel agents for optimal performance
# - Apply context-appropriate standards for each architectural layer
```

### Multiple File Operations
```python
# Multiple files - reuse session for efficiency
session = "refactor-auth-1234"
hints_for_file("src/auth/login.ts", session_id=session)
hints_for_file("src/auth/logout.ts", session_id=session)  # 70-80% token savings

# Make changes...

# ALWAYS validate in this order after edits:
lint_project(use_standards=True, target_files=["src/auth/*.ts"])  # Generated rules
check_typescript(files=["src/auth/*.ts"])  # TypeScript validation
```

### Scale to Your Task
- **Quick fix** (1 file): Standards → Edit → Done (validate only if needed)
- **Small feature** (2-5 files): Load all standards first → Edit → Validate changed files
- **Major refactor**: Use `standards:fix` for automated parallel processing with architectural intelligence
- **Large codebases**: `standards:fix` with resume capability handles extensive changes efficiently

### Other Useful Tools
Discover available tools via MCP, but these are commonly helpful:
- **`read_files()`/`write_files()`** - Batch file operations
- **`find_who_imports()`** - Check dependencies before changes
- **`lint_project()`** - Run ESLint with standards
- **`check_typescript()`** - Validate TypeScript compilation  
- **`run_test_suite()`** - Execute tests with detailed results
- **`standards:fix`** - Automated standards application with architectural intelligence and parallel processing

### Best Practices
✅ Always check standards before editing (the one hard rule)
✅ ALWAYS use `use_standards=True` when linting (generated rules are superior)
✅ Follow the required order: Standards → Edit → Lint → TypeScript
✅ Use consistent `session_id` within operations for token efficiency
✅ Focus validation on changed files
✅ Use `standards:fix` for complex refactoring with multiple files
✅ Leverage architectural batching for efficient parallel processing

❌ Don't skip `hints_for_file()` - ever
❌ Don't skip linting after edits - always validate
❌ Don't use `use_standards=False` unless debugging ESLint issues
❌ Don't run dev servers (`npm run dev`, etc.)
❌ Don't validate unchanged files unless debugging

### The Bottom Line
Check standards before editing. For large changes, use `standards:fix` for automated intelligent processing. Everything else adapts to what you're doing. Simple tasks need simple workflows.
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
│   ├── eslint_integration/        # ESLint rule generation support
│   └── standards_server/          # 🆕 V2 enhanced standards
│       ├── models/                # Enhanced rule structures
│       ├── services/              # Session, compression, context detection
│       └── utils/                 # Token optimization, example generation
```

### Key Design Principles
- **Orchestrated Intelligence**: MCP coordinates analysis, AI generates content
- **Architectural Intelligence**: Smart file categorization by purpose and runtime environment
- **Parallel Processing**: Up to 3 concurrent agents with architectural batching (max 5 files per batch)
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