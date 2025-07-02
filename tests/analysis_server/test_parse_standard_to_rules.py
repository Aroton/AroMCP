"""Tests for parse_standard_to_rules tool."""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aromcp.analysis_server.tools.parse_standard_to_rules import parse_standard_to_rules_impl


class TestParseStandardToRules:
    """Test class for parse_standard_to_rules functionality."""

    def test_basic_rule_extraction(self):
        """Test basic rule extraction from markdown content."""
        standard_content = """---
id: api-routes
name: API Route Standards
---

# API Route Standards

This document defines standards for API route handlers.

## Async Handlers Required

All route handlers must be async functions to handle database operations properly.

```typescript
// ✅ Good
router.get('/users', async (req, res) => {
  const users = await fetchUsers();
  res.json(users);
});

// ❌ Bad
router.get('/users', (req, res) => {
  fetchUsers().then(users => res.json(users));
});
```

## Error Handling

All routes must implement proper error handling.

```typescript
// ✅ Good
router.get('/users/:id', async (req, res) => {
  try {
    const user = await getUserById(req.params.id);
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="api-routes",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        assert data["standard_id"] == "api-routes"
        assert data["total_rules"] == 2
        
        rules = data["rules"]
        assert len(rules) == 2
        
        # Check first rule
        async_rule = rules[0]
        assert async_rule["name"] == "Async Handlers Required"
        assert async_rule["id"] == "api-routes-async-handlers-required"
        assert "async functions" in async_rule["description"]
        assert len(async_rule["examples"]["good"]) == 1
        assert len(async_rule["examples"]["bad"]) == 1
        
        # Check second rule
        error_rule = rules[1]
        assert error_rule["name"] == "Error Handling"
        assert error_rule["id"] == "api-routes-error-handling"
        assert len(error_rule["examples"]["good"]) == 1
        assert len(error_rule["examples"]["bad"]) == 0

    def test_rule_type_detection(self):
        """Test that rule types are correctly detected."""
        test_cases = [
            ("Function Naming Convention", "naming"),
            ("Code Structure Requirements", "structure"),
            ("Security Best Practices", "security"),
            ("Performance Optimization", "performance"),
            ("Syntax Patterns", "pattern"),
            ("General Guidelines", "general")
        ]
        
        for rule_name, expected_type in test_cases:
            standard_content = f"""# Test Standard

## {rule_name}

Description of the rule.
"""
            
            result = parse_standard_to_rules_impl(
                standard_content=standard_content,
                standard_id="test",
                extract_examples=False
            )
            
            assert "data" in result
            rules = result["data"]["rules"]
            assert len(rules) == 1
            assert rules[0]["type"] == expected_type

    def test_example_type_detection(self):
        """Test that good/bad examples are correctly identified."""
        standard_content = """# Test Standard

## Rule One

Description.

```javascript
// ✅ Good example
const result = await apiCall();
```

```javascript
// ❌ Bad example
const result = apiCall().then(data => data);
```

## Rule Two

Another rule.

```javascript
// This is correct
function goodExample() {
  return true;
}
```

```javascript
// Don't do this
function badExample() {
  return false;
}
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="test",
            extract_examples=True
        )

        assert "data" in result
        rules = result["data"]["rules"]
        assert len(rules) == 2
        
        # Rule one should have clear good/bad examples
        rule_one = rules[0]
        assert len(rule_one["examples"]["good"]) == 1
        assert len(rule_one["examples"]["bad"]) == 1
        assert "await apiCall()" in rule_one["examples"]["good"][0]["code"]
        assert "apiCall().then" in rule_one["examples"]["bad"][0]["code"]
        
        # Rule two should also have good/bad examples
        rule_two = rules[1]
        assert len(rule_two["examples"]["good"]) == 1
        assert len(rule_two["examples"]["bad"]) == 1

    def test_no_examples_handling(self):
        """Test handling of rules without code examples."""
        standard_content = """# Test Standard

## Rule Without Examples

This rule has no code examples, only text description.
It should still be extracted as a rule.

## Another Rule

This one also has no examples.
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="test",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        assert data["total_rules"] == 2
        assert data["rules_with_examples"] == 0
        
        rules = data["rules"]
        for rule in rules:
            assert len(rule["examples"]["good"]) == 0
            assert len(rule["examples"]["bad"]) == 0
            assert rule["description"] != ""

    def test_complex_markdown_structure(self):
        """Test parsing of complex markdown with nested headers."""
        standard_content = """# Main Standard

Introduction text.

## Category One

Category description.

### Specific Rule A

This is a specific rule under category one.

```python
# Good example
def function_name():
    pass
```

### Specific Rule B

Another specific rule.

## Category Two

### Rule Under Category Two

A rule in the second category.

```python
# Example for this rule
x = 1
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="complex",
            extract_examples=True
        )

        assert "data" in result
        rules = result["data"]["rules"]
        
        # Should extract rules from both h2 and h3 headers
        assert len(rules) >= 3
        
        rule_names = [rule["name"] for rule in rules]
        assert "Category One" in rule_names
        assert "Specific Rule A" in rule_names
        assert "Rule Under Category Two" in rule_names

    def test_multiple_languages(self):
        """Test extraction of examples in different programming languages."""
        standard_content = """# Multi-Language Standard

## Universal Rule

This rule applies to multiple languages.

```typescript
// TypeScript example
interface User {
  id: number;
  name: string;
}
```

```python
# Python example
class User:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
```

```javascript
// JavaScript example
const user = {
  id: 1,
  name: "John"
};
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="multi-lang",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        rules = data["rules"]
        assert len(rules) == 1
        
        rule = rules[0]
        examples = rule["examples"]["good"]
        assert len(examples) == 3
        
        languages = [ex["language"] for ex in examples]
        assert "typescript" in languages
        assert "python" in languages
        assert "javascript" in languages
        
        # Check summary
        summary_languages = data["summary"]["languages"]
        assert "typescript" in summary_languages
        assert "python" in summary_languages
        assert "javascript" in summary_languages

    def test_fixable_rule_detection(self):
        """Test detection of rules that can be auto-fixed."""
        standard_content = """# Fixability Test

## Spacing Rules

Fix spacing around operators.

```javascript
// Good
const result = a + b;
```

```javascript
// Bad
const result=a+b;
```

## Complex Logic Rules

Avoid complex nested conditions that harm readability.

```javascript
// This is a design issue, not easily fixable
if (condition1 && (condition2 || condition3) && !condition4) {
  // complex logic
}
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="fixable-test",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        rules = data["rules"]
        assert len(rules) == 2
        
        # Spacing rule should be detected as fixable
        spacing_rule = next(r for r in rules if "Spacing" in r["name"])
        assert spacing_rule["fixable"] == True
        
        # Complex logic rule should not be fixable
        logic_rule = next(r for r in rules if "Logic" in r["name"])
        assert logic_rule["fixable"] == False

    def test_summary_statistics(self):
        """Test generation of summary statistics."""
        standard_content = """# Comprehensive Standard

## Naming Convention

Use camelCase for variables.

## Code Structure

Organize code properly.

## Security Practice

Validate all inputs.

```javascript
// Example
function validateInput(input) {
  return input && input.length > 0;
}
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="comprehensive",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        assert data["total_rules"] == 3
        assert data["rules_with_examples"] == 1
        
        summary = data["summary"]
        rule_types = summary["rule_types"]
        assert rule_types["naming"] == 1
        assert rule_types["structure"] == 1
        assert rule_types["security"] == 1
        
        assert summary["complexity"] == "medium"  # 3 rules = medium complexity
        assert "javascript" in summary["languages"]

    def test_empty_content_handling(self):
        """Test handling of empty or minimal content."""
        result = parse_standard_to_rules_impl(
            standard_content="# Empty Standard\n\nNo rules here.",
            standard_id="empty",
            extract_examples=True
        )

        assert "data" in result
        data = result["data"]
        
        assert data["total_rules"] == 0
        assert data["rules_with_examples"] == 0
        assert data["fixable_rules"] == 0
        assert data["summary"]["complexity"] == "none"

    def test_error_handling(self):
        """Test error handling for invalid input."""
        # Test with None content should not crash
        result = parse_standard_to_rules_impl(
            standard_content=None,
            standard_id="test",
            extract_examples=True
        )

        assert "error" in result
        assert result["error"]["code"] == "OPERATION_FAILED"

    def test_ast_pattern_extraction(self):
        """Test that AST patterns are generated for rules."""
        standard_content = """# Pattern Test

## Function Declaration Rule

Functions should be declared properly.

```typescript
// Good
function myFunction(param: string): string {
  return param;
}
```
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="pattern-test",
            extract_examples=True
        )

        assert "data" in result
        rules = result["data"]["rules"]
        assert len(rules) == 1
        
        rule = rules[0]
        ast_pattern = rule["ast_pattern"]
        
        assert "type" in ast_pattern
        assert "description" in ast_pattern
        assert ast_pattern["has_examples"] == True
        assert "typescript" in ast_pattern["languages"]

    def test_rule_id_generation(self):
        """Test that rule IDs are generated correctly."""
        standard_content = """# ID Test

## My Special Rule!

A rule with special characters.

## Another-Rule_Name

A rule with mixed separators.
"""

        result = parse_standard_to_rules_impl(
            standard_content=standard_content,
            standard_id="id-test",
            extract_examples=True
        )

        assert "data" in result
        rules = result["data"]["rules"]
        assert len(rules) == 2
        
        # Check that IDs are properly formatted
        rule_ids = [rule["id"] for rule in rules]
        assert "id-test-my-special-rule" in rule_ids
        assert "id-test-another-rule-name" in rule_ids
        
        # Ensure IDs are unique
        assert len(set(rule_ids)) == len(rule_ids)