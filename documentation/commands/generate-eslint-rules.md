# Generate ESLint Rules from Coding Standards

## Overview

This command uses Claude Code to intelligently generate ESLint rules from markdown coding standards. Unlike deterministic pattern matching, this approach leverages AI to understand the intent and context of your standards. For large codebases, it uses parallel sub-agents to process standards efficiently.

## Prerequisites

- Coding standards in markdown format
- Standards location: `.aromcp/standards/` (or specify custom path)
- Each standard should include:
  - Clear rule descriptions
  - Good/bad code examples
  - Rationale for the rules

## Command Usage

```bash
# From your project root, ensure Claude Code can access your standards
# The AI will analyze and generate appropriate ESLint rules
```

**Important**: When calling AroMCP tools, pass parameters as their native types, not JSON strings:
- ✅ `patterns="**/*.js"` (single pattern as string)
- ✅ `patterns=["**/*.js", "**/*.ts"]` (multiple patterns as list)
- ❌ `patterns="[\"**/*.js\"]"` (JSON string - will cause validation errors)

## Process

1. **Load Standards**
   ```python
   # Use AroMCP to load all coding standards
   standards = aromcp.load_coding_standards(
       standards_dir=".aromcp/standards"  # or your custom path
   )
   ```

2. **Classify Standards**
   - Claude Code reads the markdown content
   - **ESLint-Compatible**: Standards that can be enforced via AST analysis (syntax, patterns, structure)
   - **Non-ESLint Standards**: Architectural, process, documentation, business logic standards
   - Creates `.aromcp/non-eslint-standards.md` for Claude Code usage

3. **Generate ESLint Rules** (for compatible standards only)
   - Creates complete, functional ESLint rules with **required AroMCP metadata**
   - Includes proper error messages and fix functions where applicable
   - **CRITICAL**: All generated rules must include `@aromcp-` metadata comments
   - Generates comprehensive test cases

4. **Create Plugin Structure with Configuration**
   ```
   .aromcp/
   ├── generated-rules/
   │   ├── index.js                     # Plugin entry point
   │   ├── configs/
   │   │   ├── recommended.js           # Recommended config with overrides
   │   │   ├── strict.js                # Strict config for production
   │   │   └── development.js           # Relaxed config for development
   │   ├── rules/
   │   │   ├── api-async-handlers.js    # With @aromcp- metadata
   │   │   ├── component-naming.js      # With @aromcp- metadata
   │   │   └── ...
   │   ├── tests/
   │   │   ├── api-async-handlers.test.js
   │   │   └── ...
   │   └── package.json
   └── non-eslint-standards.md          # Standards for Claude Code (always created)
   ```

5. **Generate Pattern-Based ESLint Configurations**
   - **Automatic Config Generation**: Create ESLint configs with `overrides` based on rule patterns
   - **Multiple Config Presets**: Generate different configurations for different environments
   - **Smart Grouping**: Group rules by their `@aromcp-patterns` for optimal organization

## **CRITICAL: Required ESLint Rule Metadata Format**

Every generated ESLint rule file **MUST** include AroMCP metadata in this exact format:

```javascript
//
// @aromcp-rule-id: api-async-handlers
// @aromcp-patterns: ["**/routes/**/*.ts", "**/api/**/*.ts"]
// @aromcp-severity: error
// @aromcp-tags: ["api", "routes", "async"]
// @aromcp-description: Require async handlers for API routes
//

module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Require async handlers for API routes',
            category: 'Best Practices',
            recommended: true
        },
        fixable: null,
        schema: []
    },

    create(context) {
        return {
            // ESLint rule implementation
        };
    }
};
```

**Why this metadata is required:**
- The `get_relevant_standards` tool now reads these metadata comments to determine which rules apply to files
- Without this metadata, the rule will not be discoverable at runtime
- This creates proper separation between generation-time (standards) and runtime (ESLint rules)

## Standards Classification

### ESLint-Compatible Standards
Standards that can be enforced via static code analysis:
- **Syntax patterns**: Function declarations, variable naming, import styles
- **Code structure**: Async/await usage, error handling patterns, function signatures
- **API usage**: Specific method calls, forbidden APIs, required parameters
- **Code organization**: File structure, export patterns, dependency imports

### Non-ESLint Standards (Extracted to `.aromcp/non-eslint-standards.md`)
Standards that require human judgment or runtime behavior:
- **Architecture**: Design patterns, dependency injection, separation of concerns
- **Documentation**: API documentation requirements, comment standards
- **Process**: Code review guidelines, testing requirements, deployment procedures  
- **Business Logic**: Security policies, data validation rules, audit requirements
- **Performance**: Optimization guidelines, resource usage patterns
- **Accessibility**: User experience standards, inclusive design principles

## Standards Format (INPUT for Generation)

Your markdown standards files (the INPUT to this generation command) should follow this structure.

**Important**: This is the format for original standards files that you write. The generated ESLint rules will have a different format with `@aromcp-` metadata comments.

```markdown
---
id: async-error-handling
name: Async Error Handling Standards
tags: [async, error-handling, promises]
patterns: ["**/*.ts", "**/*.js"]  # These become @aromcp-patterns in generated rules
severity: error                   # This becomes @aromcp-severity in generated rules
---

# Async Error Handling Standards

## Rule: Always handle errors in async functions

Async functions should always include proper error handling to prevent unhandled promise rejections.

### Good Examples

```javascript
// ✅ Async function with try-catch
async function fetchUser(id) {
  try {
    const response = await api.get(`/users/${id}`);
    return response.data;
  } catch (error) {
    logger.error('Failed to fetch user:', error);
    throw new UserFetchError(error);
  }
}

// ✅ Route handler with error handling
router.get('/users/:id', async (req, res, next) => {
  try {
    const user = await fetchUser(req.params.id);
    res.json(user);
  } catch (error) {
    next(error);
  }
});
```

### Bad Examples

```javascript
// ❌ No error handling
async function fetchUser(id) {
  const response = await api.get(`/users/${id}`);
  return response.data;
}

// ❌ Route handler without try-catch
router.get('/users/:id', async (req, res) => {
  const user = await fetchUser(req.params.id);
  res.json(user);
});
```
```

**Transformation Process**: The generation command reads these YAML frontmatter fields and transforms them into `@aromcp-` metadata comments in the generated ESLint rule files:

- `patterns: ["**/*.ts"]` → `@aromcp-patterns: ["**/*.ts"]`
- `severity: error` → `@aromcp-severity: error` 
- `tags: [async, error-handling]` → `@aromcp-tags: ["async", "error-handling"]`
- `id: async-error-handling` → `@aromcp-rule-id: async-error-handling`

## Patterns and Wildcards Usage

### During Generation (Reading Standards)

1. **Standards Directory Patterns**:
   ```python
   # Load from multiple directories during generation
   aromcp.load_coding_standards(standards_dir="docs/standards/**/*.md")
   ```

2. **File Patterns in Standards (INPUT format)**:
   ```yaml
   patterns:
     - "src/**/*.ts"      # All TypeScript files in src
     - "**/api/**/*.js"   # All JS files in any api directory
     - "!**/*.test.ts"    # Exclude test files
   ```

### After Generation (Runtime Rule Discovery)

3. **Check Generated Rules for Files** (NEW - reads generated ESLint rules):
   ```python
   # After ESLint rules are generated, check which rules apply to a file
   # NOTE: This now reads .aromcp/generated-rules/rules/*.js, not standards
   aromcp.get_relevant_standards(
       file_path="src/api/routes/user.ts",
       project_root="."
   )
   # Returns: applicable ESLint rules with metadata, not original standards
   ```

## Automatic ESLint Configuration Generation

The generation command creates optimized ESLint configurations that automatically apply different rules to different parts of your codebase based on the `@aromcp-patterns` metadata.

### Generated Configuration Files

```javascript
// .aromcp/generated-rules/configs/recommended.js
module.exports = {
  plugins: ['@aromcp'],
  
  overrides: [
    // API Routes Section - Generated from rules with api/routes patterns
    {
      files: ['**/routes/**/*.ts', '**/api/**/*.ts', '**/middleware/**/*.ts'],
      rules: {
        '@aromcp/api-async-handlers': 'error',        // From api-async-handlers.js rule
        '@aromcp/api-error-logging': 'error',         // From api-error-logging.js rule
        '@aromcp/middleware-validation': 'error',     // From middleware-validation.js rule
      }
    },
    
    // React Components Section - Generated from rules with component patterns
    {
      files: ['**/components/**/*.tsx', '**/pages/**/*.tsx'],
      rules: {
        '@aromcp/component-naming': 'error',          // From component-naming.js rule
        '@aromcp/props-validation': 'error',          // From props-validation.js rule
        '@aromcp/component-size': 'warn',             // From component-size.js rule
      }
    },
    
    // Utils Section - Generated from rules with utils patterns  
    {
      files: ['**/utils/**/*.ts', '**/services/**/*.ts'],
      rules: {
        '@aromcp/pure-functions': 'warn',             // From pure-functions.js rule
        '@aromcp/service-injection': 'error',         // From service-injection.js rule
      }
    },
    
    // Test Files Section - Generated from rules with test patterns
    {
      files: ['**/*.test.ts', '**/*.spec.ts', '**/__tests__/**/*.ts'],
      rules: {
        '@aromcp/test-naming': 'error',               // From test-naming.js rule
        '@aromcp/test-structure': 'warn',             // From test-structure.js rule
        // Automatically disable production rules in tests
        '@aromcp/api-async-handlers': 'off',
        '@aromcp/component-naming': 'off'
      }
    }
  ]
};
```

### Integration with Your Project

Choose from multiple generated configurations:

```javascript
// .eslintrc.js - Simple integration
module.exports = {
  extends: [
    // Your existing config
    './.aromcp/generated-rules/configs/recommended'
  ]
};

// .eslintrc.js - Environment-specific
module.exports = {
  extends: [
    process.env.NODE_ENV === 'production' 
      ? './.aromcp/generated-rules/configs/strict'
      : './.aromcp/generated-rules/configs/development'
  ]
};

// .eslintrc.js - Custom overrides
module.exports = {
  extends: ['./.aromcp/generated-rules/configs/recommended'],
  overrides: [
    // Add your own custom overrides
    {
      files: ['legacy/**/*.js'],
      rules: {
        '@aromcp/modern-syntax': 'warn'  // Relaxed for legacy code
      }
    }
  ]
};
```

## New Architecture: Generation vs Runtime Separation

**Important**: This command creates proper separation between generation-time and runtime concerns:

### Generation Time (This Command)
- **Reads**: Original `.aromcp/standards/*.md` files
- **Writes**: Generated `.aromcp/generated-rules/rules/*.js` files with `@aromcp-` metadata
- **Purpose**: Convert human-readable standards into enforceable ESLint rules

### Runtime (get_relevant_standards tool)
- **Reads**: Generated `.aromcp/generated-rules/rules/*.js` files
- **Ignores**: Original `.aromcp/standards/*.md` files
- **Purpose**: Find which ESLint rules apply to specific files

### Workflow
1. **Write standards** → `.aromcp/standards/api-routes.md` with specific patterns
2. **Run this command** → Generates:
   - `.aromcp/generated-rules/rules/api-async-handlers.js` with `@aromcp-patterns` metadata
   - `.aromcp/generated-rules/configs/recommended.js` with pattern-based overrides
3. **Integrate ESLint** → `extends: ['./.aromcp/generated-rules/configs/recommended']`
4. **Use get_relevant_standards** → Reads generated rules, returns applicable ESLint rules
5. **ESLint enforces** → Different rules for different parts of codebase automatically

### Key Benefits of Pattern-Based Configuration

1. **Automatic Scoping**: API rules only apply to API files, component rules only to components
2. **Test File Handling**: Production rules automatically disabled in test files
3. **Environment Flexibility**: Different rule strictness for development vs production
4. **Team Alignment**: Clear boundaries for different areas of responsibility
5. **Maintenance**: Changes to standards automatically update ESLint config
6. **Performance**: ESLint only loads relevant rules for each file type

## Best Practices

### Standards Writing
1. **Clear Examples**: Provide multiple, clear examples of good and bad code
2. **Explain Why**: Include rationale for each rule
3. **Specific Patterns**: Use precise file patterns to target rules appropriately
   - ✅ `**/api/routes/**/*.ts` (specific to API routes)
   - ❌ `**/*.ts` (too broad, applies everywhere)
4. **Logical Grouping**: Group related standards that should apply to the same files

### Rule Generation
5. **Test Generated Rules**: Always test generated rules on sample code
6. **Verify Metadata**: Ensure all generated rules include required `@aromcp-` comments
7. **Check Patterns**: Verify `@aromcp-patterns` match your intended file scope
8. **Test Integration**: Use `get_relevant_standards` to verify rules are discoverable

### Configuration Management
9. **Environment Testing**: Test all generated config presets (recommended, strict, development)
10. **Pattern Validation**: Ensure patterns don't overlap in unexpected ways
11. **Team Boundaries**: Align rule patterns with team responsibilities
    - API team: `**/api/**`, `**/routes/**`, `**/middleware/**`
    - Frontend team: `**/components/**`, `**/pages/**`, `**/hooks/**`
    - Utils team: `**/utils/**`, `**/services/**`, `**/lib/**`
12. **Legacy Handling**: Create separate patterns for legacy code with relaxed rules

## Troubleshooting

### ESLint Rule Issues
- **Rule Too Broad**: Add more specific bad examples
- **Rule Too Narrow**: Add edge cases to good examples
- **False Positives**: Refine the rule description and examples
- **Missing Cases**: Add more comprehensive examples

### New Architecture Issues
- **get_relevant_standards returns no rules**: Check that generated ESLint rules include `@aromcp-` metadata comments
- **Rule not discoverable**: Verify the `@aromcp-patterns` field matches your file path
- **Rule ID conflicts**: Use unique rule IDs across all generated rules
- **Missing metadata**: All generated rules must have the complete metadata comment block
- **Pattern mismatch**: Ensure patterns in `@aromcp-patterns` use proper glob syntax

### Migration from Old Architecture
- **Still reading standards files**: The `get_relevant_standards` tool now only reads generated ESLint rules
- **Different return format**: The tool now returns ESLint rule information, not original standards
- **Workflow changed**: Run ESLint generation first, then use `get_relevant_standards`

## Parallel Processing Workflow

For large projects with many standards files, use parallel sub-agents to process standards efficiently:

### Main Agent Coordination

```python
# 1. Discover all standards files
standards = aromcp.load_coding_standards()
standards_files = [s["path"] for s in standards["data"]["standards"]]

# 2. Check existing generated rules to avoid duplication
existing_rules = aromcp.get_target_files(
    patterns=".aromcp/generated-rules/rules/*.js"
)

# 3. Group standards by categories/directories for parallel processing
standards_groups = group_standards_by_category(standards_files)
```

### Parallel Sub-Agent Processing

Use 4-6 sub-agents in parallel to process different standard categories:

**Sub-Agent 1 - API Standards**: Process all API-related standards files (routes, endpoints, middleware) and generate corresponding ESLint rules. Load existing rules first to avoid conflicts.

**Sub-Agent 2 - Component Standards**: Process all component-related standards files (React, Vue, Angular) and generate UI/component ESLint rules. Load existing rules first to avoid conflicts.

**Sub-Agent 3 - Security Standards**: Process all security-related standards files (authentication, validation, encryption) and generate security ESLint rules. Load existing rules first to avoid conflicts.

**Sub-Agent 4 - General Standards**: Process all general coding standards files (naming, formatting, imports) and generate general ESLint rules. Load existing rules first to avoid conflicts.

### Sub-Agent Instructions Template

Each sub-agent should follow this pattern:

```python
# IMPORTANT: Load existing generated rules first to avoid conflicts
existing_rules = aromcp.get_target_files(
    patterns=".aromcp/generated-rules/rules/*.js"
)

# Read existing rules to understand current rule IDs and avoid duplication
if existing_rules["data"]["files"]:
    existing_rule_content = aromcp.read_files_batch(
        file_paths=existing_rules["data"]["files"][:5]  # Max 5 at a time
    )

# Load assigned standards files (max 5 at a time for performance)
assigned_standards = aromcp.read_files_batch(
    file_paths=my_assigned_standards_files[:5]
)

# Initialize collections for classification
eslint_compatible_rules = []
non_eslint_standards = []

# For each standard:
for standard_file, content in assigned_standards["data"]["files"].items():
    # Parse the standard
    parsed_rules = aromcp.parse_standard_to_rules(
        standard_content=content,
        standard_id=extract_standard_id(standard_file)
    )
    
    # Classify each rule as ESLint-compatible or not
    for rule in parsed_rules["data"]["rules"]:
        if is_eslint_compatible(rule):
            eslint_compatible_rules.append(rule)
        else:
            non_eslint_standards.append({
                "category": my_category,  # api, component, security, general
                "standard_id": rule["standard_id"],
                "rule_name": rule["name"],
                "description": rule["description"],
                "rationale": rule.get("rationale", ""),
                "applies_to": rule.get("patterns", [])
            })
    
    # Generate ESLint rules only for compatible rules
    # **CRITICAL**: Create rule files with required @aromcp- metadata comments
    # Use the sample rule creation function or follow this exact format:
    #
    # Option 1: Use the helper function
    # rule_content = aromcp.analysis_server.eslint_metadata.rule_parser.create_sample_eslint_rule(
    #     rule_id="category-rule-name",
    #     patterns=["pattern1", "pattern2"],
    #     description="Rule description",
    #     severity="error|warn|info",
    #     tags=["tag1", "tag2"]
    # )
    #
    # Option 2: Manual format (MUST include all metadata):
    #    //
    #    // @aromcp-rule-id: category-rule-name
    #    // @aromcp-patterns: ["pattern1", "pattern2"]
    #    // @aromcp-severity: error|warn|info
    #    // @aromcp-tags: ["tag1", "tag2"]
    #    // @aromcp-description: Rule description
    #    //
    # Create unique names: category-rule-name.js
    # Write to .aromcp/generated-rules/rules/

# Write non-ESLint standards to shared file (append mode for parallel agents)
# Format: Token-efficient markdown for Claude Code usage
```

### Classification Logic

```python
def is_eslint_compatible(rule):
    """Determine if a rule can be enforced via ESLint."""
    
    # ESLint-compatible indicators
    eslint_patterns = [
        "function declaration", "variable naming", "import style",
        "async/await", "error handling", "method call", "syntax",
        "code structure", "API usage", "export pattern"
    ]
    
    # Non-ESLint indicators  
    non_eslint_patterns = [
        "architecture", "design pattern", "documentation", 
        "process", "business logic", "security policy",
        "performance guideline", "accessibility", "user experience",
        "code review", "testing strategy", "deployment"
    ]
    
    description = rule["description"].lower()
    
    # Check for non-ESLint patterns first (more specific)
    if any(pattern in description for pattern in non_eslint_patterns):
        return False
        
    # Check for ESLint patterns
    if any(pattern in description for pattern in eslint_patterns):
        return True
        
    # Default: if has code examples, likely ESLint-compatible
    return bool(rule.get("examples", {}).get("good") or rule.get("examples", {}).get("bad"))
```

### Conflict Prevention Strategy

To prevent multiple agents from creating duplicate rules:

1. **Unique Rule Naming**: Each sub-agent uses category prefixes:
   - API rules: `api-[rule-name].js`
   - Component rules: `component-[rule-name].js`
   - Security rules: `security-[rule-name].js`
   - General rules: `general-[rule-name].js`

2. **Load Existing Rules First**: Each sub-agent loads existing rules before generating new ones

3. **Atomic File Creation**: Write complete rule files atomically to avoid partial overwrites

### Sequential Workflow (Alternative)

For simpler execution without parallel agents:

```python
# 1. Load existing generated rules
existing_rules = aromcp.get_target_files(
    patterns=".aromcp/generated-rules/rules/*.js"
)

# 2. Load standards in batches of 5
standards = aromcp.load_coding_standards()
standards_files = [s["path"] for s in standards["data"]["standards"]]

# 3. Process in batches
for i in range(0, len(standards_files), 5):
    batch = standards_files[i:i+5]
    
    # Load batch content
    batch_content = aromcp.read_files_batch(file_paths=batch)
    
    # Process each standard in the batch
    for file_path, content in batch_content["data"]["files"].items():
        # Parse and generate rules
        parsed_rules = aromcp.parse_standard_to_rules(
            standard_content=content,
            standard_id=extract_standard_id(file_path)
        )
        
        # Generate unique ESLint rules
        # Write to .aromcp/generated-rules/rules/
```

## Final Integration

After all sub-agents complete:

```python
# 1. Collect all generated rule files
all_rules = aromcp.get_target_files(
    patterns=".aromcp/generated-rules/rules/*.js"
)

# 2. Aggregate non-ESLint standards from all agents
non_eslint_content = create_non_eslint_standards_file()

# 3. Generate pattern-based ESLint configurations
eslint_configs = generate_eslint_configurations(all_rules)

# 4. Generate main plugin index file
# 5. Create ESLint configuration files with smart overrides
# 6. Generate package.json for the plugin
# 7. Create integration documentation
```

### ESLint Configuration Generation Algorithm

```python
def generate_eslint_configurations(rule_files):
    """Generate ESLint configs with pattern-based overrides."""
    
    # Parse all rule metadata
    rules_by_pattern = {}
    all_rules = {}
    
    for rule_file in rule_files:
        # Use the AroMCP rule parser we implemented
        rule_data = aromcp.analysis_server.eslint_metadata.rule_parser.parse_eslint_rule_file(rule_file)
        rule_name = rule_data["eslint_rule_name"]
        patterns = rule_data["patterns"]
        severity = rule_data["severity"]
        
        all_rules[rule_name] = severity
        
        # Group rules by their patterns
        for pattern in patterns:
            pattern_key = normalize_pattern(pattern)
            if pattern_key not in rules_by_pattern:
                rules_by_pattern[pattern_key] = []
            rules_by_pattern[pattern_key].append({
                "rule": rule_name,
                "severity": severity,
                "original_pattern": pattern
            })
    
    # Generate configuration overrides
    overrides = []
    
    # Group similar patterns together
    pattern_groups = group_similar_patterns(rules_by_pattern)
    
    for group_name, group_data in pattern_groups.items():
        files = list(set(group_data["patterns"]))
        rules = {}
        
        for rule_info in group_data["rules"]:
            rules[rule_info["rule"]] = rule_info["severity"]
        
        # Add automatic test file rule disabling
        if not any("test" in pattern for pattern in files):
            # This is a production rule group, disable in tests
            test_override = {
                "files": ["**/*.test.ts", "**/*.spec.ts", "**/__tests__/**/*"],
                "rules": {rule: "off" for rule in rules.keys()}
            }
            overrides.append(test_override)
        
        overrides.append({
            "files": files,
            "rules": rules
        })
    
    # Generate multiple config presets
    configs = {
        "recommended": {
            "plugins": ["@aromcp"],
            "overrides": overrides
        },
        "strict": {
            "plugins": ["@aromcp"],
            "overrides": [
                # Convert all warn/info to error for strict mode
                {**override, "rules": {
                    rule: "error" if severity != "off" else "off"
                    for rule, severity in override["rules"].items()
                }} for override in overrides
            ]
        },
        "development": {
            "plugins": ["@aromcp"],
            "overrides": [
                # Convert all error to warn for development
                {**override, "rules": {
                    rule: "warn" if severity == "error" else severity
                    for rule, severity in override["rules"].items()
                }} for override in overrides
            ]
        }
    }
    
    return configs

def group_similar_patterns(rules_by_pattern):
    """Group similar file patterns for cleaner ESLint config."""
    groups = {
        "api-routes": {
            "patterns": [],
            "rules": [],
            "keywords": ["api", "routes", "middleware", "endpoints"]
        },
        "components": {
            "patterns": [],
            "rules": [],
            "keywords": ["components", "pages", "views", "ui"]
        },
        "utils-services": {
            "patterns": [],
            "rules": [],
            "keywords": ["utils", "services", "helpers", "lib"]
        },
        "tests": {
            "patterns": [],
            "rules": [],
            "keywords": ["test", "spec", "__tests__"]
        },
        "general": {
            "patterns": [],
            "rules": [],
            "keywords": []
        }
    }
    
    for pattern, rules in rules_by_pattern.items():
        # Determine which group this pattern belongs to
        group_name = classify_pattern(pattern, groups)
        groups[group_name]["patterns"].append(pattern)
        groups[group_name]["rules"].extend(rules)
    
    # Remove empty groups
    return {k: v for k, v in groups.items() if v["patterns"]}

def normalize_pattern(pattern):
    """Normalize pattern for grouping similar patterns."""
    # Remove file extensions for grouping
    return pattern.replace("*.ts", "*").replace("*.tsx", "*").replace("*.js", "*").replace("*.jsx", "*")

def classify_pattern(pattern, groups):
    """Classify a pattern into a group based on keywords."""
    pattern_lower = pattern.lower()
    
    for group_name, group_data in groups.items():
        if group_name == "general":
            continue
        for keyword in group_data["keywords"]:
            if keyword in pattern_lower:
                return group_name
    
    return "general"
```

### Non-ESLint Standards File Format

The `.aromcp/non-eslint-standards.md` file should be token-efficient but comprehensive:

```markdown
# Project Coding Standards (Non-ESLint)

Generated: 2024-01-02 | Standards processed: 15 | Non-ESLint rules: 23

## Architecture Standards

### API Design (applies to: **/api/**/*.ts, **/routes/**/*.js)
- **Dependency Injection**: Use dependency injection containers for service management
- **Error Boundaries**: Implement centralized error handling with proper logging
- **Rate Limiting**: All public APIs must implement rate limiting

### Component Design (applies to: **/components/**/*.tsx)  
- **Single Responsibility**: Each component should have one clear purpose
- **Prop Validation**: Use TypeScript interfaces, not PropTypes
- **State Management**: Prefer composition over inheritance

## Process Standards

### Documentation (applies to: all files)
- **API Documentation**: All public APIs require comprehensive JSDoc
- **README Updates**: Update README when adding new features
- **Changelog**: Document breaking changes in CHANGELOG.md

### Testing (applies to: all code files)
- **Coverage**: Maintain 80%+ test coverage
- **Integration Tests**: Critical paths require integration tests
- **E2E Tests**: User workflows require end-to-end tests

## Business Logic Standards

### Security (applies to: **/auth/**/*.ts, **/api/**/*.ts)
- **Authentication**: Always validate user permissions before data access
- **Input Validation**: Sanitize all user inputs at API boundaries
- **Audit Logging**: Log all financial and sensitive data operations

### Performance (applies to: **/components/**/*.tsx, **/pages/**/*.tsx)
- **Lazy Loading**: Implement code splitting for routes and large components
- **Image Optimization**: Use optimized images with proper alt text
- **Cache Strategy**: Implement appropriate caching for API responses

## Quick Reference

**When to apply these standards:**
- During code review: Check for architecture and process compliance
- Before feature completion: Ensure documentation and testing requirements met
- During refactoring: Apply performance and security guidelines
- When onboarding: Reference for team coding practices

**ESLint handles:** Syntax, imports, naming, code structure
**Human judgment handles:** Architecture, documentation, business logic, testing strategy
```

### Always Create This File

```python
def create_non_eslint_standards_file():
    """Always create this file, even if empty."""
    
    # Collect all non-ESLint standards from sub-agents
    all_non_eslint = collect_from_all_agents()
    
    if not all_non_eslint:
        # Create empty file with instructions
        content = """# Project Coding Standards (Non-ESLint)

Generated: {date} | No non-ESLint standards found

This project currently has no coding standards that require human judgment.
All standards are enforced via ESLint rules.

**Note**: This file is always created and should be loaded in your project's CLAUDE.md 
to ensure Claude Code has access to all applicable coding standards.
"""
    else:
        content = generate_comprehensive_standards_markdown(all_non_eslint)
    
    aromcp.write_files_batch(files={
        ".aromcp/non-eslint-standards.md": content
    })
```

## Summary: Complete Architectural Separation

This generation command implements a clean separation between generation-time and runtime operations:

### ✅ Generation Phase (This Command)
- **Reads**: Original `.aromcp/standards/*.md` files with YAML frontmatter
- **Processes**: Converts standards into ESLint-compatible rules
- **Writes**: Generated `.aromcp/generated-rules/rules/*.js` files with `@aromcp-` metadata
- **Creates**: Pattern-based ESLint configurations for different codebase sections

### ✅ Runtime Phase (get_relevant_standards tool)
- **Reads**: Generated `.aromcp/generated-rules/rules/*.js` files with `@aromcp-` metadata
- **Ignores**: Original `.aromcp/standards/*.md` files completely
- **Returns**: Applicable ESLint rules based on file patterns
- **Enables**: Different rules for different parts of the codebase automatically

### 🔄 Key Transformation
- Standards YAML `patterns: ["**/*.ts"]` → ESLint rule `@aromcp-patterns: ["**/*.ts"]`
- Standards YAML `severity: error` → ESLint rule `@aromcp-severity: error`
- This ensures runtime pattern matching uses exactly the same patterns ESLint will enforce

### ⚠️ Breaking Changes from Legacy Architecture
- `get_relevant_standards` no longer reads original standards files
- Return format now includes ESLint rule information instead of standards metadata  
- Must run this generation command before using `get_relevant_standards`
- ESLint configuration generation creates automatic pattern-based overrides