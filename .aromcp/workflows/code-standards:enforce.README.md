# Code Standards Enforcement Workflow

## Purpose
This workflow automatically enforces code standards on changed files by applying code hints, fixing linting issues, and resolving TypeScript errors. It processes multiple files in parallel to efficiently bring your codebase into compliance with defined standards.

## Prerequisites
- Git repository with proper initialization
- AroMCP server running with access to:
  - `aromcp.hints_for_files` - Code quality hints
  - `aromcp.lint_project` - Linting with ESLint standards
  - `aromcp.check_typescript` - TypeScript type checking
- Node.js environment for TypeScript/JavaScript files
- Appropriate linters installed for other languages

## Usage
```bash
# Check and fix files changed in working directory (uncommitted changes)
mcp workflow start code-standards:enforce

# Check and fix files changed compared to main branch (default)
mcp workflow start code-standards:enforce --input compare_to=main

# Check and fix files changed compared to specific branch
mcp workflow start code-standards:enforce --input compare_to=feature/branch-name

# Check and fix files changed in a specific commit
mcp workflow start code-standards:enforce --input commit=abc123def
```

## Inputs
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| compare_to | string | No | main | Branch name to compare against for changes |
| commit | string | No | (empty) | Specific commit hash to get changed files from |

**Note**: If both parameters are provided, `commit` takes precedence. If neither is provided, compares against working directory (HEAD).

## Workflow Steps
1. **Initialize**: Sets up workflow and determines comparison target
2. **Get Changed Files**: Uses git to find all changed files including untracked
3. **Filter Code Files**: Filters to supported code extensions and excludes build directories
4. **Parallel Processing**: Processes up to 10 files simultaneously, each file:
   - Gets code quality hints from `aromcp.hints_for_files`
   - AI agent applies hint improvements
   - Runs lint check with ESLint standards
   - AI agent fixes any lint errors/warnings
   - Runs TypeScript check (for TS/JS files)
   - AI agent fixes any type errors
   - Retries up to 10 times until all checks pass
5. **Progress Monitoring**: Shows real-time progress updates
6. **Summary Report**: Displays final results with details on any failures

### Optimized Execution
This workflow uses **batched step execution** to minimize state transitions:
- User messages are grouped with actionable steps
- Multiple informational messages are delivered together
- State updates only occur when necessary
- This reduces workflow execution overhead and improves performance

## Supported File Types
- **Python**: `.py`, `.pyi`
- **TypeScript/JavaScript**: `.ts`, `.tsx`, `.js`, `.jsx`
- **Java**: `.java`
- **C/C++**: `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`
- **C#**: `.cs`
- **Ruby**: `.rb`

## Excluded Directories
The workflow automatically skips files in:
- `node_modules`
- `__pycache__`
- `.git`
- `dist`, `build`, `target`
- `bin`, `obj`, `out`
- `.venv`, `venv`, `env`
- `.pytest_cache`, `.mypy_cache`
- `vendor`

## Output
- All fixed files remain uncommitted for review
- Summary shows:
  - Total files processed
  - Number of successfully fixed files
  - Details of any files that couldn't be fixed after 10 attempts
  - Specific error counts for failed files

## Error Handling
- Each file gets up to 10 attempts to fix all issues
- If standards can't be met after 10 attempts, the file is marked as failed
- Workflow continues processing other files even if some fail
- Non-TypeScript files gracefully skip TypeScript checking
- Detailed error information is provided for debugging

## Example Output
```
Starting code standards enforcement workflow...
Checking for changed files against main...
Found 5 code files to process
Processing files... (3/5 complete)
Processing files... (5/5 complete)

====== Code Standards Enforcement Summary ======
Total files processed: 5
✅ Successfully fixed: 4 files
❌ Failed to fix: 1 files
- src/complex/module.ts
  Attempts: 10
  Last error: 3 TypeScript errors remaining

All changes have been left uncommitted. Review and commit when ready.
```

## Tips
- Review the changes before committing to ensure functionality is preserved
- For files that fail after 10 attempts, manual intervention may be needed
- Consider running tests after the workflow completes
- Use more specific comparison targets to process fewer files at once