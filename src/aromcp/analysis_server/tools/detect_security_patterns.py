"""Tool for detecting security vulnerability patterns in code files."""

import re
from pathlib import Path
from typing import Any

from ...filesystem_server.tools.get_target_files import get_target_files_impl
from .._security import validate_file_path_legacy
from ...utils.pagination import paginate_list


def detect_security_patterns_impl(
    file_paths: str | list[str],
    project_root: str,
    patterns: list[str] | None = None,
    severity_threshold: str = "low",
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Detect security vulnerability patterns in code files.
    
    Args:
        file_paths: File path(s) or glob patterns to analyze
        project_root: Root directory of the project
        patterns: Security patterns to check (uses defaults if None)
        severity_threshold: Minimum severity to report (low|medium|high|critical)
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)
        
    Returns:
        Dictionary containing paginated detected security issues
    """
    try:
        # Convert single string to list
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        # Validate severity threshold
        valid_severities = ["low", "medium", "high", "critical"]
        if severity_threshold not in valid_severities:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Invalid severity threshold: {severity_threshold}. Must be one of: {', '.join(valid_severities)}"
                }
            }

        # Validate project root
        project_path = Path(project_root)
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root directory does not exist: {project_root}"
                }
            }

        # Get security patterns
        security_patterns = patterns or _get_default_security_patterns()

        # Resolve file paths (handle glob patterns)
        target_files = []
        for file_pattern in file_paths:
            if "*" in file_pattern:
                # Handle glob patterns
                file_result = get_target_files_impl(
                    project_root=project_root,
                    status="pattern",
                    patterns=[file_pattern]
                )
                if "data" in file_result:
                    target_files.extend([f["path"] for f in file_result["data"]["files"]])
            else:
                target_files.append(file_pattern)

        # Analyze each file
        security_issues = []
        files_analyzed = 0

        for file_path in target_files:
            try:
                # Validate file path
                validated_path = validate_file_path_legacy(file_path, project_path)

                if validated_path.exists():
                    file_issues = _analyze_file_security(validated_path, security_patterns, severity_threshold)
                    if file_issues:
                        security_issues.extend(file_issues)
                    files_analyzed += 1

            except Exception as e:
                # Log file error but continue with other files
                security_issues.append({
                    "file": file_path,
                    "severity": "low",
                    "category": "analysis_error",
                    "pattern": "file_access_error",
                    "message": f"Could not analyze file: {str(e)}",
                    "line": 0,
                    "column": 0,
                    "context": "",
                    "recommendation": "Check file permissions and accessibility"
                })

        # Filter by severity threshold
        filtered_issues = _filter_by_severity(security_issues, severity_threshold)

        # Group issues by category and severity
        categorized_issues = _categorize_issues(filtered_issues)

        # Generate summary statistics
        summary = _generate_security_summary(filtered_issues, files_analyzed)

        # Create metadata for pagination
        metadata = {
            "categorized_issues": categorized_issues,
            "summary": summary,
            "files_analyzed": files_analyzed,
            "patterns_checked": len(security_patterns),
            "severity_threshold": severity_threshold
        }

        # Apply pagination with deterministic sorting
        # Sort by severity (critical > high > medium > low), then by file, then by line
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return paginate_list(
            items=filtered_issues,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: (
                severity_order.get(x.get("severity", "low"), 3),
                x.get("file", ""),
                x.get("line", 0)
            ),
            metadata=metadata
        )

    except Exception as e:
        import traceback
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to detect security patterns: {str(e)}",
                "traceback": traceback.format_exc()
            }
        }


def _get_default_security_patterns() -> list[dict[str, Any]]:
    """Get default security patterns to check for.
    
    Returns:
        List of security pattern definitions
    """
    return [
        # SQL Injection patterns
        {
            "id": "sql_injection_basic",
            "category": "injection",
            "severity": "high",
            "pattern": r"(?i)(select|insert|update|delete|drop|create|alter)\s+.*\+.*['\"]",
            "message": "Potential SQL injection via string concatenation",
            "recommendation": "Use parameterized queries or prepared statements"
        },
        {
            "id": "sql_injection_format",
            "category": "injection",
            "severity": "high",
            "pattern": r"(?i)(select|insert|update|delete)\s.*%\w|\.format\s*\(",
            "message": "Potential SQL injection via string formatting",
            "recommendation": "Use parameterized queries instead of string formatting"
        },

        # XSS patterns
        {
            "id": "xss_innerhtml",
            "category": "xss",
            "severity": "medium",
            "pattern": r"\.innerHTML\s*=\s*.*\+",
            "message": "Potential XSS via innerHTML with concatenation",
            "recommendation": "Use textContent or sanitize HTML content"
        },
        {
            "id": "xss_eval",
            "category": "injection",
            "severity": "critical",
            "pattern": r"\beval\s*\(",
            "message": "Use of eval() function - potential code injection",
            "recommendation": "Avoid eval() and use safer alternatives like JSON.parse()"
        },

        # Authentication/Authorization
        {
            "id": "hardcoded_password",
            "category": "credentials",
            "severity": "high",
            "pattern": r"(?i)(password|pwd|pass)\s*=\s*['\"][^'\"]+['\"]",
            "message": "Hardcoded password detected",
            "recommendation": "Use environment variables or secure credential storage"
        },
        {
            "id": "hardcoded_api_key",
            "category": "credentials",
            "severity": "high",
            "pattern": r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*=\s*['\"][^'\"]+['\"]",
            "message": "Hardcoded API key or token detected",
            "recommendation": "Use environment variables or secure credential storage"
        },

        # Crypto patterns
        {
            "id": "weak_crypto_md5",
            "category": "crypto",
            "severity": "medium",
            "pattern": r"\b(md5|MD5)\s*\(",
            "message": "Use of weak MD5 hash function",
            "recommendation": "Use SHA-256 or stronger hash functions"
        },
        {
            "id": "weak_crypto_sha1",
            "category": "crypto",
            "severity": "medium",
            "pattern": r"\b(sha1|SHA1)\s*\(",
            "message": "Use of weak SHA-1 hash function",
            "recommendation": "Use SHA-256 or stronger hash functions"
        },

        # File system patterns
        {
            "id": "path_traversal",
            "category": "path_traversal",
            "severity": "high",
            "pattern": r"\.\.\/|\.\.\\",
            "message": "Potential path traversal attack vector",
            "recommendation": "Validate and sanitize file paths"
        },
        {
            "id": "unsafe_file_upload",
            "category": "file_upload",
            "severity": "medium",
            "pattern": r"(?i)(multipart|upload).*\.(php|jsp|asp|py|rb|pl)$",
            "message": "Potential unsafe file upload allowing executable files",
            "recommendation": "Restrict file types and validate file content"
        },

        # Command injection
        {
            "id": "command_injection",
            "category": "injection",
            "severity": "critical",
            "pattern": r"(exec|system|popen|subprocess)\s*\(.*\+",
            "message": "Potential command injection via string concatenation",
            "recommendation": "Use parameterized commands or input validation"
        },

        # Information disclosure
        {
            "id": "debug_info_disclosure",
            "category": "information_disclosure",
            "severity": "low",
            "pattern": r"(?i)(debug|trace|print|console\.log)\s*\(.*(?:password|token|key|secret)",
            "message": "Potential information disclosure via debug output",
            "recommendation": "Remove debug statements or ensure sensitive data is not logged"
        },

        # Deserialization
        {
            "id": "unsafe_deserialization",
            "category": "deserialization",
            "severity": "high",
            "pattern": r"(pickle\.loads|yaml\.load|json\.loads).*input|request",
            "message": "Potential unsafe deserialization of user input",
            "recommendation": "Validate and sanitize input before deserialization"
        }
    ]


def _analyze_file_security(file_path: Path, patterns: list[dict[str, Any]], severity_threshold: str) -> list[dict[str, Any]]:
    """Analyze a single file for security patterns.
    
    Args:
        file_path: Path to the file to analyze
        patterns: Security patterns to check
        severity_threshold: Minimum severity to report
        
    Returns:
        List of security issues found in the file
    """
    issues = []

    try:
        # Read file content
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()

        # Check each pattern
        for pattern_def in patterns:
            pattern = pattern_def["pattern"]

            # Check if this pattern meets severity threshold
            if not _meets_severity_threshold(pattern_def["severity"], severity_threshold):
                continue

            # Search for pattern in file
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(pattern, line)

                for match in matches:
                    issue = {
                        "file": str(file_path),
                        "line": line_num,
                        "column": match.start() + 1,
                        "severity": pattern_def["severity"],
                        "category": pattern_def["category"],
                        "pattern": pattern_def["id"],
                        "message": pattern_def["message"],
                        "recommendation": pattern_def["recommendation"],
                        "context": line.strip(),
                        "matched_text": match.group(0)
                    }
                    issues.append(issue)

    except Exception as e:
        # Add file read error as a low-severity issue
        issues.append({
            "file": str(file_path),
            "line": 0,
            "column": 0,
            "severity": "low",
            "category": "analysis_error",
            "pattern": "file_read_error",
            "message": f"Could not read file for security analysis: {str(e)}",
            "recommendation": "Check file encoding and permissions",
            "context": "",
            "matched_text": ""
        })

    return issues


def _meets_severity_threshold(issue_severity: str, threshold: str) -> bool:
    """Check if issue severity meets the threshold.
    
    Args:
        issue_severity: Severity of the issue
        threshold: Minimum severity threshold
        
    Returns:
        True if issue meets threshold
    """
    severity_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return severity_levels.get(issue_severity, 0) >= severity_levels.get(threshold, 0)


def _filter_by_severity(issues: list[dict[str, Any]], threshold: str) -> list[dict[str, Any]]:
    """Filter issues by severity threshold.
    
    Args:
        issues: List of security issues
        threshold: Minimum severity threshold
        
    Returns:
        Filtered list of issues
    """
    return [issue for issue in issues if _meets_severity_threshold(issue["severity"], threshold)]


def _categorize_issues(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Categorize security issues by type and severity.
    
    Args:
        issues: List of security issues
        
    Returns:
        Dictionary with categorized issues
    """
    categorized = {
        "by_category": {},
        "by_severity": {},
        "by_file": {}
    }

    for issue in issues:
        # Group by category
        category = issue["category"]
        if category not in categorized["by_category"]:
            categorized["by_category"][category] = []
        categorized["by_category"][category].append(issue)

        # Group by severity
        severity = issue["severity"]
        if severity not in categorized["by_severity"]:
            categorized["by_severity"][severity] = []
        categorized["by_severity"][severity].append(issue)

        # Group by file
        file_path = issue["file"]
        if file_path not in categorized["by_file"]:
            categorized["by_file"][file_path] = []
        categorized["by_file"][file_path].append(issue)

    return categorized


def _generate_security_summary(issues: list[dict[str, Any]], files_analyzed: int) -> dict[str, Any]:
    """Generate summary statistics for security analysis.
    
    Args:
        issues: List of security issues
        files_analyzed: Number of files analyzed
        
    Returns:
        Summary statistics
    """
    total_issues = len(issues)

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    category_counts = {}

    for issue in issues:
        severity = issue["severity"]
        category = issue["category"]

        if severity in severity_counts:
            severity_counts[severity] += 1

        if category not in category_counts:
            category_counts[category] = 0
        category_counts[category] += 1

    # Calculate risk score (weighted by severity)
    risk_score = (
        severity_counts["critical"] * 10 +
        severity_counts["high"] * 7 +
        severity_counts["medium"] * 4 +
        severity_counts["low"] * 1
    )

    return {
        "total_issues": total_issues,
        "files_analyzed": files_analyzed,
        "severity_breakdown": severity_counts,
        "category_breakdown": category_counts,
        "risk_score": risk_score,
        "issues_per_file": round(total_issues / files_analyzed, 2) if files_analyzed > 0 else 0,
        "most_common_category": max(category_counts.keys(), key=category_counts.get) if category_counts else None,
        "highest_severity_found": _get_highest_severity(issues)
    }


def _get_highest_severity(issues: list[dict[str, Any]]) -> str:
    """Get the highest severity level found in issues.
    
    Args:
        issues: List of security issues
        
    Returns:
        Highest severity level
    """
    if not issues:
        return "none"

    severity_levels = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    max_level = max(severity_levels.get(issue["severity"], 0) for issue in issues)

    for severity, level in severity_levels.items():
        if level == max_level:
            return severity

    return "low"
