# Generate Standards and AI Hints

**Command**: `generate-standards`

**Description**: Processes markdown standards files through AI parsing to generate enhanced AI hints with context awareness and smart compression support.

**Features**: Session management, context-aware compression, and 70-80% token reduction through intelligent rule deduplication and progressive detail levels.

## Usage

```bash
# Generate from all standards in standards/ directory
claude generate-standards

# Generate from specific standards directory
claude generate-standards --standards-dir=custom/standards

# Generate with custom project root
claude generate-standards --project-root=/path/to/project

# Generate with session support (for testing hints_for_file)
claude generate-standards --session-id=test-session-123
```

## Parameters

- `--standards-dir` (optional): Directory containing markdown standards files (default: `standards`)
- `--project-root` (optional): Project root path (auto-detected if not specified)
- `--session-id` (optional): Session ID for testing hints_for_file deduplication (only affects hints_for_file calls, not register calls)

## Process Overview

This command:

1. **Discovery**: Find all markdown standards files that need processing
2. **AI Parsing**: Use AI agents to parse markdown and extract metadata + enhanced rules
3. **Registration**: Register standards with metadata only (clears existing hints/rules)
4. **Iterative Hint Addition**: Add AI hints one by one via add_hint
5. **Iterative Rule Addition**: Add ESLint rules one by one via add_rule
6. **Verification**: Confirm all standards are properly registered and rules are available

**Key Points:**
- **register()** handles only metadata and clears existing data
- **add_hint()** handles individual AI hints
- **add_rule()** handles individual ESLint JavaScript files

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

For each rule/hint, create this structure:

```python
{{
    "rule": "Clear, actionable rule statement",
    "rule_id": "unique-rule-id",  # e.g., "validate-input-zod"
    "context": "Why this matters and when to apply it",

    # Metadata for smart loading
    "metadata": {{
        "pattern_type": "validation|error-handling|routing|security|performance",
        "complexity": "basic|intermediate|advanced|expert",
        "rule_type": "must|should|may|must-not",  # RFC 2119
        "nextjs_api": ["app-router", "pages-router", "api-routes"],
        "client_server": "client-only|server-only|isomorphic|edge"
    }},

    # Compression configuration
    "compression": {{
        "example_sharable": true,  # Can share with similar rules?
        "pattern_extractable": true,  # Can extract to template?
        "progressive_detail": ["minimal", "standard", "detailed", "full"]
    }},

    # MULTIPLE EXAMPLE FORMATS (this is critical!)
    "examples": {{
        # Minimal: Ultra-compact pattern reminder (~20 tokens)
        "minimal": "schema.parse(input)",

        # Standard: Core pattern with context (~100 tokens)
        "standard": '''const validated = schema.parse(await request.json());
return createResponse(validated);''',

        # Detailed: More complete example (~200 tokens)
        "detailed": '''import {{ z }} from 'zod';

const schema = z.object({{ name: z.string() }});
export async function POST(request: Request) {{
  const validated = schema.parse(await request.json());
  return Response.json(validated);
}}''',

        # Full: Complete implementation (current format)
        "full": '''[YOUR CURRENT FULL EXAMPLE]''',

        # Reference to real file
        "reference": "See UserService.ts for production example",

        # Context-specific variants (optional)
        "context_variants": {{
            "app_router": "app router specific example",
            "pages_router": "pages router specific example"
        }}
    }},

    # Token counts for each format
    "tokens": {{
        "minimal": 20,
        "standard": 100,
        "detailed": 200,
        "full": 400  # Calculate actual count
    }},

    # Relationships to other rules
    "relationships": {{
        "similar_rules": ["validate-output-zod"],  # For grouping
        "prerequisite_rules": ["setup-zod"],  # Must understand first
        "see_also": ["error-handling"]
    }},

    # Integration fields
    "has_eslint_rule": true,
    "import_map": [...]  # Auto-generated
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
   - Your current format

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
    enhanced_format=True  # REQUIRED for enhanced metadata processing
)

# 2. ITERATIVELY add each hint/rule to avoid MCP limits
# For each enhanced rule, make a separate add_hint() call
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

# 4. Optional: List all rules for verification
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

### Step 3: Verify Results

```python
# After all AI tasks complete, verify processing
final_check = mcp.check_updates(
    standards_path="standards",
    project_root="."
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

The `generate-standards` command provides a complete workflow for:

1. **Parsing** markdown standards files to extract structured rules
2. **Registering** standards with rich metadata for context-aware loading
3. **Generating** ESLint rules for patterns that can be automatically enforced
4. **Optimizing** token usage through compression and session deduplication

Key benefits:
- **70-80% token reduction** through intelligent compression
- **Context-aware** rule loading based on what you're working on
- **Session management** prevents duplicate rule loading
- **ESLint integration** for automatic enforcement