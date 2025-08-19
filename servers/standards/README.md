# AroMCP Standards Server

Intelligent coding standards management with automated ESLint rule generation and AI-driven hints.

## Overview

The Standards server provides comprehensive coding standards management with powerful CLI commands:
- **Interactive standard creation and updates** via `/standards:create` and `/standards:update` commands
- **Automated ESLint rule generation** via `/standards:generate` command
- **Context-aware coding hints** with 70-80% token reduction through intelligent compression
- **Project-specific rule management** stored in `.aromcp` directory
- **Session-based optimization** to prevent duplicate rule loading
- **Multi-project standard support** with customizable standards directories

## Installation

### MCP Server Installation

Dependencies are automatically installed when using the run script:

```bash
./scripts/run-server.sh standards
```

### Manual Installation (if needed)

```bash
cd servers/standards
uv sync
```

### Claude Commands Installation

The standards commands (`/standards:create`, `/standards:update`, `/standards:generate`) are distributed separately and must be installed to your Claude directory.

**Quick Install:**
```bash
# From the AroMCP project root
./install.sh
```

This installs all commands from `shared-claude/` to `~/.claude/`:
- **Commands**: `standards:create.md`, `standards:update.md`, `standards:generate.md`
- **Templates**: `code-standards-template.md`
- **Agents**: `standards-fix-batch-processor.md`
```

## Running the Server

### Recommended (with automatic dependency management):
```bash
# From AroMCP project root
./scripts/run-server.sh standards

# Background mode
./scripts/run-server.sh standards --background

# Using alias
./scripts/run-server.sh std
```

### Manual (requires separate dependency installation):
```bash
cd servers/standards
uv sync  # Install dependencies first
uv run python main.py
```

## Standards Commands

The Standards server integrates with Claude Desktop via three powerful commands that work together to create, maintain, and deploy coding standards with automated ESLint rule generation.

### Quick Start Workflow

1. **Create a standard**: `/standards:create api-validation`
2. **Generate ESLint rules**: `/standards:generate`
3. **Maintain standards**: `/standards:update api-validation`

### Command Overview

| Command | Purpose | Usage |
|---------|---------|-------|
| `/standards:create` | Interactive standard creation | `claude standards:create [standard-id]` |
| `/standards:update` | Update existing standards | `claude standards:update [standard-id]` |
| `/standards:generate` | Generate ESLint rules and AI hints | `claude standards:generate` |

### 📁 Standards Directory Configuration

Standards are stored in a configurable directory. Set your preferred location:

```bash
# Create configuration file to use custom directory
echo "documentation/coding-standards" > .aromcp/.standards-dir

# Or use default "standards" directory (no configuration needed)
```

### 🎯 Model Recommendation

**Use Claude Sonnet** for all standards commands - it follows directions better than Opus for structured workflows.

---

## Command Details

### `/standards:create` - Interactive Standard Creation

Creates new coding standards using a guided interview process.

**Usage:**
```bash
# Create new standard with guided prompts
claude standards:create

# Create with initial ID
claude standards:create api-validation

# Create with specific context
claude standards:create component-patterns
```

**Process:**
1. **Requirements Analysis** - Understanding the problem being solved
2. **Metadata Collection** - ID, category, tags, severity, file patterns
3. **Critical Rules Definition** - 3-5 must-follow rules with clear rationale
4. **Example Creation** - Complete working examples at 4 complexity levels
5. **Mistake Documentation** - Common pitfalls and correct approaches
6. **AI Hint Configuration** - Context triggers and optimization settings
7. **File Generation** - Creates structured markdown in your standards directory

**Generated File Structure:**
```
{standards-dir}/
├── api-validation.md          # Complete standard with metadata
├── component-patterns.md      # Another standard
└── ...
```

**Key Features:**
- Uses template from `shared-claude/templates/code-standards-template.md`
- Generates AI-optimized metadata for smart hint loading
- Creates examples in multiple complexity levels (minimal/standard/detailed/full)
- Includes ESLint automation potential analysis
- Validates all required sections are complete

### `/standards:update` - Standard Maintenance

Updates existing standards with template compliance and content refresh.

**Usage:**
```bash
# Update specific standard
claude standards:update api-validation

# Update with section focus
claude standards:update api-validation --section=examples

# Update all outdated standards
claude standards:update --all --check-template
```

**Update Process:**
1. **Analysis** - Compare current standard against template
2. **Gap Identification** - Missing sections, outdated examples, incomplete metadata
3. **Selective Updates** - Focus on specific areas needing improvement
4. **Template Compliance** - Ensure all required sections present
5. **Version Management** - Update timestamps and changelog
6. **Validation** - Verify examples work and structure is correct

**Update Types:**
- **Comprehensive** - Full review and modernization
- **Targeted** - Specific section improvements
- **Quick Fix** - Add missing required sections
- **Metadata Only** - Update frontmatter and timestamps
- **AI Hints Refresh** - Optimize for better hint generation

### `/standards:generate` - ESLint Rules & AI Hints Generation

Processes markdown standards into deployable ESLint rules and optimized AI hints.

**Usage:**
```bash
# Generate from all standards
claude standards:generate

# Generate with session testing
claude standards:generate --session-id=test-session-123
```

**Generation Process:**
1. **Standards Discovery** - Find all markdown files needing processing
2. **AI Parsing** - Extract metadata, rules, and examples using AI agents
3. **Registration** - Register standards with the MCP server
4. **Hint Generation** - Create compressed AI hints with context awareness
5. **ESLint Rule Creation** - Generate JavaScript rules for automated enforcement
6. **Validation** - Test all generated rules work correctly
7. **Deployment** - Install rules to `.aromcp/eslint/` for project use

**Key Features:**
- **70-80% Token Reduction** through intelligent compression
- **Context-Aware Loading** based on file patterns and task types
- **Session Deduplication** prevents loading duplicate rules
- **ESLint Validation** with debug mode to catch syntax errors
- **File Pattern Filtering** ensures rules only apply to relevant files
- **Progressive Detail Levels** (minimal/standard/detailed/full examples)

**Generated Artifacts:**
```
.aromcp/
├── standards/                 # Standards registry
│   └── {standard-id}.json     # Metadata and configuration
├── hints/                     # AI hints for context-aware loading
│   └── {standard-id}/
│       ├── hint-001.json      # Individual compressed hints
│       └── hint-002.json
├── eslint/                    # Generated ESLint rules
│   ├── rules/
│   │   ├── api-validation-check-input.js
│   │   └── api-validation-async-handler.js
│   └── standards-config.js    # ESLint configuration
└── .standards-dir             # Optional: custom standards directory path
```

---

## Integration Workflow

### Initial Setup

1. **Configure Standards Directory** (optional):
   ```bash
   echo "documentation/coding-standards" > .aromcp/.standards-dir
   ```

2. **Create Your First Standard**:
   ```bash
   claude standards:create api-patterns
   ```

3. **Generate ESLint Rules**:
   ```bash
   claude standards:generate
   ```

4. **Use in Development**:
   - Standards automatically register with MCP server
   - ESLint rules apply during development
   - AI hints load contextually via `hints_for_file` tool

### Maintenance Workflow

```bash
# Regular maintenance cycle
claude standards:update api-patterns     # Update outdated standards
claude standards:generate                # Regenerate rules and hints
```

### Team Collaboration

1. **Share Standards** - Commit `.md` files in your standards directory
2. **Deploy Rules** - Each developer runs `claude standards:generate`
3. **Local Configuration** - `.aromcp/` directory is typically `.gitignore`'d
4. **Consistent Enforcement** - ESLint rules ensure team consistency

---

## Tools Available (10 Tools)

### Core Standards Management
- `hints_for_file` - Get context-aware coding hints with session management and 70-80% token reduction
- `register` - Register new coding standards with enhanced metadata
- `check_updates` - Check for updated or new standard files
- `delete` - Remove all rules and hints for a standard

### Rule & Hint Management
- `add_rule` - Add ESLint rules with context awareness
- `list_rules` - List ESLint rules for a standard
- `add_hint` - Add coding hints and best practices

### Session & Analytics
- `get_session_stats` - Get statistics for AI coding sessions
- `clear_session` - Clear session data for memory management
- `analyze_context` - Analyze context for specific files and sessions

## Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

### macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Windows
`%APPDATA%\Claude\claude_desktop_config.json`

### Linux
`~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aromcp-standards": {
      "type": "stdio",
      "command": "/usr/mcp/AroMCP/scripts/run-server.sh",
      "args": [
        "standards"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project",
        "AROMCP_STANDARDS_PATH": "/path/to/standards/storage"
      }
    }
  }
}
```

Replace `/path/to/your/project` with your project root.

## Key Configuration Changes

1. **Uses run-server.sh script**: Provides automatic dependency management and consistent startup
2. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
3. **Simple server specification**: Just specify `standards` as the server name
4. **Automatic dependency installation**: Script handles `uv sync` before starting server

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for file analysis (required)
- `AROMCP_STANDARDS_PATH` - Path to store standards data (optional)
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Features

### Context-Aware Rules
- Suggests relevant ESLint rules based on file content
- Groups related rules automatically
- Adapts to project patterns and conventions

### Intelligent Hints
- Provides file-specific coding guidance
- Learns from project patterns
- Filters hints by relevance threshold

### Efficient Storage
- Compresses rules to save tokens
- Session-based caching
- Persistent storage across sessions

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Register React coding standards for this project"
- "Add ESLint rule for consistent arrow functions"
- "What coding hints apply to this component?"
- "Update the no-console rule to allow warnings"

## Standard Templates

The server includes templates for common standards:
- React/Next.js best practices
- Node.js/Express conventions
- Python/Django guidelines
- TypeScript strict mode rules

## Session Management

- Sessions persist rule context during work
- Automatic session cleanup
- Multi-project session support

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom project root
MCP_FILE_ROOT=/my/project uv run python main.py

# With custom standards storage
AROMCP_STANDARDS_PATH=/my/standards uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Use Cases

1. **Project Onboarding**: Register project-specific standards
2. **Code Reviews**: Get automated hints for improvements
3. **Team Consistency**: Share coding standards across team
4. **Rule Evolution**: Update rules as patterns emerge

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework
- `pyyaml>=6.0.0` - YAML configuration support