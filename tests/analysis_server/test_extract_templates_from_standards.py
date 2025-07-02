"""
Tests for extract_templates_from_standards tool.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from aromcp.analysis_server.tools.extract_templates_from_standards import extract_templates_from_standards_impl


class TestExtractTemplatesFromStandards:
    """Test cases for extract_templates_from_standards tool."""

    def test_basic_functionality(self):
        """Test basic template extraction from standardized markdown."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create standards directory
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create sample standard file
            standard_content = """---
id: component-isolation
name: Component Isolation Standard
category: architecture
applies_to: ["**/*.tsx", "**/*.jsx"]
severity: error
---

# Component Isolation Standard

## Description
Components should only be imported within their parent module.

## Good Examples
```typescript
// ✅ Good: dashboard/components/Chart.tsx used only in dashboard
// dashboard/page.tsx
import { Chart } from './components/Chart';
```

## Bad Examples
```typescript
// ❌ Bad: dashboard component used in profile page
// profile/page.tsx
import { Chart } from '../dashboard/components/Chart';
```

## Pattern Detection
```yaml
detect:
  - import_contains: "/components/"
  - not_from_parent: true
```

## Auto-Fix
```yaml
fixable: false
message: "Component {componentName} should only be imported within {parentModule}"
```

## Enforcement Type
- [ ] ESLint Rule (pattern-based detection)
- [ ] AI Context (requires human judgment)
- [x] Hybrid (both ESLint and AI guidance)

## Additional Context
This enforces architectural boundaries by preventing cross-module component usage.
"""
            
            standard_file = os.path.join(standards_dir, "component-isolation.md")
            with open(standard_file, 'w', encoding='utf-8') as f:
                f.write(standard_content)
                
            # Run extraction
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                output_dir=".aromcp/templates",
                project_root=temp_dir
            )
            
            # Verify success
            assert "data" in result
            assert result["data"]["templates_extracted"] == 1
            assert result["data"]["total_files_processed"] == 1
            
            # Check template metadata
            templates = result["data"]["templates"]
            assert len(templates) == 1
            
            template = templates[0]
            assert template["standard_id"] == "component-isolation"
            assert template["source_file"] == "component-isolation.md"
            assert template["has_good_examples"] is True
            assert template["has_bad_examples"] is True
            assert template["has_pattern_detection"] is True
            assert template["enforcement_type"] == "hybrid"
            
            # Verify extracted data file exists
            data_file = os.path.join(temp_dir, ".aromcp", "templates", "data", "component-isolation_template_data.json")
            assert os.path.exists(data_file)
            
            # Verify extracted data content
            with open(data_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
                
            assert template_data["id"] == "component-isolation"
            assert template_data["name"] == "Component Isolation Standard"
            assert template_data["category"] == "architecture"
            assert template_data["applies_to"] == ["**/*.tsx", "**/*.jsx"]
            assert template_data["severity"] == "error"
            assert template_data["enforcement_type"] == "hybrid"
            
            # Check examples
            assert len(template_data["correct_examples"]) == 1
            assert len(template_data["incorrect_examples"]) == 1
            assert template_data["correct_examples"][0]["language"] == "typescript"
            assert "Chart" in template_data["correct_examples"][0]["code"]
            
            # Check pattern detection
            assert "detect" in template_data["pattern_detection"]
            assert template_data["pattern_detection"]["detect"][0]["import_contains"] == "/components/"
            
            # Check auto-fix
            assert template_data["auto_fix"]["fixable"] is False
            assert "componentName" in template_data["auto_fix"]["message"]

    def test_multiple_standards(self):
        """Test extraction from multiple standard files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create multiple standard files
            standards = [
                ("api-design.md", "api-design", "API Design Standard"),
                ("security-practices.md", "security-practices", "Security Practices")
            ]
            
            for filename, std_id, std_name in standards:
                content = f"""---
id: {std_id}
name: {std_name}
category: general
applies_to: ["**/*.ts"]
severity: warning
---

# {std_name}

## Description
Test standard for {std_name.lower()}.

## Good Examples
```javascript
// Good example
const good = true;
```

## Enforcement Type
- [x] ESLint Rule (pattern-based detection)
"""
                
                with open(os.path.join(standards_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            # Run extraction
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            # Verify results
            assert "data" in result
            assert result["data"]["templates_extracted"] == 2
            assert result["data"]["total_files_processed"] == 2
            
            # Check all templates extracted
            template_ids = [t["standard_id"] for t in result["data"]["templates"]]
            assert "api-design" in template_ids
            assert "security-practices" in template_ids

    def test_invalid_yaml_frontmatter(self):
        """Test handling of invalid YAML frontmatter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create standard with invalid YAML
            content = """---
id: invalid-yaml
name: [unclosed array
category: test
---

# Test Standard

## Description
This has invalid YAML frontmatter.
"""
            
            with open(os.path.join(standards_dir, "invalid.md"), 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Run extraction - should handle gracefully
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            # Should still process file, just without frontmatter
            assert "data" in result
            assert result["data"]["total_files_processed"] == 1

    def test_nonexistent_standards_directory(self):
        """Test error handling for nonexistent standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/nonexistent",
                project_root=temp_dir
            )
            
            assert "error" in result
            assert result["error"]["code"] == "NOT_FOUND"
            assert "not found" in result["error"]["message"].lower()

    def test_empty_standards_directory(self):
        """Test handling of empty standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            assert result["data"]["templates_extracted"] == 0
            assert result["data"]["total_files_processed"] == 0

    def test_non_markdown_files_ignored(self):
        """Test that non-markdown files are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create non-markdown files
            with open(os.path.join(standards_dir, "readme.txt"), 'w') as f:
                f.write("Not a markdown file")
                
            with open(os.path.join(standards_dir, "config.json"), 'w') as f:
                f.write("{}")
                
            # Create one markdown file
            with open(os.path.join(standards_dir, "standard.md"), 'w') as f:
                f.write("# Test Standard\n\n## Description\nTest.")
                
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            # Should only process the markdown file
            assert "data" in result
            assert result["data"]["total_files_processed"] == 1
            assert result["data"]["templates_extracted"] == 1

    def test_output_directory_creation(self):
        """Test that output directories are created automatically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create minimal standard
            with open(os.path.join(standards_dir, "test.md"), 'w') as f:
                f.write("# Test\n\n## Description\nTest standard.")
                
            # Custom output directory that doesn't exist
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                output_dir=".aromcp/custom-templates",
                project_root=temp_dir
            )
            
            assert "data" in result
            
            # Verify directories were created
            output_path = os.path.join(temp_dir, ".aromcp", "custom-templates", "data")
            assert os.path.exists(output_path)
            assert os.path.isdir(output_path)

    def test_enforcement_type_detection(self):
        """Test detection of different enforcement types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            test_cases = [
                ("eslint-only.md", "- [x] ESLint Rule (pattern-based detection)", "eslint_rule"),
                ("ai-only.md", "- [x] AI Context (requires human judgment)", "ai_context"),
                ("hybrid.md", "- [x] Hybrid (both ESLint and AI guidance)", "hybrid"),
                ("unknown.md", "- [ ] None selected", "unknown")
            ]
            
            for filename, checkbox_content, expected_type in test_cases:
                content = f"""# Test Standard

## Description
Test standard.

## Enforcement Type
{checkbox_content}
"""
                
                with open(os.path.join(standards_dir, filename), 'w') as f:
                    f.write(content)
                    
            result = extract_templates_from_standards_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            assert result["data"]["templates_extracted"] == 4
            
            # Check enforcement types
            for template in result["data"]["templates"]:
                expected = next(expected_type for fn, _, expected_type in test_cases 
                              if template["source_file"] == fn)
                assert template["enforcement_type"] == expected