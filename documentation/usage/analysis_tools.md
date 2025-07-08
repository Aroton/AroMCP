# Code Analysis Tools - Usage Guide

The Code Analysis Tools provide deterministic code analysis operations, focusing on custom ESLint rule generation from markdown coding standards and intelligent standard loading based on file context. This phase bridges the gap between human-readable coding standards and automated enforcement.

## 🆕 Standards Server V2 Features

The standards server has been completely overhauled with v2 features that provide **70-80% token reduction** through intelligent compression and session management:

### Key Enhancements

1. **Session-Based Deduplication**
   - Track loaded rules across multiple tool calls
   - Prevent duplicate rule loading within a session
   - Reference previously loaded rules instead of repeating

2. **Context-Aware Compression**
   - Automatically detect what the AI is working on
   - Compress rules based on task type and complexity
   - Show minimal examples for familiar patterns

3. **Smart Rule Grouping**
   - Group similar rules by pattern type
   - Share common examples across grouped rules
   - Optimize token usage for rule sets

4. **Progressive Detail Levels**
   - Minimal (~20 tokens): Pattern reminders
   - Standard (~100 tokens): Core implementation
   - Detailed (~200 tokens): Full examples
   - Full: Complete rule with all details

## Overview

The Code Analysis Tools include 8 production-ready tools divided into two categories:

1. **Standards Management** - Load and match coding standards to files
2. **Security & Quality Analysis** - Detect security patterns, dead code, and architectural issues

### 🔄 Important Migration Note

The `get_relevant_standards` tool has been **migrated to an ESLint-based approach**:

- **Before**: Read original `.aromcp/standards/*.md` files for pattern matching
- **After**: Read generated `.aromcp/generated-rules/rules/*.js` files for pattern matching
- **Benefits**: Proper separation between generation-time (standards) and runtime (ESLint rules) concerns
- **Required**: Run ESLint rule generation command before using `get_relevant_standards`

This change creates better architectural separation and ensures pattern matching uses the same patterns that ESLint will actually enforce.

## Available Tools

### Standards Management Tools

#### 🆕 hints_for_file (Enhanced with V2 Features)

Get relevant coding hints for a specific file with smart compression and session deduplication.

**Parameters:**
- `file_path` (str): File to get hints for
- `max_tokens` (int): Maximum tokens to return (default: 10000)
- `project_root` (str | None): Project root directory
- `session_id` (str | None): Session ID for deduplication (default: "default")
- `compression_level` (str): Compression level: minimal|standard|detailed|full (default: "auto")
- `enable_grouping` (bool): Enable rule grouping (default: True)

**Example:**
```python
# First call - loads relevant rules
hints = aromcp.hints_for_file(
    file_path="src/api/routes/user.ts",
    session_id="dev-session-123"
)
# Returns compressed rules based on context

# Second call - references already loaded rules
hints = aromcp.hints_for_file(
    file_path="src/api/routes/product.ts", 
    session_id="dev-session-123"
)
# Previously loaded patterns are referenced, not repeated
```

**Returns:**
```json
{
    "data": {
        "file_path": "src/api/routes/user.ts",
        "context": {
            "task_type": "api_development",
            "complexity_level": "intermediate",
            "nextjs_context": {
                "is_api_route": true,
                "router_type": "app"
            }
        },
        "rules": [
            {
                "ruleId": "api-async-handlers",
                "rule": "Use async/await for API handlers",
                "hint": "async (req, res) => { ... }",
                "tokens": 20
            }
        ],
        "references": [
            {
                "ruleId": "error-handling",
                "ref": "Previously loaded: Standard error handling pattern"
            }
        ],
        "session_stats": {
            "rules_loaded": 15,
            "patterns_seen": ["validation", "error-handling", "async"],
            "compression_ratio": 0.25
        },
        "total_tokens": 2500
    }
}
```

#### 🆕 get_session_stats

Get statistics about the current session's loaded rules and patterns.

**Parameters:**
- `session_id` (str): Session ID to get stats for (default: "default")

**Example:**
```python
stats = aromcp.get_session_stats(session_id="dev-session-123")
```

**Returns:**
```json
{
    "data": {
        "session_id": "dev-session-123",
        "rules_loaded": 45,
        "unique_patterns": 12,
        "files_processed": 8,
        "total_tokens_saved": 15000,
        "compression_ratio": 0.22,
        "pattern_frequencies": {
            "validation": 8,
            "error-handling": 6,
            "async": 5
        }
    }
}
```

#### 🆕 clear_session

Clear a session's loaded rules and start fresh.

**Parameters:**
- `session_id` (str): Session ID to clear (default: "default")

**Example:**
```python
result = aromcp.clear_session(session_id="dev-session-123")
```

#### 🆕 analyze_context

Analyze the current working context for a file.

**Parameters:**
- `file_path` (str): File to analyze context for
- `session_id` (str | None): Session ID for context (default: "default")

**Example:**
```python
context = aromcp.analyze_context(
    file_path="src/api/routes/user.ts",
    session_id="dev-session-123"
)
```

**Returns:**
```json
{
    "data": {
        "task_type": "api_development",
        "architectural_layer": "api",
        "technology_stack": ["typescript", "nextjs", "react"],
        "complexity_level": "intermediate",
        "working_area": "backend_api",
        "nextjs_context": {
            "router_type": "app",
            "is_api_route": true,
            "is_server_component": true
        },
        "session_phase": "implementation",
        "pattern_familiarity": {
            "validation": "familiar",
            "error-handling": "expert",
            "async": "intermediate"
        }
    }
}
```

#### load_coding_standards

Load all coding standards from the project with metadata.

**Parameters:**
- `project_root` (str | None): Project root directory (auto-resolves from MCP_FILE_ROOT)
- `standards_dir` (str): Directory containing standards (default: ".aromcp/standards")
- `include_metadata` (bool): Include parsed YAML frontmatter (default: True)

**Example:**
```python
# Load all standards with metadata
standards = aromcp.load_coding_standards()

# Load from custom directory
standards = aromcp.load_coding_standards(
    standards_dir="docs/coding-standards",
    include_metadata=True
)
```

**Returns:**
```json
{
    "data": {
        "standards": [
            {
                "id": "api-routes",
                "path": ".aromcp/standards/api-routes.md",
                "metadata": {
                    "tags": ["api", "routes", "endpoints"],
                    "patterns": ["**/routes/**/*.ts", "**/api/**/*.ts"],
                    "severity": "error"
                },
                "content": "# API Route Standards...",
                "has_examples": true
            }
        ],
        "total": 15,
        "directories_scanned": [".aromcp/standards"]
    }
}
```

#### get_relevant_standards

**🔄 MIGRATED TO ESLINT-BASED APPROACH**

Get ESLint rules relevant to a specific file based on generated rule patterns. This tool has been migrated from reading original `.aromcp/standards/*.md` files to reading generated `.aromcp/generated-rules/rules/*.js` files, creating proper separation between generation-time and runtime concerns.

**Prerequisites:**
- Generated ESLint rules must exist in `.aromcp/generated-rules/rules/`
- Use the ESLint rule generation command (see `documentation/commands/generate-eslint-rules.md`) to create rules from standards

**Parameters:**
- `file_path` (str): File to analyze
- `project_root` (str): Project root directory (required)
- `include_general` (bool): Include rules without specific patterns (deprecated, kept for compatibility)

**Example:**
```python
# Get ESLint rules for a specific file
rules = aromcp.get_relevant_standards(
    file_path="src/api/routes/user.ts",
    project_root="/project/root"
)

# Works the same but now returns ESLint rule information
rules = aromcp.get_relevant_standards(
    file_path="src/components/Button.tsx",
    project_root="/project/root"
)
```

**Returns (NEW FORMAT):**
```json
{
    "data": {
        "file_path": "src/api/routes/user.ts",
        "file_exists": true,
        "file_size": 2048,
        "applicable_rules": [
            {
                "rule_id": "api-async-handlers",
                "rule_file": ".aromcp/generated-rules/rules/api-async-handlers.js",
                "name": "Require async handlers for API routes",
                "patterns": ["**/routes/**/*.ts", "**/api/**/*.ts"],
                "pattern_matched": "**/routes/**/*.ts",
                "specificity": 0.8,
                "severity": "error",
                "tags": ["api", "routes", "async"],
                "eslint_rule_name": "@aromcp/api-async-handlers"
            }
        ],
        "categories": ["api", "routes", "typescript"],
        "total_rules": 1,
        "has_specific_rules": true,
        "highest_specificity": 0.8,
        "rules_by_category": {
            "critical": 1,
            "recommended": 0,
            "optional": 0
        },
        "eslint_config_section": "api-routes",
        "summary": {
            "specific_rules": 1,
            "general_rules": 0,
            "unique_tags": ["api", "routes", "async"],
            "severity_distribution": {
                "error": 1
            }
        },
        "registry_info": {
            "total_rules_available": 5,
            "rules_directory": ".aromcp/generated-rules/rules",
            "last_updated": 1704067200
        }
    }
}
```

**Error Response (when no ESLint rules exist):**
```json
{
    "error": {
        "code": "ESLINT_RULES_NOT_FOUND",
        "message": "Generated ESLint rules not found. Please run the ESLint rule generation command first.",
        "suggestion": "Use the ESLint rule generation command to create rules from your coding standards.",
        "details": {
            "expected_directory": ".aromcp/generated-rules/rules",
            "migration_note": "get_relevant_standards now reads ESLint rules instead of original standards files"
        }
    }
}
```

**Migration Notes:**
- **Runtime**: Now reads `.aromcp/generated-rules/rules/*.js` instead of `.aromcp/standards/*.md`
- **Generation**: Original standards files are only used for ESLint rule generation
- **Workflow**: Run ESLint generation → Use get_relevant_standards → Get applicable rules
- **Benefits**: Better separation of concerns, ESLint-native patterns, rule-based categorization

#### 🆕 register (Enhanced with V2 Features)

Register a coding standard with enhanced metadata for v2 optimization.

**Parameters:**
- `source_path` (str): Path to the standard markdown file
- `metadata` (dict | str): Enhanced metadata with v2 fields
- `project_root` (str | None): Project root directory

**Enhanced Metadata Structure:**
```python
metadata = {
    "id": "api-routes",
    "name": "API Route Standards",
    "category": "backend",
    "tags": ["api", "routes", "async"],
    "applies_to": ["typescript", "javascript"],
    "severity": "error",
    "priority": "high",
    "dependencies": ["error-handling", "validation"],
    
    # V2 Context Triggers
    "context_triggers": {
        "task_types": ["api_development", "route_creation"],
        "architectural_layers": ["api", "routes"],
        "code_patterns": ["express.Router", "app.route"],
        "import_indicators": ["express", "@types/express"],
        "file_patterns": ["**/routes/**/*.ts", "**/api/**/*.ts"],
        "nextjs_features": ["api-routes", "app-router-api"]
    },
    
    # V2 Optimization Hints
    "optimization": {
        "priority": "high",
        "load_frequency": "common",
        "compressible": True,
        "cacheable": True,
        "context_sensitive": True,
        "example_reusability": "high"
    }
}

result = aromcp.register(
    source_path=".aromcp/standards/api-routes.md",
    metadata=metadata
)
```

**Returns:**
```json
{
    "data": {
        "success": true,
        "standard_id": "api-routes",
        "rules_registered": 12,
        "optimization_enabled": {
            "compression": true,
            "grouping": true,
            "context_detection": true
        },
        "v2_features": {
            "progressive_examples": true,
            "token_optimization": true,
            "session_support": true
        }
    }
}
```

#### parse_standard_to_rules

Parse a coding standard to extract enforceable rules.

**Parameters:**
- `standard_content` (str): Markdown content of the standard
- `standard_id` (str): Identifier for the standard
- `extract_examples` (bool): Extract code examples (default: True)

**Example:**
```python
# Load and parse a standard
content = aromcp.read_files_batch([".aromcp/standards/api-routes.md"])
# Extract content from first item in paginated results
file_item = content['data']['items'][0]
rules = aromcp.parse_standard_to_rules(
    standard_content=file_item['content'],
    standard_id="api-routes"
)
```

**Returns:**
```json
{
    "data": {
        "standard_id": "api-routes",
        "rules": [
            {
                "id": "route-async-handlers",
                "name": "Require async handlers for routes",
                "description": "All route handlers must be async functions",
                "type": "structure",
                "examples": {
                    "good": ["async (req, res) => { ... }"],
                    "bad": ["(req, res) => { ... }"]
                },
                "severity": "error",
                "fixable": true
            }
        ],
        "total_rules": 5,
        "parse_warnings": []
    }
}
```

### ESLint Rule Generation with Claude Code

ESLint rule generation now uses Claude Code's AI capabilities for better understanding of your standards.

See [Generate ESLint Rules Command](../commands/generate-eslint-rules.md) for the AI-driven approach.

Basic workflow:
1. Load your standards with `load_coding_standards()`
2. Use Claude Code command to generate rules
3. Integrate generated rules into your ESLint config

### Security & Quality Analysis Tools

#### detect_security_patterns

Detect security vulnerability patterns in code files.

**Parameters:**
- `file_paths` (str | list[str]): Files to analyze
- `project_root` (str | None): Project root directory
- `patterns` (list[str] | None): Custom patterns (uses defaults if None)
- `severity_threshold` (str): Minimum severity (low|medium|high|critical)

**Example:**
```python
# Scan for security vulnerabilities
findings = aromcp.detect_security_patterns(
    file_paths=["src/**/*.ts"],
    severity_threshold="medium"
)

# Scan specific files with custom patterns
findings = aromcp.detect_security_patterns(
    file_paths=["src/api/db.ts", "src/utils/crypto.ts"],
    patterns=["hardcoded_secret", "sql_injection"],
    severity_threshold="high"
)
```

**Returns:**
```json
{
    "data": {
        "findings": [
            {
                "file": "src/api/db.ts",
                "line": 45,
                "column": 12,
                "type": "sql_injection",
                "severity": "high",
                "message": "Potential SQL injection from user input",
                "code_snippet": "query(`SELECT * FROM users WHERE id = ${userId}`)"
            }
        ],
        "summary": {
            "critical": 0,
            "high": 2,
            "medium": 5,
            "low": 12
        },
        "files_scanned": 45
    }
}
```

#### find_dead_code

Find unused code that can potentially be removed.

**Parameters:**
- `project_root` (str | None): Project root directory
- `entry_points` (list[str] | None): Entry point files (auto-detects if None)
- `include_tests` (bool): Include test files in analysis (default: False)
- `confidence_threshold` (float): Minimum confidence score (default: 0.8)

**Example:**
```python
# Find dead code with auto-detected entry points
dead_code = aromcp.find_dead_code()

# Specify entry points and include tests
dead_code = aromcp.find_dead_code(
    entry_points=["src/index.ts", "src/server.ts"],
    include_tests=True,
    confidence_threshold=0.9
)
```

**Returns:**
```json
{
    "data": {
        "dead_code": [
            {
                "type": "unused_export",
                "file": "src/utils/helpers.ts",
                "name": "deprecatedHelper",
                "line": 123,
                "confidence": 0.95
            }
        ],
        "summary": {
            "unused_exports": 15,
            "unused_functions": 8,
            "orphaned_files": 3,
            "potential_savings_kb": 45
        }
    }
}
```

#### find_import_cycles

Detect circular import dependencies in the codebase.

**Parameters:**
- `project_root` (str | None): Project root directory
- `max_depth` (int): Maximum cycle depth to search (default: 10)
- `include_node_modules` (bool): Include node_modules (default: False)

**Example:**
```python
# Find import cycles
cycles = aromcp.find_import_cycles()

# Limit search depth
cycles = aromcp.find_import_cycles(
    max_depth=5,
    include_node_modules=False
)
```

**Returns:**
```json
{
    "data": {
        "cycles": [
            {
                "type": "direct",
                "length": 3,
                "path": [
                    "src/services/auth.ts",
                    "src/services/user.ts",
                    "src/services/permission.ts",
                    "src/services/auth.ts"
                ],
                "suggestion": "Extract shared types to separate module"
            }
        ],
        "total_cycles": 2,
        "max_cycle_length": 3
    }
}
```

#### analyze_component_usage

Analyze component/function usage patterns across the codebase.

**Parameters:**
- `component_paths` (str | list[str]): Component files to analyze
- `project_root` (str | None): Project root directory
- `include_tests` (bool): Include test files (default: False)

**Example:**
```python
# Analyze specific components
usage = aromcp.analyze_component_usage(
    component_paths=["src/components/Button.tsx", "src/components/Modal.tsx"]
)

# Analyze all components
usage = aromcp.analyze_component_usage(
    component_paths="src/components/**/*.tsx",
    include_tests=True
)
```

**Returns:**
```json
{
    "data": {
        "components": [
            {
                "name": "Button",
                "file": "src/components/Button.tsx",
                "usage_count": 45,
                "used_in": [
                    "src/pages/Home.tsx",
                    "src/pages/Dashboard.tsx"
                ],
                "props_usage": {
                    "variant": 40,
                    "onClick": 45,
                    "disabled": 12
                }
            }
        ],
        "total_components": 15,
        "unused_components": 2
    }
}
```

#### extract_api_endpoints

Extract and document API endpoints from route files.

**Parameters:**
- `file_paths` (str | list[str]): Route files to analyze
- `project_root` (str | None): Project root directory
- `include_middleware` (bool): Include middleware info (default: True)

**Example:**
```python
# Extract API endpoints
endpoints = aromcp.extract_api_endpoints(
    file_paths="src/routes/**/*.ts"
)

# Extract from specific files
endpoints = aromcp.extract_api_endpoints(
    file_paths=["src/routes/api.ts", "src/routes/auth.ts"],
    include_middleware=True
)
```

**Returns:**
```json
{
    "data": {
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/users",
                "file": "src/routes/users.ts",
                "line": 25,
                "handler": "getUsers",
                "middleware": ["authenticate", "authorize"],
                "description": "Get all users"
            }
        ],
        "total_endpoints": 32,
        "by_method": {
            "GET": 15,
            "POST": 10,
            "PUT": 5,
            "DELETE": 2
        }
    }
}
```

## Common Workflows

### 1. 🆕 Session-Based Development with V2 Features

```python
# Start a development session
session_id = "feature-dev-123"

# First file - full rules loaded
hints1 = aromcp.hints_for_file(
    "src/api/routes/user.ts",
    session_id=session_id
)
# ~2500 tokens used

# Second file - smart compression kicks in
hints2 = aromcp.hints_for_file(
    "src/api/routes/product.ts",
    session_id=session_id
)
# ~500 tokens used (80% reduction!)

# Check session efficiency
stats = aromcp.get_session_stats(session_id)
print(f"Total tokens saved: {stats['data']['total_tokens_saved']}")
print(f"Compression ratio: {stats['data']['compression_ratio']}")

# Analyze context for smart decisions
context = aromcp.analyze_context(
    "src/components/UserForm.tsx",
    session_id=session_id
)
# Use context to determine approach
```

### 2. ESLint Rule Generation from Coding Standards

```python
# Step 1: Load all standards
standards = aromcp.load_coding_standards()

# Step 2: Parse standards to understand their structure
for standard in standards['data']['standards']:
    content = aromcp.read_files_batch([standard['path']])
    # Extract content from first item in paginated results
    file_item = content['data']['items'][0]
    rules = aromcp.parse_standard_to_rules(
        standard_content=file_item['content'],
        standard_id=standard['id']
    )
    # Review parsed rules for AI generation

# Step 3: Use Claude Code command for intelligent rule generation
# See documentation/commands/generate-eslint-rules.md for details
# The AI will create complex, semantic rules based on your standards
```

### 2. Analyze Code Quality and Security

```python
# Security scan
security = aromcp.detect_security_patterns(
    file_paths="src/**/*.ts",
    severity_threshold="medium"
)

# Find dead code
dead_code = aromcp.find_dead_code(
    confidence_threshold=0.9
)

# Check for circular dependencies
cycles = aromcp.find_import_cycles()

# Analyze component usage
usage = aromcp.analyze_component_usage(
    component_paths="src/components/**/*.tsx"
)
```

### 3. Get Relevant Standards for a File

```python
# Before editing a file, get its coding standards
file_path = "src/api/routes/user.ts"
standards = aromcp.get_relevant_standards(file_path)

# Display applicable rules
for standard in standards['data']['matched_standards']:
    print(f"Standard: {standard['id']} - {standard['match_reason']}")
```

## Standards Format

Coding standards should be markdown files with YAML frontmatter:

```yaml
---
id: api-routes
name: API Route Standards
version: 1.0.0
patterns:
  - "**/routes/**/*.ts"
  - "**/api/**/*.ts"
tags:
  - api
  - routes
  - typescript
severity: error
---

# API Route Standards

## Rules

### Route Handler Structure

All route handlers must be async functions:

```typescript
// ✅ Good
router.get('/users', async (req, res) => {
  const users = await fetchUsers();
  res.json(users);
});

// ❌ Bad
router.get('/users', (req, res) => {
  fetchUsers().then(users => res.json(users));
});
```
```

## Integration with ESLint

After generating rules via Claude Code commands:

```javascript
// .eslintrc.js
module.exports = {
  extends: [
    // your existing extends
    './.aromcp/generated-rules/configs/recommended'
  ],
  plugins: [
    // your existing plugins
    './.aromcp/generated-rules'
  ]
};
```

## Best Practices

1. **🆕 Session Management (V2)**
   - Use consistent `session_id` across related operations
   - Clear sessions when switching to unrelated tasks
   - Monitor compression ratios to ensure efficiency
   - Let sessions auto-expire (1 hour default) for memory management

2. **🆕 Token Optimization (V2)**
   - Start with `hints_for_file` for every new file
   - Use "auto" compression level for intelligent adaptation
   - Enable grouping for similar rules
   - Check session stats to monitor efficiency

3. **Standards Organization**
   - Keep standards in `.aromcp/standards/` directory
   - Use clear, descriptive filenames
   - Include comprehensive examples in standards
   - Tag standards appropriately for better categorization
   - Add metadata for v2 context triggers

4. **Rule Generation**
   - Always validate generated rules before use
   - Test rules against real code examples
   - Keep generated rules in version control
   - Regenerate rules when standards change

5. **Performance**
   - Cache analysis results when possible
   - Use pattern-based file selection to limit scope
   - Run security scans on changed files only
   - Batch operations for better performance
   - V2 caching provides 5-minute TTL for fast lookups

6. **Security Analysis**
   - Start with low severity threshold and adjust
   - Review findings before taking action
   - Customize patterns for your specific needs
   - Regular scans as part of CI/CD pipeline

## Error Handling

All tools return structured error responses:

```json
{
    "error": {
        "code": "INVALID_INPUT",
        "message": "Standards directory not found: .aromcp/standards"
    }
}
```

Common error codes:
- `INVALID_INPUT` - Invalid parameters provided
- `NOT_FOUND` - Resource not found
- `PARSE_ERROR` - Failed to parse content
- `GENERATION_ERROR` - Failed to generate rules
- `VALIDATION_ERROR` - Validation failed

## Environment Variables

- `MCP_FILE_ROOT` - Project root directory (auto-detected if not set)
- `MCP_CACHE_ENABLED` - Enable/disable caching (default: true)
- `MCP_ANALYSIS_TIMEOUT` - Analysis timeout in seconds (default: 300)