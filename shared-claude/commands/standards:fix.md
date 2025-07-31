# /standards:fix

**Purpose**: Orchestrate parallel application of coding standards to changed files using specialized batch processing agents.

**Execution Pattern**: Main orchestrator manages workflow state, delegates file batches to up to 10 parallel sub-agents for maximum efficiency.

## Usage
- `/standards:fix` - Fix current changeset
- `/standards:fix branch <branch-name>` - Fix changes against branch
- `/standards:fix [file-path]` - Fix specific file/directory
- `/standards:fix [commit-id]` - Fix files in commit
- `/standards:fix --resume` - Continue from previous interrupted run

## Orchestrator Workflow

### Critical Constraints
- NEVER use bash pipes or grep - filter in memory with JavaScript
- NEVER process more than 5 files per batch
- Group files categorically by type/directory for efficient processing
- ALWAYS create `.aromcp/state/` directory before writing state
- Maximum 20 batches per run (create continuation prompt if more)
- Run up to 3 sub-agent batches in PARALLEL for optimal resource usage

### Step 1: Initialize Workflow State

1. **Check for Resume State**:
   ```bash
   # Check for existing state
   if [ -f ".aromcp/state/standards-fix-state.json" ]; then
     # Resume from existing state
   else
     # Initialize new workflow
   fi
   ```

2. **Detect Target Files**:
   - No argument → `git diff --name-only HEAD`
   - Branch name → `git diff --name-only <branch>`
   - Commit hash → `git diff-tree --no-commit-id --name-only -r <hash>`
   - File path → use AroMCP `list_files` tool with code patterns

3. **Filter Files IN MEMORY** (never use bash pipes):
   ```javascript
   const codeFiles = files.filter(f => 
     /\.(ts|tsx|js|jsx|py|java|cpp|c|h|hpp)$/.test(f) &&
     !/(node_modules|\.min\.|\/dist\/|\/\.next\/|\.d\.ts|\.generated\.|\.aromcp\/)/.test(f)
   );
   ```

4. **Create Categorical Batches**:
   Group files by architectural concern and technology stack for optimal processing efficiency. The categorization should consider:

   **Primary Grouping Strategy**:
   - **Frontend UI Layer**: Components, pages, layouts, client-side rendering logic that deals with user interface
   - **Frontend Logic Layer**: Client-side services, state management, browser-specific utilities and business logic
   - **Backend API Layer**: Routes, controllers, middleware, server-side request/response handling
   - **Backend Business Layer**: Services, business logic, data processing that doesn't directly handle HTTP requests
   - **Data & Schema Layer**: Database models, schemas, type definitions, interfaces, data structures
   - **Shared Utilities**: Pure functions, constants, utilities that work in both client and server environments
   - **Testing & Quality**: Test files, mocks, test utilities, quality assurance code with testing-specific standards
   - **Configuration & Infrastructure**: Build configs, deployment scripts, environment setup, development tooling

   **Batching Logic**:
   - Analyze each file's path, imports, and patterns to determine its architectural layer
   - Group related files together (max 5 per batch) within the same category
   - Process categories that share similar standards and patterns together
   - Ensure frontend files get frontend-focused standards, backend files get backend standards
   - Handle shared code with universal standards that work across environments

5. **Initialize State Structure**:
   ```json
   {
     "version": "1.0",
     "command_args": "original command arguments",
     "total_files": 45,
     "batches": [
       ["src/components/Button.tsx", "src/components/Modal.tsx", "src/components/Form.tsx"],
       ["src/utils/helpers.ts", "src/lib/api.ts", "src/lib/auth.ts", "src/utils/format.ts"]
     ],
     "batch_status": {
       "0": "pending",
       "1": "pending"
     },
     "file_results": {
       "src/components/Button.tsx": {
         "status": "pending",
         "modified": false,
         "failure_reason": null,
         "fixes": {"standards_hints": 0, "lint_fixes": 0}
       }
     },
     "summary": {
       "completed_batches": 0,
       "completed_files": 0,
       "modified_files": 0,
       "failed_files": 0,
       "total_fixes": {"standards_hints": 0, "lint_fixes": 0}
     },
     "start_time": "2025-01-15T10:30:00Z"
   }
   ```

6. **Save Initial State**:
   ```bash
   mkdir -p .aromcp/state/
   # Save state to .aromcp/state/standards-fix-state.json
   ```

### Step 2: Parallel Batch Processing

**Launch Multiple Sub-Agents**:
1. Calculate parallel capacity: `parallelBatches = min(3, remainingPendingBatches)`
2. Launch sub-agents simultaneously using Task tool with `standards-fix-batch-processor` agent
3. Each gets unique batch assignment with this prompt:

```
Use the standards-fix-batch-processor agent to process batch [N] of [total]:

Batch files: [file1, file2, file3, file4, file5]
State file: .aromcp/state/standards-fix-state.json
Batch index: [N]

The agent will:
1. Mark batch [N] as "in_progress" in shared state
2. Process each file through the complete fix pipeline
3. Update file results atomically in state
4. Mark batch as "completed" when done
5. Update summary counts

Report when batch processing is complete.
```

**Monitor and Continue**:
- Track active sub-agents
- As each completes, launch next available batch
- Continue until all batches processed or 20 batch limit reached
- If limit reached, provide continuation: `/standards:fix --resume`

### Step 3: Final Validation and Reporting

**After All Batches Complete**:
1. **Project-Wide Validation**:
   ```bash
   # Run final checks on entire project
   check_typescript()
   lint_project(use_standards=false)
   ```

2. **Calculate Exit Code**:
   - 0 = All fixed, builds clean
   - 1 = Builds but lint issues remain
   - 2 = Build errors exist

3. **Generate Summary from State**:
   ```javascript
   const state = JSON.parse(readFile('.aromcp/state/standards-fix-state.json'));
   const summary = {
     totalBatches: Object.keys(state.batch_status).length,
     completedBatches: state.summary.completed_batches,
     filesProcessed: state.summary.completed_files,
     filesModified: state.summary.modified_files,
     filesFailed: state.summary.failed_files,
     totalFixes: state.summary.total_fixes,
     failedFiles: Object.keys(state.file_results)
       .filter(f => state.file_results[f].status === "failed")
   };
   ```

4. **Cleanup and Report**:
   - If exit code is 0, remove state file
   - Report exit code for CI/CD integration
   - Display comprehensive summary

## State Management Protocol

### Atomic Updates Only
- Sub-agents MUST use atomic diff operations
- Never overwrite entire state file
- Handle concurrent access gracefully
- Implement exponential backoff for conflicts

### State File Structure
The state file acts as the coordination mechanism between the orchestrator and all parallel sub-agents. It tracks:
- Overall workflow progress
- Individual batch assignments and status
- Per-file processing results
- Aggregated statistics for final reporting

### Resume Capability
The `--resume` flag allows continuation from interruptions:
1. Load existing state file
2. Identify incomplete batches (`status !== "completed"`)
3. Continue processing from where left off
4. Maintain all existing results

## Error Handling

### Orchestrator Level
- Git command failures: Exit with clear error
- State file corruption: Backup and reinitialize
- Sub-agent failures: Mark batch as failed, continue others
- Resource limits: Graceful degradation to fewer parallel agents

### Recovery Patterns
- State conflicts: Exponential backoff and retry
- Partial failures: Continue processing remaining batches
- Timeout scenarios: Save progress, provide resume command

## Categorical Batching Benefits

### Efficiency Gains
- **Related Files Together**: Files in the same category often share similar patterns and standards
- **Context Optimization**: Processing related files reduces context switching for the agent
- **Parallel Safety**: Different categories can be processed simultaneously without conflicts
- **Resource Management**: 3 parallel agents provide optimal balance of speed vs. resource usage

### Architectural Grouping Benefits
- **Frontend UI Files**: Components, pages, and layouts get UI-focused standards (accessibility, component patterns, styling conventions)
- **Frontend Logic Files**: Client-side services and state management get browser-specific standards (async patterns, event handling, client-side validation)
- **Backend API Files**: Routes and controllers get API-focused standards (error handling, request validation, response formatting)  
- **Backend Business Files**: Services and business logic get server-specific standards (transaction handling, data processing, security patterns)
- **Data Schema Files**: Models and types get data-focused standards (validation schemas, type safety, database conventions)
- **Shared Utility Files**: Pure functions get universal standards (immutability, functional patterns, cross-platform compatibility)
- **Testing Files**: Test code gets testing-specific standards (assertion patterns, mock usage, test organization)
- **Infrastructure Files**: Configuration and tooling get deployment-focused standards (environment handling, build optimization)

## Integration Points

### Required Tools
- AroMCP `list_files` for file discovery
- Git commands for change detection
- State file management through standard file I/O

### Sub-Agent Interface
The orchestrator delegates actual file processing to the `standards-fix-batch-processor` agent, which handles:
- Standards application via `hints_for_file`
- TypeScript validation via `check_typescript`
- Linting fixes via `lint_project`
- Atomic state updates

This separation allows the orchestrator to focus purely on workflow management while specialized agents handle the complex file processing logic.