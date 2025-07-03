# Generate Standards and AI Hints

**Command**: `generate-standards`

**Description**: Processes markdown standards files through AI parsing to generate AI hints and ESLint rules using the new standards-server MCP tools.

## Usage

```bash
# Generate from all standards in standards/ directory
claude generate-standards

# Generate from specific standards directory
claude generate-standards --standards-dir=custom/standards

# Generate with custom project root
claude generate-standards --project-root=/path/to/project
```

## Parameters

- `--standards-dir` (optional): Directory containing markdown standards files (default: `standards`)
- `--project-root` (optional): Project root path (auto-detected if not specified)

## Process Overview

This command uses the new standards-server MCP tools to:

1. **Discovery**: Find all markdown standards files that need processing
2. **AI Parsing**: Use AI agents to parse markdown and extract structured metadata + hints
3. **Registration**: Register standards with metadata in the MCP server
4. **Rule Generation**: Generate AI hints and ESLint rules from parsed content
5. **Storage**: Store everything via MCP APIs only (no direct file system access)

**IMPORTANT**: AI agents must NEVER write files directly to disk or use any MCP file writing tools. All storage is handled by the standards-server MCP APIs only.

## Implementation Steps

### Step 1: Check for Updates and Discover Standards

```python
# Check what standards need processing
update_result = mcp.check_updates(
    standards_path="standards"
)

print(f"Found {len(update_result['data']['needsUpdate'])} standards to process")
print(f"{update_result['data']['upToDate']} standards are up to date")

# Get list of files that need processing
needs_update = update_result['data']['needsUpdate']
```

### Step 2: Process Standards Files in Batches Using AI Agents

```python
# Process standards in batches with maximum parallelization
# Always use at least 7-parallel-Task method for efficiency
# IMMEDIATE EXECUTION: Launch parallel Tasks immediately upon feature requests
from math import ceil
batch_size = 2
num_batches = ceil(len(needs_update) / batch_size)

print(f"Processing {len(needs_update)} standards in {num_batches} batches with maximum parallelization")

# Create tasks for all batches immediately (maximum parallelization)
batch_tasks = []
for batch_num in range(num_batches):
    start_idx = batch_num * batch_size
    end_idx = min(start_idx + batch_size, len(needs_update))
    batch_standards = needs_update[start_idx:end_idx]

    # Create comprehensive task prompt for the entire batch
    batch_task_prompt = f"""Process batch {batch_num + 1}/{num_batches} of coding standards files.

**BATCH CONTENTS ({len(batch_standards)} standards):**
"""

    # Add each standard's info to the batch prompt (Task will handle file reading)
    for standard_info in batch_standards:
        standard_id = standard_info['standardId']
        source_path = standard_info['sourcePath']
        reason = standard_info['reason']

        batch_task_prompt += f"""
---
**Standard ID**: {standard_id}
**Source Path**: {source_path}
**Reason**: {reason}
"""

    batch_task_prompt += f"""
---

**INSTRUCTIONS**:

1. **First, read all the markdown files for this batch using the Read tool**:
   - Use the Read tool to read each source path listed above
   - Extract the markdown content from each file

2. **Then, for EACH standard in this batch, parse the markdown content and extract:**

1. **Metadata** (following the exact schema):
   - id: Use the Standard ID provided above
   - name: Human-readable name
   - category: Main category (api, components, testing, etc.)
   - tags: Array of relevant tags
   - appliesTo: Array of file patterns (*.py, *.js, components/*.tsx, etc.)
   - severity: "error", "warning", or "info"
   - priority: "required", "important", or "recommended"

2. **AI Hints** (actionable coding guidelines):
   - rule: Concise rule statement
   - context: Why this matters / background
   - correctExample: Good code example
   - incorrectExample: Bad code example
   - hasEslintRule: true if this can be enforced by ESLint, false otherwise

3. **ESLint Rules** (if applicable):
   - Generate actual ESLint rule implementations (JavaScript code)
   - Include both the rule logic AND configuration
   - Only for patterns that can be automatically detected via AST analysis

**IMPORTANT**:
- Extract 3-8 AI hints per standard (focus on most important rules)
- Each hint should be actionable and specific
- Include both positive and negative examples
- Mark hasEslintRule=true only for patterns ESLint can actually detect via AST
- **NEVER write files to disk directly** - use ONLY the MCP APIs (register, update_rule)
- **DO NOT create any folders or files** - all storage is handled by the MCP server

**For ESLint Rules:**
- Only generate if the pattern can be detected by analyzing the Abstract Syntax Tree (AST)
- Must be pure module.exports rule definitions ONLY (no configuration)
- Use ESLint selector syntax for AST pattern matching
- Test your selector logic - ensure it matches the intended patterns
- Include proper error messages that guide developers to the correct approach

**ESLint File Rules (CRITICAL):**
- **Filename MUST**: Be in format `rules/rule-name.js` (e.g., `rules/api-mandatory-pipeline.js`)
- **Filename CANNOT**: Contain "config", "index", or start with "index"
- **Content MUST**: Be `module.exports = { meta: {...}, create: function(context) {...} }`
- **Content CANNOT**: Include any ESLint configuration (plugins, rules, extends, etc.)
- **API manages**: All configuration files, plugin indexes, and rule registration

**Output the results using these MCP calls:**

1. Register the standard:
```python
register_result = mcp.register(
    source_path="{source_path}",
    metadata='''{{
        "id": "{standard_id}",
        "name": "...",
        "category": "...",
        "tags": [...],
        "appliesTo": [...],
        "severity": "...",
        "priority": "..."
    }}'''
)
```

2. Store the AI hints and ESLint files:
```python
# Prepare ESLint rule files if needed (ONLY pure rule definitions)
eslint_files = None
if has_eslint_rules:
    eslint_files = {{
        "rules/descriptive-rule-name.js": '''module.exports = {{
  meta: {{
    type: "problem",
    docs: {{
      description: "Descriptive rule explanation",
      category: "Possible Errors"
    }},
    schema: []
  }},
  create: function(context) {{
    return {{
      'CallExpression': function(node) {{
        // Rule implementation logic
        if (shouldReport(node)) {{
          context.report({{
            node: node,
            message: 'Clear error message explaining the violation'
          }});
        }}
      }}
    }};
  }}
}};'''
    }}

# CRITICAL: ESLint files are ONLY rule definitions
# - Filename format: rules/descriptive-rule-name.js
# - Content: module.exports with meta + create only
# - NO configuration, plugins, extends, or index files

# Store AI hints and ESLint files in the standards system
mcp.update_rule(
    standard_id="{standard_id}",
    clear_existing=true,
    ai_hints='''[
        {{
            "rule": "...",
            "context": "...",
            "correctExample": "...",
            "incorrectExample": "...",
            "hasEslintRule": true/false
        }},
        # ... more hints
    ]''',
    eslint_files=eslint_files
)
```

**CRITICAL RESTRICTIONS**:
- **DO NOT write any files to disk directly** (no open(), write(), etc.)
- **DO NOT create directories** (no mkdir, makedirs, etc.)
- **DO NOT use MCP write_files_batch or any file writing tools**
- **USE ONLY the MCP APIs**: mcp.register() and mcp.update_rule()
- **All file storage is handled automatically** by the MCP server
- **Your job is ONLY parsing and API calls** - no direct file system operations

**Note**: The APIs accept both JSON strings and Python objects, so you can pass the data either way.

Process the file completely and report success."""

**For EACH standard in the batch, make these MCP calls:**

1. Register the standard:
```python
register_result = mcp.register(
    source_path="SOURCE_PATH_FROM_ABOVE",
    metadata='''{{
        "id": "STANDARD_ID_FROM_ABOVE",
        "name": "...",
        "category": "...",
        "tags": [...],
        "appliesTo": [...],
        "severity": "...",
        "priority": "..."
    }}'''
)
```

2. Store AI hints and ESLint files:
```python
mcp.update_rule(
    standard_id="STANDARD_ID_FROM_ABOVE",
    clear_existing=true,
    ai_hints='''[
        {{
            "rule": "...",
            "context": "...",
            "correctExample": "...",
            "incorrectExample": "...",
            "hasEslintRule": true/false
        }},
        # ... more hints
    ]''',
    eslint_files=eslint_files_if_any
)
```

**CRITICAL RESTRICTIONS**:
- **DO NOT write any files to disk directly** (no open(), write(), etc.)
- **DO NOT create directories** (no mkdir, makedirs, etc.)
- **DO NOT use MCP write_files_batch or any file writing tools**
- **USE ONLY the MCP APIs**: mcp.register() and mcp.update_rule()
- **All file storage is handled automatically** by the MCP server
- **Your job is ONLY parsing and API calls** - no direct file system operations

**COMPLETE EXAMPLE** - Process a standard called "api-error-handling":

```python
# Step 1: Register the standard
register_result = mcp.register(
    source_path="standards/api/error-handling.md",
    metadata={
        "id": "api-error-handling",
        "name": "API Error Handling Standards",
        "category": "api",
        "tags": ["error", "http", "response"],
        "appliesTo": ["api/*.py", "*/api/*", "routes/*.js"],
        "severity": "error",
        "priority": "required"
    }
)

# Step 2: Store AI hints and ESLint rules
mcp.update_rule(
    standard_id="api-error-handling",
    clear_existing=True,
    ai_hints=[
        {
            "rule": "Always return structured error responses",
            "context": "Consistent error format helps frontend handle errors predictably",
            "correctExample": "return Response.json({error: 'User not found', code: 404}, {status: 404})",
            "incorrectExample": "return Response.json('Error!')",
            "hasEslintRule": True
        },
        {
            "rule": "Use appropriate HTTP status codes",
            "context": "Status codes communicate error type to clients",
            "correctExample": "400 for validation, 404 for not found, 500 for server errors",
            "incorrectExample": "Always returning 200 OK with error in body",
            "hasEslintRule": False
        }
    ],
    eslint_files={
        "rules/api-structured-error-response.js": '''module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Enforce structured error response format in API routes",
      category: "Possible Errors"
    },
    schema: []
  },
  create: function(context) {
    return {
      'CallExpression[callee.object.name="Response"][callee.property.name="json"]': function(node) {
        const arg = node.arguments[0];
        if (arg && arg.type === 'Literal' && typeof arg.value === 'string') {
          context.report({
            node: node,
            message: 'Use structured error objects instead of string responses'
          });
        }
      }
    };
  }
};'''
    }
)
```

Process all standards in this batch completely and report success."""

    # Launch AI agent to process this entire batch
    batch_task = Task(
        description=f"Parse batch {batch_num + 1}/{num_batches} ({len(batch_standards)} standards)",
        prompt=batch_task_prompt
    )
    batch_tasks.append(batch_task)

print(f"✅ Launched {len(batch_tasks)} parallel AI parsing tasks for {len(needs_update)} standards")
```

### Step 3: Verify Results and Get Usage Instructions

```python
# After all AI tasks complete, check what was processed
final_check = mcp.check_updates(
    standards_path="standards",
    project_root="."
)

print(f"✅ Processing complete!")
print(f"📊 Standards registered: {final_check['data']['upToDate']}")
print(f"⚠️  Still needs work: {len(final_check['data']['needsUpdate'])}")

# Show usage example
print(f"""
📖 Usage Examples:

# Get hints for a specific file:
hints_result = mcp.hints_for_file(
    file_path="src/api/users.py",
    max_tokens=8000
)

# Results will include relevant hints with relevance scores
for hint in hints_result['data']['hints']:
    print(f"Rule: {{hint['rule']}}")
    print(f"Score: {{hint['relevanceScore']}}")
    print(f"Example: {{hint['correctExample']}}")
    print("---")
""")
```

## ESLint Rule Structure

ESLint rules need to be generated as actual JavaScript files and ESLint configuration. The system should create:

### 1. Rule Implementation Files (`*.js`)
Each rule should be a separate JavaScript file:

**File: `.aromcp/eslint/rules/api-mandatory-pipeline-pattern.js`**
```javascript
module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Enforce mandatory pipeline pattern for API routes",
      category: "Possible Errors",
      recommended: true
    },
    schema: []
  },
  create: function(context) {
    return {
      'ExportNamedDeclaration': function(node) {
        // Rule implementation logic here
      },
      'CallExpression': function(node) {
        if (node.callee.type === 'MemberExpression' &&
            node.callee.object.name === 'Response' &&
            node.callee.property.name === 'json') {
          context.report({
            node: node,
            message: 'Direct Response.json() calls are forbidden - use pipeline pattern with createHandler'
          });
        }
      }
    };
  }
};
```

### 2. ESLint Configuration
**File: `.aromcp/eslint/config.json`**
```json
{
  "plugins": ["./custom-rules"],
  "rules": {
    "custom-rules/api-mandatory-pipeline-pattern": "error",
    "custom-rules/no-direct-response-returns": "error"
  }
}
```

### 3. Plugin Index File
**File: `.aromcp/eslint/custom-rules.js`**
```javascript
module.exports = {
  rules: {
    'api-mandatory-pipeline-pattern': require('./rules/api-mandatory-pipeline-pattern'),
    'no-direct-response-returns': require('./rules/no-direct-response-returns')
  }
};
```

### ESLint Rule Implementation Examples

**Simple AST Pattern Detection:**
```javascript
"create": "function(context) { return { 'CallExpression[callee.object.name=\"Response\"][callee.property.name=\"json\"]': function(node) { context.report({ node, message: 'Use createHandler instead of direct Response.json()' }); } }; }"
```

**Function Declaration Pattern:**
```javascript
"create": "function(context) { return { 'FunctionDeclaration[id.name=/^[A-Z]/]': function(node) { context.report({ node, message: 'Function names should be camelCase' }); } }; }"
```

**Import Pattern Detection:**
```javascript
"create": "function(context) { return { 'ImportDeclaration[source.value=\"lodash\"]': function(node) { context.report({ node, message: 'Use tree-shakeable imports like lodash/get' }); } }; }"
```

### When to Generate ESLint Rules vs AI Hints

**Generate ESLint Rules for:**
- Specific function/method calls that can be detected (`Response.json()`, `console.log()`)
- Import statements and module usage patterns
- Variable/function naming conventions
- Code structure patterns (function declarations, class usage)
- Syntax patterns that can be matched with AST selectors

**Use AI Hints for:**
- Architecture and design patterns
- Business logic decisions
- Complex contextual rules that require understanding intent
- Performance considerations that depend on use case
- Security practices that need human judgment
- Code organization and file structure guidelines

**Example Decision Making:**
- ✅ ESLint Rule: "No direct Response.json() calls" - detectable AST pattern
- ❌ AI Hint: "Choose appropriate HTTP status codes based on business logic" - requires context
- ✅ ESLint Rule: "Import from specific modules" - detectable import pattern
- ❌ AI Hint: "Structure API routes for maintainability" - architectural decision

## Key Features of New Workflow

### 1. **Structured Storage**
- Standards stored in `.aromcp/` directory
- Each standard gets its own folder with numbered hint files
- Fast lookup index for performance
- Manifest tracking for update detection

### 2. **Relevance Scoring**
Standards are automatically scored for files based on:
- **Exact folder match** (score: 1.0) - `api/users.py` matches category "api"
- **Glob pattern match** (score: 0.8) - File matches `appliesTo` patterns
- **Category in path** (score: 0.6) - "api" appears in file path
- **Tag in path** (score: 0.4) - Tags appear in file path or name
- **Priority boost** - Required: 1.2x, Important: 1.1x, Recommended: 1.0x

### 3. **Token Budget Management**
- Hints fit within specified token budget (default: 10k tokens)
- ESLint-covered rules get 0.7x score (deprioritized)
- Highest scoring hints returned first
- Token counts pre-calculated for fast selection

### 4. **AI-Driven Processing**
- AI agents parse markdown and extract structured data
- No fixed templates - AI interprets standards contextually
- Handles variations in markdown format and content
- Generates both human-readable hints and machine-readable ESLint rules

## Example Standard Processing

Given a markdown file `standards/api/error-handling.md`:

```markdown
# API Error Handling

## Overview
All API endpoints must implement consistent error handling...

## Rules
1. Always return proper HTTP status codes
2. Use structured error response format
3. Log errors with sufficient context
```

The AI agent will:
1. **Extract metadata**: category="api", tags=["error", "http"], appliesTo=["api/*.py", "*/api/*"]
2. **Generate hints**: 3-5 actionable rules with examples
3. **Create ESLint rules**: If patterns are detectable (HTTP status usage, etc.)
4. **Store results**: In `.aromcp/hints/api-error-handling/` directory

## Usage After Generation

```python
# Get relevant hints for any file
hints = mcp.hints_for_file("src/api/auth.py", max_tokens=5000)

# Results include contextual hints with relevance scores
for hint in hints['data']['hints']:
    print(f"{hint['relevanceScore']:.2f}: {hint['rule']}")
    print(f"✅ {hint['correctExample']}")
    print(f"❌ {hint['incorrectExample']}")
```

This provides AI agents with contextual, relevant coding standards without overwhelming them with the full 70k+ token standards documentation.

## Using Generated ESLint Rules in Your Project

After generating standards, you can integrate the ESLint rules into your project's ESLint configuration:

### Option 1: Extend the Generated Configuration

**In your `.eslintrc.js`:**
```javascript
module.exports = {
  extends: [
    // Your existing configurations
    "./.aromcp/eslint/standards-config.js"
  ],
  // Your other ESLint settings
};
```

### Option 2: Manual Integration

**In your `eslint.config.js` (ESLint 9+):**
```javascript
import standardsConfig from './.aromcp/eslint/standards-config.json';

export default [
  // Your other configurations
  {
    plugins: {
      'standards': require('./.aromcp/eslint/custom-rules.js')
    },
    rules: {
      // Convert the rules format
      ...Object.fromEntries(
        Object.entries(standardsConfig.rules).map(([rule, level]) =>
          [rule.replace('custom-rules/', 'standards/'), level]
        )
      )
    }
  }
];
```

### Option 3: Selective Rule Usage

You can also import specific rules individually:
```javascript
// .eslintrc.js
module.exports = {
  plugins: ['standards'],
  rules: {
    'standards/api-mandatory-pipeline-pattern': 'error',
    'standards/no-direct-response-returns': 'warn',
    // Add only the rules you want
  }
};
```

The generated configuration automatically includes all rules from all processed standards, making it easy to enforce coding standards across your entire project.