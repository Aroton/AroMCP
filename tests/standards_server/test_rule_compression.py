"""Tests for rule compression functionality."""


from aromcp.standards_server.models.enhanced_rule import EnhancedRule, RuleExamples, RuleMetadata, TokenCount
from aromcp.standards_server.services.rule_compressor import RuleCompressor
from aromcp.standards_server.services.session_manager import SessionState


class TestRuleCompressor:
    """Test RuleCompressor functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.compressor = RuleCompressor()
        self.session = SessionState("test-session")

        # Create sample enhanced rule
        self.sample_rule = EnhancedRule(
            rule="Always validate user input",
            rule_id="validation-001",
            context="When handling user input, always validate data before processing",
            metadata=RuleMetadata(
                pattern_type="validation",
                complexity="intermediate",
                rule_type="must"
            ),
            examples=RuleExamples(
                minimal="validate(input)",
                standard="const validated = schema.parse(input)",
                detailed="const validated = schema.parse(input); if (!validated) throw new Error('Invalid input');",
                full=(
                    "const validated = schema.parse(input); "
                    "if (!validated) { logger.error('Validation failed'); throw new Error('Invalid input'); }"
                )
            ),
            tokens=TokenCount(minimal=10, standard=25, detailed=50, full=100),
            has_eslint_rule=True
        )

    def test_determine_compression_strategy_reference(self):
        """Test determining reference strategy for already loaded rules."""
        # Add rule to session
        self.session.add_rule("validation-001", "validation", 100)

        context = {"pattern_familiarity": {}}
        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)

        assert strategy == "reference"

    def test_determine_compression_strategy_expert(self):
        """Test determining expert strategy."""
        context = {
            "pattern_familiarity": {"validation": "expert"}
        }

        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)
        assert strategy == "expert"

    def test_determine_compression_strategy_familiar(self):
        """Test determining familiar strategy."""
        context = {
            "pattern_familiarity": {"validation": "familiar"}
        }

        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)
        assert strategy == "familiar"

        context = {
            "pattern_familiarity": {"validation": "novice"}
        }

        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)
        assert strategy == "familiar"

    def test_determine_compression_strategy_first_time(self):
        """Test determining first-time strategy."""
        context = {
            "pattern_familiarity": {"validation": "new"}
        }

        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)
        assert strategy == "first_time"

        # Test with no familiarity data
        context = {"pattern_familiarity": {}}
        strategy = self.compressor._determine_compression_strategy(self.sample_rule, context, self.session)
        assert strategy == "first_time"

    def test_format_for_first_time_detailed(self):
        """Test formatting for first-time viewing with detailed level."""
        context = {
            "task_type": "learning",
            "complexity_level": "basic",
            "session_phase": "exploration"
        }

        result = self.compressor._format_for_first_time(self.sample_rule, context, self.session)

        assert result["rule_id"] == "validation-001"
        assert result["rule"] == "Always validate user input"
        assert "context" in result
        assert "example" in result
        assert "imports" in result
        assert "metadata" in result
        assert result["has_eslint_rule"] is True
        assert result["tokens"] == 50  # detailed token count

    def test_format_for_first_time_standard(self):
        """Test formatting for first-time viewing with standard level."""
        context = {
            "task_type": "implementation",
            "complexity_level": "intermediate",
            "session_phase": "development"
        }

        result = self.compressor._format_for_first_time(self.sample_rule, context, self.session)

        assert result["rule_id"] == "validation-001"
        assert result["rule"] == "Always validate user input"
        assert "example" in result
        assert result["pattern_type"] == "validation"
        assert result["tokens"] == 25  # standard token count

    def test_format_for_familiar(self):
        """Test formatting for familiar patterns."""
        context = {}

        result = self.compressor._format_for_familiar(self.sample_rule, context, self.session)

        assert result["rule_id"] == "validation-001"
        assert result["rule"] == "Always validate user input"
        assert result["hint"] == "validate(input)"
        assert result["example"] == "const validated = schema.parse(input)"
        assert result["has_eslint_rule"] is True
        assert result["tokens"] == 25

    def test_format_for_expert(self):
        """Test formatting for expert users."""
        context = {}

        result = self.compressor._format_for_expert(self.sample_rule, context, self.session)

        assert result["rule_id"] == "validation-001"
        assert result["rule"] == "Always validate user input"
        assert result["hint"] == "validate(input)"
        assert result["has_eslint_rule"] is True
        assert result["tokens"] == 10

    def test_format_for_reference(self):
        """Test formatting for reference (already seen)."""
        context = {}

        result = self.compressor._format_for_reference(self.sample_rule, context, self.session)

        assert result["rule_id"] == "validation-001"
        assert "Previously loaded" in result["reference"]
        assert result["pattern_type"] == "validation"
        assert result["has_eslint_rule"] is True
        assert result["tokens"] == 5

    def test_determine_detail_level_task_based(self):
        """Test determining detail level based on task type."""
        # Debugging task
        context = {"task_type": "debugging"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "minimal"

        # Learning task
        context = {"task_type": "learning"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "detailed"

        # Exploration task
        context = {"task_type": "exploration"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "detailed"

        # Refactoring task
        context = {"task_type": "refactoring"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "standard"

    def test_determine_detail_level_complexity_based(self):
        """Test determining detail level based on complexity."""
        # Expert user with basic rule
        context = {"complexity_level": "expert"}
        expert_rule = EnhancedRule(
            rule="Basic rule",
            rule_id="basic-001",
            context="Basic context",
            metadata=RuleMetadata(pattern_type="validation", complexity="basic"),
            examples=RuleExamples(full="basic example"),
            tokens=TokenCount(full=50)
        )

        level = self.compressor._determine_detail_level(expert_rule, context, self.session)
        assert level == "minimal"

        # Basic user with advanced rule
        context = {"complexity_level": "basic"}
        advanced_rule = EnhancedRule(
            rule="Advanced rule",
            rule_id="advanced-001",
            context="Advanced context",
            metadata=RuleMetadata(pattern_type="validation", complexity="advanced"),
            examples=RuleExamples(full="advanced example"),
            tokens=TokenCount(full=200)
        )

        level = self.compressor._determine_detail_level(advanced_rule, context, self.session)
        assert level == "detailed"

    def test_determine_detail_level_session_phase_based(self):
        """Test determining detail level based on session phase."""
        # Exploration phase
        context = {"session_phase": "exploration"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "detailed"

        # Refinement phase
        context = {"session_phase": "refinement"}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "minimal"

        # Default case
        context = {}
        level = self.compressor._determine_detail_level(self.sample_rule, context, self.session)
        assert level == "standard"

    def test_compress_rule_success(self):
        """Test successful rule compression."""
        context = {"pattern_familiarity": {"validation": "expert"}}

        result = self.compressor.compress_rule(self.sample_rule, context, self.session)

        assert result["compression_strategy"] == "expert"
        assert result["original_tokens"] == 100
        assert result["rule_id"] == "validation-001"
        assert result["tokens"] == 10

    def test_compress_rule_fallback(self):
        """Test rule compression with fallback on error."""
        # Create invalid context to trigger error
        context = None

        result = self.compressor.compress_rule(self.sample_rule, context, self.session)

        assert result["compression_strategy"] == "fallback"
        assert result["rule_id"] == "validation-001"
        assert result["rule"] == "Always validate user input"

    def test_compress_rule_batch_within_budget(self):
        """Test compressing batch of rules within token budget."""
        rules = [self.sample_rule]
        context = {"pattern_familiarity": {"validation": "expert"}}
        max_tokens = 100

        result = self.compressor.compress_rule_batch(rules, context, self.session, max_tokens)

        assert len(result["rules"]) == 1
        assert len(result["references"]) == 0
        assert result["total_tokens"] <= max_tokens
        assert "compression_stats" in result

    def test_compress_rule_batch_exceeds_budget(self):
        """Test compressing batch when exceeding token budget."""
        # Create multiple rules that exceed budget
        rules = []
        for i in range(5):
            rule = EnhancedRule(
                rule=f"Rule {i}",
                rule_id=f"rule-{i}",
                context=f"Context {i}",
                metadata=RuleMetadata(pattern_type="validation"),
                examples=RuleExamples(full=f"Example {i}"),
                tokens=TokenCount(minimal=30, standard=50, detailed=75, full=100)
            )
            rules.append(rule)

        context = {"pattern_familiarity": {"validation": "familiar"}}
        max_tokens = 100  # Too small for all rules

        result = self.compressor.compress_rule_batch(rules, context, self.session, max_tokens)

        assert result["total_tokens"] <= max_tokens
        assert len(result["rules"]) < len(rules)  # Some rules should be excluded
        assert len(result["references"]) > 0  # Some rules should be references

    def test_sort_rules_by_priority(self):
        """Test sorting rules by priority and relevance."""
        # Create rules with different priorities
        must_rule = EnhancedRule(
            rule="Must rule",
            rule_id="must-001",
            context="Must context",
            metadata=RuleMetadata(pattern_type="validation", rule_type="must"),
            examples=RuleExamples(full="Must example"),
            tokens=TokenCount(full=100)
        )

        should_rule = EnhancedRule(
            rule="Should rule",
            rule_id="should-001",
            context="Should context",
            metadata=RuleMetadata(pattern_type="validation", rule_type="should"),
            examples=RuleExamples(full="Should example"),
            tokens=TokenCount(full=100)
        )

        may_rule = EnhancedRule(
            rule="May rule",
            rule_id="may-001",
            context="May context",
            metadata=RuleMetadata(pattern_type="validation", rule_type="may"),
            examples=RuleExamples(full="May example"),
            tokens=TokenCount(full=100)
        )

        rules = [may_rule, should_rule, must_rule]  # Intentionally out of order
        context = {"pattern_familiarity": {}}

        sorted_rules = self.compressor._sort_rules_by_priority(rules, context, self.session)

        # Must rule should be first (highest priority)
        assert sorted_rules[0].rule_id == "must-001"
        assert sorted_rules[1].rule_id == "should-001"
        assert sorted_rules[2].rule_id == "may-001"

    def test_sort_rules_by_complexity_match(self):
        """Test sorting rules with complexity level matching."""
        # Create rules with different complexity levels
        basic_rule = EnhancedRule(
            rule="Basic rule",
            rule_id="basic-001",
            context="Basic context",
            metadata=RuleMetadata(pattern_type="validation", complexity="basic"),
            examples=RuleExamples(full="Basic example"),
            tokens=TokenCount(full=100)
        )

        intermediate_rule = EnhancedRule(
            rule="Intermediate rule",
            rule_id="intermediate-001",
            context="Intermediate context",
            metadata=RuleMetadata(pattern_type="validation", complexity="intermediate"),
            examples=RuleExamples(full="Intermediate example"),
            tokens=TokenCount(full=100)
        )

        rules = [basic_rule, intermediate_rule]
        context = {"complexity_level": "intermediate", "pattern_familiarity": {}}

        sorted_rules = self.compressor._sort_rules_by_priority(rules, context, self.session)

        # Intermediate rule should be first (matches complexity level)
        assert sorted_rules[0].rule_id == "intermediate-001"

    def test_sort_rules_by_pattern_familiarity(self):
        """Test sorting rules by pattern familiarity."""
        # Create rules with different patterns
        new_pattern_rule = EnhancedRule(
            rule="New pattern rule",
            rule_id="new-001",
            context="New context",
            metadata=RuleMetadata(pattern_type="new_pattern"),
            examples=RuleExamples(full="New example"),
            tokens=TokenCount(full=100)
        )

        familiar_pattern_rule = EnhancedRule(
            rule="Familiar pattern rule",
            rule_id="familiar-001",
            context="Familiar context",
            metadata=RuleMetadata(pattern_type="familiar_pattern"),
            examples=RuleExamples(full="Familiar example"),
            tokens=TokenCount(full=100)
        )

        rules = [familiar_pattern_rule, new_pattern_rule]
        context = {
            "pattern_familiarity": {"familiar_pattern": "expert"},
            "complexity_level": "intermediate"
        }

        sorted_rules = self.compressor._sort_rules_by_priority(rules, context, self.session)

        # New pattern should be first (higher priority for learning)
        assert sorted_rules[0].rule_id == "new-001"

    def test_get_compression_stats(self):
        """Test getting compression statistics."""
        compressed_rules = [
            {
                "rule_id": "rule1",
                "compression_strategy": "expert",
                "original_tokens": 100,
                "tokens": 20
            },
            {
                "rule_id": "rule2",
                "compression_strategy": "familiar",
                "original_tokens": 150,
                "tokens": 50
            },
            {
                "rule_id": "rule3",
                "compression_strategy": "expert",
                "original_tokens": 80,
                "tokens": 15
            }
        ]

        stats = self.compressor._get_compression_stats(compressed_rules)

        assert stats["strategies_used"]["expert"] == 2
        assert stats["strategies_used"]["familiar"] == 1
        assert stats["total_original_tokens"] == 330
        assert stats["total_compressed_tokens"] == 85
        assert stats["rules_processed"] == 3

        expected_ratio = 1.0 - (85 / 330)
        assert abs(stats["compression_ratio"] - expected_ratio) < 0.01

    def test_session_state_update_during_compression(self):
        """Test that session state is updated during compression."""
        rules = [self.sample_rule]
        context = {"pattern_familiarity": {"validation": "familiar"}}
        max_tokens = 100

        # Session should be empty initially
        assert len(self.session.loaded_rule_ids) == 0
        assert len(self.session.loaded_patterns) == 0
        assert self.session.token_count == 0

        self.compressor.compress_rule_batch(rules, context, self.session, max_tokens)

        # Session should be updated
        assert "validation-001" in self.session.loaded_rule_ids
        assert "validation" in self.session.loaded_patterns
        assert self.session.token_count > 0

