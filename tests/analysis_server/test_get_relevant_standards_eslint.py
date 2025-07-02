"""Tests for get_relevant_standards tool using ESLint rules."""

import tempfile
import shutil
from pathlib import Path
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aromcp.analysis_server.tools.get_relevant_standards import get_relevant_standards_impl


class TestGetRelevantStandardsESLint:
    """Test class for ESLint-based get_relevant_standards functionality."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.rules_dir = Path(self.temp_dir) / ".aromcp" / "generated-rules" / "rules"
        self.rules_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test environment after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_sample_eslint_rule(self, filename: str, content: str):
        """Helper to create a sample ESLint rule file."""
        rule_path = self.rules_dir / filename
        rule_path.write_text(content, encoding='utf-8')
        return str(rule_path)

    def create_sample_file(self, relative_path: str, content: str = "// Sample file"):
        """Helper to create a sample project file."""
        file_path = Path(self.temp_dir) / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def test_basic_eslint_rule_matching(self):
        """Test basic file-to-ESLint-rule matching."""
        # Create API route ESLint rule
        api_rule = """/*
 * @aromcp-rule-id: api-async-handlers
 * @aromcp-patterns: ["**/routes/**/*.ts", "**/api/**/*.ts"]
 * @aromcp-severity: error
 * @aromcp-tags: ["api", "routes", "async"]
 * @aromcp-description: Require async handlers for API routes
 */

module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Require async handlers for API routes',
            category: 'Best Practices',
            recommended: true
        },
        fixable: null,
        schema: []
    },

    create(context) {
        return {
            // ESLint rule implementation
        };
    }
};"""
        self.create_sample_eslint_rule("api-async-handlers.js", api_rule)
        
        # Create a sample API route file
        api_file = self.create_sample_file("src/api/users.ts")
        
        # Test matching
        result = get_relevant_standards_impl(
            file_path=api_file,
            project_root=self.project_root,
            include_general=True
        )
        
        # Verify success
        assert "data" in result
        assert result["data"]["file_path"] == api_file
        assert result["data"]["file_exists"]
        assert len(result["data"]["applicable_rules"]) > 0
        
        # Check if API rule matched
        api_matches = [r for r in result["data"]["applicable_rules"] if r["rule_id"] == "api-async-handlers"]
        assert len(api_matches) == 1
        assert api_matches[0]["specificity"] > 0.3  # Should have good specificity
        assert api_matches[0]["eslint_rule_name"] == "@aromcp/api-async-handlers"
        assert "api" in result["data"]["categories"]

    def test_eslint_rule_specificity_ordering(self):
        """Test that more specific ESLint rule patterns get higher priority."""
        # Create general TypeScript rule
        general_rule = """/*
 * @aromcp-rule-id: general-typescript
 * @aromcp-patterns: ["**/*.ts", "**/*.tsx"]
 * @aromcp-severity: info
 * @aromcp-tags: ["typescript", "general"]
 * @aromcp-description: General TypeScript best practices
 */

module.exports = {
    meta: {
        type: 'suggestion',
        docs: {
            description: 'General TypeScript best practices',
            category: 'Best Practices',
            recommended: false
        },
        fixable: null,
        schema: []
    },

    create(context) {
        return {};
    }
};"""
        
        # Create specific component rule
        component_rule = """/*
 * @aromcp-rule-id: component-naming
 * @aromcp-patterns: ["**/components/**/*.tsx"]
 * @aromcp-severity: error
 * @aromcp-tags: ["components", "react", "naming"]
 * @aromcp-description: Enforce consistent component naming conventions
 */

module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Enforce consistent component naming conventions',
            category: 'Stylistic Issues',
            recommended: true
        },
        fixable: null,
        schema: []
    },

    create(context) {
        return {};
    }
};"""
        
        self.create_sample_eslint_rule("general-typescript.js", general_rule)
        self.create_sample_eslint_rule("component-naming.js", component_rule)
        
        # Create a component file
        component_file = self.create_sample_file("src/components/Header.tsx")
        
        result = get_relevant_standards_impl(
            file_path=component_file,
            project_root=self.project_root,
            include_general=True
        )
        
        assert "data" in result
        rules = result["data"]["applicable_rules"]
        
        # Should match both rules
        assert len(rules) == 2
        
        # More specific rule should come first (higher specificity)
        assert rules[0]["rule_id"] == "component-naming"
        assert rules[1]["rule_id"] == "general-typescript"
        assert rules[0]["specificity"] > rules[1]["specificity"]

    def test_eslint_rule_categorization(self):
        """Test ESLint rule categorization by severity."""
        # Create rules with different severities
        error_rule = """/*
 * @aromcp-rule-id: critical-api
 * @aromcp-patterns: ["**/api/**/*.ts"]
 * @aromcp-severity: error
 * @aromcp-tags: ["api", "critical"]
 * @aromcp-description: Critical API rules
 */
module.exports = { meta: {}, create() { return {}; } };"""

        warn_rule = """/*
 * @aromcp-rule-id: recommended-components
 * @aromcp-patterns: ["**/components/**/*.tsx"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["components", "recommended"]
 * @aromcp-description: Recommended component rules
 */
module.exports = { meta: {}, create() { return {}; } };"""

        info_rule = """/*
 * @aromcp-rule-id: optional-utils
 * @aromcp-patterns: ["**/utils/**/*.ts"]
 * @aromcp-severity: info
 * @aromcp-tags: ["utils", "optional"]
 * @aromcp-description: Optional utility rules
 */
module.exports = { meta: {}, create() { return {}; } };"""
        
        self.create_sample_eslint_rule("critical-api.js", error_rule)
        self.create_sample_eslint_rule("recommended-components.js", warn_rule)
        self.create_sample_eslint_rule("optional-utils.js", info_rule)
        
        # Test API file (should get error rule)
        api_file = self.create_sample_file("src/api/users.ts")
        result = get_relevant_standards_impl(api_file, self.project_root)
        
        assert "data" in result
        assert result["data"]["rules_by_category"]["critical"] == 1
        assert result["data"]["rules_by_category"]["recommended"] == 0
        assert result["data"]["rules_by_category"]["optional"] == 0

    def test_no_eslint_rules_exist(self):
        """Test graceful handling when no ESLint rules directory exists."""
        # Remove the rules directory
        shutil.rmtree(self.rules_dir)
        
        # Create a sample file
        sample_file = self.create_sample_file("src/app.ts")
        
        result = get_relevant_standards_impl(
            file_path=sample_file,
            project_root=self.project_root,
            include_general=True
        )
        
        # Should return helpful error
        assert "error" in result
        assert result["error"]["code"] == "ESLINT_RULES_NOT_FOUND"
        assert "ESLint rule generation command" in result["error"]["message"]
        assert "suggestion" in result["error"]

    def test_eslint_rule_metadata_extraction(self):
        """Test extraction of metadata from ESLint rule comments."""
        # Create rule with comprehensive metadata
        comprehensive_rule = """/*
 * @aromcp-rule-id: comprehensive-test
 * @aromcp-patterns: ["**/test/**/*.spec.ts", "**/test/**/*.test.ts"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["testing", "jest", "quality"]
 * @aromcp-description: Comprehensive testing standards
 */

module.exports = {
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Comprehensive testing standards',
            category: 'Testing',
            recommended: true
        },
        fixable: 'code',
        schema: [
            {
                type: 'object',
                properties: {
                    enforceAsync: { type: 'boolean' }
                }
            }
        ]
    },

    create(context) {
        return {
            CallExpression(node) {
                // Rule implementation
            }
        };
    }
};"""
        
        self.create_sample_eslint_rule("comprehensive-test.js", comprehensive_rule)
        
        # Create test file
        test_file = self.create_sample_file("src/test/component.spec.ts")
        
        result = get_relevant_standards_impl(test_file, self.project_root)
        
        assert "data" in result
        rules = result["data"]["applicable_rules"]
        assert len(rules) == 1
        
        rule = rules[0]
        assert rule["rule_id"] == "comprehensive-test"
        assert rule["severity"] == "warn"
        assert set(rule["tags"]) == {"testing", "jest", "quality"}
        assert rule["name"] == "Comprehensive testing standards"
        assert rule["eslint_rule_name"] == "@aromcp/comprehensive-test"
        assert len(rule["patterns"]) == 2

    def test_file_categories_from_patterns(self):
        """Test that file categories are detected from rule patterns."""
        # Create rule that covers multiple file types
        multi_type_rule = """/*
 * @aromcp-rule-id: multi-type
 * @aromcp-patterns: ["**/api/**/*.ts", "**/components/**/*.tsx", "**/utils/**/*.js"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["multi", "coverage"]
 * @aromcp-description: Multi-type coverage rule
 */
module.exports = { meta: {}, create() { return {}; } };"""
        
        self.create_sample_eslint_rule("multi-type.js", multi_type_rule)
        
        # Test different file types
        test_cases = [
            ("src/api/users.ts", ["typescript", "api"]),
            ("src/components/Button.tsx", ["typescript", "react", "components"]),
            ("src/utils/helpers.js", ["javascript", "utilities"])
        ]
        
        for file_path, expected_categories in test_cases:
            sample_file = self.create_sample_file(file_path)
            result = get_relevant_standards_impl(sample_file, self.project_root)
            
            assert "data" in result
            categories = result["data"]["categories"]
            
            # Check that expected categories are present
            for expected_cat in expected_categories:
                assert expected_cat in categories, f"Expected category '{expected_cat}' missing for {file_path}"

    def test_eslint_config_section_detection(self):
        """Test ESLint config section determination."""
        rules = [
            ("api-rule.js", ["**/api/**/*.ts"], "api-routes"),
            ("component-rule.js", ["**/components/**/*.tsx"], "components"),
            ("test-rule.js", ["**/test/**/*.spec.ts"], "testing"),
            ("general-ts-rule.js", ["**/*.ts"], "typescript"),
            ("general-js-rule.js", ["**/*.js"], "javascript")
        ]
        
        for rule_file, patterns, expected_section in rules:
            rule_content = f"""/*
 * @aromcp-rule-id: {rule_file.replace('.js', '')}
 * @aromcp-patterns: {patterns}
 * @aromcp-severity: warn
 * @aromcp-tags: ["test"]
 * @aromcp-description: Test rule
 */
module.exports = {{ meta: {{}}, create() {{ return {{}}; }} }};"""
            
            self.create_sample_eslint_rule(rule_file, rule_content)
        
        # Test files and their expected config sections
        test_cases = [
            ("src/api/users.ts", "api-routes"),
            ("src/components/Button.tsx", "components"),
            ("src/test/button.spec.ts", "testing"),
            ("src/types/user.ts", "typescript"),
            ("src/legacy/old.js", "javascript")
        ]
        
        for file_path, expected_section in test_cases:
            sample_file = self.create_sample_file(file_path)
            result = get_relevant_standards_impl(sample_file, self.project_root)
            
            if "data" in result and result["data"]["applicable_rules"]:
                assert result["data"]["eslint_config_section"] == expected_section

    def test_registry_info_in_response(self):
        """Test that registry information is included in response."""
        # Create a simple rule
        simple_rule = """/*
 * @aromcp-rule-id: simple
 * @aromcp-patterns: ["**/*.ts"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["simple"]
 * @aromcp-description: Simple test rule
 */
module.exports = { meta: {}, create() { return {}; } };"""
        
        self.create_sample_eslint_rule("simple.js", simple_rule)
        
        sample_file = self.create_sample_file("src/test.ts")
        result = get_relevant_standards_impl(sample_file, self.project_root)
        
        assert "data" in result
        registry_info = result["data"]["registry_info"]
        
        assert "total_rules_available" in registry_info
        assert "rules_directory" in registry_info
        assert "last_updated" in registry_info
        assert registry_info["total_rules_available"] == 1
        assert str(self.rules_dir) in registry_info["rules_directory"]

    def test_invalid_file_path_handling(self):
        """Test handling of invalid file paths (same as before)."""
        # Create a rule
        simple_rule = """/*
 * @aromcp-rule-id: simple
 * @aromcp-patterns: ["**/*.ts"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["simple"]
 * @aromcp-description: Simple test rule
 */
module.exports = { meta: {}, create() { return {}; } };"""
        
        self.create_sample_eslint_rule("simple.js", simple_rule)
        
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

    def test_severity_distribution_summary(self):
        """Test severity distribution in summary statistics."""
        # Create rules with different severities
        rules = [
            ("error1.js", "error"),
            ("error2.js", "error"), 
            ("warn1.js", "warn"),
            ("info1.js", "info")
        ]
        
        for rule_file, severity in rules:
            rule_content = f"""/*
 * @aromcp-rule-id: {rule_file.replace('.js', '')}
 * @aromcp-patterns: ["**/*.ts"]
 * @aromcp-severity: {severity}
 * @aromcp-tags: ["test"]
 * @aromcp-description: Test rule
 */
module.exports = {{ meta: {{}}, create() {{ return {{}}; }} }};"""
            
            self.create_sample_eslint_rule(rule_file, rule_content)
        
        sample_file = self.create_sample_file("src/test.ts")
        result = get_relevant_standards_impl(sample_file, self.project_root)
        
        assert "data" in result
        severity_dist = result["data"]["summary"]["severity_distribution"]
        
        assert severity_dist["error"] == 2
        assert severity_dist["warn"] == 1
        assert severity_dist["info"] == 1