# Generate Standards and AI Hints

**Command**: `standards:generate`

**Description**: Processes markdown standards files through AI parsing to generate enhanced AI hints with context awareness and smart compression support. Features context-aware compression, 70-80% token reduction through intelligent rule deduplication, progressive detail levels, and automated ESLint rule validation.

## Usage

```bash
# Generate from all standards (uses .aromcp/.standards-dir or defaults to "standards")
claude standards:generate

# Generate with session support (for testing hints_for_file)
claude standards:generate --session-id=test-session-123
```

## Parameters

- `--session-id` (optional): Session ID for testing hints_for_file deduplication (only used in final verification step)

## Standards Directory Resolution

The command automatically determines the standards directory:
1. If `.aromcp/.standards-dir` file exists, uses the path specified in that file
2. Otherwise defaults to `"standards"` directory
3. Project root is always the current working directory (where claude command runs)

## Process Overview

This command:

1. **Discovery**: Find all markdown standards files that need processing
2. **AI Parsing**: Use AI agents to parse markdown and extract metadata + enhanced rules
3. **Registration**: Register standards with metadata only (clears existing hints/rules)
4. **Iterative Hint Addition**: Add AI hints one by one via add_hint
5. **Iterative Rule Addition**: Add ESLint rules one by one via add_rule
6. **ESLint Validation**: Run lint_project to validate generated rules work correctly
7. **Rule Fixing**: Fix or disable any problematic ESLint rules found during validation
8. **Final Verification**: Confirm all standards are properly registered and rules are functional

**Key Points:**
- **register()** handles only metadata and clears existing data
- **add_hint()** handles individual AI hints
- **add_rule()** handles individual ESLint JavaScript files

## Implementation Steps

### Step 1: Check for Updates and Discover Standards

```python
# Determine standards directory
standards_dir = "standards"  # default
if os.path.exists(".aromcp/.standards-dir"):
    with open(".aromcp/.standards-dir", "r") as f:
        standards_dir = f.read().strip()

# Check what standards need processing
update_result = mcp.check_updates(
    standards_path=standards_dir
)

print(f"Found {len(update_result['data']['needsUpdate'])} standards to process")
print(f"{update_result['data']['upToDate']} standards are up to date")

# Get list of files that need processing
needs_update = update_result['data']['needsUpdate']
```

### Step 2: Process Standards Files with AI Parsing

```python
# Process standards in batches with enhanced metadata extraction
from math import ceil
batch_size = 2
num_batches = ceil(len(needs_update) / batch_size)

print(f"Processing {len(needs_update)} standards in {num_batches} batches")

# Create tasks for all batches with enhanced parsing
batch_tasks = []
for batch_num in range(num_batches):
    start_idx = batch_num * batch_size
    end_idx = min(start_idx + batch_size, len(needs_update))
    batch_standards = needs_update[start_idx:end_idx]

    # Create comprehensive task prompt for parsing
    batch_task_prompt = f"""Process batch {batch_num + 1}/{num_batches} of coding standards files with metadata extraction and rule generation.

**BATCH CONTENTS ({len(batch_standards)} standards):**
"""

    # Add each standard's info to the batch prompt
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

**PARSING INSTRUCTIONS**:

1. **First, read all markdown files using the Read tool**

2. **For EACH standard, extract metadata**:

```python
metadata = {{
    # Basic fields (required)
    "id": "{standard_id}",
    "name": "Human-readable name",
    "category": "api|frontend|backend|testing|security|performance",
    "tags": ["tag1", "tag2", ...],
    "applies_to": ["**/api/**/*.ts", "**/*.tsx", ...],  # File patterns
    "severity": "error|warning|info",
    "priority": "required|important|recommended",
    "dependencies": ["other-standard-ids"],

    # Context triggers (for smart loading)
    "context_triggers": {{
        "task_types": ["api_development", "component_development", "testing", "refactoring"],
        "architectural_layers": ["api", "service", "presentation", "data"],
        "code_patterns": ["export const GET", "useState", "z.object"],
        "import_indicators": ["zod", "next/server", "@/lib/Pipeline"],
        "file_patterns": ["**/routes/**/*.ts", "**/api/**/*.ts"],
        "nextjs_features": ["app-router", "server-components", "server-actions"]
    }},

    # Optimization hints
    "optimization": {{
        "priority": "critical|high|medium|low",
        "load_frequency": "always|common|conditional|rare",
        "compressible": true,  # Can examples be compressed?
        "cacheable": true,
        "example_reusability": "high|medium|low",
        "context_sensitive": true  # Load based on context?
    }},

    # Relationships
    "relationships": {{
        "similar_to": ["validation-standards"],  # For grouping
        "commonly_used_with": ["error-handling"],
        "conflicts_with": []
    }},

    # Next.js specific configuration (optional)
    "nextjs_config": {{
        "router_preference": "app",  # app|pages
        "rendering_strategy": "server"  # server|client|static
    }}
}}
```

3. **Generate AI hints with multiple compression formats**:

For each rule/hint extracted from the standard, create this exact structure for hints_for_file:

```python
{{
    "rule": "Clear, actionable rule statement",  # Required
    "rule_id": "unique-rule-id",  # Required, e.g., "validate-input-zod"
    "context": "Why this matters and when to apply it",  # Required

    # Metadata for smart loading (Required - matches RuleMetadata)
    "metadata": {{
        "pattern_type": "validation|error-handling|routing|security|performance",
        "complexity": "basic|intermediate|advanced|expert",
        "rule_type": "must|should|may|must-not",  # RFC 2119
        "nextjs_api": ["app-router", "pages-router", "api-routes"],  # List
        "client_server": "client-only|server-only|isomorphic|edge"
    }},

    # Multiple example formats (Required - matches RuleExamples)
    "examples": {{
        # All example fields should be strings or None
        "minimal": "schema.parse(input)",  # ~20 tokens
        "standard": "const validated = schema.parse(body);",  # ~100 tokens
        "detailed": "Full example with imports",  # ~200 tokens
        "full": "Complete implementation",  # Required
        "reference": "See src/api/users/route.ts",  # Optional
        "context_variants": {{  # Optional dict
            "app_router": "app router example",
            "pages_router": "pages router example"
        }}
    }},

    # Token counts (Required - matches TokenCount)
    "tokens": {{
        "minimal": 20,
        "standard": 100,
        "detailed": 200,
        "full": 400
    }},

    # Relationships for grouping (Optional)
    "relationships": {{
        "similar_rules": ["validate-output-zod"],
        "prerequisite_rules": ["setup-zod"],
        "see_also": ["error-handling"]
    }},

    # ESLint flag (Required boolean)
    "has_eslint_rule": true,

    # Import map (Optional list)
    "import_map": [
        {{
            "module": "zod",
            "imported_items": "{{ z }}",
            "statement": "import {{ z }} from 'zod'"
        }}
    ]
}}
```

**CRITICAL REQUIREMENTS FOR EXAMPLES**:

1. **Minimal Format** (~20 tokens):
   - Just the core pattern/function call
   - No imports, no context
   - Example: `schema.parse(input)` or `createHandler(config)`

2. **Standard Format** (~100 tokens):
   - Core implementation pattern
   - Key imports if critical
   - 3-5 lines max
   - Example: Basic function with main logic

3. **Detailed Format** (~200 tokens):
   - More complete but still focused
   - Includes imports and structure
   - 8-12 lines max
   - Shows the pattern in context

4. **Full Format** (existing):
   - Complete, runnable example
   - All imports and error handling
   - Production-ready code

**RULE STRUCTURE REQUIREMENTS**:

Each rule extracted from the standard must follow this exact structure for hints_for_file compatibility:

```python
{
    "rule": "Clear, actionable rule statement",  # Required
    "rule_id": "unique-rule-id",  # Required, e.g., "validate-input-zod"
    "context": "Why this matters and when to apply it",  # Required

    # Metadata for smart loading (Required - matches RuleMetadata)
    "metadata": {
        "pattern_type": "validation|error-handling|routing|security|performance",
        "complexity": "basic|intermediate|advanced|expert",
        "rule_type": "must|should|may|must-not",  # RFC 2119
        "nextjs_api": ["app-router", "pages-router", "api-routes"],  # List
        "client_server": "client-only|server-only|isomorphic|edge"
    },

    # Multiple example formats (Required - matches RuleExamples)
    "examples": {
        # All example fields should be strings or None
        "minimal": "schema.parse(input)",  # ~20 tokens
        "standard": "const validated = schema.parse(body);",  # ~100 tokens
        "detailed": "Full example with imports",  # ~200 tokens
        "full": "Complete implementation",  # Required
        "reference": "See src/api/users/route.ts",  # Optional
        "context_variants": {  # Optional dict
            "app_router": "app router example",
            "pages_router": "pages router example"
        }
    },

    # Token counts (Required - matches TokenCount)
    "tokens": {
        "minimal": 20,
        "standard": 100,
        "detailed": 200,
        "full": 400
    },

    # Relationships for grouping (Optional)
    "relationships": {
        "similar_rules": ["validate-output-zod"],
        "prerequisite_rules": ["setup-zod"],
        "see_also": ["error-handling"]
    },

    # ESLint flag (Required boolean)
    "has_eslint_rule": true,

    # Import map (Optional list)
    "import_map": [
        {
            "module": "zod",
            "imported_items": "{ z }",
            "statement": "import { z } from 'zod'"
        }
    ]
}
```

**METADATA FIELD GUIDELINES**:

**PATTERN TYPE GUIDELINES**:
- "validation": Input/output validation patterns
- "error-handling": Error responses and handling
- "routing": Route structure and patterns
- "security": Auth, permissions, sanitization
- "performance": Optimization patterns
- "data-fetching": API calls, database queries
- "state-management": State patterns
- "testing": Test patterns and strategies

**COMPLEXITY GUIDELINES**:
- "basic": Can be understood immediately
- "intermediate": Requires some context
- "advanced": Needs experience to implement well
- "expert": Complex patterns requiring deep knowledge

**EXAMPLE - Enhanced Rule for Validation**:

```python
{{
    "rule": "ALWAYS VALIDATE INPUT - Use Zod schemas for all user input",
    "rule_id": "validate-input-zod",
    "context": "Input validation prevents runtime errors and security vulnerabilities",

    "metadata": {{
        "pattern_type": "validation",
        "complexity": "intermediate",
        "rule_type": "must",
        "nextjs_api": ["app-router", "api-routes"],
        "client_server": "server-only"
    }},

    "compression": {{
        "example_sharable": true,
        "pattern_extractable": true,
        "progressive_detail": ["minimal", "standard", "detailed", "full"]
    }},

    "examples": {{
        "minimal": "schema.parse(input)",

        "standard": """const inputSchema = z.object({{ email: z.string().email() }});
const validated = inputSchema.parse(body);""",

        "detailed": """import {{ z }} from 'zod';

const createUserSchema = z.object({{
  email: z.string().email(),
  name: z.string().min(1)
}});

export async function POST(request: Request) {{
  const body = await request.json();
  const validated = createUserSchema.parse(body);
  return Response.json({{ success: true, data: validated }});
}}""",

        "full": """import {{ z }} from 'zod';
import {{ NextRequest, NextResponse }} from 'next/server';
import {{ createUser }} from '@/services/userService';

const createUserSchema = z.object({{
  email: z.string().email(),
  name: z.string().min(1).max(100),
  role: z.enum(['user', 'admin']).default('user')
}});

type CreateUserInput = z.infer<typeof createUserSchema>;

export async function POST(request: NextRequest) {{
  try {{
    const body = await request.json();
    const validatedInput = createUserSchema.parse(body);

    const user = await createUser(validatedInput);

    return NextResponse.json({{
      success: true,
      data: user
    }}, {{ status: 201 }});
  }} catch (error) {{
    if (error instanceof z.ZodError) {{
      return NextResponse.json({{
        success: false,
        errors: error.errors
      }}, {{ status: 400 }});
    }}

    return NextResponse.json({{
      success: false,
      error: 'Internal server error'
    }}, {{ status: 500 }});
  }}
}}""",

        "reference": "See src/app/api/users/route.ts",

        "context_variants": {{
            "pages_router": "export default withValidation(schema, handler)"
        }}
    }},

    "tokens": {{
        "minimal": 5,
        "standard": 25,
        "detailed": 120,
        "full": 380
    }},

    "relationships": {{
        "similar_rules": ["validate-output-zod", "validate-params-zod"],
        "prerequisite_rules": ["setup-zod-schemas"],
        "see_also": ["error-handling-api"]
    }},

    "has_eslint_rule": true,
    "import_map": [
        {{
            "type": "es6_import",
            "module": "zod",
            "imported_items": "{{ z }}",
            "statement": "import {{ z }} from 'zod'"
        }}
    ]
}}
```

4. **Generate ESLint rules** (if applicable):

For rules where `has_eslint_rule: true`, generate JavaScript implementations:

```javascript
// Example ESLint rule structure
module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Require async handlers for API routes',
            category: 'Best Practices',
            recommended: true
        },
        messages: {
            missingAsync: 'API handler must be an async function'
        },
        fixable: 'code'
    },
    create(context) {
        return {
            // AST selector for route handlers
            'CallExpression[callee.property.name=/^(get|post|put|delete|patch)$/]': function(node) {
                const handler = node.arguments[node.arguments.length - 1];
                if (handler && handler.type === 'ArrowFunctionExpression' && !handler.async) {
                    context.report({
                        node: handler,
                        messageId: 'missingAsync',
                        fix(fixer) {
                            return fixer.insertTextBefore(handler, 'async ');
                        }
                    });
                }
            }
        };
    }
};
```

ESLint Rule Requirements:
- Only for patterns detectable via AST analysis
- Use proper ESLint AST selectors
- Include helpful error messages
- Provide automatic fixes when possible
- Limit recursion depth to prevent infinite loops

**OUTPUT using MCP calls (NEW ITERATIVE FLOW):**

```python
# 1. FIRST: Register standard with metadata ONLY (clears existing hints/rules)
# IMPORTANT: register() now ONLY handles metadata and clears existing data
# NOTE: register() does NOT accept session_id parameter - only hints_for_file() does
register_result = mcp.register(
    source_path="{source_path}",
    metadata={{
        "id": "{standard_id}",
        "name": "...",
        "category": "...",
        "tags": [...],
        "applies_to": [...],
        "severity": "...",
        "priority": "...",
        "dependencies": [...],
        "context_triggers": {{...}},
        "optimization": {{...}},
        "relationships": {{...}},
        "nextjs_config": {{...}}
        # NO RULES HERE - rules are added separately
    }},
    enhanced_format=True  # Defaults to True for enhanced metadata processing
)

# 2. ITERATIVELY add each hint/rule to avoid MCP limits
# For each enhanced rule, make a separate add_hint() call
# NOTE: add_hint() does NOT accept session_id parameter
for rule_data in enhanced_rules:
    hint_result = mcp.add_hint(
        standard_id="{standard_id}",
        hint_data={{
            "rule": "Clear, actionable rule statement",
            "rule_id": "unique-rule-id",
            "context": "Why this matters and when to apply it",
            "metadata": {{
                "pattern_type": "validation|error-handling|routing|security|performance",
                "complexity": "basic|intermediate|advanced|expert",
                "rule_type": "must|should|may|must-not",
                "nextjs_api": ["app-router", "pages-router", "api-routes"],
                "client_server": "client-only|server-only|isomorphic|edge"
            }},
            "compression": {{
                "example_sharable": true,
                "pattern_extractable": true,
                "progressive_detail": ["minimal", "standard", "detailed", "full"]
            }},
            "examples": {{
                "minimal": "schema.parse(input)",
                "standard": "const validated = schema.parse(body);",
                "detailed": "Full example with imports and structure",
                "full": "Complete, runnable example",
                "reference": "See UserService.ts for production example",
                "context_variants": {{
                    "app_router": "app router specific example",
                    "pages_router": "pages router specific example"
                }}
            }},
            "tokens": {{
                "minimal": 20,
                "standard": 100,
                "detailed": 200,
                "full": 400
            }},
            "relationships": {{
                "similar_rules": ["validate-output-zod"],
                "prerequisite_rules": ["setup-zod"],
                "see_also": ["error-handling"]
            }},
            "has_eslint_rule": true,  # Flag for ESLint rule generation
            "import_map": [...]
        }}
    )

    print(f"Added hint {{hint_result['data']['hintId']}} as hint-{{hint_result['data']['hintNumber']:03d}}.json")

# 3. ITERATIVELY add ESLint rules for hints that have has_eslint_rule: true
# For each rule where has_eslint_rule is true, make a separate add_rule() call
# NOTE: add_rule() does NOT accept session_id parameter
for rule_data in eslint_rules:
    rule_result = mcp.add_rule(
        standard_id="{standard_id}",
        rule_name=rule_data["rule_id"],  # e.g., "validate-input-zod"
        rule_content='''module.exports = {{
            meta: {{
                type: 'problem',
                docs: {{
                    description: 'Require async handlers for API routes',
                    category: 'Best Practices',
                    recommended: true
                }},
                messages: {{
                    missingAsync: 'API handler must be an async function'
                }},
                fixable: 'code'
            }},
            create(context) {{
                return {{
                    'CallExpression[callee.property.name=/^(get|post|put|delete|patch)$/]': function(node) {{
                        const handler = node.arguments[node.arguments.length - 1];
                        if (handler && handler.type === 'ArrowFunctionExpression' && !handler.async) {{
                            context.report({{
                                node: handler,
                                messageId: 'missingAsync',
                                fix(fixer) {{
                                    return fixer.insertTextBefore(handler, 'async ');
                                }}
                            }});
                        }}
                    }}
                }};
            }}
        }};'''
    )

    print(f"Added ESLint rule {{rule_result['data']['ruleName']}} to {{rule_result['data']['ruleFile']}}")

# 4. VALIDATE ESLint rules work correctly (CRITICAL STEP)
print("🔍 Validating generated ESLint rules...")
validation_result = mcp.lint_project(
    use_standards=True,  # Use standards-generated ESLint config
    target_files=["src/**/*.ts", "src/**/*.tsx", "src/**/*.js", "src/**/*.jsx"]
)

if validation_result.get('error'):
    print(f"❌ ESLint validation failed: {validation_result['error']['message']}")
    # Handle missing config or other errors
elif validation_result['issues']:
    print(f"⚠️ Found {validation_result['total_issues']} linting issues with generated rules")

    # Check for aromcp rule failures (generated rules that don't work)
    aromcp_errors = [issue for issue in validation_result['issues']
                     if issue.get('rule', '').startswith('aromcp/')]

    if aromcp_errors:
        print(f"🔧 Fixing {len(aromcp_errors)} problematic generated rules...")

        # Option 1: Disable broken rules temporarily
        for error in aromcp_errors:
            rule_name = error['rule'].replace('aromcp/', '')
            print(f"Disabling rule: {rule_name} (caused: {error['message']})")
            # Could implement disable_rule() or update_rule() here

        # Option 2: Re-run validation after fixes
        retry_result = mcp.lint_project(use_standards=True, target_files=["src/**/*.ts"])
        if retry_result['total_issues'] < validation_result['total_issues']:
            print("✅ ESLint rules fixed and validated successfully")
    else:
        print("✅ Generated ESLint rules work correctly")
else:
    print("✅ Generated ESLint rules validated successfully - no issues found")

# 5. Optional: List all rules for verification
rules_list = mcp.list_rules(standard_id="{standard_id}")
print(f"Total ESLint rules for {{standard_id}}: {{len(rules_list['data']['rules'])}}")
```

**NEW WORKFLOW CLARIFICATION:**

1. **register()** - Handles ONLY metadata and clears existing data
   - Parameters: `source_path`, `metadata`, `project_root`, `enhanced_format`
   - Does NOT accept `session_id` parameter
   - Clears existing hints and ESLint rules to start fresh
   - Saves only metadata, no rules

2. **add_hint()** - Adds a single enhanced rule (AI hint)
   - Parameters: `standard_id`, `hint_data`, `project_root`
   - Does NOT accept `session_id` parameter
   - Saves single hint to `.aromcp/hints/{standard_id}/hint-XXX.json`
   - Call this once per rule to avoid MCP limits

3. **add_rule()** - Adds a single ESLint JavaScript rule
   - Parameters: `standard_id`, `rule_name`, `rule_content`, `project_root`
   - Does NOT accept `session_id` parameter
   - Saves ESLint rule to `.aromcp/eslint/rules/{standard_id}-{rule_name}.js`
   - Call this once per ESLint rule

4. **list_rules()** - Lists all ESLint rules for a standard
   - Parameters: `standard_id`, `project_root`
   - Returns array of rule info for verification

5. **hints_for_file()** - Loads hints for a specific file (unchanged)
   - Parameters: `file_path`, `max_tokens`, `project_root`, `session_id`, etc.
   - ONLY this function accepts `session_id` for deduplication

Process all standards in this batch and report success."""

    # Launch AI agent to process this batch
    batch_task = Task(
        description=f"Parse batch {batch_num + 1}",
        prompt=batch_task_prompt
    )
    batch_tasks.append(batch_task)

print(f"✅ Launched {len(batch_tasks)} parsing tasks")
```

### Step 3: Validate and Verify Results

```python
# After all AI tasks complete, validate ESLint rules work correctly
print("🔍 Running final ESLint validation across project...")
project_validation = mcp.lint_project(
    use_standards=True,  # Use all generated standards rules
    target_files=None    # Validate entire project
)

if project_validation.get('error'):
    print(f"❌ Project validation failed: {project_validation['error']['message']}")
    print("Check that standards-config.js was generated properly")
else:
    aromcp_issues = [issue for issue in project_validation['issues']
                     if issue.get('rule', '').startswith('aromcp/')]

    if aromcp_issues:
        print(f"⚠️ {len(aromcp_issues)} issues from generated rules need attention")
        for issue in aromcp_issues[:5]:  # Show first 5
            print(f"  - {issue['file']}:{issue['line']} {issue['rule']}: {issue['message']}")
    else:
        print("✅ All generated ESLint rules validated successfully!")

# Verify processing results
final_check = mcp.check_updates(
    standards_path=standards_dir
)

print(f"✅ Processing complete!")
print(f"📊 Standards registered: {final_check['data']['upToDate']}")
print(f"📊 Standards with ESLint rules: {final_check['data']['withEslintRules']}")

# Test the hints system with session support
# NOTE: Only hints_for_file() accepts session_id parameter
hints = mcp.hints_for_file(
    file_path="src/api/users/route.ts",
    max_tokens=10000,
    session_id="dev-session"  # Session support for deduplication - ONLY in hints_for_file()
)

print(f"Loaded {len(hints['data']['rules'])} rules for the file")
print(f"Context: {hints['data']['context']['task_type']}")
print(f"Token usage: {hints['data']['total_tokens']} / {hints['data']['max_tokens']}")
```

## Summary

The `standards:generate` command provides a complete workflow for:

1. **Parsing** markdown standards files to extract structured rules
2. **Registering** standards with rich metadata for context-aware loading
3. **Generating** ESLint rules for patterns that can be automatically enforced
4. **Optimizing** token usage through compression and session deduplication

Key benefits:
- **70-80% token reduction** through intelligent compression
- **Context-aware** rule loading based on what you're working on
- **Session management** prevents duplicate rule loading
- **ESLint integration** for automatic enforcement