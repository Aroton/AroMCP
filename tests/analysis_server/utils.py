"""Test utilities for analysis server tests."""

from pathlib import Path
from typing import Any


def create_test_standard(
    standard_id: str,
    name: str = None,
    patterns: list[str] = None,
    tags: list[str] = None,
    severity: str = "error",
    content: str = None,
    **kwargs,
) -> str:
    """Create a test standard with specified metadata.

    Args:
        standard_id: Unique identifier for the standard
        name: Display name (defaults to formatted ID)
        patterns: File patterns this standard applies to
        tags: Categorization tags
        severity: Rule severity level
        content: Main content body
        **kwargs: Additional metadata fields

    Returns:
        Complete markdown content with frontmatter
    """
    if name is None:
        name = standard_id.replace("-", " ").title()

    if patterns is None:
        patterns = ["**/*.py"]

    if tags is None:
        tags = ["test"]

    if content is None:
        content = f"# {name}\n\nThis is a test standard for {standard_id}."

    # Build frontmatter
    frontmatter = {"id": standard_id, "name": name, "patterns": patterns, "tags": tags, "severity": severity, **kwargs}

    # Convert to YAML
    import yaml

    yaml_content = yaml.dump(frontmatter, default_flow_style=False)

    return f"---\n{yaml_content}---\n\n{content}"


def create_test_standards_directory(temp_dir: str, standards: dict[str, str]) -> Path:
    """Create a test standards directory with multiple files.

    Args:
        temp_dir: Temporary directory path
        standards: Dictionary mapping filename to content

    Returns:
        Path to the created standards directory
    """
    standards_path = Path(temp_dir) / ".aromcp" / "standards"
    standards_path.mkdir(parents=True, exist_ok=True)

    for filename, content in standards.items():
        if not filename.endswith(".md"):
            filename += ".md"
        (standards_path / filename).write_text(content)

    return standards_path


def create_sample_project_structure(temp_dir: str) -> dict[str, Path]:
    """Create a sample project structure for testing pattern matching.

    Args:
        temp_dir: Temporary directory path

    Returns:
        Dictionary mapping category to list of created file paths
    """
    project_root = Path(temp_dir)

    # Define sample structure
    files_to_create = {
        "api": [
            "src/api/routes/user.ts",
            "src/api/routes/auth.ts",
            "src/api/middleware/cors.ts",
        ],
        "components": [
            "src/components/Button.tsx",
            "src/components/Modal.tsx",
            "src/components/Form.jsx",
        ],
        "utils": [
            "src/utils/helpers.py",
            "src/utils/validators.ts",
            "lib/utils/formatters.js",
        ],
        "tests": [
            "tests/test_api.py",
            "src/components/__tests__/Button.test.tsx",
            "src/utils/helpers.spec.ts",
        ],
        "config": [
            "config/database.json",
            "config/app.yaml",
            ".eslintrc.js",
        ],
        "docs": [
            "docs/api.md",
            "README.md",
            "docs/setup.md",
        ],
    }

    created_files = {}

    for category, file_paths in files_to_create.items():
        created_files[category] = []
        for file_path in file_paths:
            full_path = project_root / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Create simple content based on file type
            if full_path.suffix == ".py":
                content = f"# {full_path.name}\ndef example_function():\n    pass\n"
            elif full_path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                content = f"// {full_path.name}\nexport default function example() {{}}\n"
            elif full_path.suffix == ".md":
                content = f"# {full_path.stem}\n\nSample documentation.\n"
            elif full_path.suffix in [".json", ".yaml", ".yml"]:
                content = "# Sample configuration\nkey: value\n"
            else:
                content = f"Sample content for {full_path.name}\n"

            full_path.write_text(content)
            created_files[category].append(full_path)

    return created_files


def mock_standards_with_overlapping_patterns() -> dict[str, str]:
    """Create mock standards with overlapping patterns for testing.

    Returns:
        Dictionary mapping filename to standard content
    """
    return {
        "general-python": create_test_standard(
            "general-python",
            name="General Python Standards",
            patterns=["**/*.py"],
            tags=["python", "general"],
            content="General Python coding standards.",
        ),
        "api-routes": create_test_standard(
            "api-routes",
            name="API Route Standards",
            patterns=["**/api/**/*.py", "**/routes/**/*.py"],
            tags=["python", "api", "routes"],
            content="Standards for API route handlers.",
        ),
        "test-files": create_test_standard(
            "test-files",
            name="Test File Standards",
            patterns=["**/test_*.py", "**/*_test.py", "**/tests/**/*.py"],
            tags=["python", "testing"],
            content="Standards for test files.",
        ),
        "typescript-components": create_test_standard(
            "typescript-components",
            name="TypeScript Component Standards",
            patterns=["**/*.tsx", "**/components/**/*.ts"],
            tags=["typescript", "react", "components"],
            content="Standards for TypeScript React components.",
        ),
        "config-files": create_test_standard(
            "config-files",
            name="Configuration File Standards",
            patterns=["**/*.json", "**/*.yaml", "**/*.yml", "**/config/**/*"],
            tags=["configuration", "json", "yaml"],
            content="Standards for configuration files.",
        ),
    }


def assert_error_response(result: dict[str, Any], expected_code: str = None):
    """Assert that a result contains an error response.

    Args:
        result: Result dictionary to check
        expected_code: Expected error code (optional)
    """
    assert "error" in result, f"Expected error response, got: {result}"
    assert "code" in result["error"], "Error response missing code"
    assert "message" in result["error"], "Error response missing message"

    if expected_code:
        assert (
            result["error"]["code"] == expected_code
        ), f"Expected error code {expected_code}, got {result['error']['code']}"


def assert_success_response(result: dict[str, Any]):
    """Assert that a result contains a successful data response.

    Args:
        result: Result dictionary to check
    """
    assert "data" in result, f"Expected success response, got: {result}"
    assert "error" not in result, f"Unexpected error in response: {result.get('error')}"


def count_standards_by_tag(standards: list[dict[str, Any]], tag: str) -> int:
    """Count standards that have a specific tag.

    Args:
        standards: List of standard dictionaries
        tag: Tag to count

    Returns:
        Number of standards with the specified tag
    """
    count = 0
    for standard in standards:
        if "metadata" in standard:
            tags = standard["metadata"].get("tags", [])
            if tag in tags:
                count += 1
    return count


def get_standards_by_pattern(standards: list[dict[str, Any]], pattern: str) -> list[dict[str, Any]]:
    """Get standards that include a specific pattern.

    Args:
        standards: List of standard dictionaries
        pattern: Pattern to search for

    Returns:
        List of standards containing the pattern
    """
    matching = []
    for standard in standards:
        if "metadata" in standard:
            patterns = standard["metadata"].get("patterns", [])
            if pattern in patterns:
                matching.append(standard)
    return matching
