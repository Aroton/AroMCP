# Phase 4: Code Analysis Tools - Implementation Plan

## Overview

Phase 4 implements code analysis tools that perform deterministic analysis operations, focusing on custom ESLint rule generation from markdown coding standards and intelligent standard loading based on file context. This phase bridges the gap between human-readable coding standards and automated enforcement.

**Complexity**: Medium-High
**Dependencies**: FileSystem Tools (Phase 1), Build Tools (Phase 2)
**Timeline**: 2 weeks

## Core Features

1. **Standards Management**: Load and organize coding standards with metadata
2. **Context-Aware Loading**: Dynamically load relevant standards/rules based on file patterns
3. **Security & Quality Analysis**: Detect security patterns, dead code, and architectural issues
4. **Standards Parsing**: Extract enforceable rules from human-readable markdown
5. **Metadata Management**: Track and organize standards with pattern matching

**Note**: ESLint rule generation is now handled via Claude Code commands for AI-driven rule creation.

## Detailed Implementation Instructions

### 1. Directory Structure

Following the established MCP server patterns, create the following structure within `src/aromcp/analysis_server/`:

```
analysis_server/
├── tools/
│   ├── __init__.py                    # FastMCP tool registration
│   ├── load_coding_standards.py       # Load all standards with metadata
│   ├── get_relevant_standards.py      # Get standards for specific file
│   ├── parse_standard_to_rules.py     # Extract rules from markdown
│   ├── detect_security_patterns.py    # Security vulnerability scanning
│   ├── find_dead_code.py              # Dead code detection
│   ├── find_import_cycles.py          # Circular dependency detection
│   ├── analyze_component_usage.py     # Component/function usage stats
│   └── extract_api_endpoints.py       # API route documentation
├── standards_management/
│   ├── __init__.py
│   ├── pattern_matcher.py             # File pattern matching logic
│   ├── metadata_parser.py             # YAML frontmatter parsing
│   └── standards_registry.py          # Central standards registry
├── analyzers/
│   ├── __init__.py
│   ├── typescript_analyzer.py         # TypeScript-specific analysis
│   ├── security_patterns.py           # Security pattern definitions
│   └── complexity_metrics.py          # Code complexity calculations
├── _security.py                       # Security validation (follows Phase 1 pattern)
└── utils/
    ├── __init__.py
    ├── ast_cache.py                   # Cache parsed ASTs
    └── rule_cache.py                  # Cache generated rules
```

### 2. Tool Implementation Details

#### 2.1 Standards Management Tools

**Tool: `load_coding_standards`**
```
Parameters:
- project_root: str | None = None (auto-resolves to MCP_FILE_ROOT)
- standards_dir: str = ".aromcp/standards" (relative to project root)
- include_metadata: bool = True

Implementation:
1. Validate project_root using get_project_root() pattern
2. Scan standards_dir for .md files recursively
3. For each markdown file:
   - Parse YAML frontmatter for metadata (tags, patterns, severity)
   - Extract content sections (rules, examples, rationale)
   - Identify code blocks marked as good/bad examples
4. Build standards registry with:
   - File path and name
   - Metadata from frontmatter
   - Parsed content structure
   - Pattern mappings for file matching
5. Cache results for performance

Returns:
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
                "rules": [...],
                "examples": {...}
            }
        ],
        "total": 15
    }
}
```

**Tool: `get_relevant_standards`**
```
Parameters:
- file_path: str (file to analyze)
- project_root: str | None = None
- include_general: bool = True (include general/default standards)

Implementation:
1. Load standards registry (use cache if available)
2. Normalize file_path relative to project_root
3. For each standard in registry:
   - Apply pattern matching using minimatch algorithm
   - Score matches by pattern specificity
4. Include general standards if include_general=True
5. Sort by specificity (most specific first)
6. Return matched standards with reason for match

Returns:
{
    "data": {
        "file_path": "src/api/routes/user.ts",
        "matched_standards": [
            {
                "id": "api-routes",
                "path": ".aromcp/standards/api-routes.md",
                "match_reason": "Pattern '**/routes/**/*.ts' matched",
                "specificity": 0.8
            },
            {
                "id": "general-typescript",
                "path": ".aromcp/standards/general-typescript.md",
                "match_reason": "Default standard",
                "specificity": 0.1
            }
        ],
        "categories": ["api", "routes", "typescript"]
    }
}
```

**Tool: `parse_standard_to_rules`**
```
Parameters:
- standard_content: str (markdown content)
- standard_id: str (identifier for the standard)
- extract_examples: bool = True

Implementation:
1. Parse markdown structure to identify:
   - Rule sections (headers with specific patterns)
   - Code blocks with good/bad examples
   - Rule descriptions and requirements
2. For each identified rule:
   - Extract rule name and description
   - Parse good/bad code examples
   - Identify patterns from examples using AST analysis
   - Determine rule type (naming, structure, pattern)
3. Map to appropriate ESLint rule template
4. Extract metadata (severity, fixable, suggestions)

Returns:
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
                "ast_pattern": {...},
                "severity": "error",
                "fixable": true
            }
        ],
        "total_rules": 5
    }
}
```

#### 2.2 ESLint Rule Generation (AI-Driven)

ESLint rule generation is now handled through Claude Code commands rather than deterministic MCP tools. This provides better rule quality through AI understanding of standards.

See `documentation/commands/generate-eslint-rules.md` for the AI-driven approach.

#### 2.3 Security & Quality Analysis Tools

**Tool: `detect_security_patterns`**
```
Parameters:
- file_paths: str | list[str]
- project_root: str | None = None
- patterns: list[str] | None = None (use defaults if None)
- severity_threshold: str = "low" (low|medium|high|critical)

Implementation:
1. Load security pattern definitions
2. For each file:
   - Parse to AST (cache results)
   - Scan for:
     - Hardcoded credentials (API keys, passwords)
     - SQL injection vulnerabilities
     - Command injection risks
     - Path traversal attempts
     - Unsafe crypto usage
   - Apply pattern matching with context
3. Categorize findings by severity
4. Filter by severity_threshold

Returns:
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
        }
    }
}
```

**Tool: `find_dead_code`**
```
Parameters:
- project_root: str | None = None
- entry_points: list[str] | None = None (auto-detect if None)
- include_tests: bool = False
- confidence_threshold: float = 0.8

Implementation:
1. Build complete import/export graph
2. Identify entry points:
   - Main files (index.ts, main.ts)
   - Test files (if include_tests)
   - Explicitly provided entry points
3. Traverse from entry points marking reachable code
4. Identify unreachable:
   - Exports never imported
   - Functions never called
   - Files never imported
   - Variables never used
5. Calculate confidence scores

Returns:
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

**Tool: `find_import_cycles`**
```
Parameters:
- project_root: str | None = None
- max_depth: int = 10 (maximum cycle depth to search)
- include_node_modules: bool = False

Implementation:
1. Build directed graph of imports
2. Use Tarjan's algorithm for cycle detection
3. For each cycle found:
   - Calculate cycle length
   - Determine cycle type (direct, indirect)
   - Identify breaking points
4. Generate refactoring suggestions

Returns:
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

### 3. Claude Command Implementation

Create a comprehensive Claude command at `.aromcp/commands/generate-eslint-rules.md`:

```markdown
# Generate ESLint Rules from Coding Standards

## Objective
Parse all coding standards in the project and generate corresponding ESLint rules that enforce the standards automatically.

## Prerequisites
- Coding standards exist in `.aromcp/standards/` directory
- Each standard has YAML frontmatter with metadata
- Standards include good/bad code examples

## Process Overview

1. **Discovery Phase**
   - Load all coding standards from the project
   - Analyze their structure and patterns
   - Identify enforceable rules

2. **Rule Generation Phase**
   - Parse each standard to extract rules
   - Generate ESLint rules for each identified pattern
   - Create test cases from examples

3. **Configuration Phase**
   - Create ESLint configurations for each standard category
   - Generate file pattern mappings
   - Integrate with existing ESLint setup

4. **Validation Phase**
   - Validate all generated rules
   - Test against provided examples
   - Generate summary report

## Execution Steps

### Step 1: Load and Analyze Standards
```python
# Load all standards with metadata
standards = aromcp.load_coding_standards()

# Analyze each standard
for standard in standards['data']['standards']:
    print(f"Processing: {standard['id']}")

    # Load full content
    content = aromcp.read_files_batch([standard['path']])

    # Parse to rules
    rules = aromcp.parse_standard_to_rules(
        standard_content=content['data']['files'][standard['path']],
        standard_id=standard['id']
    )
```

### Step 2: Generate ESLint Rules
```python
# Collect all parsed rules
all_rules = []
for standard_id, rules in parsed_rules.items():
    all_rules.extend(rules['data']['rules'])

# Generate ESLint rule files
result = aromcp.generate_eslint_rules(
    rules=all_rules,
    output_dir='.aromcp/generated-rules',
    typescript=True
)

# Validate generated rules
validation = aromcp.validate_generated_rules(
    rule_files=result['data']['generated_files'],
    run_tests=True
)
```

### Step 3: Create Configuration
```python
# Create ESLint configurations
config = aromcp.create_eslint_config(
    standards_mappings=standards['data'],
    existing_config_path='.eslintrc.js',
    output_dir='.aromcp/eslint-configs'
)
```

### Step 4: Generate Report
Create a summary report with:
- Total standards processed
- Rules generated per standard
- Validation results
- Integration instructions

## Expected Output Structure
```
.aromcp/
├── generated-rules/
│   ├── index.js                    # Plugin entry point
│   ├── api-route-structure.js      # Individual rules
│   ├── component-naming.js
│   └── ...
├── eslint-configs/
│   ├── main.js                     # Main config with overrides
│   ├── api-routes.js               # Category-specific configs
│   ├── components.js
│   └── ...
├── standards-mapping.json          # Pattern to standards mapping
└── generation-report.md            # Summary report
```

## Integration Instructions

After generation, update your project's ESLint configuration:

```javascript
// .eslintrc.js
module.exports = {
  extends: [
    // your existing extends
    './.aromcp/eslint-configs/main.js'
  ],
  plugins: [
    // your existing plugins
    './.aromcp/generated-rules'
  ]
};
```

## Error Handling

If rule generation fails:
1. Check the generation report for specific errors
2. Verify standard format matches expected structure
3. Ensure code examples are valid TypeScript/JavaScript
4. Review the error log in `.aromcp/logs/rule-generation.log`
```

### 4. Standards Metadata Schema

Define the expected YAML frontmatter structure for standards:

```yaml
# .aromcp/standards/example-standard.md
---
# Required fields
id: api-routes
name: API Route Standards
version: 1.0.0

# File patterns this standard applies to
patterns:
  - "**/routes/**/*.ts"
  - "**/api/**/*.ts"
  - "**/endpoints/**/*.ts"

# Tags for categorization
tags:
  - api
  - routes
  - typescript

# Default severity for rules from this standard
severity: error

# Optional fields
enabled: true
priority: 1  # Higher priority standards override lower ones
dependencies:  # Other standards this depends on
  - general-typescript

# Rule generation hints
rules:
  naming_convention: camelCase
  async_required: true
  error_handling: required
---

# API Route Standards

## Overview
This document defines standards for API route handlers...

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

### 5. Configuration Files

**Standards mapping configuration** (`.aromcp/standards-mapping.json`):
```json
{
  "version": "1.0",
  "defaultStandards": [
    "general-typescript",
    "code-style"
  ],
  "mappings": [
    {
      "name": "API Routes",
      "standards": ["api-routes", "error-handling"],
      "patterns": ["**/routes/**/*.ts", "**/api/**/*.ts"],
      "eslintConfig": "api-routes",
      "priority": 1
    },
    {
      "name": "React Components",
      "standards": ["react-components", "react-hooks"],
      "patterns": ["**/*.tsx", "**/components/**/*"],
      "eslintConfig": "react-components",
      "priority": 2
    }
  ]
}
```

## Acceptance Criteria

### Functional Requirements

1. **Standards Loading**
   - ✅ Load all markdown standards from `.aromcp/standards/` directory
   - ✅ Parse YAML frontmatter for metadata (tags, patterns, severity)
   - ✅ Handle missing or invalid metadata gracefully
   - ✅ Support nested directory structures

2. **Pattern Matching**
   - ✅ Match files to relevant standards using glob patterns
   - ✅ Support pattern specificity (more specific patterns take precedence)
   - ✅ Include default/general standards for all files
   - ✅ Return matched standards with match reasons

3. **Rule Parsing**
   - ✅ Parse markdown to identify enforceable rules
   - ✅ Extract good/bad code examples
   - ✅ Structure rules for AI-driven generation
   - ✅ Support rule metadata and categorization

4. **ESLint Integration (via AI Commands)**
   - ✅ Provide standards structure for AI rule generation
   - ✅ Support pattern-based standard loading
   - ✅ Enable integration with existing ESLint configurations

5. **Security Analysis**
   - ✅ Detect hardcoded credentials and secrets
   - ✅ Identify SQL injection vulnerabilities
   - ✅ Find command injection risks
   - ✅ Categorize by severity levels

6. **Code Quality Analysis**
   - ✅ Find unused exports and dead code
   - ✅ Detect circular dependencies
   - ✅ Track component/function usage
   - ✅ Extract API endpoints with documentation

### Non-Functional Requirements

1. **Performance**
   - ✅ Cache parsed ASTs and generated rules
   - ✅ Support incremental rule generation
   - ✅ Process large codebases efficiently (<5s for 1000 files)

2. **Error Handling**
   - ✅ Follow established error response format
   - ✅ Provide actionable error messages
   - ✅ Never expose system paths in errors

3. **Security**
   - ✅ Validate all file paths against project root
   - ✅ Prevent directory traversal attacks
   - ✅ Limit file size processing (configurable)

4. **Maintainability**
   - ✅ Follow MCP server coding conventions
   - ✅ Comprehensive docstrings and type annotations
   - ✅ Modular architecture for easy extension

## Testing Strategy

### Test Structure

Following the established pattern from Phase 1, create modular test files:

```
tests/analysis_server/
├── test_load_coding_standards.py
├── test_get_relevant_standards.py
├── test_parse_standard_to_rules.py
├── test_detect_security_patterns.py
├── test_find_dead_code.py
├── test_find_import_cycles.py
├── test_security_validation.py      # Cross-tool security tests
└── test_integration_workflows.py    # End-to-end workflows
```

### Test Cases Per Tool

#### `TestLoadCodingStandards`
1. **test_load_basic_standards** - Load standards from directory
2. **test_parse_yaml_frontmatter** - Extract metadata correctly
3. **test_handle_invalid_metadata** - Graceful handling of bad YAML
4. **test_nested_directories** - Support subdirectories
5. **test_empty_directory** - Handle no standards gracefully
6. **test_large_standards_file** - Performance with large files

#### `TestGetRelevantStandards`
1. **test_exact_pattern_match** - Direct pattern matches
2. **test_glob_pattern_match** - Wildcard pattern matching
3. **test_pattern_specificity** - More specific patterns win
4. **test_default_standards** - Include general standards
5. **test_no_match** - Handle files with no matching standards
6. **test_multiple_matches** - Handle overlapping patterns

#### `TestParseStandardToRules`
1. **test_extract_simple_rules** - Basic rule extraction
2. **test_parse_code_examples** - Extract good/bad examples
3. **test_identify_rule_types** - Categorize rules correctly
4. **test_handle_complex_markdown** - Nested structures
5. **test_missing_examples** - Handle rules without examples
6. **test_invalid_code_blocks** - Handle syntax errors


#### `TestSecurityAnalysis`
1. **test_detect_hardcoded_secrets** - Find API keys, passwords
2. **test_sql_injection_detection** - Identify SQL vulnerabilities
3. **test_command_injection** - Find command injection risks
4. **test_path_traversal** - Detect path manipulation
5. **test_severity_filtering** - Filter by severity levels
6. **test_false_positive_handling** - Minimize false positives

#### `TestIntegrationWorkflows`
1. **test_complete_standard_processing** - End-to-end standard processing
2. **test_incremental_updates** - Update existing rules
3. **test_multi_standard_project** - Handle multiple standards
4. **test_eslint_integration** - Verify ESLint compatibility
5. **test_performance_large_codebase** - Performance benchmarks

### Test Utilities

Create shared test utilities in `tests/analysis_server/utils.py`:
- Sample markdown standards with various structures
- Mock file systems with different project layouts
- ESLint rule validation helpers
- AST comparison utilities

### Test Data

Create test fixtures in `tests/analysis_server/fixtures/`:
- Sample coding standards (`.aromcp/standards/`)
- Example TypeScript/JavaScript files
- Expected ESLint rule outputs
- Invalid/edge case examples

## Success Metrics

1. **Coverage**: >90% code coverage for all analysis tools
2. **Performance**: Process 1000 files in <5 seconds
3. **Accuracy**: <5% false positive rate for security detection
4. **Compatibility**: Generated rules work with ESLint 8.x+
5. **Reliability**: All tests pass consistently across environments

## Implementation Notes

1. **Follow Phase 1 Patterns**:
   - Use `@json_convert` decorator for list/dict parameters
   - Default `project_root` to None and resolve with `get_project_root()`
   - Use `validate_file_path()` for all file operations
   - Return structured responses with data/error format

2. **Leverage Existing Tools**:
   - Use FileSystem tools for file operations
   - Use Build tools for running ESLint validation
   - Maintain consistent error codes and patterns

3. **Performance Optimizations**:
   - Cache parsed ASTs and generated rules
   - Batch operations where possible
   - Use incremental processing for large codebases

4. **Security Considerations**:
   - Never execute generated code during validation
   - Sanitize all paths and patterns
   - Limit resource usage (memory, CPU)