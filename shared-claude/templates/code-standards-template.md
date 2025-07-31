---
# YAML Frontmatter - Machine-readable metadata for tooling and automation
id: {unique-identifier}  # Kebab-case identifier matching filename
name: {Human Readable Name}  # Display name for the standard
category: {category}  # Primary category: api, frontend, backend, database, testing, security, performance, pipeline
tags: [{tag1}, {tag2}]  # Searchable tags for discovery
applies_to: ["path/pattern/**/**.ts"]  # File glob patterns where this applies
severity: error  # error | warning | info - How violations are treated
updated: {YYYY-MM-DDTHH:mm:ss}  # ISO timestamp - Can be automated via git hooks or CI/CD
priority: required  # required | important | recommended | optional
dependencies: [{standard-id}]  # Other standards that must be followed with this one
description: {One-line description for quick scanning}

# AI Hint Generation Metadata (for standards:generate command)
context_triggers:
  task_types: []        # e.g., ["api_development", "component_development", "testing", "refactoring"]
  architectural_layers: []  # e.g., ["api", "service", "presentation", "data"]
  code_patterns: []     # e.g., ["export async function POST", "export const GET", "useState", "z.object"]
  import_indicators: [] # e.g., ["zod", "next/server", "@/lib/Pipeline"]
  file_patterns: []     # e.g., ["**/routes/**/*.ts", "**/api/**/*.ts"]
  nextjs_features: []   # e.g., ["app-router", "server-components", "server-actions"]

optimization:
  priority: high        # critical | high | medium | low
  load_frequency: common  # always | common | conditional | rare
  compressible: true    # Can examples be compressed?
  cacheable: true       # Can be cached across files?
  example_reusability: high  # high | medium | low
  context_sensitive: true    # Load based on context?

relationships:
  similar_to: []        # Related standards for grouping
  commonly_used_with: [] # Standards often used together
  conflicts_with: []    # Incompatible standards

# Next.js specific configuration (optional)
nextjs_config:
  router_preference: app  # app | pages
  rendering_strategy: server  # server | client | static
---

# {Standard Name}

<!--
TEMPLATE USAGE GUIDE:
- REQUIRED sections: Critical Rules, Overview, Examples (at least 1 correct), Quick Reference
- RECOMMENDED sections: Common Mistakes, Migration Guide (for existing code), Automation
- OPTIONAL sections: All others - include based on relevance to your standard
- This template is designed for AI/tooling consumption - verbosity is acceptable
-->

Updated: {YYYY-MM-DD} - {Brief description of latest changes}_

## 🚨 Critical Rules
<!-- Non-negotiable rules that MUST be followed. Keep to 5 or fewer. -->
<!-- Format: VERB + SPECIFIC ACTION - Explanation -->
1. **{RULE IN CAPS}** - {Brief explanation of why this is critical}
2. **{RULE IN CAPS}** - {Brief explanation of why this is critical}
3. **{RULE IN CAPS}** - {Brief explanation of why this is critical}

## Overview
<!-- REQUIRED: 2-3 paragraphs explaining what this standard provides and why it exists -->

**Problem**: {What specific problem does this solve?}

**Solution**: {How does this standard solve the problem?}

**Benefits**: {What benefits does following this standard provide?}

**When to Apply**: {In what situations should this standard be used?}

## Core Requirements
<!-- OPTIONAL: Bullet list of key requirements. More detailed than critical rules but still concise -->
- **{Requirement Category}**: {Specific requirement description}
- **{Requirement Category}**: {Specific requirement description}
- **{Requirement Category}**: {Specific requirement description}

## Structure & Organization
<!-- OPTIONAL: Convert file/folder structure into rules for the Critical Rules section -->
<!--
HINT GENERATION: Structure patterns should become rules in the Critical Rules section.
Examples:
- "ORGANIZE API routes in /app/api/[resource]/route.ts pattern"
- "NAME components using PascalCase with .tsx extension"
- "STRUCTURE services in /lib/services with single responsibility"

Each structural requirement should be a clear, actionable rule with examples.
-->

### File Organization
```
path/to/resource/
├── {file}.ts         # {Description}
├── {folder}/
│   └── {file}.ts     # {Description}
└── {folder}/
    └── {file}.ts     # {Description}
```

### Naming Conventions
<!-- OPTIONAL: Tables work well for naming patterns -->
| Item | Pattern | Example | Notes |
|------|---------|---------|-------|
| {Item type} | {Pattern description} | `{example}` | {When to use} |

## Examples
<!-- REQUIRED: Progressive complexity examples for optimal AI hint compression -->

### ✅ Correct Implementation

<!-- Minimal Pattern (~20 tokens) - Just the essential pattern -->
<details>
<summary>📄 Minimal Pattern</summary>

```typescript
{core.pattern()}
```
</details>

<!-- Standard Implementation (~100 tokens) - Common usage -->
<details>
<summary>📋 Standard Implementation</summary>

```typescript
{basic implementation with key imports}
```
</details>

<!-- Detailed Example (~200 tokens) - With context -->
<details>
<summary>📖 Detailed Example</summary>

```typescript
{more complete example showing structure}
```
</details>

<!-- Full Implementation - Complete, production-ready code -->
#### Full Implementation
```typescript
// Complete example with all imports, error handling, and edge cases
{full implementation}
```

<!-- Reference to real implementation -->
> 💡 **Production Example**: See `{path/to/real/file.ts}` for a complete real-world implementation.

## Common Mistakes
<!-- RECOMMENDED: Focus on the most frequent errors with clear explanations -->

### 1. {Mistake Name}
**Why developers do this**: {Common reasoning or misconception}
**Why it's problematic**: {Specific issues it causes}

❌ **Don't:**
```typescript
{bad example}
```

✅ **Do:**
```typescript
{good example}
```

### 2. {Mistake Name}
**Why developers do this**: {Common reasoning or misconception}
**Why it's problematic**: {Specific issues it causes}

❌ **Don't:**
```typescript
{bad example}
```

✅ **Do:**
```typescript
{good example}
```

## Decision Guide
<!-- OPTIONAL: Help developers choose the right approach -->
| Scenario | Recommended Approach | Reason |
|----------|---------------------|---------|
| {Specific situation} | {Approach to use} | {Why this is best} |
| {Specific situation} | {Approach to use} | {Why this is best} |

## Automation
<!-- RECOMMENDED: ESLint rules and detection patterns -->

### Pattern Detection
<!-- When should this standard be suggested by AI? -->
```yaml
# File patterns that need this standard
applies_to:
  - "**/api/**/*.ts"
  - "**/routes/**/*.ts"

# Code patterns that trigger this standard
triggers:
  - "export async function POST"
  - "export async function GET"
  - "request.json()"
```

### ESLint Rule Potential
<!-- Can this be automatically enforced? -->
```yaml
# Rule name (kebab-case, matching rule_id)
rule_name: "{kebab-case-rule-name}"

# What to detect (AST selectors)
detect:
  - selector: 'CallExpression[callee.property.name="json"]'
    without: 'CallExpression[callee.property.name="parse"]'

# Can violations be fixed automatically?
fixable: {true|false}

# Error message
message: "{What to tell developers}"
```

## Related Standards
<!-- OPTIONAL: Link to related documentation -->
- [{Standard Name}](./{filename}.md) - {How it relates}
- [{Standard Name}](./{filename}.md) - {How it relates}

## Quick Reference
<!-- REQUIRED: Summary for easy scanning - emojis help with visual scanning -->
⭐ **ALWAYS**: {Critical thing to always do}
📝 **PREFER**: {Best practice to follow when possible}
🚫 **NEVER**: {Critical thing to never do}
🔧 **USE**: {Tool/pattern} for {specific purpose}
💡 **TIP**: {Helpful tip for implementation}

---
<!-- Footer with metadata -->
*Standard ID: `{id}` | Category: `{category}` | Priority: `{priority}` | Version: `{version}`*

<!--
SECTION REQUIREMENTS SUMMARY:
✅ REQUIRED: Critical Rules, Overview, Examples (correct implementation with 4 levels), Quick Reference
👍 RECOMMENDED: Common Mistakes, Structure & Organization, Automation
➕ OPTIONAL: Core Requirements, Decision Guide, Related Standards

AI HINT GENERATION NOTES:
- Convert Structure & Organization into actionable rules in Critical Rules section
- Examples should have 4 levels: minimal, standard, detailed, full
- Include context_triggers in frontmatter for smart loading
- Add ESLint configuration in Automation for enforceable rules
-->