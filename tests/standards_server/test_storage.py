"""Tests for storage utilities."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from aromcp.standards_server._storage import (
    get_aromcp_dir,
    load_manifest,
    save_manifest,
    save_standard_metadata,
    load_standard_metadata,
    save_ai_hints,
    load_ai_hints,
    build_index,
    load_index
)


class TestStorage:
    """Test storage functionality."""
    
    def test_aromcp_directory_creation(self):
        """Test .aromcp directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            aromcp_dir = get_aromcp_dir(temp_dir)
            
            assert aromcp_dir.exists()
            assert aromcp_dir.is_dir()
            assert aromcp_dir.name == ".aromcp"
    
    def test_manifest_operations(self):
        """Test manifest save and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test loading non-existent manifest
            manifest = load_manifest(temp_dir)
            assert "standards" in manifest
            assert "lastUpdated" in manifest
            
            # Test saving manifest
            manifest["standards"]["test"] = {"data": "value"}
            save_manifest(manifest, temp_dir)
            
            # Test loading saved manifest
            loaded = load_manifest(temp_dir)
            assert loaded["standards"]["test"]["data"] == "value"
    
    def test_standard_metadata_operations(self):
        """Test standard metadata save and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            # Save metadata
            save_standard_metadata("test-standard", metadata, temp_dir)
            
            # Load metadata
            loaded = load_standard_metadata("test-standard", temp_dir)
            assert loaded == metadata
            
            # Test non-existent standard
            assert load_standard_metadata("nonexistent", temp_dir) is None
    
    def test_ai_hints_operations(self):
        """Test AI hints save and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            hints = [
                {
                    "rule": "Use proper error handling",
                    "context": "Always catch exceptions",
                    "correctExample": "try: ...",
                    "incorrectExample": "just do it",
                    "hasEslintRule": False
                },
                {
                    "rule": "Use meaningful variable names",
                    "context": "Variables should be descriptive",
                    "correctExample": "user_count = 5",
                    "incorrectExample": "x = 5",
                    "hasEslintRule": True
                }
            ]
            
            # Save hints
            count = save_ai_hints("test-standard", hints, temp_dir)
            assert count == 2
            
            # Load hints
            loaded = load_ai_hints("test-standard", temp_dir)
            assert len(loaded) == 2
            assert all("tokens" in hint for hint in loaded)  # Token count added
            
            # Test non-existent standard
            assert load_ai_hints("nonexistent", temp_dir) == []
    
    def test_index_operations(self):
        """Test index build and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test data
            metadata = {
                "id": "test-standard",
                "name": "Test Standard", 
                "category": "testing",
                "tags": ["test", "example"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            save_standard_metadata("test-standard", metadata, temp_dir)
            
            hints = [{
                "rule": "Test rule",
                "context": "Test context",
                "correctExample": "correct",
                "incorrectExample": "incorrect",
                "hasEslintRule": False
            }]
            
            save_ai_hints("test-standard", hints, temp_dir)
            
            # Build index
            build_index(temp_dir)
            
            # Load index
            index = load_index(temp_dir)
            
            assert "standards" in index
            assert "lastBuilt" in index
            assert "test-standard" in index["standards"]
            
            standard_index = index["standards"]["test-standard"]
            assert standard_index["category"] == "testing"
            assert standard_index["tags"] == ["test", "example"]
            assert standard_index["appliesTo"] == ["*.py"]
            assert standard_index["priority"] == "required"
            assert standard_index["hintCount"] == 1