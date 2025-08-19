# /standards:fix

**Purpose**: Orchestrate parallel application of coding standards to changed files using specialized batch processing agents.

**Execution Pattern**: Main orchestrator manages workflow state, delegates file batches to up to 10 parallel sub-agents for maximum efficiency.

## Usage
- `/standards:fix` - Fix current changeset
- `/standards:fix branch <branch-name>` - Fix changes against branch
- `/standards:fix [file-path]` - Fix specific file/directory
- `/standards:fix [commit-id]` - Fix files in commit
- `/standards:fix --working-set` - Fix all unstaged/untracked files
- `/standards:fix --resume` - Continue from previous interrupted run

## Orchestrator Workflow

### Critical Constraints
- NEVER use bash pipes or grep - filter in memory with JavaScript
- NEVER process more than 10 files per batch
- Group files categorically by type/directory for efficient processing
- ALWAYS create `.aromcp/state/` directory before writing state
- Maximum 20 batches per run (create continuation prompt if more)
- Run sub-agent batches in SERIAL for optimal deduplication

### Step 1: Initialize Workflow State

1. **Check for Resume State**:
   - Check if `.aromcp/state/standards-fix-state.json` exists
   - If it exists: Resume from existing state
   - If not: Initialize new workflow

2. **Detect Target Files**:
   - No argument → `git diff --name-only HEAD`
   - Branch name → `git diff --name-only <branch>`
   - Commit hash → `git diff-tree --no-commit-id --name-only -r <hash>`
   - `--working-set` → `git ls-files -m -o --exclude-standard`
   - File path → Use AroMCP `list_files` tool with code patterns

3. **Filter Files IN MEMORY** (never use bash pipes):

   Filter for code files with these extensions: `ts`, `tsx`, `js`, `jsx`, `py`, `java`, `cpp`, `c`, `h`, `hpp`

   **Exclude files containing these patterns:**
   - `node_modules` directories
   - Minified files (`.min.`)
   - Distribution folders (`/dist/`)
   - Next.js build folders (`/.next/`)
   - TypeScript declaration files (`.d.ts`)
   - Generated files (`.generated.`)
   - Files with `.aromcp` in the path

4. **Create Semantic Domain Batches**:

   Group files by semantic domain and directory hierarchy for optimal processing efficiency. Use domain-based keyword extraction with directory hierarchy weighting to identify files that "go together" functionally.

   **Domain Extraction Strategy:**
   - Extract semantic keywords from file paths (examples: `subscription`, `auth`, `payment`, `user`, `notification`, `dashboard`)
   - Weight relationships by directory proximity (shared parent directories indicate stronger relationships)
   - Group files sharing domain keywords regardless of architectural layer to maintain functional context

   **Batching Logic**:

   1. **Extract Domain Keywords**: For each file, identify semantic keywords from:
      - Directory path segments (`features/subscription/`, `components/auth/`)
      - Filename patterns (`SubscriptionCard.tsx`, `useAuth.ts`, `payment-api.ts`)
      - Common domain terms: `subscription`, `auth`, `payment`, `user`, `notification`, `dashboard`, `billing`, `profile`, `settings`, `admin`
      - Technical patterns: `api`, `component`, `service`, `util`, `hook`, `store`, `model`, `type`, `test`, `config`
      - CamelCase/PascalCase breakdowns (`UserProfile` → `user`, `profile`)

   2. **Group by Shared Domains**:
      - Files sharing the same domain keywords should be batched together
      - Prioritize larger domain groups first (more files = stronger domain signal)
      - Files with multiple shared keywords have stronger relationships

   3. **Apply Directory Proximity**:
      - Within each domain group, prioritize files from the same directory
      - Files in `features/subscription/` are more related than files just containing "subscription"
      - Maintain max 10 files per batch, splitting large directories across multiple batches

   4. **Handle Remaining Files**:
      - Files without clear domain keywords get grouped by directory proximity only
      - Ensure all files are assigned to exactly one batch

   **Domain Grouping Benefits**:
   - Files related to "subscription" features are processed together, sharing context about subscription logic
   - Directory proximity ensures related files in same folder/feature are batched together
   - Cross-layer grouping allows agents to see full feature context (components + services + types)
   - Reduces duplication by processing functionally related files as a unit

5. **Initialize State Structure**:
   ```json
   {
     "version": "1.0",
     "command_args": "original command arguments",
     "total_files": 45,
     "batches": [
       ["src/components/Button.tsx", "src/components/Modal.tsx", "src/components/Form.tsx", "src/utils/helpers.ts", "src/lib/api.ts", "src/lib/auth.ts", "src/utils/format.ts", "src/types/user.ts", "src/hooks/useAuth.ts", "src/services/api.ts"]
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
         "fixes": {"standards_hints": 0, "lint_fixes": 0, "duplicates_consolidated": 0},
       "deduplication_actions": []
       }
     },
     "summary": {
       "completed_batches": 0,
       "completed_files": 0,
       "modified_files": 0,
       "failed_files": 0,
       "total_fixes": {"standards_hints": 0, "lint_fixes": 0, "duplicates_consolidated": 0}
     },
     "start_time": "2025-01-15T10:30:00Z"
   }
   ```

6. **Save Initial State**:
   ```bash
   mkdir -p .aromcp/state/
   # Save state to .aromcp/state/standards-fix-state.json
   ```

### Step 2: Serial Batch Processing

**Launch Sub-Agents Sequentially**:
1. Process one batch at a time to avoid deduplication conflicts
2. Launch sub-agents using Task tool with `standards-fix-batch-processor` agent
3. Each gets batch assignment with this prompt:

```
Use the standards-fix-batch-processor agent to process batch [N] of [total]:

Batch files: [file1, file2, file3, file4, file5, file6, file7, file8, file9, file10]
State file: .aromcp/state/standards-fix-state.json
Batch index: [N]

The agent will:
1. Mark batch [N] as "in_progress" in shared state
2. Process each file through the complete fix pipeline WITH deduplication
3. Use analysis server APIs to consolidate duplicate functions across entire codebase
4. Remove unused code detected during processing
5. Update file results atomically in state
6. Mark batch as "completed" when done
7. Update summary counts including deduplication actions

Report when batch processing is complete.
```

**Monitor and Continue**:
- Wait for current batch to complete before starting next batch
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

## Semantic Domain Batching Benefits

### Serial Processing Benefits
- **Comprehensive Deduplication**: Each batch can check entire codebase for duplicates without conflicts
- **Consistent State**: No race conditions or conflicts between parallel agents
- **Resource Efficiency**: Larger batches (10 files) reduce context switching overhead
- **Quality Assurance**: TypeScript compilation validates all changes before proceeding
- **Reliable Cleanup**: Unused code removal works safely without parallel conflicts

### Domain Grouping Benefits
- **Feature Cohesion**: All "subscription" related files (components, services, types, tests) processed together with shared context
- **Reduced Duplication**: Agent understands relationships between files and avoids reimplementing similar patterns
- **Directory Awareness**: Files in same directory/feature folder are prioritized for batching together
- **Semantic Understanding**: Keyword extraction identifies functional relationships beyond just file type
- **Cross-Architecture Processing**: Related files processed together regardless of whether they're frontend, backend, or shared code

### Examples of Domain Batching
- **Subscription Domain**: `SubscriptionCard.tsx`, `subscription-api.ts`, `useSubscription.ts`, `subscription.types.ts`
- **Authentication Domain**: `LoginForm.tsx`, `auth-service.ts`, `useAuth.ts`, `auth.middleware.ts`
- **Payment Domain**: `PaymentButton.tsx`, `payment-api.ts`, `billing.types.ts`, `stripe-webhook.ts`
- **User Profile Domain**: `ProfilePage.tsx`, `user-service.ts`, `profile.types.ts`, `useProfile.ts`

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