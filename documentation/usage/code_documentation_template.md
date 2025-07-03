---
# YAML Frontmatter - Machine-readable metadata for tooling and automation
id: {unique-identifier}  # Kebab-case identifier matching filename
name: {Human Readable Name}  # Display name for the standard
category: {category}  # Primary category: pipeline, api, database, security, etc.
tags: [{tag1}, {tag2}]  # Searchable tags for discovery
applies_to: ["path/pattern/**/**.ts"]  # File glob patterns where this applies
severity: error  # error | warning | info - How violations are treated
updated: {YYYY-MM-DDTHH:mm:ss}  # ISO timestamp - Can be automated via git hooks or CI/CD
priority: required  # required | recommended | optional
dependencies: [{standard-id}]  # Other standards that must be followed with this one
description: {One-line description for quick scanning}
---

# {Standard Name}

<!--
TEMPLATE USAGE GUIDE:
- REQUIRED sections: Critical Rules, Overview, Examples (at least 1 correct), Quick Reference
- RECOMMENDED sections: Common Mistakes, Migration Guide (for existing code), Automation
- OPTIONAL sections: All others - include based on relevance to your standard
- This template is designed for AI/tooling consumption - verbosity is acceptable
-->

<!-- Version banner - Keep at top for visibility -->
_Updated: {YYYY-MM-DD} - {Brief description of latest changes}_

## 🚨 Critical Rules
<!-- Non-negotiable rules that MUST be followed. Keep to 5 or fewer. -->
1. **{RULE IN CAPS}** - {Brief explanation}
2. **{RULE IN CAPS}** - {Brief explanation}

## Overview
<!-- REQUIRED: 2-3 paragraphs explaining what this standard provides and why it exists -->
{What problem does this solve?}

{What benefits does following this standard provide?}

{When should this standard be applied?}

## Core Requirements
<!-- OPTIONAL: Bullet list of key requirements. More detailed than critical rules but still concise -->
- **{Requirement}**: {Description}
- **{Requirement}**: {Description}

## Structure & Organization
<!-- OPTIONAL: How code/files should be organized when following this standard -->

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
| Item | Pattern | Example |
|------|---------|---------|
| {Item type} | {Pattern description} | `{example}` |

## Examples
<!-- REQUIRED: At least one correct example. Incorrect and refactoring examples are optional -->

### ✅ Correct Implementation
```typescript
// Explain why this is correct
{code example}
```

### ❌ Incorrect Implementation
<!-- OPTIONAL: Show what NOT to do -->
```typescript
// Explain what's wrong
{code example}
```

### 📝 Refactoring Example
<!-- OPTIONAL: Show before/after to guide migration -->
<details>
<summary>Before → After Transformation</summary>

**Before:**
```typescript
{old code}
```

**After:**
```typescript
{new code}
```
</details>

## Common Mistakes
<!-- OPTIONAL BUT RECOMMENDED: Focus on the most frequent errors. Include "Why it's problematic" -->

### 1. {Mistake Name}
**Why it's problematic:** {Explanation}

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
| {Scenario} | {Approach} | {Why} |

## Implementation Details
<!-- OPTIONAL: Detailed examples, API references, etc. -->
<details>
<summary>📁 Complete Implementation Example</summary>

```typescript
{comprehensive example}
```
</details>

## Testing
<!-- OPTIONAL: How to test code following this standard -->
```typescript
{test example}
```

## Performance & Security
<!-- OPTIONAL: Only include if relevant to the standard -->
- **{Consideration}**: {Explanation}

## Migration Guide
<!-- OPTIONAL BUT RECOMMENDED for existing codebases: Steps to migrate existing code -->
1. **{Step}**: {Description}
2. **{Step}**: {Description}

## Automation
<!-- OPTIONAL BUT RECOMMENDED: Pattern detection and auto-fix rules for tooling -->

### Pattern Detection
```yaml
detect:
  patterns:
    - pattern: "{regex}"  # {What this detects}
  exclude:
    - "**/node_modules/**"
    - "**/*.test.ts"
```

### Auto-Fix Rules
```yaml
fixable: {true|false|partial}
fixes:
  - pattern: "{regex}"
    replacement: "{replacement}"
    message: "{error message}"
```

## Related Standards
<!-- OPTIONAL: Link to related documentation -->
- [{Standard Name}](./{filename}.md) - {Relationship}

## Quick Reference
<!-- REQUIRED: Summary for easy scanning -->
⭐ **ALWAYS**: {Do this}
📝 **PREFER**: {Do this when possible}
🚫 **NEVER**: {Don't do this}
🔧 **USE**: {Tool/pattern} for {purpose}

---
<!-- Footer with metadata -->
*Standard ID: `{id}` | Category: `{category}` | Priority: `{priority}`*

<!--
SECTION REQUIREMENTS SUMMARY:
✅ REQUIRED: Critical Rules, Overview, Examples (≥1 correct), Quick Reference
👍 RECOMMENDED: Common Mistakes, Migration Guide, Automation
➕ OPTIONAL: Core Requirements, Structure & Organization, Testing, Performance & Security, Implementation Details, Decision Guide, Related Standards

Remember: This document will be processed by AI/tooling - comprehensive detail is beneficial!
-->