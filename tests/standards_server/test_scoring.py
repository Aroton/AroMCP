"""Tests for scoring utilities."""


from aromcp.standards_server._scoring import (
    _estimate_tokens,
    _matches_pattern,
    score_relevance,
    select_hints_by_budget,
)


class TestScoring:
    """Test scoring functionality."""

    def test_exact_folder_match(self):
        """Test exact folder match scoring."""
        metadata = {
            "category": "api",
            "tags": ["error", "exceptions"],
            "appliesTo": ["*.py"],
            "priority": "required"
        }

        # Exact category match
        score = score_relevance(metadata, "api/users.py")
        assert score == 1.0 * 1.2  # 1.0 for exact match * 1.2 for required priority

        # Exact tag match in folder
        score = score_relevance(metadata, "error/handler.py")
        assert score == 1.0 * 1.2

    def test_glob_pattern_match(self):
        """Test glob pattern match scoring."""
        metadata = {
            "category": "widgets",  # Different from folder name to avoid exact match
            "tags": ["ui"],
            "appliesTo": ["components/*.tsx", "*.jsx"],
            "priority": "important"
        }

        # Pattern match (no exact folder match, so uses glob pattern)
        score = score_relevance(metadata, "components/Button.tsx")
        assert score == 0.8 * 1.1  # 0.8 for pattern match * 1.1 for important priority

        # Different pattern match
        score = score_relevance(metadata, "src/MyComponent.jsx")
        assert score == 0.8 * 1.1

    def test_category_in_path(self):
        """Test category substring match scoring."""
        metadata = {
            "category": "api",
            "tags": ["test"],
            "appliesTo": ["*.other"],
            "priority": "recommended"
        }

        # Category substring in folder
        score = score_relevance(metadata, "src/api-routes/handler.py")
        assert score == 0.6 * 1.0  # 0.6 for category in path * 1.0 for recommended

    def test_tag_in_path(self):
        """Test tag substring match scoring."""
        metadata = {
            "category": "other",
            "tags": ["error", "validation"],
            "appliesTo": ["*.other"],
            "priority": "recommended"
        }

        # Tag in path
        score = score_relevance(metadata, "src/error-handling/utils.py")
        assert score == 0.4 * 1.0  # 0.4 for tag in path

        # Tag in filename
        score = score_relevance(metadata, "src/utils/validation.py")
        assert score == 0.4 * 1.0

    def test_no_match(self):
        """Test no relevance match."""
        metadata = {
            "category": "api",
            "tags": ["error"],
            "appliesTo": ["*.js"],
            "priority": "required"
        }

        score = score_relevance(metadata, "unrelated/file.txt")
        assert score == 0.0

    def test_priority_multipliers(self):
        """Test priority multiplier effects."""
        base_metadata = {
            "category": "test",
            "tags": [],
            "appliesTo": [],
            "priority": "required"
        }

        # Required priority
        metadata_required = {**base_metadata, "priority": "required"}
        score = score_relevance(metadata_required, "test/file.py")
        assert score == 1.0 * 1.2

        # Important priority
        metadata_important = {**base_metadata, "priority": "important"}
        score = score_relevance(metadata_important, "test/file.py")
        assert score == 1.0 * 1.1

        # Recommended priority
        metadata_recommended = {**base_metadata, "priority": "recommended"}
        score = score_relevance(metadata_recommended, "test/file.py")
        assert score == 1.0 * 1.0

        # Unknown priority defaults to 1.0
        metadata_unknown = {**base_metadata, "priority": "unknown"}
        score = score_relevance(metadata_unknown, "test/file.py")
        assert score == 1.0 * 1.0

    def test_case_insensitive_matching(self):
        """Test that matching is case insensitive."""
        metadata = {
            "category": "API",
            "tags": ["Error"],
            "appliesTo": [],
            "priority": "required"
        }

        # Category match (case insensitive)
        score = score_relevance(metadata, "api/users.py")
        assert score > 0

        # Tag match (case insensitive)
        score = score_relevance(metadata, "error/handler.py")
        assert score > 0

    def test_matches_pattern(self):
        """Test glob pattern matching utility."""
        assert _matches_pattern("api/users.py", "api/*.py") is True
        assert _matches_pattern("components/Button.tsx", "*.tsx") is True
        assert _matches_pattern("src/utils.js", "*/utils.js") is True
        assert _matches_pattern("test.py", "*.py") is True

        # No match cases
        assert _matches_pattern("api/users.js", "*.py") is False
        assert _matches_pattern("other/file.py", "api/*.py") is False

        # Invalid patterns should not crash
        assert _matches_pattern("file.py", None) is False
        assert _matches_pattern("file.py", 123) is False

    def test_estimate_tokens(self):
        """Test token estimation utility."""
        hint = {
            "rule": "Use proper error handling",
            "context": "This helps with debugging",
            "correctExample": "try: ... except: ...",
            "incorrectExample": "just do it"
        }

        tokens = _estimate_tokens(hint)
        assert tokens > 0
        assert isinstance(tokens, int)

        # Larger hint should have more tokens
        large_hint = {
            "rule": "A very long rule description that goes on and on with lots of detail",
            "context": "An extensive context explanation with many words and detailed information",
            "correctExample": "def very_detailed_function_example(): pass # with comments",
            "incorrectExample": "bad_example = lambda: None  # poorly written code"
        }

        large_tokens = _estimate_tokens(large_hint)
        assert large_tokens > tokens

    def test_select_hints_by_budget_basic(self):
        """Test basic hint selection within budget."""
        hints_with_scores = [
            ({"rule": "Rule 1", "context": "Context 1", "correctExample": "ex1",
              "incorrectExample": "bad1", "tokens": 50, "metadata": {"priority": "required"}}, 1.0),
            ({"rule": "Rule 2", "context": "Context 2", "correctExample": "ex2",
              "incorrectExample": "bad2", "tokens": 30, "metadata": {"priority": "important"}}, 0.8),
            ({"rule": "Rule 3", "context": "Context 3", "correctExample": "ex3",
              "incorrectExample": "bad3", "tokens": 40, "metadata": {"priority": "recommended"}}, 0.6)
        ]

        selected, total_tokens = select_hints_by_budget(hints_with_scores, 100)

        assert len(selected) > 0
        assert total_tokens <= 100

        # Should be sorted by relevance score
        if len(selected) > 1:
            scores = [hint["relevanceScore"] for hint in selected]
            assert scores == sorted(scores, reverse=True)

    def test_select_hints_by_budget_tight(self):
        """Test hint selection with tight budget."""
        hints_with_scores = [
            ({"rule": "Rule 1", "context": "Context 1", "correctExample": "ex1",
              "incorrectExample": "bad1", "tokens": 80, "metadata": {"priority": "required"}}, 1.0),
            ({"rule": "Rule 2", "context": "Context 2", "correctExample": "ex2",
              "incorrectExample": "bad2", "tokens": 70, "metadata": {"priority": "important"}}, 0.8)
        ]

        selected, total_tokens = select_hints_by_budget(hints_with_scores, 100)

        # Should only get the highest scoring hint that fits
        assert len(selected) == 1
        assert selected[0]["relevanceScore"] == 1.0
        assert total_tokens == 80

    def test_select_hints_by_budget_empty(self):
        """Test hint selection with empty input."""
        selected, total_tokens = select_hints_by_budget([], 1000)

        assert selected == []
        assert total_tokens == 0

    def test_select_hints_by_budget_no_tokens_field(self):
        """Test hint selection when hints don't have tokens field."""
        hints_with_scores = [
            ({"rule": "Rule 1", "context": "Context 1", "correctExample": "ex1",
              "incorrectExample": "bad1", "metadata": {"priority": "required"}}, 1.0)
        ]

        selected, total_tokens = select_hints_by_budget(hints_with_scores, 1000)

        # Should estimate tokens and still work
        assert len(selected) == 1
        assert total_tokens > 0
        assert "relevanceScore" in selected[0]

    def test_priority_sorting(self):
        """Test that hints are sorted by priority when scores are equal."""
        hints_with_scores = [
            ({"rule": "Rule 1", "context": "Context 1", "correctExample": "ex1",
              "incorrectExample": "bad1", "tokens": 30, "metadata": {"priority": "recommended"}}, 0.5),
            ({"rule": "Rule 2", "context": "Context 2", "correctExample": "ex2",
              "incorrectExample": "bad2", "tokens": 30, "metadata": {"priority": "required"}}, 0.5),
            ({"rule": "Rule 3", "context": "Context 3", "correctExample": "ex3",
              "incorrectExample": "bad3", "tokens": 30, "metadata": {"priority": "important"}}, 0.5)
        ]

        selected, total_tokens = select_hints_by_budget(hints_with_scores, 1000)

        # Should get all hints, ordered by priority (required > important > recommended)
        assert len(selected) == 3
        assert selected[0]["rule"] == "Rule 2"  # required
        assert selected[1]["rule"] == "Rule 3"  # important
        assert selected[2]["rule"] == "Rule 1"  # recommended
