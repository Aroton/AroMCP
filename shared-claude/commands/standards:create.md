# Create Coding Standard

**Command**: `standards:create`

**Description**: Interactively create a new coding standard using the template at ~/.claude/templates/code-standards-template.md

## Usage

```bash
# Create new standard interactively
claude standards:create

# Create with initial ID
claude standards:create api-validation

# Create in current project directory
claude standards:create
```

## Process Overview

I'll guide you through creating a comprehensive coding standard by:
1. Checking for `.aromcp/.standards-dir` file to determine standards directory (defaults to "standards")
2. Asking clarifying questions about your requirements
3. Using the template at `~/.claude/templates/code-standards-template.md`
4. Ensuring all required sections are populated
5. Generating AI hint metadata for the `standards:generate` command

## Interactive Creation Process

### Step 1: Understand the Standard's Purpose

Let me understand what you're trying to standardize:

**Core Questions:**
1. What specific problem or pattern are you addressing?
2. Can you give me a concrete example of code that should follow this standard?
3. What goes wrong when developers don't follow this pattern?
4. Is this for a specific framework/library (Next.js, React, etc.)?

### Step 2: Gather Basic Metadata

**Standard Identity:**
- **ID** (kebab-case): How should we identify this? (e.g., `api-error-handling`)
- **Name**: Human-readable name? (e.g., "API Error Handling Standard")
- **Category**: Which category fits best?
  - `api` - API routes, endpoints, REST/GraphQL
  - `frontend` - UI components, client-side logic
  - `backend` - Server logic, services, data processing
  - `database` - Data models, queries, migrations
  - `testing` - Test patterns, mocking, assertions
  - `security` - Auth, validation, sanitization
  - `performance` - Optimization, caching, efficiency
  - `pipeline` - Data transformation, streaming
- **Tags**: What keywords describe this? (comma-separated)

### Step 3: Define Scope and Application

**Where does this standard apply?**
- File patterns (e.g., `**/api/**/*.ts`, `**/*.tsx`)
- Specific Next.js contexts? (app router, pages router, middleware)
- Client-side only, server-side only, or both?
- Any specific file naming conventions?

**Standard Configuration:**
- **Severity**: `error` (must fix) | `warning` (should fix) | `info` (consider)
- **Priority**: `required` (non-negotiable) | `recommended` (best practice) | `optional` (nice to have)
- **Dependencies**: Other standards that must be followed with this one?

### Step 4: Define Critical Rules

**What are the 3-5 absolute MUST-FOLLOW rules?**

Consider including structural rules like:
- File organization patterns (e.g., "PLACE API routes in app/api/[resource]/route.ts")
- Naming conventions (e.g., "NAME components with PascalCase")
- Code organization (e.g., "SEPARATE business logic into services")

For each rule, I need:
1. The rule statement (start with ALWAYS/NEVER/MUST/PLACE/NAME/ORGANIZE)
2. Brief explanation of WHY this matters
3. What specific problems it prevents

Example format:
- **ALWAYS USE ZOD VALIDATION** - Prevents runtime type errors and security vulnerabilities
- **PLACE API ROUTES IN app/api/** - Follows Next.js conventions for automatic routing
- **NEVER RETURN RAW ERRORS** - Leaks implementation details to clients

### Step 5: Create Examples

**Correct Implementation:**
Please provide a complete, working example that demonstrates the RIGHT way. Include:
- All necessary imports
- Full function/component implementation
- Comments explaining key decisions

We need 4 complexity levels:
1. **Minimal** (~20 tokens): Just the core pattern
2. **Standard** (~100 tokens): Basic working implementation
3. **Detailed** (~200 tokens): With imports and structure
4. **Full**: Complete production-ready code

Note: We only need correct examples. Incorrect examples are not used by the hint system.

**Common Mistakes:**
What are 2-3 mistakes you see repeatedly? For each:
- What developers typically do wrong
- Why they do it (what's the misconception?)
- The correct approach

### Step 6: Core Requirements and Common Mistakes

**Core Requirements** (if beyond Critical Rules):
- What additional requirements support the critical rules?
- Any specific technical constraints?
- Required dependencies or configurations?

**Common Mistakes:**
What are 2-3 mistakes you see repeatedly? For each:
- What developers typically do wrong
- Why they do it (what's the misconception?)
- The correct approach

### Step 7: AI Hint and Automation Configuration

**For AI hint generation (hints_for_file compatibility):**

Each rule in your standard will be converted to this structure:

**Rule Structure Requirements:**
- **rule**: Clear, actionable statement (e.g., "ALWAYS validate input with Zod schemas")
- **rule_id**: Unique kebab-case ID (e.g., "validate-input-zod")
- **context**: Why this matters (1-2 sentences)

**Rule Metadata** (for each rule):
- **pattern_type**: What kind of pattern is this?
  - `validation` - Input/output validation
  - `error-handling` - Error responses and handling
  - `routing` - Route structure and patterns
  - `security` - Auth, permissions, sanitization
  - `performance` - Optimization patterns
- **complexity**: How difficult to implement?
  - `basic` - Can be understood immediately
  - `intermediate` - Requires some context
  - `advanced` - Needs experience to implement well
  - `expert` - Complex patterns requiring deep knowledge
- **rule_type** (RFC 2119): How mandatory?
  - `must` - Absolutely required
  - `should` - Strongly recommended
  - `may` - Optional but beneficial
  - `must-not` - Prohibited
- **nextjs_api**: Which Next.js features? (list)
  - `app-router` - App directory routes
  - `pages-router` - Pages directory
  - `api-routes` - API endpoints
- **client_server**: Where does this apply?
  - `client-only` - Browser only
  - `server-only` - Server only
  - `isomorphic` - Both environments
  - `edge` - Edge runtime

**Example Formats** (provide all 4 levels):
1. **Minimal** (~20 tokens): Just the core pattern
   - Example: `schema.parse(input)`
2. **Standard** (~100 tokens): Basic implementation
   - Example: 3-5 lines showing core usage
3. **Detailed** (~200 tokens): With imports and structure
   - Example: 8-12 lines with context
4. **Full**: Complete, production-ready implementation

**Context Triggers** (when to load this standard):
- **task_types**: [`api_development`, `component_development`, `testing`, `refactoring`]
- **architectural_layers**: [`api`, `service`, `presentation`, `data`]
- **code_patterns**: [`export async function POST`, `useState`, `z.object`]
- **import_indicators**: [`zod`, `next/server`, `@/lib/Pipeline`]
- **file_patterns**: [`**/routes/**/*.ts`, `**/api/**/*.ts`]
- **nextjs_features**: [`app-router`, `server-components`, `server-actions`]

**ESLint Automation**:
- Can this be detected via AST analysis? (sets `has_eslint_rule: true`)
- What AST selectors would find violations?
- Can violations be auto-fixed?
- What error message should show?

**Relationships** (for rule grouping):
- **similar_rules**: Rules that can be grouped together
- **prerequisite_rules**: Rules that must be understood first
- **see_also**: Related but different rules

### Step 8: Create the Standard

Now I'll create the complete standard file. First, let me determine the standards directory and load the template:

```bash
# Check for custom standards directory
if [ -f ".aromcp/.standards-dir" ]; then
    STANDARDS_DIR=$(cat .aromcp/.standards-dir)
else
    STANDARDS_DIR="standards"
fi

# Load the template using AroMCP read_files
aromcp.read_files(["~/.claude/templates/code-standards-template.md"])
```

Then create the standard at: `${STANDARDS_DIR}/{id}.md`

The generated file will include:

```yaml
---
# Basic metadata
id: {id}
name: {name}
category: {category}
tags: [{tags}]
applies_to: [{patterns}]
severity: {severity}
updated: {ISO timestamp}
priority: {priority}
dependencies: [{standard-ids}]
description: {one-line description}

# AI Hint Generation Metadata
context_triggers:
  task_types: [{task_types}]
  architectural_layers: [{layers}]
  code_patterns: [{patterns}]
  import_indicators: [{imports}]
  file_patterns: [{files}]
  nextjs_features: [{features}]

optimization:
  priority: {priority}
  load_frequency: {frequency}
  compressible: true
  cacheable: true
  example_reusability: {reusability}
  context_sensitive: true

relationships:
  similar_to: [{standards}]
  commonly_used_with: [{standards}]
  conflicts_with: []

# Next.js configuration (if applicable)
nextjs_config:
  router_preference: {router}
  rendering_strategy: {strategy}

# Version tracking
version: "1.0.0"
changelog:
  - version: "1.0.0"
    date: {date}
    changes: ["Initial version"]
---
```

Followed by all required sections:
- 🚨 Critical Rules (including structure/organization rules)
- Overview (problem/solution/benefits)
- Core Requirements (if applicable)
- Structure & Organization (if applicable - convert to rules)
- Examples (✅ Correct implementation with 4 levels)
- Common Mistakes
- Decision Guide (if applicable)
- Automation (with pattern detection and ESLint potential)
- Related Standards
- Quick Reference

### Step 9: Validation and Next Steps

After creating the file:

1. **Validate** all required sections are present
2. **Check** examples are complete and runnable
3. **Verify** metadata is properly formatted
4. **Suggest** running `standards:generate` to create AI hints

**Output Summary:**
```
✅ Created: {standards_dir}/{id}.md
📋 Category: {category}
🏷️  Tags: {tags}
⚡ Priority: {priority}
🎯 Applies to: {file count} files in your project

Next steps:
1. Review the generated standard
2. Run: claude standards:generate
3. Test: claude standards:validate {id}
```

## Error Handling

- Check if standard ID already exists
- Validate file patterns are valid globs
- Ensure examples have proper syntax
- Verify template exists at expected location

## State Management

The command will track progress in case of interruption:
- Save partial answers to `.claude/standards-create-state.json`
- Resume from last question if interrupted
- Clear state on successful completion