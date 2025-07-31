"""Tests for list_files implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.models.filesystem_models import ListFilesResponse
from aromcp.filesystem_server.tools import list_files_impl


class TestListFiles:
    """Test list_files implementation."""

    def test_basic_pattern_matching(self):
        """Test basic pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = ["test.py", "src/main.py", "docs/readme.md"]
            for file_path in test_files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("test content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["*.py"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 2  # Both test.py and src/main.py match
            assert "test.py" in result.files
            assert "src/main.py" in result.files

    def test_recursive_pattern_matching(self):
        """Test recursive pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            files = ["src/main.py", "src/utils/helper.py", "tests/test_main.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("# Python file")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.py"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 3
            assert set(result.files) == {"src/main.py", "src/utils/helper.py", "tests/test_main.py"}

    def test_multiple_patterns(self):
        """Test multiple glob patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create diverse file structure
            files = ["src/main.py", "src/utils.js", "tests/test.py", "docs/readme.md", "config.json", "style.css"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.py", "**/*.js", "*.json"])

            assert isinstance(result, ListFilesResponse)
            expected = {"src/main.py", "src/utils.js", "tests/test.py", "config.json"}
            assert set(result.files) == expected

    def test_single_string_pattern(self):
        """Test single pattern as string instead of list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["test.py", "other.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns="*.py")

            assert isinstance(result, ListFilesResponse)
            assert result.files == ["test.py"]

    def test_no_matches(self):
        """Test when no files match the pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files that won't match
            files = ["readme.md", "config.json"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["*.py"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 0

    def test_duplicate_removal(self):
        """Test that duplicate paths are removed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file that would match multiple patterns
            file_path = Path(temp_dir) / "test.py"
            file_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Use patterns that would both match the same file
            result = list_files_impl(patterns=["*.py", "test.*"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["test.py"]

    def test_brace_expansion_basic(self):
        """Test basic brace expansion like {js,jsx,ts,tsx}."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with different extensions
            files = [
                "src/components/Button.js",
                "src/components/Header.jsx",
                "src/components/Footer.ts",
                "src/components/Modal.tsx",
                "src/components/styles.css",  # Should not match
                "src/components/README.md",  # Should not match
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("// content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test the exact pattern from user's request
            result = list_files_impl(patterns=["src/components/**/*.{js,jsx,ts,tsx}"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 4
            expected = {
                "src/components/Button.js",
                "src/components/Header.jsx",
                "src/components/Footer.ts",
                "src/components/Modal.tsx",
            }
            assert set(result.files) == expected

    def test_brace_expansion_directory_names(self):
        """Test brace expansion with directory names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files in different directories
            files = [
                "src/components/Button.ts",
                "src/utils/helper.ts",
                "src/services/api.ts",  # Should not match
                "tests/components/Button.test.ts",  # Should not match
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("// content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["src/{components,utils}/**/*.ts"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 2
            expected = {"src/components/Button.ts", "src/utils/helper.ts"}
            assert set(result.files) == expected

    def test_brace_expansion_nested_braces(self):
        """Test nested brace expansion patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files for nested brace testing
            files = [
                "src/components/Button.js",
                "src/components/Button.ts",
                "src/utils/helper.js",
                "src/utils/helper.ts",
                "src/services/api.py",  # Should not match
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("// content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["src/{components,utils}/**/*.{js,ts}"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 4
            expected = {
                "src/components/Button.js",
                "src/components/Button.ts",
                "src/utils/helper.js",
                "src/utils/helper.ts",
            }
            assert set(result.files) == expected

    def test_brace_expansion_no_braces(self):
        """Test that patterns without braces work unchanged."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/main.py", "src/utils.py", "test.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("# content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.py"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 2
            expected = {"src/main.py", "src/utils.py"}
            assert set(result.files) == expected

    def test_brace_expansion_single_option(self):
        """Test brace expansion with single option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/main.py", "src/utils.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.{py}"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["src/main.py"]

    def test_brace_expansion_malformed_patterns(self):
        """Test that malformed brace patterns are handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/test.py", "src/test{malformed.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test patterns with unmatched braces - should treat as literal
            result = list_files_impl(patterns=["**/*.{py"])

            assert isinstance(result, ListFilesResponse)
            # Should find no matches since literal "{py" doesn't match any file
            assert len(result.files) == 0

    def test_character_classes(self):
        """Test character class patterns like [abc] and [a-z]."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with different extensions
            files = ["src/test.js", "src/test.ts", "src/test.py", "src/test.css", "src/main.jsx", "src/main.tsx"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("// content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test character classes for extensions
            result = list_files_impl(patterns=["src/**/*.[jt]s"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 2
            expected = {"src/test.js", "src/test.ts"}
            assert set(result.files) == expected

    def test_character_class_ranges(self):
        """Test character class ranges like [a-z]."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with single character names
            files = ["a.js", "b.js", "c.js", "z.js", "1.js", "A.js"]  # Should not match [a-z]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("// content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["[a-z].js"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 4
            expected = {"a.js", "b.js", "c.js", "z.js"}
            assert set(result.files) == expected

    def test_single_character_wildcards(self):
        """Test single character wildcard ? patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different name lengths
            files = [
                "a.js",
                "b.ts",
                "c.py",  # Single char names
                "ab.js",
                "test.js",  # Multi char names
                "main.tsx",  # Multi char name
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["?.js"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["a.js"]

    def test_multiple_single_wildcards(self):
        """Test multiple ? wildcards in a pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with exact character lengths
            files = [
                "ab.js",
                "xy.ts",
                "12.py",  # 2 chars + extension
                "abc.js",
                "test.js",  # 3+ chars + extension
                "a.js",  # 1 char + extension
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["??.js"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["ab.js"]

    def test_combined_advanced_patterns(self):
        """Test combining character classes, wildcards, and brace expansion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create diverse test files
            files = ["src/a.js", "src/b.ts", "src/c.jsx", "src/d.tsx", "src/x.py", "src/test.js", "src/main.css"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Combine single wildcard with brace expansion
            result = list_files_impl(patterns=["src/?{.js,.ts,.jsx,.tsx}"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 4
            expected = {"src/a.js", "src/b.ts", "src/c.jsx", "src/d.tsx"}
            assert set(result.files) == expected

    def test_complex_pattern_combinations(self):
        """Test complex combinations of all pattern types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create comprehensive test structure
            files = [
                "src/components/Button.js",
                "src/components/Header.jsx",
                "src/utils/a.ts",
                "src/utils/b.tsx",
                "src/services/api.py",
                "tests/unit/x.js",
                "tests/integration/y.ts",
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Complex pattern: directory braces + character classes + wildcards
            # Pattern *.[jt]s? means: filename + dot + [j or t] + s + any single character
            # So .jsx and .tsx match, but .js and .ts don't (they lack the final character)
            result = list_files_impl(patterns=["src/{components,utils}/**/*.[jt]s?"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 2
            expected = {
                "src/components/Header.jsx",  # matches .*jsx (j + s + x)
                "src/utils/b.tsx",  # matches .*tsx (t + s + x)
            }
            assert set(result.files) == expected

    def test_pattern_validation_empty_braces(self):
        """Test handling of empty braces."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/test.py", "src/test{}.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test empty braces - should treat as literal
            result = list_files_impl(patterns=["src/test{}.js"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["src/test{}.js"]

    def test_pattern_validation_empty_options(self):
        """Test handling of empty options in braces."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/test.js", "src/test.ts"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test braces with empty options
            result = list_files_impl(patterns=["src/test.{js,,}"])

            assert isinstance(result, ListFilesResponse)
            assert len(result.files) == 1
            assert result.files == ["src/test.js"]  # Empty options filtered out

    def test_pattern_validation_robust_error_handling(self):
        """Test that pattern errors don't crash the function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["src/test.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test various edge cases that should not crash
            test_patterns = [
                None,  # This would be filtered out before reaching the function
                "",
                "normal_pattern.py",
                "pattern_with_unmatched_{brackets",
                "pattern_with_}unmatched_brackets",
                "src/**/*.{}",
            ]

            for pattern in test_patterns:
                if pattern is not None:  # Skip None as it would be filtered earlier
                    try:
                        result = list_files_impl(patterns=[pattern])
                        assert isinstance(result, ListFilesResponse)
                        # Should not crash, results may be empty but that's fine
                    except Exception as e:
                        assert False, f"Pattern '{pattern}' caused unexpected error: {e}"

    def test_integration_with_read_files(self):
        """Test that list_files output works seamlessly with read_files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with diverse content
            files = {
                "src/components/Button.js": "export const Button = () => <button>Click me</button>;",
                "src/components/Header.jsx": "import React from 'react'; export const Header = () => <h1>Title</h1>;",
                "src/utils/helper.ts": "export function formatDate(date: Date): string { return date.toISOString(); }",
            }
            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # First, use list_files with brace expansion
            list_result = list_files_impl(patterns=["src/**/*.{js,jsx,ts}"])

            assert isinstance(list_result, ListFilesResponse)
            assert len(list_result.files) == 3
            expected_files = {"src/components/Button.js", "src/components/Header.jsx", "src/utils/helper.ts"}
            assert set(list_result.files) == expected_files

            # Then, use the result with read_files to verify the pattern works end-to-end
            from aromcp.filesystem_server.tools.read_files import read_files_impl

            read_result = read_files_impl(list_result.files)

            assert "items" in read_result
            assert len(read_result["items"]) == 3

            # Verify content matches what we expect
            file_contents = {item["file"]: item["content"] for item in read_result["items"]}
            assert "export const Button" in file_contents["src/components/Button.js"]
            assert "import React" in file_contents["src/components/Header.jsx"]
            assert "formatDate" in file_contents["src/utils/helper.ts"]

    def test_workflow_pattern_discovery(self):
        """Test common workflow of discovering files by pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a realistic project structure
            files = {
                "src/pages/Home.tsx": "export default function Home() { return <div>Home</div>; }",
                "src/pages/_app.tsx": "export default function App() { return <div>App</div>; }",
                "src/components/Button.tsx": "export const Button = () => <button>Click</button>;",
                "src/components/Modal.tsx": "export const Modal = () => <div>Modal</div>;",
                "src/utils/api.ts": "export const api = { get: () => {} };",
                "src/utils/format.ts": "export const format = (s: string) => s;",
                "tests/pages/Home.test.tsx": "test('Home renders', () => {});",
                "tests/components/Button.test.tsx": "test('Button works', () => {});",
            }
            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Workflow 1: Find all React components (tsx files in src but not tests)
            components_result = list_files_impl(patterns=["src/**/*.tsx"])
            assert len(components_result.files) == 4
            expected_components = {
                "src/pages/Home.tsx",
                "src/pages/_app.tsx",
                "src/components/Button.tsx",
                "src/components/Modal.tsx",
            }
            assert set(components_result.files) == expected_components

            # Workflow 2: Find all TypeScript files (both .ts and .tsx) in specific directories
            ts_files_result = list_files_impl(patterns=["src/{pages,utils}/**/*.{ts,tsx}"])
            assert len(ts_files_result.files) == 4
            expected_ts = {"src/pages/Home.tsx", "src/pages/_app.tsx", "src/utils/api.ts", "src/utils/format.ts"}
            assert set(ts_files_result.files) == expected_ts

            # Workflow 3: Find test files
            test_files_result = list_files_impl(patterns=["tests/**/*.test.tsx"])
            assert len(test_files_result.files) == 2
            expected_tests = {"tests/pages/Home.test.tsx", "tests/components/Button.test.tsx"}
            assert set(test_files_result.files) == expected_tests

    def test_cursor_based_pagination(self):
        """Test cursor-based pagination functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create many files with longer names to force pagination
            files = [f"file_with_very_long_filename_for_testing_pagination_{i:03d}.py" for i in range(50)]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text(f"# Content for {file_path}")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test first page with cursor pagination - use smaller token limit to force pagination
            result1 = list_files_impl(patterns=["*.py"], cursor=None, max_tokens=500)

            assert isinstance(result1, ListFilesResponse)
            assert len(result1.files) > 0
            assert len(result1.files) < 50  # Should be paginated
            assert result1.has_more is True
            assert result1.next_cursor is not None
            assert result1.cursor is None  # First page has no cursor

            # Test second page using cursor
            result2 = list_files_impl(patterns=["*.py"], cursor=result1.next_cursor, max_tokens=1000)

            assert isinstance(result2, ListFilesResponse)
            assert len(result2.files) > 0
            assert result2.cursor == result1.next_cursor

            # Verify no overlap between pages
            page1_files = set(result1.files)
            page2_files = set(result2.files)
            assert len(page1_files.intersection(page2_files)) == 0

    def test_cursor_pagination_vs_page_pagination(self):
        """Test that cursor and page pagination are mutually exclusive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with longer names
            files = [f"file_with_longer_name_{i:03d}.py" for i in range(20)]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text(f"# Content for {file_path}")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test that cursor takes precedence over page - use small token limit to force pagination
            result = list_files_impl(patterns=["*.py"], page=2, cursor="file_with_longer_name_005.py", max_tokens=100)

            # Should use cursor-based pagination, not page-based
            assert result.cursor == "file_with_longer_name_005.py"
            # Should return files after cursor position (but limited by tokens)
            assert len(result.files) > 0
            # Should start after the cursor file
            assert "file_with_longer_name_005.py" not in result.files
            # Page-based fields should be None
            assert result.page is None
            assert result.total_pages is None

    def test_cursor_pagination_exhaustive_navigation(self):
        """Test navigating through all pages using cursors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with longer names for testing
            files = [f"file_with_long_name_for_pagination_test_{i:03d}.py" for i in range(25)]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text(f"# Content for {file_path}")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Navigate through all pages
            all_files = []
            cursor = None
            page_count = 0

            while True:
                result = list_files_impl(patterns=["*.py"], cursor=cursor, max_tokens=200)  # Smaller token limit
                all_files.extend(result.files)
                page_count += 1

                if not result.has_more:
                    assert result.next_cursor is None
                    break
                else:
                    assert result.next_cursor is not None
                    cursor = result.next_cursor

            # Verify we got all files
            assert len(all_files) == 25
            assert set(all_files) == set(files)
            assert page_count > 1  # Should require multiple pages

    def test_cursor_backward_compatibility(self):
        """Test that page-based pagination still works as before."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with longer names to ensure pagination
            files = [f"file_with_much_longer_name_for_testing_{i:03d}.py" for i in range(30)]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text(f"# Content for {file_path}")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test page-based pagination (no cursor provided - use default)
            result = list_files_impl(patterns=["*.py"], page=1, max_tokens=200)  # cursor defaults to "NOT_PROVIDED"

            assert isinstance(result, ListFilesResponse)
            # Should use page-based pagination
            assert result.page is not None
            assert result.has_more is not None
            # Cursor fields should be None for page-based pagination
            assert result.cursor is None
            assert result.next_cursor is None
            # Should be paginated (not all files returned)
            assert len(result.files) < 30

    def test_cursor_with_invalid_cursor(self):
        """Test behavior with invalid cursor values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["a.py", "b.py", "c.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("# test content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Test with invalid cursor (should start from beginning)
            result = list_files_impl(patterns=["*.py"], cursor="invalid_cursor", max_tokens=1000)

            assert isinstance(result, ListFilesResponse)
            assert result.files == ["a.py", "b.py", "c.py"]  # Should get all files
            # For small result sets that don't require pagination, cursor fields may be None
            # The key test is that it returns all files starting from beginning when cursor is invalid
            assert len(result.files) == 3
