"""Tests for get_relevant_standards tool."""

import tempfile
import shutil
from pathlib import Path
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aromcp.analysis_server.tools.get_relevant_standards import get_relevant_standards_impl


class TestGetRelevantStandards:
    """Test class for get_relevant_standards functionality."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.standards_dir = Path(self.temp_dir) / ".aromcp" / "standards"
        self.standards_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test environment after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_sample_standard(self, filename: str, content: str):
        """Helper to create a sample standard file."""
        standard_path = self.standards_dir / filename
        standard_path.write_text(content, encoding='utf-8')
        return str(standard_path)

    def create_sample_file(self, relative_path: str, content: str = "// Sample file"):
        """Helper to create a sample project file."""
        file_path = Path(self.temp_dir) / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def test_basic_functionality(self):
        """Test basic file-to-standard matching."""
        # Create a TypeScript-specific standard
        ts_standard = """---
id: typescript-rules
name: TypeScript Standards
patterns:
  - "**/*.ts"
  - "**/*.tsx"
tags:
  - typescript
  - types
severity: error
---

# TypeScript Standards

Rules for TypeScript files.
"""
        self.create_sample_standard("typescript-rules.md", ts_standard)
        
        # Create a sample TypeScript file
        ts_file = self.create_sample_file("src/components/Button.tsx")
        
        # Test matching
        result = get_relevant_standards_impl(
            file_path=ts_file,
            project_root=self.project_root,
            include_general=True
        )
        
        # Verify success
        assert "data" in result
        assert result["data"]["file_path"] == ts_file
        assert result["data"]["file_exists"]
        assert len(result["data"]["matched_standards"]) > 0
        
        # Check if TypeScript standard matched
        ts_matches = [s for s in result["data"]["matched_standards"] if s["id"] == "typescript-rules"]
        assert len(ts_matches) == 1
        assert ts_matches[0]["specificity"] > 0.3  # Should have good specificity
        assert "typescript" in result["data"]["categories"]

    def test_pattern_specificity_ordering(self):
        """Test that more specific patterns get higher priority."""
        # Create general and specific standards
        general_standard = """---
id: general-ts
name: General TypeScript
patterns:
  - "**/*.ts"
  - "**/*.tsx"
tags:
  - typescript
severity: warn
---

# General TypeScript Rules
"""
        
        specific_standard = """---
id: component-ts
name: Component TypeScript
patterns:
  - "**/components/**/*.tsx"
tags:
  - typescript
  - components
  - react
severity: error
---

# Component TypeScript Rules
"""
        
        self.create_sample_standard("general-ts.md", general_standard)
        self.create_sample_standard("component-ts.md", specific_standard)
        
        # Create a component file
        component_file = self.create_sample_file("src/components/Header.tsx")
        
        result = get_relevant_standards_impl(
            file_path=component_file,
            project_root=self.project_root,
            include_general=True
        )
        
        assert "data" in result
        standards = result["data"]["matched_standards"]
        
        # Should match both standards
        assert len(standards) == 2
        
        # More specific standard should come first (higher specificity)
        assert standards[0]["id"] == "component-ts"
        assert standards[1]["id"] == "general-ts"
        assert standards[0]["specificity"] > standards[1]["specificity"]

    def test_include_general_parameter(self):
        """Test the include_general parameter functionality."""
        # Create a general standard (without patterns)
        general_standard = """---
id: general-coding
name: General Coding Standards
tags:
  - general
  - style
severity: warn
---

# General Coding Standards

Apply to all files.
"""
        
        # Create a specific standard
        specific_standard = """---
id: api-routes
name: API Route Standards
patterns:
  - "**/api/**/*.ts"
tags:
  - api
  - routes
severity: error
---

# API Route Standards
"""
        
        self.create_sample_standard("general.md", general_standard)
        self.create_sample_standard("api-routes.md", specific_standard)
        
        # Create an API file
        api_file = self.create_sample_file("src/api/users.ts")
        
        # Test with include_general=True
        result_with_general = get_relevant_standards_impl(
            file_path=api_file,
            project_root=self.project_root,
            include_general=True
        )
        
        # Test with include_general=False
        result_without_general = get_relevant_standards_impl(
            file_path=api_file,
            project_root=self.project_root,
            include_general=False
        )
        
        # With general: should have both standards
        assert len(result_with_general["data"]["matched_standards"]) == 2
        standard_ids_with = {s["id"] for s in result_with_general["data"]["matched_standards"]}
        assert "general-coding" in standard_ids_with
        assert "api-routes" in standard_ids_with
        
        # Without general: should only have specific standard
        assert len(result_without_general["data"]["matched_standards"]) == 1
        assert result_without_general["data"]["matched_standards"][0]["id"] == "api-routes"

    def test_file_categories_detection(self):
        """Test that file categories are correctly detected."""
        # Create a standard
        react_standard = """---
id: react-components
name: React Component Standards
patterns:
  - "**/*.tsx"
tags:
  - react
  - components
severity: error
---

# React Component Standards
"""
        self.create_sample_standard("react.md", react_standard)
        
        # Test different file types
        test_cases = [
            ("src/components/Button.tsx", ["typescript", "react", "components"]),
            ("src/utils/helpers.js", ["javascript", "utilities"]),
            ("src/api/routes/users.ts", ["typescript", "api", "routes"]),
            ("docs/README.md", ["documentation"]),
            ("src/styles/main.css", ["styles"]),
            ("tests/unit/button.test.js", ["javascript", "tests"])
        ]
        
        for file_path, expected_categories in test_cases:
            sample_file = self.create_sample_file(file_path)
            result = get_relevant_standards_impl(
                file_path=sample_file,
                project_root=self.project_root,
                include_general=True
            )
            
            assert "data" in result
            categories = result["data"]["categories"]
            
            # Check that all expected categories are present
            for expected_cat in expected_categories:
                assert expected_cat in categories, f"Expected category '{expected_cat}' missing for {file_path}"

    def test_nonexistent_file_handling(self):
        """Test handling of files that don't exist."""
        # Create a standard
        standard = """---
id: test-standard
name: Test Standard
patterns:
  - "**/*.ts"
---

# Test Standard
"""
        self.create_sample_standard("test.md", standard)
        
        # Test with nonexistent file
        nonexistent_file = str(Path(self.temp_dir) / "src" / "nonexistent.ts")
        
        result = get_relevant_standards_impl(
            file_path=nonexistent_file,
            project_root=self.project_root,
            include_general=True
        )
        
        # Should still work but indicate file doesn't exist
        assert "data" in result
        assert not result["data"]["file_exists"]
        assert result["data"]["file_size"] == 0
        
        # Should still match based on path pattern
        assert len(result["data"]["matched_standards"]) > 0

    def test_no_matching_standards(self):
        """Test behavior when no standards match a file."""
        # Create a standard with specific patterns
        specific_standard = """---
id: python-only
name: Python Only Standards
patterns:
  - "**/*.py"
tags:
  - python
severity: error
---

# Python Standards
"""
        self.create_sample_standard("python.md", specific_standard)
        
        # Create a file that won't match
        js_file = self.create_sample_file("src/app.js")
        
        # Test without including general standards
        result = get_relevant_standards_impl(
            file_path=js_file,
            project_root=self.project_root,
            include_general=False
        )
        
        assert "data" in result
        assert len(result["data"]["matched_standards"]) == 0
        assert result["data"]["total_matches"] == 0
        assert not result["data"]["has_specific_matches"]

    def test_invalid_file_path(self):
        """Test handling of invalid file paths."""
        # Test with path outside project root
        invalid_path = "/etc/passwd"
        
        result = get_relevant_standards_impl(
            file_path=invalid_path,
            project_root=self.project_root,
            include_general=True
        )
        
        # Should return an error
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_summary_statistics(self):
        """Test summary statistics in the response."""
        # Create mixed standards
        general_standard = """---
id: general
name: General Standards
tags:
  - general
severity: warn
---

# General Standards
"""
        
        specific_standard = """---
id: typescript-specific
name: TypeScript Specific
patterns:
  - "**/*.ts"
  - "**/*.tsx"
tags:
  - typescript
  - specific
severity: error
---

# TypeScript Specific
"""
        
        high_specific_standard = """---
id: components-specific
name: Component Specific
patterns:
  - "**/components/**/*.tsx"
tags:
  - components
  - typescript
  - react
severity: error
---

# Component Specific
"""
        
        self.create_sample_standard("general.md", general_standard)
        self.create_sample_standard("typescript.md", specific_standard)
        self.create_sample_standard("components.md", high_specific_standard)
        
        # Create a component file
        component_file = self.create_sample_file("src/components/App.tsx")
        
        result = get_relevant_standards_impl(
            file_path=component_file,
            project_root=self.project_root,
            include_general=True
        )
        
        assert "data" in result
        summary = result["data"]["summary"]
        
        # Should have proper counts
        assert summary["specific_standards"] >= 1  # At least the component-specific one
        assert summary["general_standards"] >= 1   # At least the general one
        
        # Should have unique tags
        assert len(summary["unique_tags"]) > 0
        expected_tags = {"general", "typescript", "specific", "components", "react"}
        assert expected_tags.issubset(set(summary["unique_tags"]))
        
        # Should have specific matches
        assert result["data"]["has_specific_matches"]
        assert result["data"]["highest_specificity"] > 0.2

    def test_multiple_pattern_matching(self):
        """Test standards with multiple patterns."""
        multi_pattern_standard = """---
id: web-files
name: Web File Standards
patterns:
  - "**/*.js"
  - "**/*.ts"
  - "**/*.jsx"
  - "**/*.tsx"
  - "**/*.css"
tags:
  - web
  - frontend
severity: warn
---

# Web File Standards
"""
        self.create_sample_standard("web-files.md", multi_pattern_standard)
        
        # Test different matching files
        test_files = [
            "src/app.js",
            "src/utils.ts", 
            "src/Button.jsx",
            "src/Header.tsx",
            "src/styles.css"
        ]
        
        for file_path in test_files:
            sample_file = self.create_sample_file(file_path)
            result = get_relevant_standards_impl(
                file_path=sample_file,
                project_root=self.project_root,
                include_general=True
            )
            
            assert "data" in result
            
            # Should match the web-files standard
            web_matches = [s for s in result["data"]["matched_standards"] if s["id"] == "web-files"]
            assert len(web_matches) == 1, f"Web standard should match {file_path}"
            
            # Check that the correct pattern was matched
            match = web_matches[0]
            expected_pattern = f"**/*{Path(file_path).suffix}"
            assert match["pattern_matched"] == expected_pattern