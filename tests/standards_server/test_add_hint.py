"""Tests for add_hint tool."""

import json
import os
import tempfile
from pathlib import Path

from aromcp.standards_server.tools.add_hint import add_hint_impl
from aromcp.standards_server.tools.register import register_impl


class TestAddHint:
    """Test the add_hint functionality."""

    def setup_method(self):
        """Set up test environment with a registered standard."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

        # Register a test standard first
        source_file = Path(self.temp_dir) / "standards" / "test.md"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# Test Standard")

        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        result = register_impl("standards/test.md", metadata, self.temp_dir)
        assert "data" in result

    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_add_basic_hint(self):
        """Test adding a basic hint to a standard."""
        hint_data = {
            "rule": "Always validate input parameters",
            "rule_id": "validate-input",
            "context": "Input validation prevents security vulnerabilities",
            "metadata": {
                "pattern_type": "validation",
                "complexity": "basic",
                "rule_type": "must",
                "nextjs_api": ["app-router"],
                "client_server": "server-only"
            },
            "compression": {
                "example_sharable": True,
                "pattern_extractable": True,
                "progressive_detail": ["minimal", "standard", "detailed", "full"]
            },
            "examples": {
                "minimal": "validate(input)",
                "standard": "const validated = validate(input);",
                "detailed": "import { validate } from './utils';\nconst validated = validate(input);",
                "full": "Complete example with error handling",
                "reference": "See utils/validation.py"
            },
            "tokens": {
                "minimal": 10,
                "standard": 25,
                "detailed": 50,
                "full": 100
            },
            "relationships": {
                "similar_rules": ["validate-output"],
                "prerequisite_rules": [],
                "see_also": ["error-handling"]
            },
            "has_eslint_rule": True,
            "import_map": []
        }

        result = add_hint_impl("test-standard", hint_data, self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert result["data"]["hintNumber"] == 1
        assert result["data"]["hintId"] == "validate-input"

        # Verify hint file was created
        hint_file = Path(result["data"]["hintFile"])
        assert hint_file.exists()
        assert hint_file.name == "hint-001.json"

        # Verify hint content
        with open(hint_file) as f:
            saved_hint = json.load(f)

        assert saved_hint["rule"] == "Always validate input parameters"
        assert saved_hint["rule_id"] == "validate-input"
        assert saved_hint["metadata"]["pattern_type"] == "validation"

    def test_add_multiple_hints(self):
        """Test adding multiple hints to a standard."""
        # Add first hint
        hint1_data = {
            "rule": "First rule",
            "rule_id": "rule-1",
            "context": "Context for rule 1",
            "examples": {"full": "Example 1"}
        }

        result1 = add_hint_impl("test-standard", hint1_data, self.temp_dir)
        assert result1["data"]["hintNumber"] == 1

        # Add second hint
        hint2_data = {
            "rule": "Second rule",
            "rule_id": "rule-2",
            "context": "Context for rule 2",
            "examples": {"full": "Example 2"}
        }

        result2 = add_hint_impl("test-standard", hint2_data, self.temp_dir)
        assert result2["data"]["hintNumber"] == 2

        # Verify both files exist
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-standard"
        assert (hints_dir / "hint-001.json").exists()
        assert (hints_dir / "hint-002.json").exists()

    def test_add_hint_with_json_string(self):
        """Test adding a hint with JSON string parameter."""
        hint_data_json = json.dumps({
            "rule": "JSON string rule",
            "rule_id": "json-rule",
            "context": "Rule from JSON string",
            "examples": {"full": "JSON example"}
        })

        result = add_hint_impl("test-standard", hint_data_json, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintId"] == "json-rule"

    def test_add_hint_invalid_json(self):
        """Test adding a hint with invalid JSON string."""
        invalid_json = "{ invalid json"

        result = add_hint_impl("test-standard", invalid_json, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON" in result["error"]["message"]

    def test_add_hint_nonexistent_standard(self):
        """Test adding a hint to a nonexistent standard."""
        hint_data = {
            "rule": "Test rule",
            "rule_id": "test-rule",
            "context": "Test context"
        }

        result = add_hint_impl("nonexistent-standard", hint_data, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "Standard nonexistent-standard not found" in result["error"]["message"]

    def test_add_hint_auto_generates_examples(self):
        """Test that missing examples are auto-generated."""
        hint_data = {
            "rule": "Rule with auto-generated examples",
            "rule_id": "auto-examples",
            "context": "Test auto-generation",
            "examples": {
                "full": "const result = processData(input);\nreturn result;"
                # minimal and standard will be auto-generated
            }
        }

        result = add_hint_impl("test-standard", hint_data, self.temp_dir)
        assert "data" in result

        # Load the saved hint and check that examples were generated
        hint_file = Path(result["data"]["hintFile"])
        with open(hint_file) as f:
            saved_hint = json.load(f)

        # Should have auto-generated minimal and standard examples
        assert saved_hint["examples"]["minimal"] is not None
        assert saved_hint["examples"]["standard"] is not None
        assert saved_hint["examples"]["full"] == "const result = processData(input);\nreturn result;"

    def test_add_hint_calculates_token_counts(self):
        """Test that token counts are calculated for examples."""
        hint_data = {
            "rule": "Rule with token calculation",
            "rule_id": "token-calc",
            "context": "Test token calculation",
            "examples": {
                "minimal": "const validateInput = (data) => schema.parse(data);",
                "standard": "const validateInput = (data) => { const schema = z.object({ email: z.string() }); "
                           "return schema.parse(data); };",
                "detailed": "import { z } from 'zod'; const validateInput = (data) => { "
                           "const schema = z.object({ email: z.string().email(), name: z.string().min(1) }); "
                           "try { return schema.parse(data); } catch (error) { "
                           "throw new ValidationError(error.message); } };",
                "full": "import { z } from 'zod'; import { ValidationError } from './errors'; "
                       "const createUserSchema = z.object({ email: z.string().email(), "
                       "name: z.string().min(1).max(100), role: z.enum(['user', 'admin']).default('user') }); "
                       "export const validateUserInput = (data: unknown) => { try { "
                       "return createUserSchema.parse(data); } catch (error) { "
                       "if (error instanceof z.ZodError) { throw new ValidationError('Invalid user data', "
                       "error.errors); } throw error; } };"
            }
        }

        result = add_hint_impl("test-standard", hint_data, self.temp_dir)
        assert "data" in result

        # Check that token counts were calculated and are logical
        tokens = result["data"]["tokens"]
        assert tokens["minimal"] > 0
        assert tokens["standard"] >= tokens["minimal"]
        assert tokens["detailed"] >= tokens["standard"]
        assert tokens["full"] >= tokens["detailed"]

    def test_add_hint_directory_creation(self):
        """Test that hints directory is created if it doesn't exist."""
        # Remove the hints directory
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-standard"
        if hints_dir.exists():
            import shutil
            shutil.rmtree(hints_dir)

        hint_data = {
            "rule": "Test directory creation",
            "rule_id": "dir-creation",
            "context": "Test context"
        }

        result = add_hint_impl("test-standard", hint_data, self.temp_dir)

        assert "data" in result
        assert hints_dir.exists()
        assert result["data"]["hintNumber"] == 1

    def test_add_hint_index_rebuild(self):
        """Test that index is rebuilt after adding a hint."""
        hint_data = {
            "rule": "Index rebuild test",
            "rule_id": "index-rebuild",
            "context": "Test index rebuild"
        }

        # Check index before
        index_file = Path(self.temp_dir) / ".aromcp" / "hints" / "index.json"
        if index_file.exists():
            with open(index_file) as f:
                json.load(f)
        else:
            pass

        result = add_hint_impl("test-standard", hint_data, self.temp_dir)
        assert "data" in result

        # Check index after
        assert index_file.exists()
        with open(index_file) as f:
            index_after = json.load(f)

        # Index should have been updated
        assert "standards" in index_after
        assert "test-standard" in index_after["standards"]
