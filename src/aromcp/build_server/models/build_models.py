"""Dataclass models for build server MCP tool output schemas."""

from dataclasses import dataclass
from typing import Any, Union


# Standard cursor pagination fields for all paginated responses:
# - total: int | None - Total number of items across all pages (None if not paginated)
# - page_size: int | None - Number of items in current page
# - next_cursor: str | None - Cursor for next page (None if no more pages)
# - has_more: bool | None - Whether there are more pages


@dataclass
class TypescriptError:
    """Individual TypeScript error item."""

    file: str
    line: int
    column: int
    message: str
    code: str
    severity: str


@dataclass
class CheckTypescriptResponse:
    """Response schema for check_typescript tool."""

    errors: list[TypescriptError]
    total_errors: int
    files_checked: int
    check_again: bool
    success: bool
    # Standard cursor pagination fields
    total: int | None = None
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class LintIssue:
    """Individual lint issue item."""

    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str
    fixable: bool


@dataclass
class LintProjectResponse:
    """Response schema for lint_project tool."""

    issues: list[LintIssue]
    total_issues: int
    fixable_issues: int
    files_checked: int
    check_again: bool
    success: bool
    # Standard cursor pagination fields
    total: int | None = None
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class TestResult:
    """Individual test result item."""

    name: str
    status: str  # "passed", "failed", "skipped"
    duration: float
    file: str
    error_message: str | None = None


@dataclass
class TestSuiteInfo:
    """Test suite summary information."""

    total: int
    passed: int
    failed: int


@dataclass
class RunTestSuiteResponse:
    """Response schema for run_test_suite tool."""

    tests_passed: int
    tests_failed: int
    tests_skipped: int
    total_tests: int
    framework: str
    duration: float
    success: bool
    coverage: dict[str, Any] | None
    test_results: list[TestResult]
    test_suites: TestSuiteInfo | None = None
    # Standard cursor pagination fields
    total: int | None = None
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None
