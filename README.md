# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as intelligent utilities for AI-driven development workflows. AroMCP provides deterministic operations and AI-orchestrated processes, enabling Claude Code to perform complex development tasks efficiently while maintaining token optimization.

## 🚀 Production Ready Servers

AroMCP consists of **5 fully functional MCP servers**, each providing specialized development tools:

### **1. [Filesystem Server](servers/filesystem/README.md)** - File Operations
- **Tools**: `list_files`, `read_files`, `write_files` (3 tools)
- **Purpose**: File I/O operations with advanced glob patterns and pagination
- **Features**: Multi-file operations, automatic directory creation, cursor pagination

### **2. [Build Server](servers/build/README.md)** - Development Automation  
- **Tools**: `check_typescript`, `lint_project`, `run_test_suite` (3 tools)
- **Purpose**: Build automation, linting, and testing
- **Features**: ESLint integration, TypeScript error checking, test execution with pagination

### **3. [Analysis Server](servers/analysis/README.md)** - TypeScript Analysis
- **Tools**: `find_references`, `get_function_details`, `analyze_call_graph` (3 tools)
- **Purpose**: Advanced TypeScript code analysis and symbol resolution
- **Features**: Symbol references, function details, static call graph analysis

### **4. [Standards Server](servers/standards/README.md)** - Coding Guidelines
- **Tools**: 10 tools including `hints_for_file`, `register`, `add_rule`, `get_session_stats`
- **Purpose**: Intelligent coding standards management with 70-80% token reduction
- **Features**: Context-aware hints, session management, ESLint rule integration

### **5. [Workflow Server](servers/workflow/README.md)** - State Management ⚠️ **IN DEVELOPMENT**
- **Status**: 🚧 **NOT YET FUNCTIONAL** - Under active development
- **Tools**: 14 tools planned for workflow execution and state management
- **Purpose**: Persistent state for long-running development processes (when complete)
- **Features**: Workflow orchestration, state persistence, checkpoint/resume capabilities (planned)

**Total**: **19 production-ready tools** across 4 functional servers + 1 development server

## ⚡ Quick Start

```bash
# 1. Clone and install
git clone <repository-url>
cd AroMCP
uv sync --dev

# 2. Create system-wide symlink (recommended)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP

# 3. Configure Claude Desktop with desired servers
# See documentation/INSTALLATION.md for complete setup guide
```

**📋 [Complete Installation Guide](documentation/INSTALLATION.md)** - Detailed setup for all deployment options

### 🚀 Individual Server Architecture

AroMCP uses an individual server architecture where each server provides specialized functionality:

```bash
# Run individual servers
uv run python servers/filesystem/main.py   # File operations (3 tools)
uv run python servers/build/main.py        # Build automation (3 tools)  
uv run python servers/analysis/main.py     # TypeScript analysis (3 tools)
uv run python servers/standards/main.py    # Coding standards (10 tools)
# uv run python servers/workflow/main.py   # ⚠️ IN DEVELOPMENT - NOT FUNCTIONAL YET

# Management scripts
./scripts/run-all-servers.sh     # Start all servers in background
./scripts/health-check.py        # Check server health
./scripts/stop-all-servers.sh    # Stop all servers
```

**Architecture Benefits:**
- 🎯 **Selective Deployment** - Enable only the servers you need
- 📦 **Minimal Dependencies** - Each server has minimal, focused requirements
- 🚀 **Better Performance** - Reduced memory footprint per server
- 🔧 **Independent Scaling** - Scale servers based on usage patterns

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

# TypeScript code analysis
aromcp.find_references(symbol_name="calculateTotal", file_path="src/utils.ts")
aromcp.get_function_details(function_name="processPayment", file_path="src/payment.ts")
aromcp.analyze_call_graph(entry_points=["src/main.ts"], max_depth=3)
```

## 🔗 Claude Code Integration

AroMCP integrates seamlessly with Claude Code for enhanced AI-driven development.

### Quick Setup
1. **Install AroMCP** (see Quick Start above)
2. **Configure Claude Code** - Add AroMCP to your MCP servers
3. **Set Environment** - `export MCP_FILE_ROOT=/path/to/your/project`
4. **Copy Integration Template** - Copy the contents of [`CLAUDE-MD-HINT.md`](documentation/CLAUDE-MD-HINT.md) into your project's `CLAUDE.md` file

### Integration Template
📋 **[CLAUDE-MD-HINT.md](documentation/CLAUDE-MD-HINT.md)** - Complete template with usage patterns and best practices

**To integrate AroMCP with your project:**
1. Copy the markdown content from `documentation/CLAUDE-MD-HINT.md`
2. Paste it into your project's `CLAUDE.md` file
3. Customize the patterns for your specific project needs

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