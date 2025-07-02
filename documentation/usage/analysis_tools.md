# Code Analysis Tools - Usage Guide

The Code Analysis Tools provide deterministic code analysis operations, focusing on custom ESLint rule generation from markdown coding standards and intelligent standard loading based on file context. This phase bridges the gap between human-readable coding standards and automated enforcement.

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
rules = aromcp.parse_standard_to_rules(
    standard_content=content['data']['files']['.aromcp/standards/api-routes.md'],
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

### 1. ESLint Rule Generation from Coding Standards

```python
# Step 1: Load all standards
standards = aromcp.load_coding_standards()

# Step 2: Parse standards to understand their structure
for standard in standards['data']['standards']:
    content = aromcp.read_files_batch([standard['path']])
    rules = aromcp.parse_standard_to_rules(
        standard_content=content['data']['files'][standard['path']],
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

1. **Standards Organization**
   - Keep standards in `.aromcp/standards/` directory
   - Use clear, descriptive filenames
   - Include comprehensive examples in standards
   - Tag standards appropriately for better categorization

2. **Rule Generation**
   - Always validate generated rules before use
   - Test rules against real code examples
   - Keep generated rules in version control
   - Regenerate rules when standards change

3. **Performance**
   - Cache analysis results when possible
   - Use pattern-based file selection to limit scope
   - Run security scans on changed files only
   - Batch operations for better performance

4. **Security Analysis**
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