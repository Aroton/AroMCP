## Development Workflow with AroMCP

### The Core Principle
**The ONE mandatory requirement**: Always call `hints_for_file()` before editing any file to get project standards.

### Essential Tools
1. **`hints_for_file(filepath, session_id?)`** - Get project standards and coding rules (MANDATORY before edits)
2. **`lint_project(use_standards=True)`** - Check code style using generated rules (ALWAYS use generated rules)
3. **`check_typescript()`** - Validate TypeScript compilation

### Required Workflow Order
```python
# 1. Get standards before editing
hints = hints_for_file("src/api/user.ts", session_id="fix-user-api-123")

# 2. Make your edits following the standards...

# 3. Run linter with generated rules (REQUIRED)
lint_results = lint_project(use_standards=True)

# 4. Check TypeScript errors (REQUIRED)
ts_errors = check_typescript()
```


### Multiple File Operations
```python
# Multiple files - reuse session for efficiency
session = "refactor-auth-1234"
hints_for_file("src/auth/login.ts", session_id=session)
hints_for_file("src/auth/logout.ts", session_id=session)  # 70-80% token savings

# Make changes...

# ALWAYS validate in this order after edits:
lint_project(use_standards=True, files=["src/auth/*.ts"])  # Generated rules
check_typescript(files=["src/auth/*.ts"])  # TypeScript validation
```

### Other Useful Tools
Discover available tools via MCP, but these are commonly helpful:

#### File Operations (Filesystem Server)
- **`list_files()`** - List files with glob patterns and pagination
- **`read_files()`/`write_files()`** - Batch file operations

#### Code Analysis (Analysis Server)
- **`find_references()`** - Find symbol references across files (check dependencies before changes)
- **`get_function_details()`** - Extract detailed function information
- **`analyze_call_graph()`** - Generate static call graphs

#### Build & Quality (Build Server)
- **`lint_project()`** - Run ESLint with standards
- **`check_typescript()`** - Validate TypeScript compilation
- **`run_test_suite()`** - Execute tests with detailed results

#### Standards Management (Standards Server)
- **`hints_for_file()`** - Get project standards and coding rules (core development tool)

### Best Practices
✅ Always check standards before editing (the one hard rule)
✅ ALWAYS use `use_standards=True` when linting (generated rules are superior)
✅ Follow the required order: Standards → Edit → Lint → TypeScript
✅ Use consistent `session_id` within operations for token efficiency
✅ Focus validation on changed files
✅ Apply standards consistently across related files using session IDs
✅ Validate changes incrementally to catch issues early

❌ Don't skip `hints_for_file()` - ever
❌ Don't skip linting after edits - always validate
❌ Don't use `use_standards=False` unless debugging ESLint issues
❌ Don't run dev servers (`npm run dev`, etc.)
❌ Don't validate unchanged files unless debugging

### The Bottom Line
Check standards before editing. Apply standards consistently using session IDs for token efficiency. Everything else adapts to what you're doing. Simple tasks need simple workflows.