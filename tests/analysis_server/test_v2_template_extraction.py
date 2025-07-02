"""
Tests for V2 template extraction with enhanced documentation format.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from aromcp.analysis_server.tools.extract_templates_from_standards import extract_templates_from_standards_impl
from aromcp.analysis_server.tools.analyze_standards_for_rules import analyze_standards_for_rules_impl


class TestV2TemplateExtraction:
    """Test cases for V2 template extraction with comprehensive documentation format."""

    def test_comprehensive_v2_template_extraction(self):
        """Test extraction from comprehensive V2 template format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create standards directory
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create simplified V2 standard for testing core functionality
            v2_standard_content = """---
id: api-route-structure
name: API Route Structure Standard
category: api
tags: [routes, api, structure, typescript]
applies_to: ["**/api/**/*.ts", "**/routes/**/*.ts"]
severity: error
updated: 2024-01-15
priority: required
dependencies: [type-safety-checklist, security-standards]
description: Standardized structure and patterns for API route implementation
---

# API Route Structure Standard

## 🚨 CRITICAL RULES
1. **NEVER** expose sensitive data - always use response schemas
2. **ALWAYS** validate input using Zod schemas - prevents injection attacks

## Core Requirements
- **Input Validation**: All inputs must be validated using Zod schemas
- **Error Handling**: Consistent error response format
- **Authentication**: Proper auth middleware integration

## Naming Conventions
| Item | Pattern | Example |
|------|---------|---------|
| Route Files | kebab-case | `user-profile.ts` |
| Handler Functions | camelCase | `getUserProfile` |

## Examples

### ✅ CORRECT: Proper API Route Structure
```typescript
// Good example
const schema = z.object({ id: z.string() });
```

### ❌ INCORRECT: Missing Validation
```typescript
// Bad example
const id = req.query.id; // No validation
```

## Common Mistakes & Anti-Patterns

### 1. Missing Input Validation
**Why it's problematic:** Security vulnerabilities and runtime errors

❌ **Don't do this:**
```typescript
const userId = req.query.id;
```

✅ **Do this instead:**
```typescript
const { userId } = UserIdSchema.parse(req.query);
```

## Pattern Detection
```yaml
detect:
  patterns:
    - file_pattern: "**/api/**/*.ts"
    - missing_validation: "z.object"

validation:
  - must_have_schema: true
```

## Auto-Fix Configuration
```yaml
fixable: partial
fixes:
  - pattern: "req.query"
    replacement: "InputSchema.parse(req.query)"
```
"""
            
            with open(os.path.join(standards_dir, "api-route-structure.md"), 'w') as f:
                f.write(v2_standard_content)
                
            # Run template extraction
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                output_dir=".aromcp/templates",
                project_root=temp_dir
            )
            
            # Verify extraction success
            assert "data" in result
            assert result["data"]["templates_extracted"] == 1
            
            # Check template metadata
            template = result["data"]["templates"][0]
            assert template["standard_id"] == "api-route-structure"
            assert template["has_good_examples"] is True
            assert template["has_bad_examples"] is True
            assert template["has_pattern_detection"] is True
            assert template["enforcement_type"] == "hybrid"  # Has both automation and critical rules
            
            # Verify extracted data file
            data_file = os.path.join(temp_dir, ".aromcp", "templates", "data", "api-route-structure_template_data.json")
            assert os.path.exists(data_file)
            
            with open(data_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
                
            # Verify comprehensive extraction
            assert template_data["id"] == "api-route-structure"
            assert template_data["template_version"] == "v2"
            assert template_data["category"] == "api"
            assert template_data["priority"] == "required"
            assert template_data["tags"] == ["routes", "api", "structure", "typescript"]
            assert template_data["dependencies"] == ["type-safety-checklist", "security-standards"]
            
            # Verify critical rules extraction
            assert template_data["has_critical_rules"] is True
            assert len(template_data["critical_rules"]) == 2
            assert template_data["critical_rules"][0]["type"] == "NEVER"
            
            # Verify core requirements
            assert len(template_data["core_requirements"]) == 3
            assert template_data["core_requirements"][0]["requirement"] == "Input Validation"
            
            # Verify naming conventions
            assert "route files" in template_data["naming_conventions"]
            assert template_data["naming_conventions"]["route files"]["pattern"] == "kebab-case"
            
            # Verify examples
            assert len(template_data["correct_examples"]) == 1
            assert len(template_data["incorrect_examples"]) == 1
            
            # Verify common mistakes
            assert len(template_data["common_mistakes"]) == 1
            assert template_data["common_mistakes"][0]["name"] == "Missing Input Validation"
            
            # Verify pattern detection and auto-fix
            assert "detect" in template_data["pattern_detection"]
            assert template_data["auto_fix"]["fixable"] == "partial"
            
            # Verify complexity score
            assert template_data["complexity_score"] > 0.5  # Should be high complexity

    def test_v2_standards_analysis_enhanced_metadata(self):
        """Test that standards analysis properly handles V2 template metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create V2 template standard
            v2_content = """---
id: component-patterns
name: Component Design Patterns
category: frontend
tags: [components, react, patterns]
applies_to: ["**/*.tsx", "**/*.jsx"]
severity: error
priority: important
---

# Component Design Patterns

## 🚨 CRITICAL RULES
1. **ALWAYS** use TypeScript for type safety

## Core Requirements
- **Props Validation**: All props must be typed
- **Error Boundaries**: Wrap components in error boundaries

## Common Mistakes & Anti-Patterns
### 1. Missing Prop Types
**Why it's problematic:** Runtime errors

## Pattern Detection
```yaml
detect:
  - missing_types: true
```

## Auto-Fix Configuration
```yaml
fixable: true
```
"""
            
            with open(os.path.join(standards_dir, "component-patterns.md"), 'w') as f:
                f.write(v2_content)
                
            # Run analysis
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            standards = result["data"]["standards"]
            assert len(standards) == 1
            
            standard = standards[0]
            
            # Verify V2 metadata extraction
            assert standard["id"] == "component-patterns"
            assert standard["template_version"] == "v2"
            assert standard["priority"] == "important"
            assert standard["tags"] == ["components", "react", "patterns"]
            assert standard["has_critical_rules"] is True
            assert standard["has_core_requirements"] is True
            assert standard["has_common_mistakes"] is True
            assert standard["has_patterns"] is True
            assert standard["has_auto_fix"] is True
            assert standard["enforcement_type"] == "hybrid"
            assert standard["complexity_score"] > 0.3
            
            # Verify generation hints
            hints = result["data"]["generation_hints"]
            assert "component-patterns" in hints["hybrid_standards"]
            assert "component-patterns" in hints["template_v2_standards"]
            assert "generation_strategy" in hints
            assert hints["generation_strategy"]["prefer_hybrid_for_complex"] is True

    def test_backward_compatibility_with_v1_templates(self):
        """Test that V1 templates still work alongside V2 templates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create V1 style template
            v1_content = """---
id: old-style-standard
name: Old Style Standard
category: general
applies_to: ["**/*.js"]
severity: warning
---

# Old Style Standard

## Description
This is an old style standard.

## Good Examples
```javascript
const good = true;
```

## Bad Examples
```javascript
var bad = true;
```

## Enforcement Type
- [x] ESLint Rule (pattern-based detection)
"""
            
            # Create V2 style template
            v2_content = """---
id: new-style-standard
name: New Style Standard
category: frontend
tags: [modern, typescript]
priority: required
---

# New Style Standard

## 🚨 CRITICAL RULES
1. **ALWAYS** use modern syntax

## Core Requirements
- **Type Safety**: Use TypeScript
"""
            
            with open(os.path.join(standards_dir, "old-style.md"), 'w') as f:
                f.write(v1_content)
            with open(os.path.join(standards_dir, "new-style.md"), 'w') as f:
                f.write(v2_content)
                
            # Run analysis
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            standards = result["data"]["standards"]
            assert len(standards) == 2
            
            # Find each standard
            v1_standard = next(s for s in standards if s["id"] == "old-style-standard")
            v2_standard = next(s for s in standards if s["id"] == "new-style-standard")
            
            # Verify V1 standard processed correctly
            assert v1_standard["template_version"] == "v1"
            assert v1_standard["has_critical_rules"] is False
            assert v1_standard["has_core_requirements"] is False
            assert v1_standard["enforcement_type"] == "eslint_rule"  # From explicit checkbox
            
            # Verify V2 standard processed correctly  
            assert v2_standard["template_version"] == "v2"
            assert v2_standard["has_critical_rules"] is True
            assert v2_standard["has_core_requirements"] is True
            assert v2_standard["enforcement_type"] == "ai_context"  # Inferred from structure
            assert v2_standard["priority"] == "required"
            assert v2_standard["tags"] == ["modern", "typescript"]
            
            # Verify generation hints handle both versions
            hints = result["data"]["generation_hints"]
            assert "old-style-standard" in hints["eslint_capable"]
            assert "new-style-standard" in hints["ai_context_only"]
            assert len(hints["template_v2_standards"]) == 1
            assert "new-style-standard" in hints["template_v2_standards"]