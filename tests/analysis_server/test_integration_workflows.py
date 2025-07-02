"""Integration tests for analysis server workflows.

Tests end-to-end workflows that combine multiple analysis tools
to demonstrate complete functionality.
"""

import json
from pathlib import Path
import pytest

from aromcp.analysis_server.tools.load_coding_standards import load_coding_standards_impl
from aromcp.analysis_server.tools.get_relevant_standards import get_relevant_standards_impl
from aromcp.analysis_server.tools.parse_standard_to_rules import parse_standard_to_rules_impl
from aromcp.analysis_server.tools.detect_security_patterns import detect_security_patterns_impl
from aromcp.analysis_server.tools.find_dead_code import find_dead_code_impl
from aromcp.analysis_server.tools.find_import_cycles import find_import_cycles_impl


class TestIntegrationWorkflows:
    """Test complete analysis workflows."""

    def test_complete_standards_management_workflow(self, tmp_path):
        """Test complete workflow for standards management and parsing."""
        # Step 1: Create coding standards
        standards_dir = tmp_path / ".aromcp" / "standards"
        standards_dir.mkdir(parents=True)
        
        # API Routes standard
        api_standard = standards_dir / "api-routes.md"
        api_standard.write_text('''---
id: api-routes
name: API Route Standards
version: 1.0.0
patterns:
  - "**/routes/**/*.js"
  - "**/api/**/*.js"
tags:
  - api
  - routes
  - express
severity: error
priority: 1
---

# API Route Standards

## Async Route Handlers

All route handlers must be async functions for proper error handling.

```javascript
// ✅ Good
router.get('/users', async (req, res) => {
  const users = await User.findAll();
  res.json(users);
});

// ❌ Bad
router.get('/users', (req, res) => {
  User.findAll().then(users => res.json(users));
});
```

## Error Handling

Routes must include proper error handling.

```javascript
// ✅ Good
router.post('/users', async (req, res, next) => {
  try {
    const user = await User.create(req.body);
    res.status(201).json(user);
  } catch (error) {
    next(error);
  }
});

// ❌ Bad
router.post('/users', async (req, res) => {
  const user = await User.create(req.body);
  res.status(201).json(user);
});
```
''')

        # Component standard
        component_standard = standards_dir / "react-components.md"
        component_standard.write_text('''---
id: react-components
name: React Component Standards
version: 1.0.0
patterns:
  - "**/components/**/*.jsx"
  - "**/components/**/*.tsx"
tags:
  - react
  - components
  - jsx
severity: error
priority: 2
---

# React Component Standards

## Function Components

Use function components with hooks instead of class components.

```jsx
// ✅ Good
function UserProfile({ userId }) {
  const [user, setUser] = useState(null);
  
  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, [userId]);
  
  return <div>{user?.name}</div>;
}

// ❌ Bad
class UserProfile extends React.Component {
  constructor(props) {
    super(props);
    this.state = { user: null };
  }
  
  componentDidMount() {
    fetchUser(this.props.userId).then(user => {
      this.setState({ user });
    });
  }
  
  render() {
    return <div>{this.state.user?.name}</div>;
  }
}
```
''')

        # Step 2: Load coding standards
        standards_result = load_coding_standards_impl(
            project_root=str(tmp_path),
            standards_dir=".aromcp/standards",
            include_metadata=True
        )
        
        assert "data" in standards_result
        assert len(standards_result["data"]["standards"]) == 2
        
        # Step 3: Test getting relevant standards for specific files
        api_file = tmp_path / "src" / "routes" / "users.js"
        api_file.parent.mkdir(parents=True)
        api_file.write_text("// API route file")
        
        relevant_result = get_relevant_standards_impl(
            file_path=str(api_file),
            project_root=str(tmp_path)
        )
        
        assert "data" in relevant_result
        matched_standards = relevant_result["data"]["matched_standards"]
        assert len(matched_standards) >= 1
        assert any(s["id"] == "api-routes" for s in matched_standards)
        
        # Step 4: Parse standards to extract rule structure
        all_rules = []
        for standard in standards_result["data"]["standards"]:
            # Read standard content
            standard_path = tmp_path / standard["path"]
            content = standard_path.read_text()
            
            rules_result = parse_standard_to_rules_impl(
                standard_content=content,
                standard_id=standard["id"]
            )
            
            assert "data" in rules_result
            all_rules.extend(rules_result["data"]["rules"])
        
        assert len(all_rules) > 0
        
        # Verify rule structure for AI generation
        for rule in all_rules:
            assert "id" in rule
            assert "name" in rule
            assert "description" in rule
            # Should have examples for AI to understand
            if "examples" in rule:
                assert "good" in rule["examples"] or "bad" in rule["examples"]

    def test_security_analysis_workflow(self, tmp_path):
        """Test comprehensive security analysis workflow."""
        # Create files with various security issues
        
        # File with SQL injection
        sql_file = tmp_path / "database.js"
        sql_file.write_text('''
const mysql = require('mysql');

function getUser(userId) {
    // SQL injection vulnerability
    const query = "SELECT * FROM users WHERE id = " + userId;
    return mysql.query(query);
}

function updateUser(userId, data) {
    // Another SQL injection
    const query = `UPDATE users SET name = '${data.name}' WHERE id = ${userId}`;
    return mysql.query(query);
}

// Hardcoded credentials
const dbConfig = {
    host: 'localhost',
    user: 'admin',
    password: 'hardcoded-password-123',
    database: 'production'
};

// API key exposure
const API_SECRET = "sk-1234567890abcdef";
''')

        # File with XSS vulnerabilities
        xss_file = tmp_path / "frontend.js"
        xss_file.write_text('''
function displayUserInput(input) {
    // XSS vulnerability
    document.getElementById('content').innerHTML = input;
}

function showAlert(message) {
    // Another XSS issue
    document.write("<script>alert('" + message + "')</script>");
}

// Insecure random number generation
function generateToken() {
    return Math.random().toString(36).substring(7);
}
''')

        # File with command injection
        command_file = tmp_path / "utils.js"
        command_file.write_text('''
const { exec } = require('child_process');

function processFile(filename) {
    // Command injection vulnerability
    exec(`cat ${filename}`, (error, stdout, stderr) => {
        console.log(stdout);
    });
}

function deleteFile(filepath) {
    // Another command injection
    exec("rm " + filepath);
}
''')

        # Run security analysis on all files
        all_files = [str(sql_file), str(xss_file), str(command_file)]
        
        security_result = detect_security_patterns_impl(
            file_paths=all_files,
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        assert "data" in security_result
        security_issues = security_result["data"]["security_issues"]
        
        # Should detect multiple types of security issues
        issue_types = [issue["type"] for issue in security_issues]
        assert "sql_injection" in issue_types
        assert "hardcoded_secret" in issue_types
        assert "command_injection" in issue_types
        
        # Check summary statistics
        summary = security_result["data"]["summary"]
        assert summary["total_issues"] > 0
        assert summary["high_severity"] > 0 or summary["medium_severity"] > 0

    def test_code_quality_analysis_workflow(self, tmp_path):
        """Test code quality analysis workflow with dead code and cycles."""
        # Create a project with dead code and import cycles
        
        # Main entry point
        main_file = tmp_path / "main.js"
        main_file.write_text('''
const { serviceA } = require('./services/serviceA');
const { helperFunction } = require('./utils/helpers');

function main() {
    console.log(serviceA.process());
    console.log(helperFunction());
}

if (require.main === module) {
    main();
}
''')

        # Service A (part of cycle)
        services_dir = tmp_path / "services"
        services_dir.mkdir()
        
        service_a = services_dir / "serviceA.js"
        service_a.write_text('''
const { serviceB } = require('./serviceB');

const serviceA = {
    process() {
        return serviceB.helper() + " from A";
    },
    
    unused() {
        return "never called";
    }
};

module.exports = { serviceA };
''')

        # Service B (part of cycle)
        service_b = services_dir / "serviceB.js"
        service_b.write_text('''
const { serviceA } = require('./serviceA');

const serviceB = {
    helper() {
        return "processed";
    },
    
    cyclicMethod() {
        // This creates a cycle but isn't used
        return serviceA.process();
    },
    
    deadMethod() {
        return "completely unused";
    }
};

module.exports = { serviceB };
''')

        # Utilities with dead code
        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        
        helpers_file = utils_dir / "helpers.js"
        helpers_file.write_text('''
function helperFunction() {
    return "helper result";
}

function deadHelper1() {
    return "never used";
}

function deadHelper2() {
    return deadHelper3();
}

function deadHelper3() {
    return "deep dead code";
}

class UnusedClass {
    method() {
        return "unused class";
    }
}

module.exports = { helperFunction };
''')

        # Completely orphaned file
        orphan_file = tmp_path / "orphaned.js"
        orphan_file.write_text('''
function orphanedFunction() {
    return "this file is never imported";
}

const orphanedData = {
    value: "unused data"
};

module.exports = { orphanedFunction, orphanedData };
''')

        # Step 1: Find import cycles
        cycle_result = find_import_cycles_impl(
            project_root=str(tmp_path),
            max_depth=10
        )
        
        assert "data" in cycle_result
        cycles = cycle_result["data"]["cycles"]
        
        # Should detect the cycle between serviceA and serviceB
        assert len(cycles) >= 1
        cycle_files = cycles[0]["files"] if cycles else []
        assert any("serviceA.js" in f for f in cycle_files)
        assert any("serviceB.js" in f for f in cycle_files)
        
        # Step 2: Find dead code
        dead_code_result = find_dead_code_impl(
            project_root=str(tmp_path),
            confidence_threshold=0.7
        )
        
        assert "data" in dead_code_result
        dead_candidates = dead_code_result["data"]["dead_code_candidates"]
        
        # Should find multiple dead code candidates
        assert len(dead_candidates) > 0
        
        dead_names = [c["identifier"] for c in dead_candidates]
        # Should find some of the unused functions
        assert any("unused" in name.lower() or "dead" in name.lower() for name in dead_names)
        
        # Check summary
        summary = dead_code_result["data"]["summary"]
        assert summary["dead_code_candidates"] > 0
        assert summary["files_with_dead_code"] > 0

    def test_mixed_language_analysis_workflow(self, tmp_path):
        """Test analysis workflow with mixed Python and JavaScript files."""
        # Create Python files
        py_main = tmp_path / "main.py"
        py_main.write_text('''
from services.auth import authenticate
from utils.helpers import format_response

def main():
    user = authenticate("admin", "password123")  # Security issue
    return format_response(user)

if __name__ == "__main__":
    main()
''')

        services_dir = tmp_path / "services"
        services_dir.mkdir()
        
        auth_py = services_dir / "auth.py"
        auth_py.write_text('''
import sqlite3
from utils.helpers import log_action

def authenticate(username, password):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    conn = sqlite3.connect("users.db")
    cursor = conn.execute(query)
    result = cursor.fetchone()
    log_action(f"Login attempt for {username}")
    return result

def unused_auth_function():
    return "never called"
''')

        # Create JavaScript files
        js_main = tmp_path / "app.js"
        js_main.write_text('''
const express = require('express');
const { authMiddleware } = require('./middleware/auth');

const app = express();

// Non-async route handler (potential issue)
app.get('/api/users', (req, res) => {
    res.json({ users: [] });
});

// Unused route
app.post('/api/unused', authMiddleware, (req, res) => {
    res.json({ message: "never called" });
});

module.exports = app;
''')

        middleware_dir = tmp_path / "middleware"
        middleware_dir.mkdir()
        
        auth_js = middleware_dir / "auth.js"
        auth_js.write_text('''
const jwt = require('jsonwebtoken');

// Hardcoded secret
const JWT_SECRET = "super-secret-key-123";

function authMiddleware(req, res, next) {
    const token = req.headers.authorization;
    
    if (!token) {
        return res.status(401).json({ error: 'No token' });
    }
    
    try {
        const decoded = jwt.verify(token, JWT_SECRET);
        req.user = decoded;
        next();
    } catch (error) {
        res.status(401).json({ error: 'Invalid token' });
    }
}

function unusedAuthHelper() {
    return "dead code";
}

module.exports = { authMiddleware };
''')

        # Shared utilities
        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        
        helpers_py = utils_dir / "helpers.py"
        helpers_py.write_text('''
import json
import logging

def format_response(data):
    return json.dumps(data)

def log_action(message):
    logging.info(message)

def unused_helper():
    return "python dead code"
''')

        # Run comprehensive analysis
        all_files = [
            str(py_main), str(auth_py), str(helpers_py),
            str(js_main), str(auth_js)
        ]

        # Security analysis
        security_result = detect_security_patterns_impl(
            file_paths=all_files,
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        assert "data" in security_result
        security_issues = security_result["data"]["security_issues"]
        
        # Should find issues in both Python and JavaScript
        py_issues = [i for i in security_issues if i["file"].endswith('.py')]
        js_issues = [i for i in security_issues if i["file"].endswith('.js')]
        
        assert len(py_issues) > 0  # SQL injection in Python
        assert len(js_issues) > 0  # Hardcoded secret in JavaScript

        # Dead code analysis
        dead_code_result = find_dead_code_impl(
            project_root=str(tmp_path),
            confidence_threshold=0.6
        )
        
        assert "data" in dead_code_result
        dead_candidates = dead_code_result["data"]["dead_code_candidates"]
        
        # Should find dead code in both languages
        assert len(dead_candidates) > 0
        
        # Import cycle analysis
        cycle_result = find_import_cycles_impl(
            project_root=str(tmp_path),
            max_depth=10
        )
        
        assert "data" in cycle_result
        # May or may not find cycles, but should complete successfully

    def test_performance_with_large_project_simulation(self, tmp_path):
        """Test analysis performance with simulated large project."""
        # Create a larger project structure
        num_modules = 20
        
        # Create main modules
        for i in range(num_modules):
            module_dir = tmp_path / f"module_{i}"
            module_dir.mkdir()
            
            # Main file
            main_file = module_dir / "index.js"
            imports = []
            if i > 0:
                imports.append(f"const prev = require('../module_{i-1}');")
            if i < num_modules - 1:
                imports.append(f"const next = require('../module_{i+1}');")
            
            main_file.write_text(f'''
{chr(10).join(imports)}

function publicFunction{i}() {{
    return "public_{i}";
}}

function privateFunction{i}() {{
    return "private_{i}";
}}

function unusedFunction{i}() {{
    return "unused_{i}";
}}

// Some security issues
const apiKey{i} = "secret-key-{i}";

module.exports = {{ publicFunction{i} }};
''')
            
            # Add some utility files
            utils_file = module_dir / "utils.js"
            utils_file.write_text(f'''
function util{i}A() {{
    return "util_{i}_a";
}}

function util{i}B() {{
    return "util_{i}_b";
}}

function deadUtil{i}() {{
    return "dead_util_{i}";
}}

module.exports = {{ util{i}A, util{i}B }};
''')

        # Create entry point
        entry_file = tmp_path / "index.js"
        entry_imports = [f"const mod{i} = require('./module_{i}');" for i in range(0, min(5, num_modules))]
        entry_file.write_text(f'''
{chr(10).join(entry_imports)}

function main() {{
    console.log("Starting application");
    // Use only first few modules
    {chr(10).join([f"    console.log(mod{i}.publicFunction{i}());" for i in range(0, min(5, num_modules))])}
}}

if (require.main === module) {{
    main();
}}
''')

        # Run analysis and measure performance
        import time
        
        # Get all JavaScript files
        js_files = list(tmp_path.rglob("*.js"))
        
        start_time = time.time()
        
        # Security analysis
        security_result = detect_security_patterns_impl(
            file_paths=[str(f) for f in js_files],
            project_root=str(tmp_path),
            severity_threshold="medium"
        )
        
        security_time = time.time() - start_time
        
        # Dead code analysis
        start_time = time.time()
        dead_code_result = find_dead_code_impl(
            project_root=str(tmp_path),
            confidence_threshold=0.7
        )
        dead_code_time = time.time() - start_time
        
        # Import cycle analysis
        start_time = time.time()
        cycle_result = find_import_cycles_impl(
            project_root=str(tmp_path),
            max_depth=10
        )
        cycle_time = time.time() - start_time
        
        # Verify results
        assert "data" in security_result
        assert "data" in dead_code_result
        assert "data" in cycle_result
        
        # Check that analysis completed in reasonable time
        assert security_time < 30  # Should complete within 30 seconds
        assert dead_code_time < 30
        assert cycle_time < 30
        
        # Verify we found significant results
        assert len(security_result["data"]["security_issues"]) > 0
        assert len(dead_code_result["data"]["dead_code_candidates"]) > 0
        
        # Check analysis coverage
        security_summary = security_result["data"]["summary"]
        dead_summary = dead_code_result["data"]["summary"]
        cycle_summary = cycle_result["data"]["summary"]
        
        assert security_summary["files_analyzed"] >= num_modules
        assert dead_summary["total_files_analyzed"] >= num_modules
        assert cycle_summary["total_files_analyzed"] >= num_modules

    def test_error_handling_in_workflows(self, tmp_path):
        """Test error handling in complex workflows."""
        # Create files with various issues that might cause errors
        
        # File with syntax errors
        syntax_error_file = tmp_path / "syntax_error.js"
        syntax_error_file.write_text('''
function brokenFunction( {
    // Missing closing parenthesis and brace
    return "broken;
}

// This should still be analyzable
function workingFunction() {
    return "working";
}
''')

        # File with encoding issues
        encoding_file = tmp_path / "encoding_test.py"
        # Write with specific encoding that might cause issues
        encoding_file.write_bytes(b'''
def working_function():
    return "working"

# Invalid UTF-8 sequence: \xff\xfe
def another_function():
    return "more content"
''')

        # Empty file
        empty_file = tmp_path / "empty.js"
        empty_file.write_text("")

        # Very large file (simulated)
        large_file = tmp_path / "large.py"
        large_content = "# Large file\n" + "def function_{}(): return {}\n".format("x", "x") * 1000
        large_file.write_text(large_content)

        all_files = [
            str(syntax_error_file),
            str(encoding_file), 
            str(empty_file),
            str(large_file)
        ]

        # Run analysis and ensure it handles errors gracefully
        
        # Security analysis should handle files with syntax errors
        security_result = detect_security_patterns_impl(
            file_paths=all_files,
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        
        # Should complete successfully even with problematic files
        assert "data" in security_result or "error" in security_result
        if "data" in security_result:
            # Check that some files were still analyzed
            summary = security_result["data"]["summary"]
            assert "files_analyzed" in summary

        # Dead code analysis should handle errors gracefully
        dead_code_result = find_dead_code_impl(
            project_root=str(tmp_path),
            confidence_threshold=0.5
        )
        
        assert "data" in dead_code_result or "error" in dead_code_result
        if "data" in dead_code_result:
            usage_analysis = dead_code_result["data"]["usage_analysis"]
            assert "total_files_analyzed" in usage_analysis

        # Import cycle analysis should handle errors gracefully  
        cycle_result = find_import_cycles_impl(
            project_root=str(tmp_path),
            max_depth=5
        )
        
        assert "data" in cycle_result or "error" in cycle_result
        if "data" in cycle_result:
            summary = cycle_result["data"]["summary"]
            assert "total_files_analyzed" in summary

    def test_caching_effectiveness_in_workflows(self, tmp_path):
        """Test that caching improves performance in repeated workflows."""
        # Create a moderate-sized project
        for i in range(10):
            file_path = tmp_path / f"module_{i}.py"
            file_path.write_text(f'''
import ast
import json

def function_{i}():
    return "result_{i}"

def another_function_{i}():
    # This uses ast module
    tree = ast.parse("print('hello')")
    return json.dumps({{"module": {i}}})

def unused_function_{i}():
    return "unused_{i}"
''')

        # Run analysis multiple times to test caching
        all_files = [str(f) for f in tmp_path.glob("*.py")]
        
        import time
        
        # First run (no cache)
        start_time = time.time()
        first_result = detect_security_patterns_impl(
            file_paths=all_files,
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        first_run_time = time.time() - start_time
        
        # Second run (with cache)
        start_time = time.time()
        second_result = detect_security_patterns_impl(
            file_paths=all_files,
            project_root=str(tmp_path),
            severity_threshold="low"
        )
        second_run_time = time.time() - start_time
        
        # Both runs should succeed
        assert "data" in first_result
        assert "data" in second_result
        
        # Results should be consistent
        assert len(first_result["data"]["security_issues"]) == len(second_result["data"]["security_issues"])
        
        # Second run should be faster (or at least not significantly slower)
        # Note: In small tests, timing differences might not be significant
        # But we can at least verify the cache doesn't break anything
        assert second_run_time <= first_run_time * 2  # Allow some variance