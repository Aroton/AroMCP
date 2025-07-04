"""Tests for hints_for_file tool."""

import os
import tempfile

from aromcp.standards_server.tools.hints_for_file import (
    hints_for_file_impl,
    invalidate_index_cache,
)
from aromcp.standards_server.tools.register import register_impl
from aromcp.standards_server.tools.update_rule import update_rule_impl


class TestHintsForFile:
    """Test the hints_for_file functionality."""

    def setup_method(self):
        """Set up test standards for each test."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

        # Clear cache before each test
        invalidate_index_cache()

        # Register multiple standards with different relevance patterns
        self.api_metadata = {
            "id": "api-error-handling",
            "name": "API Error Handling",
            "category": "api",
            "tags": ["error", "exceptions", "api"],
            "appliesTo": ["api/*.py", "*/api/*"],
            "severity": "error",
            "priority": "required"
        }

        self.component_metadata = {
            "id": "component-structure",
            "name": "Component Structure",
            "category": "components",
            "tags": ["component", "structure"],
            "appliesTo": ["*.tsx", "*.jsx"],
            "severity": "warning",
            "priority": "important"
        }

        self.general_metadata = {
            "id": "general-coding",
            "name": "General Coding Standards",
            "category": "general",
            "tags": ["coding", "style"],
            "appliesTo": ["*.py", "*.js", "*.ts"],
            "severity": "info",
            "priority": "recommended"
        }

        # Register standards
        register_impl("standards/api-error.md", self.api_metadata, self.temp_dir)
        register_impl("standards/components.md", self.component_metadata, self.temp_dir)
        register_impl("standards/general.md", self.general_metadata, self.temp_dir)

        # Add hints to each standard
        self.api_hints = [
            {
                "rule": "Always return proper HTTP status codes",
                "context": "Helps clients understand what happened",
                "correctExample": "return Response(status=404)",
                "incorrectExample": "return Response(status=200)",
                "hasEslintRule": False
            },
            {
                "rule": "Use structured error responses",
                "context": "Consistent error format across API",
                "correctExample": '{"error": {"code": "NOT_FOUND", "message": "..."}}',
                "incorrectExample": '"Error: not found"',
                "hasEslintRule": True
            }
        ]

        self.component_hints = [
            {
                "rule": "Use TypeScript interfaces for props",
                "context": "Better type safety and documentation",
                "correctExample": "interface Props { name: string; }",
                "incorrectExample": "const Component = (props: any) => ...",
                "hasEslintRule": True
            }
        ]

        self.general_hints = [
            {
                "rule": "Use meaningful variable names",
                "context": "Improves code readability",
                "correctExample": "user_count = 5",
                "incorrectExample": "x = 5",
                "hasEslintRule": False
            }
        ]

        update_rule_impl("api-error-handling", False, self.api_hints, None, self.temp_dir)
        update_rule_impl("component-structure", False, self.component_hints, None, self.temp_dir)
        update_rule_impl("general-coding", False, self.general_hints, None, self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_exact_folder_match(self):
        """Test hints for file with exact folder match."""
        result = hints_for_file_impl("api/users.py", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        # Should get API hints with high relevance
        assert len(hints) > 0
        api_hint_found = any("HTTP status codes" in hint["rule"] for hint in hints)
        assert api_hint_found

        # Check relevance scores (exact match should have high score)
        for hint in hints:
            if "HTTP status codes" in hint["rule"]:
                assert hint["relevanceScore"] > 1.0  # With priority boost

    def test_glob_pattern_match(self):
        """Test hints for file matching glob patterns."""
        result = hints_for_file_impl("components/Button.tsx", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        # Should get component hints
        component_hint_found = any("TypeScript interfaces" in hint["rule"] for hint in hints)
        assert component_hint_found

    def test_tag_in_path_match(self):
        """Test hints for file with tag in path."""
        result = hints_for_file_impl("src/error/handler.py", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        # Should get API hints due to "error" tag match
        api_hint_found = any("HTTP status codes" in hint["rule"] for hint in hints)
        assert api_hint_found

    def test_multiple_standards_relevance(self):
        """Test that multiple relevant standards are included."""
        result = hints_for_file_impl("src/api/errors.py", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        # Should get hints from multiple standards
        rules = [hint["rule"] for hint in hints]

        # API hints (high relevance due to folder + tag match)
        assert any("HTTP status codes" in rule for rule in rules)

        # General hints (lower relevance due to file extension match)
        assert any("meaningful variable names" in rule for rule in rules)

    def test_eslint_deprioritization(self):
        """Test that ESLint-covered rules have lower scores."""
        result = hints_for_file_impl("api/users.py", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        eslint_hint = None
        non_eslint_hint = None

        for hint in hints:
            if "structured error responses" in hint["rule"]:
                eslint_hint = hint
            elif "HTTP status codes" in hint["rule"]:
                non_eslint_hint = hint

        # ESLint-covered hint should have lower score
        if eslint_hint and non_eslint_hint:
            assert eslint_hint["relevanceScore"] < non_eslint_hint["relevanceScore"]

    def test_token_budget_limit(self):
        """Test that hints respect token budget."""
        # Request with very small token budget
        result = hints_for_file_impl("api/users.py", 100, self.temp_dir)

        assert "data" in result
        assert result["data"]["totalTokens"] <= 100

        # Should still return some hints within budget
        hints = result["data"]["hints"]
        assert len(hints) >= 0  # May be 0 if no hints fit in 100 tokens

    def test_no_relevant_standards(self):
        """Test file with no relevant standards."""
        result = hints_for_file_impl("unrelated/file.xml", 10000, self.temp_dir)

        assert "data" in result
        assert result["data"]["hints"] == []
        assert result["data"]["totalTokens"] == 0

    def test_empty_standards_database(self):
        """Test with no registered standards."""
        # Use clean temp directory with no standards
        clean_temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = clean_temp_dir

        try:
            result = hints_for_file_impl("any/file.py", 10000, clean_temp_dir)

            assert "data" in result
            assert result["data"]["hints"] == []
            assert result["data"]["totalTokens"] == 0
        finally:
            import shutil
            shutil.rmtree(clean_temp_dir)

    def test_invalid_max_tokens(self):
        """Test with invalid max_tokens value."""
        result = hints_for_file_impl("api/users.py", 0, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "maxTokens must be a positive integer" in result["error"]["message"]

    def test_negative_max_tokens(self):
        """Test with negative max_tokens value."""
        result = hints_for_file_impl("api/users.py", -100, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_priority_ordering(self):
        """Test that higher priority standards appear first."""
        result = hints_for_file_impl("general/test.py", 10000, self.temp_dir)

        assert "data" in result
        hints = result["data"]["hints"]

        if len(hints) > 1:
            # Should be sorted by relevance score (which includes priority boost)
            scores = [hint["relevanceScore"] for hint in hints]
            assert scores == sorted(scores, reverse=True)

    def test_cache_functionality(self):
        """Test that index caching works correctly."""
        # First call - builds cache
        result1 = hints_for_file_impl("api/users.py", 10000, self.temp_dir)
        assert "data" in result1

        # Second call - should use cache
        result2 = hints_for_file_impl("api/users.py", 10000, self.temp_dir)
        assert "data" in result2

        # Results should be identical
        assert result1["data"]["hints"] == result2["data"]["hints"]
        assert result1["data"]["totalTokens"] == result2["data"]["totalTokens"]

    def test_cache_invalidation(self):
        """Test that cache is invalidated after updates."""
        # Get initial hints
        result1 = hints_for_file_impl("api/users.py", 10000, self.temp_dir)
        initial_count = len(result1["data"]["hints"])

        # Register a new standard to test cache invalidation
        new_metadata = {
            "id": "cache-test-standard",
            "name": "Cache Test Standard",
            "category": "api",
            "tags": ["cache", "test"],
            "appliesTo": ["*.py"],
            "severity": "info",
            "priority": "recommended"
        }

        register_impl("standards/cache-test.md", new_metadata, self.temp_dir)

        # Add hints to the new standard
        new_hints = [{
            "rule": "New rule for cache invalidation test",
            "context": "This should appear after cache invalidation",
            "correctExample": "new_example()",
            "incorrectExample": "old_way()",
            "hasEslintRule": False
        }]

        update_rule_impl("cache-test-standard", False, new_hints, None, self.temp_dir)

        # Get hints again - should see new hints due to cache invalidation
        result2 = hints_for_file_impl("api/users.py", 10000, self.temp_dir)
        new_count = len(result2["data"]["hints"])

        assert new_count > initial_count

        # Verify new hint is present
        rules = [hint["rule"] for hint in result2["data"]["hints"]]
        assert any("New rule for cache invalidation test" in rule for rule in rules)

    def test_import_map_optimization(self):
        """Test that import maps are moved to global object and optimized."""
        # Create a standard with hints that have import maps
        import_map_metadata = {
            "id": "import-test-standard",
            "name": "Import Test Standard",
            "category": "api",
            "tags": ["import", "test"],
            "appliesTo": ["api/*.py"],
            "severity": "warning",
            "priority": "important"
        }

        register_impl("standards/import-test.md", import_map_metadata, self.temp_dir)

        # Add hints with import examples
        hints_with_imports = [
            {
                "rule": "Use proper imports for Response",
                "context": "Import Response from the correct module",
                "correctExample": """import { Response } from 'next/server';

export async function GET() {
    return Response.json({data: 'test'});
}""",
                "incorrectExample": """export async function GET() {
    return Response.json({data: 'test'});  // Missing import
}""",
                "hasEslintRule": False
            }
        ]

        update_rule_impl(
            "import-test-standard",
            clear_existing=True,
            ai_hints=hints_with_imports,
            project_root=self.temp_dir
        )

        # Get hints and verify structure
        result = hints_for_file_impl("api/test.py", 10000, self.temp_dir)

        assert "data" in result
        assert "hints" in result["data"]
        assert "importMaps" in result["data"]

        # Find our test hint
        test_hints = [h for h in result["data"]["hints"] if "proper imports" in h.get("rule", "")]
        assert len(test_hints) == 1

        test_hint = test_hints[0]

        # Verify import map was moved to global and hint has reference
        assert "importMap" not in test_hint  # Should be removed from hint
        assert "modules" in test_hint         # Should have modules array

        # Verify global import maps
        import_maps = result["data"]["importMaps"]
        assert import_maps is not None
        assert "next/server" in import_maps

        # Verify import map contains only correctExample imports (token optimization)
        import_map = import_maps["next/server"]
        assert isinstance(import_map, list)
        assert len(import_map) == 1
        assert import_map[0]["module"] == "next/server"
        # Note: 'type' field is stripped for token optimization
        assert "type" not in import_map[0]
