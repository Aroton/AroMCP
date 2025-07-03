---
id: [kebab-case-id]
name: [Human Readable Name]
category: [api|database|frontend|architecture|security|pipeline|general]
tags: [keyword1, keyword2]
applies_to: ["**/*.ts", "**/*.tsx"]
severity: [error|warning|info]
priority: [required|important|recommended]
---

# [Standard Name]

## Why & When
<!-- 2-3 sentences max: problem solved, when to apply -->
Brief explanation of the problem this solves and when it applies.

## Core Rules
<!-- Only the MUST-follow rules, numbered for reference -->
1. **NEVER** [critical prohibition] - [consequence]
2. **ALWAYS** [critical requirement] - [reason]
3. **USE** [pattern/convention] for [what]

## Pattern

### Structure
```
feature/
├── components/    # UI components
├── hooks/        # Custom hooks
└── types/        # TypeScript types
```

### Implementation
```typescript
// Minimal but complete example showing the pattern
export const pattern = {
  // Essential structure only
};
```

## Examples

### ✅ Correct
```typescript
// Why: Follows rules 1, 2, 3
const correctExample = async () => {
  // Minimal correct implementation
};
```

### ❌ Wrong
```typescript
// Violates: Rule 2 - missing error handling
const wrongExample = () => {
  // What not to do
};
```

## Common Mistakes
1. **[Mistake]**: [Why bad] → Use [solution] instead
2. **[Mistake]**: [Why bad] → Use [solution] instead

## Automation
<!-- For ESLint/tooling generation -->
```yaml
detect:
  patterns: ["oldPattern", "deprecated"]
  exclude: ["**/node_modules/**"]

fix:
  - replace: {from: "oldImport", to: "newImport"}
```

## Related
```yaml
dependencies:
  - id: pipeline-architecture
    reason: "Defines overall structure this pattern fits into"
  - id: api-standards
    reason: "Required for API endpoint implementations"
  - id: type-safety
    reason: "TypeScript conventions used throughout"
```