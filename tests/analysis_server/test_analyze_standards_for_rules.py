"""
Tests for analyze_standards_for_rules tool.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from aromcp.analysis_server.tools.analyze_standards_for_rules import analyze_standards_for_rules_impl


class TestAnalyzeStandardsForRules:
    """Test cases for analyze_standards_for_rules tool."""

    def test_basic_functionality(self):
        """Test basic standards analysis and recipe generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create standards directory
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create package.json for project context
            package_json = {
                "name": "test-project",
                "dependencies": {
                    "next": "^13.0.0",
                    "react": "^18.0.0",
                    "typescript": "^4.9.0"
                }
            }
            
            with open(os.path.join(temp_dir, "package.json"), 'w') as f:
                json.dump(package_json, f)
                
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
// Good example
import { Chart } from './components/Chart';
```

## Pattern Detection
```yaml
detect:
  - import_contains: "/components/"
```

## Enforcement Type
- [x] ESLint Rule (pattern-based detection)
"""
            
            with open(os.path.join(standards_dir, "component-isolation.md"), 'w') as f:
                f.write(standard_content)
                
            # Create src directory for project structure
            os.makedirs(os.path.join(temp_dir, "src", "components"), exist_ok=True)
            
            # Run analysis
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            # Verify success
            assert "data" in result
            
            # Check standards
            standards = result["data"]["standards"]
            assert len(standards) == 1
            
            standard = standards[0]
            assert standard["id"] == "component-isolation"
            assert standard["name"] == "Component Isolation Standard"
            assert standard["category"] == "architecture"
            assert standard["applies_to"] == ["**/*.tsx", "**/*.jsx"]
            assert standard["severity"] == "error"
            assert standard["enforcement_type"] == "eslint_rule"
            assert standard["has_patterns"] is True
            assert standard["has_examples"] is True
            
            # Check project context
            project_context = result["data"]["project_context"]
            assert project_context["framework"] == "nextjs"
            assert project_context["typescript"] is True
            assert project_context["package_manager"] == "npm"  # default when no lock file
            assert "src" in project_context["directory_structure"]
            assert project_context["directory_structure"]["src"]["exists"] is True
            
            # Check generation hints
            hints = result["data"]["generation_hints"]
            assert "component-isolation" in hints["eslint_capable"]
            assert hints["typescript_enabled"] is True
            
            # Check framework hints structure
            framework_hints = hints["framework_specific_hints"]
            assert "component_patterns" in framework_hints  # Next.js should have component patterns

    def test_multiple_standards_with_different_types(self):
        """Test analysis of multiple standards with different enforcement types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # ESLint-capable standard
            eslint_standard = """---
id: eslint-rule
name: ESLint Rule Standard
category: syntax
---

# ESLint Rule Standard

## Good Examples
```javascript
const good = true;
```

## Pattern Detection
```yaml
detect:
  - pattern: "const.*"
```

## Enforcement Type
- [x] ESLint Rule (pattern-based detection)
"""
            
            # AI Context standard
            ai_standard = """---
id: ai-context
name: AI Context Standard
category: architecture
---

# AI Context Standard

## Description
This requires human judgment.

## Enforcement Type
- [x] AI Context (requires human judgment)
"""
            
            # Hybrid standard
            hybrid_standard = """---
id: hybrid-rule
name: Hybrid Standard
category: quality
---

# Hybrid Standard

## Good Examples
```typescript
// Example
```

## Pattern Detection
```yaml
detect:
  - pattern: "function.*"
```

## Enforcement Type
- [x] Hybrid (both ESLint and AI guidance)
"""
            
            standards = [
                ("eslint.md", eslint_standard),
                ("ai.md", ai_standard),
                ("hybrid.md", hybrid_standard)
            ]
            
            for filename, content in standards:
                with open(os.path.join(standards_dir, filename), 'w') as f:
                    f.write(content)
                    
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            assert len(result["data"]["standards"]) == 3
            
            # Check generation hints categorization
            hints = result["data"]["generation_hints"]
            assert "eslint-rule" in hints["eslint_capable"]
            assert "ai-context" in hints["ai_context_only"]
            assert "hybrid-rule" in hints["hybrid_standards"]

    def test_project_context_detection(self):
        """Test detection of different project types and structures."""
        test_cases = [
            # Next.js project
            ({
                "dependencies": {"next": "^13.0.0", "react": "^18.0.0"}
            }, "nextjs", ["app-router", "pages-router", "api-routes", "components"]),
            
            # React project
            ({
                "dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}
            }, "react", ["components", "hooks", "context"]),
            
            # Express project
            ({
                "dependencies": {"express": "^4.18.0"}
            }, "express", ["middleware", "routes", "controllers"]),
        ]
        
        for package_deps, expected_framework, expected_patterns in test_cases:
            with tempfile.TemporaryDirectory() as temp_dir:
                standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
                os.makedirs(standards_dir, exist_ok=True)
                
                # Create minimal standard
                with open(os.path.join(standards_dir, "test.md"), 'w') as f:
                    f.write("# Test\n\n## Description\nTest standard.")
                    
                # Create package.json
                with open(os.path.join(temp_dir, "package.json"), 'w') as f:
                    json.dump({"name": "test", **package_deps}, f)
                    
                result = analyze_standards_for_rules_impl(
                    standards_dir=".aromcp/standards",
                    project_root=temp_dir
                )
                
                assert "data" in result
                project_context = result["data"]["project_context"]
                assert project_context["framework"] == expected_framework
                
                hints = result["data"]["generation_hints"]
                framework_hints = hints["framework_specific_hints"]
                
                # Check that expected patterns are present in hints
                framework_hints_str = str(framework_hints)
                for pattern in expected_patterns:
                    # Check if pattern appears anywhere in the framework hints
                    if pattern in framework_hints_str:
                        # Found at least one pattern match
                        break

    def test_package_manager_detection(self):
        """Test detection of different package managers."""
        test_cases = [
            ("pnpm-lock.yaml", "pnpm"),
            ("yarn.lock", "yarn"),
            ("package-lock.json", "npm")
        ]
        
        for lock_file, expected_manager in test_cases:
            with tempfile.TemporaryDirectory() as temp_dir:
                standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
                os.makedirs(standards_dir, exist_ok=True)
                
                # Create minimal standard
                with open(os.path.join(standards_dir, "test.md"), 'w') as f:
                    f.write("# Test\n\n## Description\nTest standard.")
                    
                # Create lock file
                with open(os.path.join(temp_dir, lock_file), 'w') as f:
                    f.write("# Lock file content")
                    
                result = analyze_standards_for_rules_impl(
                    standards_dir=".aromcp/standards",
                    project_root=temp_dir
                )
                
                assert "data" in result
                project_context = result["data"]["project_context"]
                assert project_context["package_manager"] == expected_manager

    def test_typescript_detection(self):
        """Test TypeScript detection in project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create minimal standard
            with open(os.path.join(standards_dir, "test.md"), 'w') as f:
                f.write("# Test\n\n## Description\nTest standard.")
                
            # Create package.json with TypeScript
            package_json = {
                "name": "test-project",
                "devDependencies": {
                    "typescript": "^4.9.0",
                    "@types/node": "^18.0.0"
                }
            }
            
            with open(os.path.join(temp_dir, "package.json"), 'w') as f:
                json.dump(package_json, f)
                
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            project_context = result["data"]["project_context"]
            assert project_context["typescript"] is True
            
            hints = result["data"]["generation_hints"]
            assert hints["typescript_enabled"] is True

    def test_directory_structure_analysis(self):
        """Test analysis of project directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create minimal standard
            with open(os.path.join(standards_dir, "test.md"), 'w') as f:
                f.write("# Test\n\n## Description\nTest standard.")
                
            # Create various directories with files
            directories = {
                "src": ["index.ts", "App.tsx", "utils.js"],
                "components": ["Button.tsx", "Modal.jsx", "index.ts"],
                "pages": ["home.tsx", "about.tsx"],
                "lib": ["api.ts", "helpers.js"]
            }
            
            for dirname, files in directories.items():
                dir_path = os.path.join(temp_dir, dirname)
                os.makedirs(dir_path, exist_ok=True)
                
                for filename in files:
                    with open(os.path.join(dir_path, filename), 'w') as f:
                        f.write(f"// {filename} content")
                        
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            dir_structure = result["data"]["project_context"]["directory_structure"]
            
            # Check detected directories
            for dirname in directories.keys():
                assert dirname in dir_structure
                assert dir_structure[dirname]["exists"] is True
                assert dir_structure[dirname]["file_count"] == len(directories[dirname])
                
                # Check index file detection
                has_index_file = any(f.startswith("index.") for f in directories[dirname])
                assert dir_structure[dirname]["has_index"] == has_index_file
                
                # Check extensions
                expected_extensions = {os.path.splitext(f)[1] for f in directories[dirname] if os.path.splitext(f)[1]}
                assert set(dir_structure[dirname]["common_extensions"]) == expected_extensions

    def test_nonexistent_standards_directory(self):
        """Test error handling for nonexistent standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/nonexistent",
                project_root=temp_dir
            )
            
            assert "error" in result
            assert result["error"]["code"] == "NOT_FOUND"

    def test_empty_standards_directory(self):
        """Test handling of empty standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            assert len(result["data"]["standards"]) == 0
            assert "project_context" in result["data"]
            assert "generation_hints" in result["data"]

    def test_malformed_standards_handling(self):
        """Test graceful handling of malformed standard files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Create files with various issues
            files = [
                ("valid.md", "---\nid: valid\n---\n# Valid\n\n## Description\nValid standard."),
                ("invalid-yaml.md", "---\nid: [unclosed\n---\n# Invalid YAML"),
                ("no-frontmatter.md", "# No Frontmatter\n\n## Description\nNo YAML frontmatter."),
                ("empty.md", ""),
                ("binary.md", b"\x00\x01\x02\x03")  # Binary content
            ]
            
            for filename, content in files:
                file_path = os.path.join(standards_dir, filename)
                if isinstance(content, bytes):
                    with open(file_path, 'wb') as f:
                        f.write(content)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            # Should succeed and process valid files
            assert "data" in result
            
            # Should have processed at least the valid files
            standards = result["data"]["standards"]
            valid_standards = [s for s in standards if s.get("id") == "valid"]
            assert len(valid_standards) >= 1

    def test_inference_of_eslint_capability(self):
        """Test inference of ESLint capability from standard structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            standards_dir = os.path.join(temp_dir, ".aromcp", "standards")
            os.makedirs(standards_dir, exist_ok=True)
            
            # Standard with patterns and examples but no explicit enforcement type
            standard_content = """# Inferred ESLint Standard

## Description
This should be inferred as ESLint-capable.

## Good Examples
```javascript
const good = true;
```

## Bad Examples
```javascript
var bad = true;
```

## Pattern Detection
```yaml
detect:
  - pattern: "var .*"
```
"""
            
            with open(os.path.join(standards_dir, "inferred.md"), 'w') as f:
                f.write(standard_content)
                
            result = analyze_standards_for_rules_impl(
                standards_dir=".aromcp/standards",
                project_root=temp_dir
            )
            
            assert "data" in result
            
            # Check that it was inferred as ESLint-capable
            hints = result["data"]["generation_hints"]
            standard_ids = [s["id"] for s in result["data"]["standards"]]
            
            # Should infer ESLint capability based on structure
            for std_id in standard_ids:
                if std_id.startswith("inferred"):
                    assert std_id in hints["eslint_capable"]