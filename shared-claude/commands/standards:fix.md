# /standards:fix

**Purpose**: Apply project-specific coding standards to changed files using hints and automated fixes.

**Execution Pattern**: Main agent orchestrates, delegates batches to up to 10 parallel sub-agents for maximum efficiency.

## Usage
- `/standards:fix` - Fix current changeset
- `/standards:fix branch <branch-name>` - Fix changes against branch
- `/standards:fix [file-path]` - Fix specific file/directory
- `/standards:fix [commit-id]` - Fix files in commit
- `/standards:fix --resume` - Continue from previous interrupted run

## Main Agent Workflow

### Critical Constraints
- NEVER use bash pipes or grep - filter in memory with JavaScript
- NEVER process more than 3 files per batch
- ALWAYS create `.aromcp/state/` directory before writing state
- Use appropriate tools for file operations (let agent choose best tool)
- Maximum 20 batches per run (create continuation prompt if more)
- Run up to 10 sub-agent batches in PARALLEL for faster processing

### Step 1: Initialize and Detect Files
1. Check for existing state in `.aromcp/state/standards-fix-state.json` using appropriate file reading method
2. If no state or new command, detect files:
   - No argument → `git diff --name-only HEAD`
   - Branch name → `git diff --name-only <branch>`
   - Commit hash → `git diff-tree --no-commit-id --name-only -r <hash>`
   - File path → use list_files tool with code patterns
3. Filter results IN MEMORY (never use bash pipes):
   - Keep only: ts, tsx, js, jsx, py, java, cpp, c, h, hpp
   - Exclude: node_modules, .min., /dist/, /.next/, .d.ts, .generated., .aromcp/
4. Create batches of 3 files maximum
5. Initialize state structure:
   ```
   {
     version: "1.0",
     total_files: number,
     batches: [[file1, file2, file3], ...],
     batch_status: {
       "0": "pending",  // batch index -> status
       "1": "pending",
       // ... for each batch
     },
     file_results: {
       "path/to/file1.ts": {
         status: "pending",  // pending|completed|failed
         modified: false,
         failure_reason: null,
         fixes: {standards_hints: 0, lint_fixes: 0}
       },
       // ... for each file
     },
     summary: {
       completed_batches: 0,
       completed_files: 0,
       modified_files: 0,
       failed_files: 0,
       total_fixes: {standards_hints: 0, lint_fixes: 0}
     },
     start_time: ISO timestamp
   }
   ```
6. Save state to `.aromcp/state/standards-fix-state.json` using appropriate file operation

### Step 2: Delegate Batches to Sub-Agents
Process batches in parallel for maximum efficiency:
1. Launch up to 10 sub-agents in parallel:
   - Calculate: `parallelBatches = min(10, remainingBatches)`
   - Launch multiple Task tool instances simultaneously
   - Each sub-agent gets unique batch assignment

2. For each parallel group:
   - Track running batches: maintain list of active sub-agent tasks
   - Launch sub-agents with Task tool prompts:
     ```
     Process standards fixes for batch N of M:
     Files: [file1, file2, file3]
     State file: .aromcp/state/standards-fix-state.json
     Batch index: N

     1. Mark batch as "in_progress" in state
     2. For each file:
        - Check with hints_for_file, lint_project(use_standards=true), check_typescript
        - Apply fixes if needed (up to 3 attempts)
        - Update file result in state
     3. Mark batch as "completed" in state
     4. Update summary counts

     Apply all state updates using atomic diff operations.
     Report completion status when done.
     ```
   - Monitor all sub-agents for completion
   - As each completes, launch next batch if available
   - Check state file for results from completed batches

3. Continue until all batches processed or 20 total batches completed
4. If more batches remain:
   - Report progress
   - Provide continuation command: `/standards:fix --resume`

### Step 3: Final Validation
After all batches show "completed" status:
1. Run `check_typescript()` on entire project
2. Run `lint_project(use_standards=false)` on entire project
3. Calculate exit code:
   - 0 = All fixed, builds clean
   - 1 = Builds but lint issues remain
   - 2 = Build errors exist
4. Generate summary from state file:
   - Total batches: `Object.keys(state.batch_status).length`
   - Completed batches: `state.summary.completed_batches`
   - Files processed: `state.summary.completed_files`
   - Files modified: `state.summary.modified_files`
   - Files failed: `state.summary.failed_files`
   - Total fixes: `state.summary.total_fixes`
   - Failed files list: Files where `file_results[f].status === "failed"`
5. If exit code is 0, clean up state file
6. Report exit code for CI/CD integration

---

## Sub-Agent Instructions (for each batch)

**You are processing a specific batch of files for standards compliance.**

### Your Task
1. Get your batch assignment (batch index N and file list)
2. Apply state diff: Mark your batch as "in_progress"
   ```
   {
     "batch_status": {
       "N": "in_progress"  // Update just this line
     }
   }
   ```
3. Process each file in your batch:
   - Use `hints_for_file` to get standards
   - Use `lint_project(use_standards=true, target_files=[file])`
   - Use `check_typescript([file])`
   - Apply fixes based on hints (up to 3 attempts)
   - After each file, apply state diff for that file's result
4. Apply final state diff:
   - Mark batch as "completed"
   - Update summary counts
5. Report completion

### File Processing
For each file in your batch:
1. Check current issues:
   - `hints = await hints_for_file(file)`
   - `lintResult = await lint_project(use_standards=true, target_files=[file], fix=false)`
   - `tsResult = await check_typescript([file])`

2. If issues found, attempt fixes (up to 3 attempts):
   - Track fixes locally for this file:
     * `file_fixes = {standards_hints: 0, lint_fixes: 0}`
   - If lint has fixable issues:
     * Run `lint_project(use_standards=true, target_files=[file], fix=true)`
     * Track: `file_fixes.lint_fixes += result.fixed`
   - Apply hint transformations:
     * Read the file content using the most appropriate tool
     * Apply fixes based on hint.rule_id (use Edit for small changes, rewrite for major changes)
     * Add imports from hint.imports if not present
     * Save the modified content using the best tool for the changes made
     * Track: `file_fixes.standards_hints += hints.length`

3. Verify with `check_typescript([file])` after each attempt

4. Apply state diff for this file:
   ```
   {
     "file_results": {
       "path/to/file.ts": {
         "status": "completed",  // or "failed"
         "modified": true,       // or false
         "failure_reason": null, // or error message
         "fixes": {"standards_hints": 2, "lint_fixes": 3}
       }
     }
   }
   ```

### State Diff Application Process
**CRITICAL**: All state updates MUST be applied as atomic diffs:

1. **Read current state** - Load `.aromcp/state/standards-fix-state.json`
2. **Apply your diff** - Update only the specific fields you're changing:
   - For batch status: Update only `batch_status[N]`
   - For file results: Update only `file_results[filepath]`
   - For summary: Increment counts based on your results
3. **Write merged state** - Save the updated state back atomically

Example diff sequence for a batch:
```
// Step 1: Mark batch in progress
{"batch_status": {"2": "in_progress"}}

// Step 2: After processing file1
{"file_results": {"src/file1.ts": {"status": "completed", "modified": true, "failure_reason": null, "fixes": {"standards_hints": 1, "lint_fixes": 2}}}}

// Step 3: After processing file2
{"file_results": {"src/file2.ts": {"status": "failed", "modified": false, "failure_reason": "TypeScript error", "fixes": {"standards_hints": 0, "lint_fixes": 0}}}}

// Step 4: Mark batch completed and update summary
{
  "batch_status": {"2": "completed"},
  "summary": {
    "completed_batches": "+1",  // Increment notation
    "completed_files": "+2",
    "modified_files": "+1",
    "failed_files": "+1",
    "total_fixes": {
      "standards_hints": "+1",
      "lint_fixes": "+2"
    }
  }
}
```

**Never overwrite the entire state file** - Always apply minimal diffs to avoid race conditions.

### Understanding Hints
Each hint from hints_for_file contains:
- `rule_id`: Stable identifier (e.g., 'use-cache-function', 'export-schema-types')
- `rule`: What needs fixing
- `example`: Code showing correct implementation
- `imports`: Array of {module, imported_items, statement}
- `context`: When/why to apply

### Error Handling
- Git command fails: Exit with clear error
- File not found: Skip and continue
- State corruption: Start fresh
- Build errors after fix: Count as attempt, retry