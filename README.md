# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as intelligent utilities for AI-driven development workflows. AroMCP provides both deterministic operations and AI-orchestrated processes, enabling Claude Code to perform complex development tasks efficiently while maintaining token optimization.

## 🚀 Key Features

### ✅ Production Ready
- **[FileSystem Tools](documentation/usage/filesystem_tools.md)** - File I/O, git integration, code parsing, and document loading
- **[Build Tools](documentation/usage/build_tools.md)** - Build, lint, test, and validation commands
- **[Code Analysis Tools](documentation/usage/analysis_tools.md)** - Enhanced standards management with v2 features (70-80% token reduction, session deduplication, context-aware compression)
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

### Comprehensive File Operations
```python
# Efficient file discovery and batch operations
files = aromcp.get_target_files(patterns=["**/*.ts"])
content = aromcp.read_files_batch(file_paths=["src/main.ts", "src/utils.ts"])
# Access files from paginated results: content["data"]["items"]
aromcp.write_files_batch(files={"output.json": json.dumps(analysis)})
```

### Build & Quality Automation
```python
# Integrated build, lint, and test workflows
aromcp.parse_lint_results(target_files=["src/**/*.ts"])
aromcp.parse_typescript_errors()
aromcp.run_test_suite(pattern="**/*.test.ts")
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
## AroMCP Development Tools

### Workflow Patterns
- **File Operations**: Prefer `get_target_files` → `read_files_batch` → `write_files_batch` for batch operations
- **Code Quality**: After changes run `parse_lint_results` and `parse_typescript_errors`
- **Standards**: Load with `hints_for_file` before editing files (70-80% token reduction with session support)
- **ESLint Generation**: Use orchestrated `generate_eslint_rules` for project-specific rules
- **Session Management**: Use consistent `session_id` across requests for optimal deduplication

## Mandatory File Operation Workflow

**CRITICAL**: For ANY file operation (single file or multiple files - create, modify, delete, analyze), you MUST follow this structured workflow. This applies to everything from creating a single "hello world" file to complex multi-file refactoring:

**Phase 1: Discovery & Planning** (MANDATORY for ALL operations - MUST use separate Task agent)
- Launch a dedicated Task agent for discovery that focuses on the specific work at hand
- This task has the following goals:
  - Determine what files need to be created
  - Summarize standards that should be used
  - Determine optimal agent strategy (single vs parallel) for the actual work phase
- Use targeted AroMCP file discovery tools to understand relevant project context (avoid reading all files of a type)
- Always load coding standards FIRST for target files.
- Analyze the scope and complexity of operations needed based on the specific task requirements
- **Example**:
  - I am creating a new file in "api/test/route.ts"
  - Call `hints_for_file` for "api/test/route.ts"
  - Analyze hints, and determine what standards must be followed
  - Look up any other files if unclear on standards
  - Determine whether files should be processed in parallel. Determine file batches to process in each sub agent.

**Phase 2: Structured Operations** (MANDATORY for ALL operations)
- Launch Task agents to handle file operations (use judgment on single vs parallel based on Phase 1 analysis) **launch parallel agents with the task tool for parallel workstrems**
- **SESSION ID REQUIREMENT**: Each agent MUST use a unique `session_id` for all AroMCP tool calls within their scope
  - Format: `{agent-type}-{task-description}-{timestamp}` (e.g., `discovery-api-routes-1734567890`, `worker-user-auth-1734567891`)
  - **CRITICAL**: No two agents can share the same session_id - this prevents cross-agent data corruption
  - Use consistent session_id within each agent's scope for deduplication benefits
- **FIRST ACTION**: Each agent must call `hints_for_file` for all files they will modify OR create (including new files that don't exist yet)
  - Use the agent's unique `session_id` for deduplication (70-80% token savings within agent scope)
  - Previously loaded rules within the same agent session are automatically referenced, not repeated
- Each agent should choose appropriate tools for file operations (AroMCP tools preferred, but agents can use standard tools when more suitable)
- Agents can create new files when necessary (this overrides general "avoid file creation" guidance)
- Agents should use the hints to guide their implementation decisions and follow project patterns
- **Example**:
  - agent analyzes summary from phase 1
  - agent calls `hints_for_file` for API file path
  - agent creates files according to standards
  - agent calls MCP APIs for targeted validation: `parse_lint_results(target_files=[...])` and `parse_typescript_errors()` ONLY for modified files
  - **MANDATORY**: Use MCP APIs, NOT system commands (no npm, no build commands)
  - **MANDATORY**: agent DOES NOT RUN DEV SERVERS, curl COMMANDS, or npm run commands
  - **PHASE 2 COMPLETE**: Mark when all file operations and targeted MCP validations are finished

**Phase 3: Quality Assurance** (MANDATORY for ALL operations - ONLY after ALL work is complete)
- Wait until ALL Task agents from Phase 2 have completed their file operations
- Run comprehensive quality checks using MCP APIs: `parse_lint_results` and `parse_typescript_errors` for all project files
- Identify any linting errors, type errors, or other issues introduced during operations
- Launch additional Task agents to fix specific errors, with each agent focusing on particular files or error types
- **MANDATORY**: Run full build command (npm run build, etc.) to ensure project compiles successfully
- **MANDATORY**: NEVER run dev servers (npm run dev, npm start, etc.)
- **PHASE 3 COMPLETE**: Mark when all errors are fixed and full build succeeds
- **Example**: Even after creating one simple file, validate it integrates properly with the project

**Decision Points for AI:**
- **Batch Size**: Agents decide optimal file grouping based on file size, complexity, and relationships
- **Agent Strategy**: Determine whether to use parallel agents (tasks) or single agent (todowrite) based on task complexity
- **Error Handling**: Choose appropriate strategies for fixing different types of errors
- **File Dependencies**: Consider import relationships and dependencies when organizing work
- **Operation Type**: Adapt strategy based on whether creating, modifying, or deleting files

**Key Principles:**
- **Mandatory Workflow**: ALWAYS follow all 3 phases for ANY file operation, no exceptions
- **Unique Session IDs**: Each agent MUST use a unique `session_id` for AroMCP tools - no sharing between agents
- **Separate Discovery Agent**: Phase 1 must always use a dedicated Task agent for targeted discovery
- **Hints at Work Start**: Every Phase 2 agent must call `hints_for_file` as their first action for all target files
- **Focused Discovery**: Avoid over-broad discovery; focus on specific work requirements
- **Complete Before Validate**: Phase 3 validation only starts after ALL Phase 2 work is complete
- **File Creation Permitted**: This workflow overrides general "avoid file creation" guidance when files are needed
- **Token Efficiency**: Each Task agent works within manageable token limits
- **Sub agents**: parallel work streams are run in sub agents using the task tool. Run multiple Task invocations in a SINGLE message.

**Phase Completion Markers** (MANDATORY - explicitly state when each phase is done):
- **Phase 1**: "Discovery complete, strategy determined"
- **Phase 2**: "All file operations complete, targeted validations finished"  
- **Phase 3**: "Quality assurance complete, full build successful"

**Command Types (CRITICAL distinction)**:
- **MCP APIs** (use these): `parse_lint_results`, `parse_typescript_errors`, `hints_for_file`, `get_target_files`, etc.
- **System Commands** (use sparingly): `npm run build` (only in Phase 3), `uv run pytest` (only for final validation)
- **FORBIDDEN Commands**: `npm run dev`, `npm start`, `yarn dev`, any dev server commands

**Common Examples Requiring This Workflow:**
- ✅ Creating a single new API endpoint file
- ✅ Modifying one configuration file
- ✅ Adding a new utility function file
- ✅ Deleting unused files
- ✅ Complex multi-file refactoring
- ✅ ANY file operation, regardless of size or complexity
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