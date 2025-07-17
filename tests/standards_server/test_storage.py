"""Tests for storage utilities."""

import tempfile

from aromcp.standards_server._storage import (
    _group_rules_by_patterns,
    build_index,
    get_aromcp_dir,
    load_ai_hints,
    load_index,
    load_manifest,
    load_standard_metadata,
    save_ai_hints,
    save_manifest,
    save_standard_metadata,
    update_eslint_config,
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
                "priority": "required",
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
                    "hasEslintRule": False,
                },
                {
                    "rule": "Use meaningful variable names",
                    "context": "Variables should be descriptive",
                    "correctExample": "user_count = 5",
                    "incorrectExample": "x = 5",
                    "hasEslintRule": True,
                },
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
                "priority": "required",
            }

            save_standard_metadata("test-standard", metadata, temp_dir)

            hints = [
                {
                    "rule": "Test rule",
                    "context": "Test context",
                    "correctExample": "correct",
                    "incorrectExample": "incorrect",
                    "hasEslintRule": False,
                }
            ]

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

    def test_group_rules_by_patterns(self):
        """Test grouping rules by appliesTo patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create metadata for different standards with different patterns
            api_metadata = {
                "id": "api-standard",
                "name": "API Standard",
                "category": "api",
                "appliesTo": ["api/**/*.js", "routes/**/*.js"],
                "priority": "required",
            }

            component_metadata = {
                "id": "component-standard",
                "name": "Component Standard",
                "category": "components",
                "appliesTo": ["components/**/*.tsx", "ui/**/*.tsx"],
                "priority": "recommended",
            }

            global_metadata = {
                "id": "global-standard",
                "name": "Global Standard",
                "category": "general",
                "appliesTo": [],  # No specific patterns
                "priority": "important",
            }

            # Save metadata
            save_standard_metadata("api-standard", api_metadata, temp_dir)
            save_standard_metadata("component-standard", component_metadata, temp_dir)
            save_standard_metadata("global-standard", global_metadata, temp_dir)

            # Test grouping with rules that match standards
            rule_names = ["api-standard", "component-standard", "global-standard", "unknown-rule"]
            groups = _group_rules_by_patterns(rule_names, temp_dir)

            # Should have 3 groups: api+routes, components+ui, catch-all
            assert len(groups) == 3

            # Find each group
            api_group = next((g for g in groups if "api/**/*.js" in g["files"]), None)
            component_group = next((g for g in groups if "components/**/*.tsx" in g["files"]), None)
            catchall_group = next((g for g in groups if g["files"] == ["**/*.{js,jsx,ts,tsx}"]), None)

            assert api_group is not None
            assert component_group is not None
            assert catchall_group is not None

            # Check rules are in correct groups
            assert "api-standard" in api_group["rules"]
            assert "component-standard" in component_group["rules"]
            assert "global-standard" in catchall_group["rules"]
            assert "unknown-rule" in catchall_group["rules"]

            # Check file patterns
            assert set(api_group["files"]) == {"api/**/*.js", "routes/**/*.js"}
            assert set(component_group["files"]) == {"components/**/*.tsx", "ui/**/*.tsx"}

    def test_update_eslint_config_with_patterns(self):
        """Test ESLint config generation with file-specific patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create metadata for standards with different patterns
            api_metadata = {
                "id": "api-validation",
                "name": "API Validation",
                "category": "api",
                "appliesTo": ["api/**/*.js"],
                "priority": "required",
            }

            component_metadata = {
                "id": "component-props",
                "name": "Component Props",
                "category": "components",
                "appliesTo": ["components/**/*.tsx"],
                "priority": "recommended",
            }

            save_standard_metadata("api-validation", api_metadata, temp_dir)
            save_standard_metadata("component-props", component_metadata, temp_dir)

            # Create dummy rule files
            from aromcp.standards_server._storage import get_eslint_dir

            eslint_dir = get_eslint_dir(temp_dir)
            rules_dir = eslint_dir / "rules"
            rules_dir.mkdir(exist_ok=True)

            # Create dummy rule files
            (rules_dir / "api-validation.js").write_text("module.exports = { meta: {}, create: () => ({}) };")
            (rules_dir / "component-props.js").write_text("module.exports = { meta: {}, create: () => ({}) };")

            # Update ESLint config
            update_eslint_config(temp_dir)

            # Check that config files were created
            assert (eslint_dir / "standards-config.js").exists()
            assert (eslint_dir / "standards-config.json").exists()

            # Read and verify JSON config
            import json

            with open(eslint_dir / "standards-config.json") as f:
                config = json.load(f)

            assert "configs" in config
            assert len(config["configs"]) == 2  # Two different pattern groups

            # Check that rules are properly grouped by patterns
            api_config = next((c for c in config["configs"] if "api/**/*.js" in c["files"]), None)
            component_config = next((c for c in config["configs"] if "components/**/*.tsx" in c["files"]), None)

            assert api_config is not None
            assert component_config is not None

            assert "aromcp/api-validation" in api_config["rules"]
            assert "aromcp/component-props" in component_config["rules"]
