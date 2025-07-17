"""Integration tests for the new register -> add_hint -> add_rule flow."""

import json
import os
import tempfile
from pathlib import Path

from aromcp.standards_server.tools.add_hint import add_hint_impl
from aromcp.standards_server.tools.add_rule import add_rule_impl, list_rules_impl
from aromcp.standards_server.tools.register import register_impl


class TestNewRegistrationFlow:
    """Test the complete new registration flow."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_complete_new_flow(self):
        """Test the complete new flow: register -> add_hint -> add_rule."""

        # 1. Create source file
        source_file = Path(self.temp_dir) / "standards" / "validation.md"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# Validation Standard")

        # 2. Register standard with metadata only (no rules)
        metadata = {
            "id": "validation-standard",
            "name": "Input Validation Standard",
            "category": "security",
            "tags": ["validation", "security", "zod"],
            "appliesTo": ["*.ts", "*.js"],
            "severity": "error",
            "priority": "required",
            "context_triggers": {
                "task_types": ["validation", "form_handling"],
                "file_patterns": ["**/api/**/*.ts", "**/*.tsx"],
                "code_patterns": ["z.object", "schema.parse"],
                "import_indicators": ["zod"],
                "nextjs_features": ["app-router"],
            },
            "optimization": {
                "priority": "critical",
                "load_frequency": "common",
                "compressible": True,
                "cacheable": True,
                "example_reusability": "high",
                "context_sensitive": True,
            },
            "relationships": {
                "similar_to": ["error-handling"],
                "commonly_used_with": ["api-standards"],
                "conflicts_with": [],
            },
            "nextjs_config": {"router_preference": "app", "rendering_strategy": "server"},
        }

        register_result = register_impl("standards/validation.md", metadata, self.temp_dir, enhanced_format=True)

        assert "data" in register_result
        assert register_result["data"]["standardId"] == "validation-standard"
        assert register_result["data"]["enhanced"] is True

        # Verify metadata file was created
        metadata_file = Path(self.temp_dir) / ".aromcp" / "hints" / "validation-standard" / "metadata.json"
        assert metadata_file.exists()

        # 3. Add multiple hints iteratively
        hint1_data = {
            "rule": "ALWAYS VALIDATE INPUT - Use Zod schemas for all user input",
            "rule_id": "validate-input-zod",
            "context": "Input validation prevents runtime errors and security vulnerabilities",
            "metadata": {
                "pattern_type": "validation",
                "complexity": "intermediate",
                "rule_type": "must",
                "nextjs_api": ["app-router", "api-routes"],
                "client_server": "server-only",
            },
            "compression": {
                "example_sharable": True,
                "pattern_extractable": True,
                "progressive_detail": ["minimal", "standard", "detailed", "full"],
            },
            "examples": {
                "minimal": "schema.parse(input)",
                "standard": "const validated = inputSchema.parse(body);",
                "detailed": "import { z } from 'zod';\nconst schema = z.object({ email: z.string() });\n"
                "const validated = schema.parse(input);",
                "full": "import { z } from 'zod';\nimport { NextRequest } from 'next/server';\n\n"
                "const createUserSchema = z.object({\n  email: z.string().email(),\n  "
                "name: z.string().min(1).max(100)\n});\n\nexport async function POST(request: NextRequest) {\n  "
                "const body = await request.json();\n  const validated = createUserSchema.parse(body);\n  "
                "return Response.json({ success: true, data: validated });\n}",
                "reference": "See src/app/api/users/route.ts",
            },
            "has_eslint_rule": True,
            "relationships": {
                "similar_rules": ["validate-output-zod"],
                "prerequisite_rules": [],
                "see_also": ["error-handling"],
            },
        }

        hint1_result = add_hint_impl("validation-standard", hint1_data, self.temp_dir)
        assert "data" in hint1_result
        assert hint1_result["data"]["hintNumber"] == 1
        assert hint1_result["data"]["hintId"] == "validate-input-zod"

        # Add second hint
        hint2_data = {
            "rule": "VALIDATE OUTPUT - Ensure API responses match expected schemas",
            "rule_id": "validate-output-zod",
            "context": "Output validation ensures data integrity and API contract compliance",
            "metadata": {
                "pattern_type": "validation",
                "complexity": "intermediate",
                "rule_type": "should",
                "nextjs_api": ["app-router", "api-routes"],
                "client_server": "server-only",
            },
            "examples": {
                "full": "const responseSchema = z.object({ id: z.string(), email: z.string().email() });\n"
                "const response = responseSchema.parse(userData);\nreturn Response.json(response);"
            },
            "has_eslint_rule": False,
        }

        hint2_result = add_hint_impl("validation-standard", hint2_data, self.temp_dir)
        assert "data" in hint2_result
        assert hint2_result["data"]["hintNumber"] == 2
        assert hint2_result["data"]["hintId"] == "validate-output-zod"

        # Verify hint files were created
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "validation-standard"
        assert (hints_dir / "hint-001.json").exists()
        assert (hints_dir / "hint-002.json").exists()

        # 4. Add ESLint rules for hints that have has_eslint_rule: true
        eslint_rule_content = """module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Require input validation with Zod schemas',
            category: 'Best Practices',
            recommended: true
        },
        messages: {
            missingValidation: 'API handler should validate input with Zod schema'
        },
        fixable: 'code'
    },
    create(context) {
        return {
            'CallExpression[callee.property.name=/^(POST|PUT|PATCH)$/]': function(node) {
                // Check for validation pattern
                const parent = node.parent;
                const sourceCode = context.getSourceCode();
                const text = sourceCode.getText(parent);

                if (!text.includes('.parse(') && !text.includes('.safeParse(')) {
                    context.report({
                        node: node,
                        messageId: 'missingValidation'
                    });
                }
            }
        };
    }
};"""

        rule_result = add_rule_impl("validation-standard", "validate-input-zod", eslint_rule_content, self.temp_dir)
        assert "data" in rule_result
        assert rule_result["data"]["ruleName"] == "validate-input-zod"
        assert rule_result["data"]["standardId"] == "validation-standard"

        # Verify ESLint rule file was created
        rule_file = Path(rule_result["data"]["ruleFile"])
        assert rule_file.exists()
        assert rule_file.name == "validation-standard-validate-input-zod.js"
        assert rule_file.read_text() == eslint_rule_content

        # 5. List rules to verify
        rules_list = list_rules_impl("validation-standard", self.temp_dir)
        assert "data" in rules_list
        assert len(rules_list["data"]["rules"]) == 1
        assert rules_list["data"]["rules"][0]["ruleName"] == "validate-input-zod"

        # 6. Verify the index was updated throughout the process
        index_file = Path(self.temp_dir) / ".aromcp" / "hints" / "index.json"
        assert index_file.exists()

        with open(index_file) as f:
            index = json.load(f)

        assert "standards" in index
        assert "validation-standard" in index["standards"]
        assert index["standards"]["validation-standard"]["category"] == "security"

    def test_register_clears_existing_data(self):
        """Test that register clears existing hints and rules."""

        # Set up initial standard with hints and rules
        metadata = {
            "id": "test-clear",
            "name": "Test Clear",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.js"],
            "severity": "warning",
            "priority": "recommended",
        }

        # First registration
        register_impl("standards/test.md", metadata, self.temp_dir)

        # Add some hints and rules
        hint_data = {"rule": "Test rule", "rule_id": "test-rule", "context": "Test"}
        add_hint_impl("test-clear", hint_data, self.temp_dir)
        add_rule_impl("test-clear", "test-rule", "module.exports = {};", self.temp_dir)

        # Verify they exist
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-clear"
        rules_dir = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules"
        assert (hints_dir / "hint-001.json").exists()
        assert (rules_dir / "test-clear-test-rule.js").exists()

        # Register again (should clear)
        register_impl("standards/test.md", metadata, self.temp_dir)

        # Verify they were cleared
        assert not (hints_dir / "hint-001.json").exists()
        assert not (rules_dir / "test-clear-test-rule.js").exists()

        # But the hints directory and metadata should still exist
        assert hints_dir.exists()
        assert (hints_dir / "metadata.json").exists()
