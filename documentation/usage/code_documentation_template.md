---
id: [kebab-case-unique-id]
name: [Human Readable Standard Name]
category: [api|database|frontend|architecture|security|pipeline|general]
tags: [keyword1, keyword2, keyword3]
applies_to: ["**/*.ts", "**/*.tsx"]
severity: [error|warning|info]
updated: YYYY-MM-DD
priority: [required|important|recommended]
dependencies: [related-standard-id-1, related-standard-id-2]
description: Brief one-line description for the standards index
---

# [Standard Name]

_Updated: YYYY-MM-DD - Brief summary of latest changes_

## 🚨 CRITICAL RULES
<!-- Only include this section for standards with critical/breaking rules -->
1. **NEVER** do X - it will cause Y
2. **ALWAYS** ensure Z - to prevent security vulnerabilities

## Overview
<!-- High-level introduction explaining what this standard covers, why it exists, and its importance to the project -->

Brief overview of what this standard enforces and why it's important. Include context about when this standard applies and its impact on the codebase.

## Core Requirements
<!-- Essential rules that must be followed -->
- **Requirement 1**: Clear, actionable requirement
- **Requirement 2**: Another requirement with rationale
- **Requirement 3**: Include the "why" behind each requirement

## [Main Pattern/Feature] Structure
<!-- Replace with actual pattern name, e.g., "API Route Structure", "Component Structure" -->

### Pattern Organization
```
feature/
├── components/       # Feature-specific components
├── hooks/           # Custom hooks
├── utils/           # Utility functions
└── types/           # TypeScript types
```

### Implementation Pattern
<!-- Describe the core pattern with a structural example -->
```typescript
// pattern-example.ts
export const patternExample = {
  // Show the expected structure
};
```

## Naming Conventions
<!-- Specific naming patterns for this standard -->
| Item | Pattern | Example |
|------|---------|---------|
| Files | kebab-case | `user-profile.tsx` |
| Components | PascalCase | `UserProfile` |
| Functions | camelCase | `getUserData` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |

## Examples

### ✅ CORRECT: [Descriptive Example Title]
```typescript
// src/correct/example.ts
// This follows the standard because:
// 1. It uses proper naming conventions
// 2. It follows the prescribed pattern
// 3. It includes proper error handling

export const correctImplementation = async () => {
  // Implementation details
};
```

### ❌ INCORRECT: [What Not to Do]
```typescript
// src/incorrect/example.ts
// This violates the standard because:
// 1. It uses incorrect naming
// 2. It breaks the pattern
// 3. It lacks error handling

export const badImplementation = () => {
  // Problematic code
};
```

### 📝 REFACTORING EXAMPLE
<!-- Show before/after for migrating existing code -->
**Before:**
```typescript
// Old pattern that needs updating
const oldWay = () => { /* ... */ };
```

**After:**
```typescript
// New pattern following the standard
const newWay = () => { /* ... */ };
```

## Common Mistakes & Anti-Patterns

### 1. [Common Mistake Name]
**Why it's problematic:** Explanation of the issue

❌ **Don't do this:**
```typescript
// Example of the anti-pattern
```

✅ **Do this instead:**
```typescript
// Correct implementation
```

### 2. [Another Common Mistake]
<!-- Add more as needed -->

## Decision Guide
<!-- When to use different approaches -->

| Scenario | Recommended Approach | Reason |
|----------|---------------------|---------|
| Simple CRUD operations | Use Pattern A | Maintains consistency |
| Complex business logic | Use Pattern B | Better separation of concerns |
| Real-time features | Use Pattern C | Optimized for performance |

## Complete Example
<!-- Comprehensive example showing all concepts together -->

<details>
<summary>📁 Full Implementation Example</summary>

```typescript
// src/features/example/complete-example.ts
// This example demonstrates all aspects of the standard

import { requiredImports } from './dependencies';

// 1. Proper structure
export class ExampleImplementation {
  // 2. Correct naming
  private readonly configOptions: ConfigType;

  // 3. Following all patterns
  constructor(options: ConfigType) {
    this.configOptions = options;
  }

  // 4. Error handling
  public async performAction(): Promise<Result> {
    try {
      // Implementation following the standard
      return await this.processData();
    } catch (error) {
      // Proper error handling
      throw new CustomError('Action failed', error);
    }
  }
}
```

</details>

## Testing Patterns
<!-- How to test code following this standard -->
```typescript
// example.test.ts
describe('Standard Compliance', () => {
  it('should follow the prescribed pattern', () => {
    // Test implementation
  });
});
```

## Security Considerations
<!-- Include only if relevant to the standard -->
- **Authentication**: Ensure all endpoints require proper auth
- **Input validation**: Always validate using Zod schemas
- **Data exposure**: Never expose sensitive fields

## Performance Considerations
<!-- Include only if relevant to the standard -->
- **Caching**: Consider caching for expensive operations
- **Batch operations**: Use batch processing for multiple items
- **Query optimization**: Ensure database queries are optimized

## Migration Guide
<!-- Steps to update existing code to comply with this standard -->
1. **Identify affected files**: Use `grep` to find instances
2. **Update imports**: Change from old to new pattern
3. **Refactor structure**: Follow the examples above
4. **Test thoroughly**: Ensure no regressions

## Related Standards
<!-- Link to related standards that should be considered together -->
- [Pipeline Architecture](./pipeline-pattern.md) - For overall architecture
- [API Standards](./api-standards.md) - For API-specific patterns
- [Type Safety](./type-safety-checklist.md) - For TypeScript guidelines

## Pattern Detection
<!-- Automated detection rules for tooling -->
```yaml
detect:
  patterns:
    - import_pattern: "from ['\"](\.\.\/){2,}" # Detect deep imports
    - file_pattern: "**/components/**/*.tsx"    # Component files
    - contains_any: ["oldPattern", "deprecated"] # Legacy patterns

  exclude:
    - "**/node_modules/**"
    - "**/*.test.ts"
    - "**/*.spec.ts"

validation:
  - must_have_export: true
  - must_have_types: true
  - max_file_lines: 500
```

## Auto-Fix Configuration
<!-- Automated fixing rules if applicable -->
```yaml
fixable: partial
fixes:
  - pattern: "oldImport"
    replacement: "newImport"
  - pattern: /(\w+)Service/
    replacement: "$1Pipeline"

message_templates:
  import_violation: "Import '{import}' violates isolation rules"
  naming_violation: "Name '{name}' doesn't follow {expected} convention"
```

## Summary Rules
<!-- Quick reference checklist -->
1. ⭐ **ALWAYS** follow the naming conventions specified above
2. ⭐ **ALWAYS** include proper error handling
3. 📝 **ORGANIZE** files according to the prescribed structure
4. 🚫 **NEVER** bypass the validation layers
5. 🔧 **REFACTOR** existing code incrementally when touched
6. 📚 **DOCUMENT** any deviations with clear justification