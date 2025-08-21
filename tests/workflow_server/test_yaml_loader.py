"""Tests for YAML loader."""

import os
import tempfile
import pytest
import yaml
from pathlib import Path

from aromcp.workflow_server.yaml_loader import YAMLLoader, get_yaml_loader


class TestYAMLLoader:
    """Test class for YAMLLoader."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.loader = YAMLLoader(cache_ttl=60)  # 60 second TTL for tests
        
    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_yaml(self, filename: str, content: dict) -> str:
        """Create a test YAML file."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w') as f:
            yaml.dump(content, f)
        return file_path

    def test_basic_yaml_loading(self):
        """Test basic YAML file loading."""
        test_content = {
            "name": "test-workflow",
            "steps": [
                {"id": "step1", "action": "shell", "command": "echo hello"}
            ]
        }
        
        file_path = self.create_test_yaml("test.yaml", test_content)
        
        # Load the YAML
        result = self.loader.load_yaml(file_path)
        
        assert result is not None
        assert result["name"] == "test-workflow"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["id"] == "step1"

    def test_yaml_caching(self):
        """Test that YAML files are cached properly."""
        test_content = {"name": "cached-workflow"}
        file_path = self.create_test_yaml("cached.yaml", test_content)
        
        # Load twice
        result1 = self.loader.load_yaml(file_path)
        result2 = self.loader.load_yaml(file_path)
        
        # Should be the same object (cached)
        assert result1 is result2
        assert self.loader.get_cache_stats()["hits"] > 0

    def test_file_modification_detection(self):
        """Test that modified files invalidate cache."""
        test_content = {"name": "original"}
        file_path = self.create_test_yaml("modified.yaml", test_content)
        
        # Load original
        result1 = self.loader.load_yaml(file_path)
        assert result1["name"] == "original"
        
        # Modify file
        import time
        time.sleep(0.1)  # Ensure different mtime
        modified_content = {"name": "modified"}
        with open(file_path, 'w') as f:
            yaml.dump(modified_content, f)
        
        # Load again - should get new content
        result2 = self.loader.load_yaml(file_path)
        assert result2["name"] == "modified"
        assert result1 is not result2

    def test_yaml_vs_yml_extensions(self):
        """Test support for both .yaml and .yml extensions."""
        content = {"name": "extension-test"}
        
        yaml_path = self.create_test_yaml("test.yaml", content)
        yml_path = self.create_test_yaml("test.yml", content)
        
        yaml_result = self.loader.load_yaml(yaml_path)
        yml_result = self.loader.load_yaml(yml_path)
        
        assert yaml_result["name"] == "extension-test"
        assert yml_result["name"] == "extension-test"

    def test_malformed_yaml_error_handling(self):
        """Test error handling for malformed YAML."""
        # Create malformed YAML file
        file_path = os.path.join(self.temp_dir, "malformed.yaml")
        with open(file_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        result = self.loader.load_yaml(file_path)
        assert result is None

    def test_nonexistent_file_handling(self):
        """Test handling of non-existent files."""
        nonexistent_path = os.path.join(self.temp_dir, "does-not-exist.yaml")
        result = self.loader.load_yaml(nonexistent_path)
        assert result is None

    def test_path_validation(self):
        """Test path validation for security."""
        # Test directory traversal attempt
        dangerous_path = "../../../etc/passwd"
        result = self.loader.load_yaml(dangerous_path)
        assert result is None

    def test_preload_directory(self):
        """Test preloading all YAML files in a directory."""
        # Create multiple YAML files
        content1 = {"name": "workflow1"}
        content2 = {"name": "workflow2"}
        
        self.create_test_yaml("workflow1.yaml", content1)
        self.create_test_yaml("workflow2.yml", content2)
        self.create_test_yaml("not-yaml.txt", {"ignored": True})
        
        # Preload directory
        loaded_count = self.loader.preload_directory(self.temp_dir)
        assert loaded_count == 2  # Only YAML files should be loaded
        
        # Verify files are cached
        stats = self.loader.get_cache_stats()
        assert stats["cached_files"] >= 2

    def test_cache_statistics(self):
        """Test cache statistics functionality."""
        content = {"name": "stats-test"}
        file_path = self.create_test_yaml("stats.yaml", content)
        
        # Initial stats
        stats = self.loader.get_cache_stats()
        initial_hits = stats["hits"]
        initial_misses = stats["misses"]
        
        # Load file (should be a miss)
        self.loader.load_yaml(file_path)
        stats_after_load = self.loader.get_cache_stats()
        assert stats_after_load["misses"] == initial_misses + 1
        
        # Load again (should be a hit)
        self.loader.load_yaml(file_path)
        stats_after_hit = self.loader.get_cache_stats()
        assert stats_after_hit["hits"] == initial_hits + 1

    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        content = {"name": "clear-test"}
        file_path = self.create_test_yaml("clear.yaml", content)
        
        # Load file
        self.loader.load_yaml(file_path)
        assert self.loader.get_cache_stats()["cached_files"] > 0
        
        # Clear cache
        cleared = self.loader.clear_cache()
        assert cleared > 0
        assert self.loader.get_cache_stats()["cached_files"] == 0

    def test_complex_yaml_structures(self):
        """Test loading complex YAML structures."""
        complex_content = {
            "name": "complex-workflow",
            "version": "1.0",
            "inputs": {
                "required": ["input1", "input2"],
                "optional": {"timeout": 30}
            },
            "steps": [
                {
                    "id": "step1",
                    "action": "shell",
                    "command": "echo {{ inputs.input1 }}",
                    "needs_state": ["input1"],
                    "output_to": "step1_result"
                },
                {
                    "id": "step2",
                    "action": "conditional",
                    "condition": "step1_result == 'success'",
                    "then": [
                        {"action": "shell", "command": "echo success"}
                    ],
                    "else": [
                        {"action": "shell", "command": "echo failure"}
                    ]
                }
            ]
        }
        
        file_path = self.create_test_yaml("complex.yaml", complex_content)
        result = self.loader.load_yaml(file_path)
        
        assert result["name"] == "complex-workflow"
        assert len(result["steps"]) == 2
        assert "inputs" in result
        assert "required" in result["inputs"]


class TestGlobalYAMLLoader:
    """Test global YAML loader singleton."""

    def test_global_loader_singleton(self):
        """Test that global loader is a singleton."""
        loader1 = get_yaml_loader()
        loader2 = get_yaml_loader()
        
        assert loader1 is loader2

    def test_global_loader_functionality(self):
        """Test that global loader works correctly."""
        loader = get_yaml_loader()
        
        # Create a simple test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({"name": "global-test"}, f)
            temp_path = f.name
        
        try:
            result = loader.load_yaml(temp_path)
            assert result is not None
            assert result["name"] == "global-test"
        finally:
            os.unlink(temp_path)