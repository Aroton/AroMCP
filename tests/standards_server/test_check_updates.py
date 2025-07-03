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
---

# Valid Standard
This has a valid YAML header with id field.""")
            
            # Create a file without YAML header
            invalid_md = standards_dir / "invalid-standard.md"
            invalid_md.write_text("# Invalid Standard\n\nThis has no YAML header.")
            
            # Create a file with YAML header but no id field
            no_id_md = standards_dir / "no-id-standard.md"
            no_id_md.write_text("""---
name: No ID Standard
category: general
---

# No ID Standard
This has YAML header but no id field.""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            # Only the valid file should be processed
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
            
            # Create file without template updated field
            no_template_md = standards_dir / "no-template-updated.md"
            no_template_md.write_text("""---
id: no-template-updated
name: No Template Updated
category: general
tags: [test]
applies_to: ["**/*.ts"]
severity: error
priority: required
---

# No Template Updated Standard""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert len(result["data"]["needsUpdate"]) == 2
            
            # Find the entries
            template_entry = next(
                item for item in result["data"]["needsUpdate"] 
                if item["standardId"] == "template-updated"
            )
            no_template_entry = next(
                item for item in result["data"]["needsUpdate"] 
                if item["standardId"] == "no-template-updated"
            )
            
            # Verify template updated field is used when available
            assert template_entry["templateUpdated"] == "2024-02-01T12:00:00Z"
            assert template_entry["lastModified"] == "2024-02-01T12:00:00Z"
            
            # Verify filesystem timestamp is used when template field is missing
            assert no_template_entry["templateUpdated"] == ""
            assert no_template_entry["lastModified"] == no_template_entry["filesystemModified"]
    
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