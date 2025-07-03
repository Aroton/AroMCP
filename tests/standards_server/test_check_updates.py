"""Tests for check_updates tool."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from aromcp.standards_server.tools.check_updates import check_updates_impl


class TestCheckUpdates:
    """Test the check_updates functionality."""
    
    def test_basic_functionality(self):
        """Test basic check_updates functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Create standards directory
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create a sample markdown file with valid YAML header
            sample_md = standards_dir / "error-handling.md"
            sample_md.write_text("""---
id: error-handling
name: Error Handling
category: general
tags: [error, handling]
applies_to: ["**/*.ts", "**/*.tsx"]
severity: error
updated: 2024-01-15T10:30:00Z
priority: required
---

# Error Handling

Sample standard content.""")
            
            # Test with no existing manifest
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert "needsUpdate" in result["data"]
            assert "upToDate" in result["data"]
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["reason"] == "new"
            assert result["data"]["needsUpdate"][0]["standardId"] == "error-handling"
            # Verify template updated field is used
            assert result["data"]["needsUpdate"][0]["templateUpdated"] == "2024-01-15T10:30:00Z"
            assert "filesystemModified" in result["data"]["needsUpdate"][0]
    
    def test_empty_standards_directory(self):
        """Test with empty standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert result["data"]["needsUpdate"] == []
            assert result["data"]["upToDate"] == 0
    
    def test_invalid_standards_path(self):
        """Test with invalid standards path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            result = check_updates_impl("nonexistent", temp_dir)
            
            assert "data" in result
            assert result["data"]["needsUpdate"] == []
            assert result["data"]["upToDate"] == 0

    def test_yaml_header_filtering(self):
        """Test that files without valid YAML headers are filtered out."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create a file with valid YAML header
            valid_md = standards_dir / "valid-standard.md"
            valid_md.write_text("""---
id: valid-standard
name: Valid Standard
category: general
updated: 2024-01-01T00:00:00Z
---

# Valid Standard
This has a valid YAML header with id and updated fields.""")
            
            # Create a file without YAML header
            invalid_md = standards_dir / "invalid-standard.md"
            invalid_md.write_text("# Invalid Standard\n\nThis has no YAML header.")
            
            # Create a file with YAML header but missing required fields
            no_id_md = standards_dir / "no-id-standard.md"
            no_id_md.write_text("""---
name: No ID Standard
category: general
---

# No ID Standard
This has YAML header but no id field.""")

            # Create a file with id but no updated field
            no_updated_md = standards_dir / "no-updated-standard.md"
            no_updated_md.write_text("""---
id: no-updated-standard
name: No Updated Standard
category: general
---

# No Updated Standard
This has id but no updated field.""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            # Only the valid file with both id and updated should be processed
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["standardId"] == "valid-standard"
    
    def test_template_updated_field_priority(self):
        """Test that template updated field takes priority over filesystem timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create file with template updated field
            template_md = standards_dir / "template-updated.md"
            template_md.write_text("""---
id: template-updated
name: Template Updated
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: 2024-02-01T12:00:00Z
priority: required
---

# Template Updated Standard""")
            
            # Create file with different template updated field format
            different_format_md = standards_dir / "different-format-updated.md"
            different_format_md.write_text("""---
id: different-format-updated
name: Different Format Updated
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: 2024-01-01
priority: required
---

# Different Format Updated Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 2
            
            # Find the entries
            template_entry = next(
                item for item in result["data"]["needsUpdate"] 
                if item["standardId"] == "template-updated"
            )
            different_format_entry = next(
                item for item in result["data"]["needsUpdate"] 
                if item["standardId"] == "different-format-updated"
            )
            
            # Verify template updated field is used correctly
            assert template_entry["templateUpdated"] == "2024-02-01T12:00:00Z"
            assert template_entry["lastModified"] == "2024-02-01T12:00:00Z"
            
            # Verify different date format is handled correctly
            assert different_format_entry["templateUpdated"] == "2024-01-01"
            assert different_format_entry["lastModified"] == "2024-01-01"
    
    def test_modified_detection_with_template_field(self):
        """Test that modifications are detected based on template updated field."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create .aromcp directory and manifest
            aromcp_dir = Path(temp_dir) / ".aromcp"
            aromcp_dir.mkdir()
            
            manifest = {
                "standards": {
                    "test-standard": {
                        "sourcePath": "standards/test-standard.md",
                        "lastModified": "2024-01-01T00:00:00Z",
                        "registered": True
                    }
                }
            }
            
            manifest_path = aromcp_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)
            
            # Create file with newer template updated field
            test_md = standards_dir / "test-standard.md"
            test_md.write_text("""---
id: test-standard
name: Test Standard
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: 2024-01-15T10:30:00Z
priority: required
---

# Test Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["reason"] == "modified"
            assert result["data"]["needsUpdate"][0]["standardId"] == "test-standard"
            assert result["data"]["needsUpdate"][0]["templateUpdated"] == "2024-01-15T10:30:00Z"
    
    def test_date_only_format_handling(self):
        """Test that date-only format in updated field is handled correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create file with date-only updated field
            date_only_md = standards_dir / "date-only.md"
            date_only_md.write_text("""---
id: date-only
name: Date Only Standard
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: 2024-01-15
priority: required
---

# Date Only Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["standardId"] == "date-only"
            # Should convert date to ISO string format
            assert result["data"]["needsUpdate"][0]["templateUpdated"] == "2024-01-15"
    
    def test_real_world_header_format(self):
        """Test with actual header format from frontend-standards file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create file with real-world header format
            frontend_md = standards_dir / "frontend-standards.md"
            frontend_md.write_text("""---
id: frontend-standards
name: Frontend Standards
category: frontend
tags: [react, nextjs, typescript, components, hooks, ssr, forms, performance]
applies_to: ["app/**/*.tsx", "src/components/**/*.tsx", "src/hooks/**/*.ts", "app/**/*.ts"]
severity: warning
updated: 2025-01-03T10:00:00
priority: required
dependencies: [data-fetching-patterns, type-safety-checklist, api-standards]
description: Standards for React components, hooks, SSR/CSR patterns, and frontend architecture in Next.js
---

# Frontend Standards

Real world content here.""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 1
            entry = result["data"]["needsUpdate"][0]
            assert entry["standardId"] == "frontend-standards"
            assert entry["reason"] == "new"
            # Should handle datetime format correctly  
            assert entry["templateUpdated"] == "2025-01-03T10:00:00Z"
            assert "filesystemModified" in entry
    
    def test_invalid_updated_field_format(self):
        """Test handling of invalid or unexpected updated field formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create file with non-standard updated field (dict/object)
            invalid_md = standards_dir / "invalid-updated.md"
            invalid_md.write_text("""---
id: invalid-updated
name: Invalid Updated Field
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: {year: 2024, month: 1, day: 15}
priority: required
---

# Invalid Updated Field Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 1
            entry = result["data"]["needsUpdate"][0]
            assert entry["standardId"] == "invalid-updated"
            # Should convert to string without crashing
            assert isinstance(entry["templateUpdated"], str)
            # Should contain the dict representation
            assert "year" in entry["templateUpdated"] or "2024" in entry["templateUpdated"]
    
    def test_missing_updated_field_filtered_out(self):
        """Test that files without updated field are filtered out completely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create file without updated field at all
            no_updated_md = standards_dir / "no-updated.md"
            no_updated_md.write_text("""---
id: no-updated
name: No Updated Field
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
priority: required
---

# No Updated Field Standard""")
            
            # Create file with both id and updated (should be processed)
            valid_md = standards_dir / "valid-standard.md"
            valid_md.write_text("""---
id: valid-standard
name: Valid Standard
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
updated: 2024-01-15T10:00:00Z
priority: required
---

# Valid Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            # Only the valid file should be processed
            assert len(result["data"]["needsUpdate"]) == 1
            entry = result["data"]["needsUpdate"][0]
            assert entry["standardId"] == "valid-standard"