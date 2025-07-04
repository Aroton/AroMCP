"""Tests for parse_lint_results tool."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from aromcp.build_server.tools.parse_lint_results import (
    _get_standards_eslint_config,
    _is_nextjs_project,
    _parse_eslint_output,
    parse_lint_results_impl,
)


class TestParseLintResults(unittest.TestCase):
    """Test cases for parse_lint_results functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(self.temp_dir))

    def test_nextjs_detection_with_package_json(self):
        """Test Next.js detection via package.json dependencies."""
        # Create package.json with Next.js dependency
        package_json = {
            "dependencies": {
                "next": "13.0.0",
                "react": "18.0.0"
            },
            "scripts": {
                "lint": "next lint"
            }
        }

        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        result = _is_nextjs_project(self.temp_dir)
        self.assertTrue(result)

    def test_nextjs_detection_with_dev_dependencies(self):
        """Test Next.js detection via package.json devDependencies."""
        # Create package.json with Next.js in devDependencies
        package_json = {
            "dependencies": {
                "react": "18.0.0"
            },
            "devDependencies": {
                "next": "13.0.0"
            }
        }

        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        result = _is_nextjs_project(self.temp_dir)
        self.assertTrue(result)

    def test_nextjs_detection_with_config_file(self):
        """Test Next.js detection via next.config.js."""
        # Create next.config.js
        with open(os.path.join(self.temp_dir, "next.config.js"), "w") as f:
            f.write("module.exports = {}")

        result = _is_nextjs_project(self.temp_dir)
        self.assertTrue(result)

    def test_nextjs_detection_with_config_mjs(self):
        """Test Next.js detection via next.config.mjs."""
        # Create next.config.mjs
        with open(os.path.join(self.temp_dir, "next.config.mjs"), "w") as f:
            f.write("export default {}")

        result = _is_nextjs_project(self.temp_dir)
        self.assertTrue(result)

    def test_nextjs_detection_with_config_ts(self):
        """Test Next.js detection via next.config.ts."""
        # Create next.config.ts
        with open(os.path.join(self.temp_dir, "next.config.ts"), "w") as f:
            f.write("export default {}")

        result = _is_nextjs_project(self.temp_dir)
        self.assertTrue(result)

    def test_nextjs_detection_non_nextjs_project(self):
        """Test Next.js detection returns False for non-Next.js projects."""
        # Create regular package.json without Next.js
        package_json = {
            "dependencies": {
                "react": "18.0.0",
                "lodash": "4.17.21"
            }
        }

        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        result = _is_nextjs_project(self.temp_dir)
        self.assertFalse(result)

    def test_nextjs_detection_no_package_json(self):
        """Test Next.js detection with no package.json."""
        result = _is_nextjs_project(self.temp_dir)
        self.assertFalse(result)

    def test_nextjs_detection_invalid_package_json(self):
        """Test Next.js detection with invalid package.json."""
        # Create invalid JSON
        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            f.write("{ invalid json")

        result = _is_nextjs_project(self.temp_dir)
        self.assertFalse(result)

    def test_standards_eslint_config_detection(self):
        """Test standards ESLint config detection."""
        # Create standards config directory and file
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")

        # Write flat config format content
        flat_config_content = """const aromcpPlugin = require('./eslint-plugin-aromcp');

module.exports = [
  {
    plugins: {
      aromcp: aromcpPlugin,
    },
    rules: {
      'aromcp/test-rule': 'error',
    },
  },
];"""
        with open(config_path, "w") as f:
            f.write(flat_config_content)

        # Create the aromcp plugin file (required for standards config to be used)
        aromcp_plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(aromcp_plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        result = _get_standards_eslint_config(self.temp_dir)
        self.assertEqual(result, config_path)

    def test_standards_eslint_config_not_found(self):
        """Test standards ESLint config when file doesn't exist."""
        result = _get_standards_eslint_config(self.temp_dir)
        self.assertIsNone(result)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_eslint_command_generation_nextjs(self, mock_run):
        """Test ESLint command generation for Next.js projects."""
        # Setup Next.js project
        package_json = {
            "dependencies": {"next": "13.0.0"},
            "scripts": {"lint": "next lint"}
        }

        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            target_files=["src/components/Button.tsx"]
        )

        # Check that npm run lint was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertEqual(call_args[:3], ["npm", "run", "lint"])
        self.assertIn("--", call_args)
        self.assertIn("--format", call_args)
        self.assertIn("json", call_args)
        self.assertIn("src/components/Button.tsx", call_args)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_eslint_command_generation_standard(self, mock_run):
        """Test ESLint command generation for standard projects."""
        # Setup standard project (no Next.js)
        package_json = {
            "dependencies": {"react": "18.0.0"}
        }

        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            target_files=["src/utils/helper.js"]
        )

        # Check that npx eslint was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertEqual(call_args[:2], ["npx", "eslint"])
        self.assertIn("--format", call_args)
        self.assertIn("json", call_args)
        self.assertIn("src/utils/helper.js", call_args)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_standards_eslint_integration(self, mock_run):
        """Test standards ESLint config integration."""
        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")

        # Write flat config format content
        flat_config_content = """const aromcpPlugin = require('./eslint-plugin-aromcp');

module.exports = [
  {
    plugins: {
      aromcp: aromcpPlugin,
    },
    rules: {
      'aromcp/test-rule': 'error',
    },
  },
];"""
        with open(config_path, "w") as f:
            f.write(flat_config_content)

        # Create the aromcp plugin file (required for standards config to be used)
        aromcp_plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(aromcp_plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        # Check that config file was used
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertIn("--config", call_args)
        config_index = call_args.index("--config")
        self.assertEqual(call_args[config_index + 1], config_path)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_standards_eslint_takes_precedence_over_custom_config(self, mock_run):
        """Test that standards ESLint config takes precedence when use_standards_eslint=True."""
        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        standards_config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")

        # Write flat config format content
        flat_config_content = """const aromcpPlugin = require('./eslint-plugin-aromcp');

module.exports = [
  {
    plugins: {
      aromcp: aromcpPlugin,
    },
    rules: {
      'aromcp/test-rule': 'error',
    },
  },
];"""
        with open(standards_config_path, "w") as f:
            f.write(flat_config_content)

        # Create the aromcp plugin file (required for standards config to be used)
        aromcp_plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(aromcp_plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        # Create custom config
        custom_config_path = os.path.join(self.temp_dir, ".eslintrc.js")
        with open(custom_config_path, "w") as f:
            f.write("module.exports = { rules: { 'no-console': 'error' } }")

        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            config_file=custom_config_path,
            use_standards_eslint=True
        )

        # Check that standards config was used (not custom config)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertIn("--config", call_args)
        config_index = call_args.index("--config")
        self.assertEqual(call_args[config_index + 1], standards_config_path)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_custom_config_file_without_standards(self, mock_run):
        """Test that custom config file is used when standards ESLint is disabled."""
        # Create custom config
        custom_config_path = os.path.join(self.temp_dir, ".eslintrc.js")
        with open(custom_config_path, "w") as f:
            f.write("module.exports = { rules: { 'no-console': 'error' } }")

        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            config_file=custom_config_path,
            use_standards_eslint=False
        )

        # Check that custom config file was used
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertIn("--config", call_args)
        config_index = call_args.index("--config")
        self.assertEqual(call_args[config_index + 1], custom_config_path)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_eslint_output_parsing(self, mock_run):
        """Test ESLint output parsing."""
        # Mock ESLint JSON output
        eslint_output = [
            {
                "filePath": os.path.join(self.temp_dir, "src/component.js"),
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "Variable 'unused' is assigned a value but never used.",
                        "line": 5,
                        "column": 7,
                        "fix": None
                    },
                    {
                        "ruleId": "no-console",
                        "severity": 1,
                        "message": "Unexpected console statement.",
                        "line": 10,
                        "column": 3,
                        "fix": {"range": [100, 120], "text": ""}
                    }
                ]
            }
        ]

        mock_run.return_value = MagicMock(
            returncode=1,  # ESLint returns 1 when issues found
            stdout=json.dumps(eslint_output),
            stderr=''
        )

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir
        )

        # Verify successful parsing
        self.assertIn("data", result)
        self.assertIn("items", result["data"])
        self.assertEqual(len(result["data"]["items"]), 2)

        # Check first issue
        issue1 = result["data"]["items"][0]
        self.assertEqual(issue1["severity"], "error")
        self.assertEqual(issue1["rule"], "no-unused-vars")
        self.assertEqual(issue1["line"], 5)
        self.assertEqual(issue1["column"], 7)
        self.assertFalse(issue1["fixable"])

        # Check second issue
        issue2 = result["data"]["items"][1]
        self.assertEqual(issue2["severity"], "warning")
        self.assertEqual(issue2["rule"], "no-console")
        self.assertEqual(issue2["line"], 10)
        self.assertEqual(issue2["column"], 3)
        self.assertTrue(issue2["fixable"])

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_eslint_warnings_filtering(self, mock_run):
        """Test ESLint warnings filtering."""
        # Mock ESLint JSON output with warnings
        eslint_output = [
            {
                "filePath": os.path.join(self.temp_dir, "src/component.js"),
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "Variable 'unused' is assigned a value but never used.",
                        "line": 5,
                        "column": 7
                    },
                    {
                        "ruleId": "no-console",
                        "severity": 1,
                        "message": "Unexpected console statement.",
                        "line": 10,
                        "column": 3
                    }
                ]
            }
        ]

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps(eslint_output),
            stderr=''
        )

        # Test with warnings excluded
        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            include_warnings=False
        )

        # Should only have errors
        self.assertIn("data", result)
        self.assertIn("items", result["data"])
        self.assertEqual(len(result["data"]["items"]), 1)
        self.assertEqual(result["data"]["items"][0]["severity"], "error")

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = parse_lint_results_impl(
            linter="eslint",
            project_root="/nonexistent/path"
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "OPERATION_FAILED")

    def test_unsupported_linter(self):
        """Test handling of unsupported linter."""
        result = parse_lint_results_impl(
            linter="unsupported_linter",
            project_root=self.temp_dir
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNSUPPORTED")

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_eslint_timeout(self, mock_run):
        """Test ESLint timeout handling."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired(cmd=[], timeout=120)

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            timeout=120
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "TIMEOUT")

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_target_files_string_conversion(self, mock_run):
        """Test target_files parameter string to list conversion."""
        # Mock successful ESLint run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            target_files="src/component.js"  # String instead of list
        )

        # Check that string was converted to list
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # Get the command array
        self.assertIn("src/component.js", call_args)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_pagination_functionality(self, mock_run):
        """Test pagination functionality."""
        # Create mock output with multiple issues
        eslint_output = [
            {
                "filePath": os.path.join(self.temp_dir, f"src/component{i}.js"),
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": f"Variable 'unused{i}' is assigned a value but never used.",
                        "line": i + 1,
                        "column": 7
                    }
                ]
            }
            for i in range(50)  # Create 50 issues
        ]

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps(eslint_output),
            stderr=''
        )

        # Test first page
        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            page=1,
            max_tokens=1000  # Small limit to force pagination
        )

        self.assertIn("data", result)
        self.assertIn("pagination", result["data"])
        self.assertEqual(result["data"]["pagination"]["page"], 1)
        self.assertGreater(result["data"]["pagination"]["total_pages"], 1)

    def test_parse_eslint_output_function(self):
        """Test the _parse_eslint_output helper function."""

        # Create mock result with ESLint output
        eslint_output = [
            {
                "filePath": os.path.join(self.temp_dir, "src/component.js"),
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "Variable 'unused' is assigned a value but never used.",
                        "line": 5,
                        "column": 7,
                        "fix": None
                    }
                ]
            }
        ]

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(eslint_output)

        issues = _parse_eslint_output(mock_result, self.temp_dir, True, "test_source")

        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue["source"], "test_source")
        self.assertEqual(issue["rule"], "no-unused-vars")
        self.assertEqual(issue["severity"], "error")
        self.assertEqual(issue["file"], "src/component.js")

    def test_parse_eslint_output_nextjs_success_message(self):
        """Test _parse_eslint_output handles Next.js success message."""

        mock_result = MagicMock()
        mock_result.stdout = "✔ No ESLint warnings or errors"

        issues = _parse_eslint_output(mock_result, self.temp_dir, True, "nextjs")

        self.assertEqual(len(issues), 0)

    def test_parse_eslint_output_invalid_json(self):
        """Test _parse_eslint_output handles invalid JSON gracefully."""

        mock_result = MagicMock()
        mock_result.stdout = "invalid json output"

        issues = _parse_eslint_output(mock_result, self.temp_dir, True, "eslint")

        self.assertEqual(len(issues), 0)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_nextjs_with_standards_combined_mode(self, mock_run):
        """Test Next.js project with standards ESLint in combined mode."""
        # Setup Next.js project
        package_json = {
            "dependencies": {"next": "13.0.0"},
            "scripts": {"lint": "next lint"}
        }
        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("""const aromcpPlugin = require('./eslint-plugin-aromcp');
module.exports = [
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    ignores: ['.aromcp/**', 'node_modules/**'],
    plugins: { aromcp: aromcpPlugin },
    rules: { 'aromcp/test-rule': 'error' }
  }
];""")

        # Create plugin file
        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        # Mock ESLint outputs
        nextjs_output = [{"filePath": f"{self.temp_dir}/src/page.tsx", "messages": [
            {
                "ruleId": "react/no-unescaped-entities",
                "severity": 1,
                "message": "Unescaped entity",
                "line": 1,
                "column": 1
            }
        ]}]

        standards_output = [{"filePath": f"{self.temp_dir}/src/page.tsx", "messages": [
            {"ruleId": "aromcp/test-rule", "severity": 2, "message": "Test rule violation", "line": 2, "column": 1}
        ]}]

        # Mock multiple calls - first for Next.js, second for standards
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=json.dumps(nextjs_output), stderr=''),
            MagicMock(returncode=1, stdout=json.dumps(standards_output), stderr='')
        ]

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        # Should have called subprocess twice
        self.assertEqual(mock_run.call_count, 2)

        # Check first call (Next.js)
        first_call = mock_run.call_args_list[0][0][0]
        self.assertEqual(first_call[:3], ["npm", "run", "lint"])

        # Check second call (standards)
        second_call = mock_run.call_args_list[1][0][0]
        self.assertEqual(second_call[:2], ["npx", "eslint"])
        self.assertIn("--config", second_call)
        self.assertIn("--no-config-lookup", second_call)

        # Check combined results
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]["items"]), 2)

        # Check source tracking
        sources = [item["source"] for item in result["data"]["items"]]
        self.assertIn("nextjs", sources)
        self.assertIn("standards", sources)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_standards_eslint_no_config_lookup_flag(self, mock_run):
        """Test that standards ESLint uses --no-config-lookup flag."""
        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("""module.exports = [
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    ignores: ['.aromcp/**', 'node_modules/**'],
    rules: { 'aromcp/test-rule': 'error' }
  }
];""")

        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        # Mock successful run
        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        # Verify --no-config-lookup flag is present
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("--no-config-lookup", call_args)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_default_file_patterns_without_ignore_flags(self, mock_run):
        """Test that default file patterns work without command-line ignore flags."""
        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("""module.exports = [
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    ignores: ['.aromcp/**', 'node_modules/**', 'dist/**', 'build/**'],
    rules: { 'aromcp/test-rule': 'error' }
  }
];""")

        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: { 'test-rule': {} } }")

        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        # Verify no --ignore-pattern flags in command
        call_args = mock_run.call_args[0][0]
        self.assertNotIn("--ignore-pattern", call_args)

        # Should have "src" as target directory
        self.assertIn("src", call_args)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_command_metadata_tracking(self, mock_run):
        """Test that command metadata is properly tracked."""
        # Setup Next.js project with standards
        package_json = {"dependencies": {"next": "13.0.0"}}
        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("module.exports = []")

        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: {} }")

        # Mock successful runs
        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        # Check command metadata shows both were run
        self.assertIn("data", result)
        command = result["data"]["command"]
        self.assertIn("nextjs", command)
        self.assertIn("standards", command)

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_issue_source_attribution(self, mock_run):
        """Test that issues are properly attributed to their source."""
        # Setup Next.js project with standards
        package_json = {"dependencies": {"next": "13.0.0"}}
        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("module.exports = []")

        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: {} }")

        # Mock outputs with different sources
        nextjs_output = [{"filePath": f"{self.temp_dir}/src/page.tsx", "messages": [
            {"ruleId": "react/no-unescaped-entities", "severity": 1, "message": "React issue", "line": 1, "column": 1}
        ]}]

        standards_output = [{"filePath": f"{self.temp_dir}/src/utils.ts", "messages": [
            {"ruleId": "aromcp/custom-rule", "severity": 2, "message": "Standards issue", "line": 1, "column": 1}
        ]}]

        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=json.dumps(nextjs_output), stderr=''),
            MagicMock(returncode=1, stdout=json.dumps(standards_output), stderr='')
        ]

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            use_standards_eslint=True
        )

        issues = result["data"]["items"]
        self.assertEqual(len(issues), 2)

        # Find issues by rule and check source
        react_issue = next(i for i in issues if i["rule"] == "react/no-unescaped-entities")
        standards_issue = next(i for i in issues if i["rule"] == "aromcp/custom-rule")

        self.assertEqual(react_issue["source"], "nextjs")
        self.assertEqual(standards_issue["source"], "standards")

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_error_handling_configuration_errors(self, mock_run):
        """Test handling of ESLint configuration errors."""
        # Mock configuration error (exit code 2)
        mock_run.return_value = MagicMock(
            returncode=2,
            stdout='',
            stderr='ESLint configuration error: Invalid config'
        )

        result = parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "OPERATION_FAILED")
        self.assertIn("ESLint configuration error", result["error"]["message"])

    @patch('aromcp.build_server.tools.parse_lint_results.subprocess.run')
    def test_target_files_with_nextjs_and_standards(self, mock_run):
        """Test target files parameter with Next.js and standards combined."""
        # Setup Next.js project
        package_json = {"dependencies": {"next": "13.0.0"}}
        with open(os.path.join(self.temp_dir, "package.json"), "w") as f:
            json.dump(package_json, f)

        # Create standards config
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "eslint"))
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        with open(config_path, "w") as f:
            f.write("module.exports = []")

        plugin_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        with open(plugin_path, "w") as f:
            f.write("module.exports = { rules: {} }")

        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')

        target_files = ["src/components/Button.tsx", "src/pages/index.tsx"]

        parse_lint_results_impl(
            linter="eslint",
            project_root=self.temp_dir,
            target_files=target_files,
            use_standards_eslint=True
        )

        # Should have called twice (Next.js + standards)
        self.assertEqual(mock_run.call_count, 2)

        # Both calls should include target files
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            for target_file in target_files:
                self.assertIn(target_file, cmd)

    def test_standards_config_with_ignore_patterns_generation(self):
        """Test that generated standards config includes ignore patterns."""
        # This tests the config generation in _storage.py
        from aromcp.standards_server._storage import update_eslint_config

        # Create a mock rule for testing
        os.makedirs(os.path.join(self.temp_dir, ".aromcp", "standards"))
        rule_file = os.path.join(self.temp_dir, ".aromcp", "standards", "test-standard.md")
        with open(rule_file, "w") as f:
            f.write("# Test Standard\n\nThis is a test standard.")

        # Generate ESLint config
        update_eslint_config(self.temp_dir)

        # Check that standards-config.js was created with ignore patterns
        config_path = os.path.join(self.temp_dir, ".aromcp", "eslint", "standards-config.js")
        self.assertTrue(os.path.exists(config_path))

        with open(config_path) as f:
            config_content = f.read()

        # Verify ignore patterns are in the config
        self.assertIn("ignores:", config_content)
        self.assertIn("'.aromcp/**'", config_content)
        self.assertIn("'node_modules/**'", config_content)
        self.assertIn("'dist/**'", config_content)
        self.assertIn("'build/**'", config_content)
        self.assertIn("'.next/**'", config_content)


if __name__ == "__main__":
    unittest.main()

