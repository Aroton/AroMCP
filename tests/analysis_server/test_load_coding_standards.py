"""Tests for load_coding_standards tool."""

import tempfile
import pytest
from pathlib import Path

from aromcp.analysis_server.tools.load_coding_standards import load_coding_standards_impl


class TestLoadCodingStandards:
    """Test class for load_coding_standards tool."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.standards_dir = ".aromcp/standards"
        
        # Create standards directory
        standards_path = Path(self.temp_dir) / self.standards_dir
        standards_path.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_functionality(self):
        """Test basic loading of coding standards."""
        # Create a simple standard file
        standards_path = Path(self.project_root) / self.standards_dir
        standard_file = standards_path / "test-standard.md"
        
        standard_content = """---
id: test-standard
name: Test Standard
version: 1.0.0
patterns:
  - "**/*.py"
tags:
  - python
  - testing
severity: error
---

# Test Standard

This is a test standard for validation.

## Rules

### Rule 1
All functions must have docstrings.

```python
# ✅ Good
def good_function():
    \"\"\"This function has a docstring.\"\"\"
    pass

# ❌ Bad
def bad_function():
    pass
```
"""
        standard_file.write_text(standard_content)
        
        # Test loading standards
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        # Verify successful loading
        assert "data" in result
        data = result["data"]
        
        assert data["total"] == 1
        assert len(data["standards"]) == 1
        
        standard = data["standards"][0]
        assert standard["id"] == "test-standard"
        assert standard["file_name"] == "test-standard.md"
        assert "metadata" in standard
        assert standard["metadata"]["name"] == "Test Standard"
        assert "python" in standard["metadata"]["tags"]

    def test_empty_directory(self):
        """Test handling of empty standards directory."""
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert data["total"] == 0
        assert len(data["standards"]) == 0
        assert "warnings" in data
        assert any("No markdown files found" in warning for warning in data["warnings"])

    def test_nonexistent_directory(self):
        """Test handling of nonexistent standards directory."""
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=".aromcp/nonexistent",
            include_metadata=True
        )
        
        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_invalid_yaml_frontmatter(self):
        """Test handling of invalid YAML frontmatter."""
        standards_path = Path(self.project_root) / self.standards_dir
        standard_file = standards_path / "invalid-yaml.md"
        
        # Create file with invalid YAML
        invalid_content = """---
id: invalid-standard
name: Invalid Standard
invalid_yaml: [unclosed list
---

# Invalid Standard
Content here.
"""
        standard_file.write_text(invalid_content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert data["files_with_errors"] == 1
        assert "processing_errors" in data
        assert len(data["processing_errors"]) == 1

    def test_missing_required_metadata(self):
        """Test handling of standards with missing required metadata."""
        standards_path = Path(self.project_root) / self.standards_dir
        standard_file = standards_path / "missing-metadata.md"
        
        # Create file with missing required fields
        incomplete_content = """---
name: Standard Without ID
---

# Standard Without ID
This standard is missing the required 'id' field.
"""
        standard_file.write_text(incomplete_content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert data["files_with_errors"] == 1
        assert "processing_errors" in data

    def test_multiple_standards(self):
        """Test loading multiple standards files."""
        standards_path = Path(self.project_root) / self.standards_dir
        
        # Create multiple standard files
        for i in range(3):
            standard_file = standards_path / f"standard-{i}.md"
            content = f"""---
id: standard-{i}
name: Standard {i}
patterns:
  - "**/*.py"
tags:
  - test
---

# Standard {i}
Content for standard {i}.
"""
            standard_file.write_text(content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert data["total"] == 3
        assert len(data["standards"]) == 3
        
        # Verify standards are sorted by ID
        ids = [s["id"] for s in data["standards"]]
        assert ids == sorted(ids)

    def test_nested_directories(self):
        """Test loading standards from nested directories."""
        standards_path = Path(self.project_root) / self.standards_dir
        
        # Create nested directory structure
        nested_dir = standards_path / "category1" / "subcategory"
        nested_dir.mkdir(parents=True)
        
        # Create standard in nested directory
        nested_file = nested_dir / "nested-standard.md"
        content = """---
id: nested-standard
name: Nested Standard
---

# Nested Standard
This standard is in a nested directory.
"""
        nested_file.write_text(content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert data["total"] == 1
        assert data["standards"][0]["id"] == "nested-standard"

    def test_metadata_disabled(self):
        """Test loading standards without metadata parsing."""
        standards_path = Path(self.project_root) / self.standards_dir
        standard_file = standards_path / "test-standard.md"
        
        content = """---
id: test-standard
name: Test Standard
---

# Test Standard
Content here.
"""
        standard_file.write_text(content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=False
        )
        
        assert "data" in result
        data = result["data"]
        assert data["total"] == 1
        
        standard = data["standards"][0]
        assert "metadata" not in standard
        assert "rule_metadata" not in standard
        assert standard["id"] == "test-standard"  # Should use filename stem as fallback

    def test_pattern_analysis_included(self):
        """Test that pattern analysis is included when metadata is enabled."""
        standards_path = Path(self.project_root) / self.standards_dir
        standard_file = standards_path / "patterns-test.md"
        
        content = """---
id: patterns-test
name: Patterns Test
patterns:
  - "**/*.py"
  - "src/**/*.ts"
tags:
  - python
  - typescript
---

# Patterns Test
Standard with patterns for analysis.
"""
        standard_file.write_text(content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        
        # Should include pattern analysis
        assert "pattern_analysis" in data
        pattern_analysis = data["pattern_analysis"]
        assert pattern_analysis["total_patterns"] == 2
        assert pattern_analysis["standards_with_patterns"] == 1

    def test_summary_statistics(self):
        """Test that summary statistics are calculated correctly."""
        standards_path = Path(self.project_root) / self.standards_dir
        
        # Create standards with different attributes
        contents = [
            """---
id: standard-1
name: Standard 1
tags: [python, api]
severity: error
enabled: true
---
# Standard 1""",
            """---
id: standard-2
name: Standard 2
tags: [typescript, components]
severity: warn
enabled: false
---
# Standard 2""",
            """---
id: standard-3
name: Standard 3
tags: [python, utils]
severity: error
enabled: true
---
# Standard 3"""
        ]
        
        for i, content in enumerate(contents):
            (standards_path / f"standard-{i+1}.md").write_text(content)
        
        result = load_coding_standards_impl(
            project_root=self.project_root,
            standards_dir=self.standards_dir,
            include_metadata=True
        )
        
        assert "data" in result
        data = result["data"]
        assert "summary" in data
        
        summary = data["summary"]
        assert summary["tags"]["python"] == 2
        assert summary["tags"]["typescript"] == 1
        assert summary["severities"]["error"] == 2
        assert summary["severities"]["warn"] == 1
        assert summary["enabled_status"]["enabled"] == 2
        assert summary["enabled_status"]["disabled"] == 1