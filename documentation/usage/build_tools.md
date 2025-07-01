# Build Tools Usage Guide

This guide provides comprehensive documentation for all Build Tools in the AroMCP server. These tools execute build, lint, test, and validation commands with structured output parsing, focusing on actionable error reporting for AI-driven development workflows.

## Overview

The Build Tools provide 7 specialized tools for development workflow automation:

1. **run_command** - Execute whitelisted commands with security validation
2. **get_build_config** - Extract and analyze build configuration files
3. **check_dependencies** - Analyze package dependencies and security
4. **parse_typescript_errors** - Parse TypeScript compilation errors
5. **parse_lint_results** - Parse linter output (ESLint, Prettier, Stylelint)
6. **run_test_suite** - Execute and parse test results
7. **run_nextjs_build** - Specialized Next.js build with categorized reporting

## Tool Documentation

### 1. run_command

Execute whitelisted commands with structured output and security validation.

**Parameters:**
- `command` (string, required): Command to execute (must be in whitelist)
- `args` (list[str], optional): Arguments to pass to the command
- `project_root` (string, optional): Directory to execute command in (defaults to MCP_FILE_ROOT)
- `allowed_commands` (list[str], optional): Custom list of allowed commands
- `timeout` (int, optional): Maximum execution time in seconds (default: 300)
- `capture_output` (bool, optional): Whether to capture stdout/stderr (default: true)
- `env_vars` (dict[str, str], optional): Additional environment variables

**Default Whitelisted Commands:**
```
npm, yarn, pnpm, node, npx, tsc, eslint, jest, vitest, mocha,
python, python3, pip, pip3, cargo, rustc, go, mvn, gradle,
make, cmake, docker, git
```

**Example Usage:**
```json
{
  "command": "npm",
  "args": ["install", "--verbose"],
  "timeout": 180,
  "env_vars": {"NODE_ENV": "development"}
}
```

**Response Format:**
```json
{
  "data": {
    "command": "npm install --verbose",
    "exit_code": 0,
    "stdout": "...",
    "stderr": "...",
    "success": true,
    "working_directory": "/path/to/project"
  },
  "metadata": {
    "timestamp": "2024-01-15 10:30:45",
    "duration_ms": 15420,
    "timeout_seconds": 180
  }
}
```

### 2. get_build_config

Extract build configuration from various sources and detect build tools.

**Parameters:**
- `project_root` (string, optional): Directory to search for config files (defaults to MCP_FILE_ROOT)
- `config_files` (list[str], optional): Specific config files to read (defaults to common build configs)

**Default Config Files Detected:**
```
package.json, tsconfig.json, next.config.js, vite.config.js,
webpack.config.js, eslint.config.js, .eslintrc.json, 
prettier.config.js, jest.config.js, tailwind.config.js,
Dockerfile, docker-compose.yml, Cargo.toml, go.mod, pom.xml,
pyproject.toml, requirements.txt, Makefile
```

**Example Usage:**
```json
{
  "project_root": "/path/to/project"
}
```

**Response Format:**
```json
{
  "data": {
    "config_files": {
      "package.json": {
        "type": "json",
        "content": {
          "name": "my-app",
          "scripts": {"build": "next build"},
          "dependencies": {"next": "^13.0.0"}
        }
      },
      "tsconfig.json": {
        "type": "json", 
        "content": {"compilerOptions": {"target": "es2020"}}
      }
    },
    "detected_tools": ["npm", "node", "nextjs", "typescript"],
    "build_info": {
      "name": "my-app",
      "scripts": {"build": "next build"},
      "typescript": {
        "target": "es2020",
        "strict": true
      }
    },
    "project_root": "/path/to/project"
  }
}
```

### 3. check_dependencies

Analyze package.json dependencies with outdated and security checking.

**Parameters:**
- `project_root` (string, optional): Directory containing package.json (defaults to MCP_FILE_ROOT)
- `package_manager` (string, optional): Package manager ("npm", "yarn", "pnpm", "auto") - default: "auto"
- `check_outdated` (bool, optional): Whether to check for outdated packages (default: true)
- `check_security` (bool, optional): Whether to run security audit (default: true)

**Example Usage:**
```json
{
  "package_manager": "npm",
  "check_outdated": true,
  "check_security": true
}
```

**Response Format:**
```json
{
  "data": {
    "package_manager": "npm",
    "dependencies": {
      "production": {"react": "^18.0.0", "next": "^13.0.0"},
      "development": {"typescript": "^4.0.0"},
      "peer": {"react-dom": "^18.0.0"},
      "optional": {"fsevents": "^2.0.0"},
      "total_count": 4
    },
    "outdated": [
      {
        "package": "react",
        "current": "18.0.0",
        "wanted": "18.2.0", 
        "latest": "18.2.0"
      }
    ],
    "security": {
      "summary": {"total": 1, "high": 1, "moderate": 0},
      "vulnerabilities": [
        {
          "id": "1065",
          "title": "Prototype Pollution",
          "severity": "high",
          "module_name": "lodash"
        }
      ]
    },
    "engines": {"node": ">=16.0.0"}
  }
}
```

### 4. parse_typescript_errors

Run TypeScript compiler and return structured error data.

**Parameters:**
- `project_root` (string, optional): Directory containing TypeScript project (defaults to MCP_FILE_ROOT)
- `tsconfig_path` (string, optional): Path to tsconfig.json relative to project_root (default: "tsconfig.json")
- `include_warnings` (bool, optional): Whether to include TypeScript warnings (default: true)
- `timeout` (int, optional): Maximum execution time in seconds (default: 120)

**Example Usage:**
```json
{
  "tsconfig_path": "tsconfig.build.json",
  "include_warnings": false
}
```

**Response Format:**
```json
{
  "data": {
    "errors": [
      {
        "file": "src/components/Button.tsx",
        "line": 15,
        "column": 8,
        "severity": "error",
        "code": "TS2741",
        "message": "Property 'onClick' is missing in type",
        "category": "semantic"
      }
    ],
    "summary": {
      "total_errors": 3,
      "total_warnings": 1,
      "total_issues": 4,
      "files_with_errors": 2,
      "compilation_success": false,
      "exit_code": 1
    },
    "categories": {
      "semantic": {
        "count": 2,
        "errors": 2,
        "warnings": 0,
        "common_codes": {"TS2741": 1, "TS2345": 1}
      }
    }
  }
}
```

### 5. parse_lint_results

Run linters and return categorized issues.

**Parameters:**
- `linter` (string, optional): Linter to use ("eslint", "prettier", "stylelint") - default: "eslint"
- `project_root` (string, optional): Directory to run linter in (defaults to MCP_FILE_ROOT)
- `target_files` (list[str], optional): Specific files to lint (defaults to linter defaults)
- `config_file` (string, optional): Path to linter config file
- `include_warnings` (bool, optional): Whether to include warnings (default: true)
- `timeout` (int, optional): Maximum execution time in seconds (default: 120)

**Example Usage:**
```json
{
  "linter": "eslint",
  "target_files": ["src/**/*.{js,ts,tsx}"],
  "include_warnings": true
}
```

**Response Format:**
```json
{
  "data": {
    "linter": "eslint",
    "issues": [
      {
        "file": "src/utils/api.ts",
        "line": 23,
        "column": 5,
        "severity": "warning",
        "rule": "no-console",
        "message": "Unexpected console statement",
        "fixable": true
      }
    ],
    "summary": {
      "total_errors": 2,
      "total_warnings": 5,
      "total_issues": 7,
      "files_with_issues": 3,
      "fixable_issues": 4,
      "exit_code": 1
    },
    "categories": {
      "no-console": {
        "count": 2,
        "errors": 0,
        "warnings": 2,
        "fixable": 2,
        "files": ["src/utils/api.ts"]
      }
    }
  }
}
```

### 6. run_test_suite

Execute tests with parsed results for multiple frameworks.

**Parameters:**
- `project_root` (string, optional): Directory to run tests in (defaults to MCP_FILE_ROOT)
- `test_command` (string, optional): Custom test command (auto-detected if None)
- `test_framework` (string, optional): Test framework ("jest", "vitest", "mocha", "pytest", "auto") - default: "auto"
- `pattern` (string, optional): Test file pattern to run specific tests
- `coverage` (bool, optional): Whether to generate coverage report (default: false)
- `timeout` (int, optional): Maximum execution time in seconds (default: 300)

**Supported Frameworks:**
- **Jest** - Auto-detected via package.json dependencies
- **Vitest** - Auto-detected via package.json dependencies  
- **Mocha** - Auto-detected via package.json dependencies
- **pytest** - Auto-detected via pytest.ini or pyproject.toml

**Example Usage:**
```json
{
  "test_framework": "jest",
  "pattern": "**/*.test.ts",
  "coverage": true
}
```

**Response Format:**
```json
{
  "data": {
    "framework": "jest",
    "summary": {
      "total": 25,
      "passed": 23,
      "failed": 2,
      "skipped": 0,
      "duration": 4.5
    },
    "test_files": [
      {
        "file": "src/components/Button.test.tsx",
        "passed": 3,
        "failed": 1,
        "skipped": 0,
        "duration": 1.2
      }
    ],
    "coverage": {
      "lines": {"total": 100, "covered": 85, "pct": 85},
      "statements": {"total": 120, "covered": 102, "pct": 85}
    },
    "command": "npm test --coverage",
    "success": false,
    "exit_code": 1
  }
}
```

### 7. run_nextjs_build

Specialized Next.js build with categorized error reporting.

**Parameters:**
- `project_root` (string, optional): Directory containing Next.js project (defaults to MCP_FILE_ROOT)
- `build_command` (string, optional): Command to run the build (default: "npm run build")
- `include_typescript_check` (bool, optional): Whether to include TypeScript type checking (default: true)
- `include_lint_check` (bool, optional): Whether to include ESLint checking (default: true)
- `timeout` (int, optional): Maximum execution time in seconds (default: 600)

**Example Usage:**
```json
{
  "build_command": "yarn build",
  "include_typescript_check": true,
  "include_lint_check": true
}
```

**Response Format:**
```json
{
  "data": {
    "typescript_errors": [
      {
        "file": "src/pages/api/users.ts",
        "line": 10,
        "column": 15,
        "severity": "error",
        "code": "TS2345",
        "message": "Argument of type 'string' is not assignable to parameter of type 'number'"
      }
    ],
    "eslint_violations": [
      {
        "file": "src/components/Header.tsx",
        "line": 5,
        "column": 10,
        "severity": "warning",
        "rule": "react-hooks/exhaustive-deps",
        "message": "React Hook useEffect has a missing dependency"
      }
    ],
    "bundle_warnings": [
      {
        "type": "bundle_size",
        "size": "512KB",
        "severity": "warning",
        "message": "Large bundle detected in main chunk"
      }
    ],
    "build_errors": [],
    "performance_info": {
      "shared_js_size": "85.2kB"
    },
    "summary": {
      "success": false,
      "total_errors": 1,
      "total_warnings": 2,
      "pages_count": 8,
      "static_pages": 5,
      "ssr_pages": 3
    },
    "additional_checks": {
      "typescript": {
        "success": false,
        "errors": [{"file": "...", "message": "..."}],
        "error_count": 1
      },
      "eslint": {
        "success": true,
        "violations": [],
        "error_count": 0,
        "warning_count": 0
      }
    },
    "command": "npm run build",
    "exit_code": 1,
    "success": false
  }
}
```

## Common Usage Patterns

### 1. Full Build Pipeline

Execute a complete build pipeline with all checks:

```json
// 1. Check dependencies first
{
  "tool": "check_dependencies",
  "parameters": {
    "check_outdated": true,
    "check_security": true
  }
}

// 2. Run TypeScript check
{
  "tool": "parse_typescript_errors",
  "parameters": {
    "include_warnings": false
  }
}

// 3. Run linting
{
  "tool": "parse_lint_results", 
  "parameters": {
    "linter": "eslint",
    "include_warnings": true
  }
}

// 4. Run tests
{
  "tool": "run_test_suite",
  "parameters": {
    "coverage": true
  }
}

// 5. Build application
{
  "tool": "run_nextjs_build",
  "parameters": {
    "include_typescript_check": false,
    "include_lint_check": false
  }
}
```

### 2. Configuration Analysis

Analyze project configuration and detect tools:

```json
{
  "tool": "get_build_config",
  "parameters": {}
}
```

Use the `detected_tools` to determine which subsequent tools to run.

### 3. Targeted Error Checking

Check specific aspects of the build:

```json
// TypeScript only
{
  "tool": "parse_typescript_errors",
  "parameters": {
    "tsconfig_path": "tsconfig.strict.json"
  }
}

// ESLint specific files
{
  "tool": "parse_lint_results",
  "parameters": {
    "linter": "eslint", 
    "target_files": ["src/components/**/*.tsx"]
  }
}

// Test specific pattern
{
  "tool": "run_test_suite",
  "parameters": {
    "pattern": "integration",
    "timeout": 600
  }
}
```

### 4. Security and Maintenance

Check for security issues and outdated dependencies:

```json
{
  "tool": "check_dependencies",
  "parameters": {
    "check_security": true,
    "check_outdated": true,
    "package_manager": "npm"
  }
}
```

### 5. Custom Command Execution

Run custom build commands with security validation:

```json
{
  "tool": "run_command",
  "parameters": {
    "command": "docker",
    "args": ["build", "-t", "myapp", "."],
    "timeout": 300
  }
}
```

## Error Handling

All tools follow consistent error response format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Detailed error message"
  }
}
```

**Common Error Codes:**
- `INVALID_INPUT`: Parameter validation failed
- `NOT_FOUND`: Resource (package.json, config file) not found  
- `PERMISSION_DENIED`: Command not in whitelist or security check failed
- `OPERATION_FAILED`: Command execution or parsing failed
- `TIMEOUT`: Operation exceeded timeout limit
- `UNSUPPORTED`: Feature or linter not supported

## Security Features

### Command Whitelisting

All command execution goes through security validation:

- **Default Whitelist**: Common development tools (npm, tsc, eslint, etc.)
- **Custom Whitelist**: Override with `allowed_commands` parameter
- **Path Validation**: All operations restricted to project root
- **Resource Limits**: Configurable timeouts and memory limits

### Input Validation

- **Path Traversal Protection**: Prevents access outside project root
- **Parameter Sanitization**: All inputs validated against expected types
- **Command Injection Prevention**: Arguments properly escaped and validated

## Performance Considerations

### Timeouts

Default timeouts are optimized for typical projects:

- **Quick Operations** (lint, typescript): 120 seconds
- **Standard Operations** (tests, build): 300 seconds  
- **Long Operations** (Next.js build): 600 seconds

### Optimization Tips

1. **Use Specific Patterns**: Target specific files instead of entire project
2. **Disable Unnecessary Checks**: Skip warnings or specific validations when not needed
3. **Parallel Execution**: Run independent tools concurrently 
4. **Incremental Builds**: Use framework-specific incremental build options

## Integration Examples

### CI/CD Pipeline Integration

```bash
# Example using the tools in a CI pipeline
npm run aromcp:check-deps
npm run aromcp:typecheck  
npm run aromcp:lint
npm run aromcp:test
npm run aromcp:build
```

### IDE Integration

Tools can be integrated with IDEs to provide:
- Real-time error checking
- Build status reporting
- Dependency analysis
- Test result parsing

### Custom Workflows

Create custom development workflows by chaining tools:
1. Configuration analysis → Tool detection
2. Dependency checking → Security validation
3. Code quality checks → Error reporting
4. Test execution → Coverage analysis
5. Build process → Production readiness

---

For more information about the AroMCP server architecture and other tool categories, see the main [README.md](../../README.md) and [technical documentation](../simplify-workflow.md).