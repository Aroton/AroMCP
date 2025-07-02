"""Tests for detect_security_patterns tool."""

from pathlib import Path
import pytest

from aromcp.analysis_server.tools.detect_security_patterns import detect_security_patterns_impl


class TestDetectSecurityPatterns:
    """Test cases for detect_security_patterns functionality."""

    def test_detect_basic_security_patterns(self, tmp_path):
        """Test detection of basic security patterns."""
        # Create a file with security issues
        vulnerable_code = '''
import sqlite3

def get_user(user_id):
    # SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = " + user_id
    conn = sqlite3.connect("database.db")
    cursor = conn.execute(query)
    return cursor.fetchone()

def update_profile(user_input):
    # XSS vulnerability
    document.getElementById("profile").innerHTML = "<p>" + user_input + "</p>";

# Hardcoded credentials
API_KEY = "secret-api-key-12345"
password = "hardcoded-password"
'''
        
        # Write vulnerable code to file
        vulnerable_file = tmp_path / "vulnerable.py"
        vulnerable_file.write_text(vulnerable_code)
        
        # Run security analysis
        result = detect_security_patterns_impl(
            file_paths=[str(vulnerable_file)],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Check result structure
        assert "data" in result
        assert "security_issues" in result["data"]
        assert "summary" in result["data"]
        
        # Should detect multiple issues
        issues = result["data"]["security_issues"]
        assert len(issues) > 0
        
        # Check for specific vulnerability types
        issue_categories = [issue["category"] for issue in issues]
        assert "injection" in issue_categories or "credentials" in issue_categories

    def test_security_patterns_with_severity_threshold(self, tmp_path):
        """Test filtering by severity threshold."""
        # Create code with mixed severity issues
        mixed_code = '''
# Low severity - debug info
print("Debug: user password is", user_password)

# High severity - SQL injection
query = "DELETE FROM users WHERE id = " + request.form['id']

# Medium severity - weak crypto
import hashlib
hash_value = hashlib.md5(password.encode()).hexdigest()
'''
        
        code_file = tmp_path / "mixed_severity.py"
        code_file.write_text(mixed_code)
        
        # Test with high severity threshold
        result_high = detect_security_patterns_impl(
            file_paths=[str(code_file)],
            project_root=str(tmp_path),
            severity_threshold="high"
        )
        
        # Test with low severity threshold
        result_low = detect_security_patterns_impl(
            file_paths=[str(code_file)],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Low threshold should find more issues than high threshold
        high_issues = result_high["data"]["security_issues"]
        low_issues = result_low["data"]["security_issues"]
        assert len(low_issues) >= len(high_issues)

    def test_security_patterns_with_glob_patterns(self, tmp_path):
        """Test using glob patterns to analyze multiple files."""
        # Create multiple files with security issues
        files_content = {
            "auth.py": 'password = "secret123"',
            "db.py": 'query = "SELECT * FROM users WHERE name = \'" + username + "\'"',
            "utils.js": 'eval(user_input);',
            "config.py": 'API_SECRET = "abc123"'
        }
        
        for filename, content in files_content.items():
            file_path = tmp_path / filename
            file_path.write_text(content)
        
        # Analyze all Python files
        result = detect_security_patterns_impl(
            file_paths=["**/*.py"],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Should find issues in Python files
        assert "data" in result
        issues = result["data"]["security_issues"]
        assert len(issues) > 0
        
        # Check that issues are from Python files
        python_files = [issue["file"] for issue in issues if issue["file"].endswith('.py')]
        assert len(python_files) > 0

    def test_security_patterns_with_custom_patterns(self, tmp_path):
        """Test using custom security patterns."""
        # Create code with custom vulnerability
        custom_code = '''
def dangerous_function():
    # Custom pattern we want to detect
    exec_command("rm -rf /")
    return "done"
'''
        
        code_file = tmp_path / "custom.py"
        code_file.write_text(custom_code)
        
        # Define custom patterns
        custom_patterns = [
            {
                "id": "dangerous_exec",
                "category": "custom_injection",
                "severity": "critical",
                "pattern": r"exec_command\s*\(",
                "message": "Use of dangerous exec_command function",
                "recommendation": "Avoid exec_command or validate input strictly"
            }
        ]
        
        # Run analysis with custom patterns
        result = detect_security_patterns_impl(
            file_paths=[str(code_file)],
            project_root=str(tmp_path),
            patterns=custom_patterns,
            severity_threshold="low"
        )
        
        # Should detect custom pattern
        assert "data" in result
        issues = result["data"]["security_issues"]
        assert len(issues) > 0
        assert any(issue["category"] == "custom_injection" for issue in issues)

    def test_security_patterns_with_invalid_severity(self, tmp_path):
        """Test handling of invalid severity threshold."""
        code_file = tmp_path / "test.py"
        code_file.write_text("print('hello')")
        
        # Use invalid severity
        result = detect_security_patterns_impl(
            file_paths=[str(code_file)],
            project_root=str(tmp_path),
            severity_threshold="invalid"
        )
        
        # Should return error
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_security_patterns_with_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = detect_security_patterns_impl(
            file_paths=["test.py"],
            project_root="/nonexistent/directory"
        )
        
        # Should return error
        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_security_patterns_with_unreadable_file(self, tmp_path):
        """Test handling of files that can't be read."""
        # Create a file with problematic encoding
        problem_file = tmp_path / "problem.py"
        problem_file.write_bytes(b'\x80\x81\x82\x83')  # Invalid UTF-8
        
        result = detect_security_patterns_impl(
            file_paths=[str(problem_file)],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Should handle gracefully
        assert "data" in result
        # May have an analysis error in the issues
        issues = result["data"]["security_issues"]
        if issues:
            assert any(issue.get("category") == "analysis_error" for issue in issues)

    def test_security_summary_statistics(self, tmp_path):
        """Test that summary statistics are calculated correctly."""
        # Create files with known security issues
        files_content = {
            "file1.py": 'password = "secret"',  # High severity
            "file2.py": 'print("debug:", secret_data)',  # Low severity
            "file3.py": 'query = "SELECT * FROM users WHERE id = " + user_id'  # High severity
        }
        
        for filename, content in files_content.items():
            (tmp_path / filename).write_text(content)
        
        result = detect_security_patterns_impl(
            file_paths=["**/*.py"],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Check summary statistics
        assert "data" in result
        summary = result["data"]["summary"]
        
        assert "total_issues" in summary
        assert "files_analyzed" in summary
        assert "severity_breakdown" in summary
        assert "risk_score" in summary
        assert summary["total_issues"] > 0

    def test_security_patterns_categorization(self, tmp_path):
        """Test that security issues are properly categorized."""
        # Create code with different types of vulnerabilities
        multi_vuln_code = '''
# Injection vulnerabilities
query = "SELECT * FROM users WHERE id = " + user_id
eval(user_input)

# Credential issues
API_KEY = "secret-key"
password = "hardcoded-pass"

# Crypto issues
import hashlib
weak_hash = hashlib.md5(data).hexdigest()
'''
        
        vuln_file = tmp_path / "multi_vuln.py"
        vuln_file.write_text(multi_vuln_code)
        
        result = detect_security_patterns_impl(
            file_paths=[str(vuln_file)],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Check categorization
        assert "data" in result
        categorized = result["data"]["categorized_issues"]
        
        assert "by_category" in categorized
        assert "by_severity" in categorized
        assert "by_file" in categorized
        
        # Should have multiple categories
        categories = list(categorized["by_category"].keys())
        assert len(categories) > 1

    def test_security_patterns_no_issues_found(self, tmp_path):
        """Test handling when no security issues are found."""
        # Create clean code
        clean_code = '''
def safe_function():
    return "This is safe code"

def another_safe_function(data):
    return data.upper()
'''
        
        clean_file = tmp_path / "clean.py"
        clean_file.write_text(clean_code)
        
        result = detect_security_patterns_impl(
            file_paths=[str(clean_file)],
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Should return success with no issues
        assert "data" in result
        assert result["data"]["summary"]["total_issues"] == 0
        assert len(result["data"]["security_issues"]) == 0