# /diff:analyze

**Purpose**: Analyze uncommitted changes with deep implementation understanding to identify behavior changes, lost functionality, and refactoring risks.

## Usage
- `/diff:analyze` - Analyze all uncommitted changes
- `/diff:analyze --critical` - Focus only on high-risk changes

## Critical Rules
- NEVER assume renamed files preserve functionality - verify implementation
- ALWAYS trace code flow changes between old and new versions
- ALWAYS check if removed functions/methods are still referenced
- FOCUS on code files (.js, .ts, .jsx, .tsx, .py, .java, .go, .rb, .php, .cs)
- IGNORE config/data files unless they contain logic

## Execution Process

### 1. Initialize
- Get diff: `git diff --name-status`
- Filter for code files only
- Group changes: Added (A), Modified (M), Deleted (D), Renamed (R)
- Create TODOs for batch processing (4-6 files per batch)

### 2. Process Renamed Files [TODO: analyze-renames-N]
For each renamed file pair:
- Load both old and new file contents
- Calculate content similarity percentage
- Extract all functions/classes from both versions
- Compare implementations:
  - Map old functions to new functions by signature
  - Identify missing functions (potential lost functionality)
  - Analyze behavior changes in matched functions
  - Check if logic flow has changed significantly
- Flag as HIGH RISK if:
  - <70% content similarity
  - Missing functions that were exported/public
  - Core logic flow altered

### 3. Process Modified Files [TODO: analyze-modified-N]
For each modified file:
- Get full diff with context: `git diff -U10 <file>`
- Identify changed functions/methods
- For each changed function:
  - Analyze old vs new implementation
  - Check if function signature changed (breaking change)
  - Compare control flow (loops, conditions, returns)
  - Identify removed error handling
  - Check for removed features/branches
- Flag as HIGH RISK if:
  - Public API signatures changed
  - Error handling removed
  - Major control flow changes
  - Security-sensitive code modified

### 4. Process Deleted Files [TODO: analyze-deleted-N]
For each deleted file:
- Extract all exported/public functions
- Search codebase for references: `grep -r "function_name" --include="*.js" --include="*.ts"`
- Flag as HIGH RISK if:
  - Still referenced elsewhere
  - Contains business logic (not just utilities)
  - No apparent replacement

### 5. Process Added Files [TODO: analyze-added-N]
For each added file:
- Identify if it replaces deleted functionality
- Extract main purpose and functions
- Check for potential duplicated logic

### 6. Cross-Reference Analysis [TODO: analyze-dependencies]
- For all removed/renamed functions:
  - Search for usages across codebase
  - Verify replacements exist
- For modified function signatures:
  - Find all call sites
  - Verify compatibility

### 7. Generate Report [TODO: generate-report]
Create markdown report at `.claude/reports/diff-analysis-[timestamp].md`:

```markdown
# Diff Analysis Report
Generated: [timestamp]
Files analyzed: [count]

## Executive Summary
[2-3 sentence high-level summary of changes]

## Risk Assessment
### 🔴 Critical Risks ([count])
[Changes that likely break functionality]

### 🟡 High Risks ([count])
[Changes that may alter behavior]

### 🟢 Low Risks ([count])
[Safe refactoring/improvements]

## Detailed Analysis

### 1. Renamed Files ([count])
| Old Path | New Path | Similarity | Risk | Notes |
|----------|----------|------------|------|-------|
| src/user.js | src/models/user.js | 95% | 🟢 Low | Pure move, no logic change |
| api/v1.js | api/v2.js | 45% | 🔴 Critical | Major refactor, 5 methods removed |

### 2. Functionality Changes
#### Lost Functionality
- **File**: `src/auth.js`
  - **Function**: `validateLegacyToken()`
  - **Risk**: 🔴 Critical - Still called by 3 files
  - **Description**: Legacy auth support removed without migration

#### Added Functionality
- **File**: `src/auth-v2.js`
  - **Function**: `validateJWT()`
  - **Description**: New JWT validation, replaces legacy tokens

### 3. Modified Behaviors
#### High Risk Changes
- **File**: `src/payment.js`
  - **Function**: `processPayment()`
  - **Change**: Error handling removed from stripe integration
  - **Old**: Try-catch with retry logic
  - **New**: Direct call without error handling
  - **Impact**: Payment failures will crash instead of retry

### 4. Breaking Changes
- **API Changes**:
  - `getUserById(id)` → `getUserById(id, options)` - New required parameter
  - Affects: 12 call sites need updating

### 5. Recommendations
1. **Immediate Actions**:
   - Restore error handling in payment.js
   - Update getUserById call sites

2. **Review Required**:
   - Verify legacy token migration plan
   - Test payment flow extensively
```

## Implementation Helpers

```javascript
// Function to analyze code flow changes
function analyzeFlowChange(oldCode, newCode) {
  const oldFlow = extractControlFlow(oldCode);
  const newFlow = extractControlFlow(newCode);

  return {
    addedBranches: newFlow.branches.filter(b => !oldFlow.branches.includes(b)),
    removedBranches: oldFlow.branches.filter(b => !newFlow.branches.includes(b)),
    modifiedLoops: compareLoops(oldFlow.loops, newFlow.loops),
    changedReturns: oldFlow.returns !== newFlow.returns
  };
}

// Calculate similarity between renamed files
function calculateSimilarity(oldContent, newContent) {
  const oldLines = oldContent.split('\n');
  const newLines = newContent.split('\n');
  const commonLines = oldLines.filter(line => newLines.includes(line)).length;
  return Math.round((commonLines / Math.max(oldLines.length, newLines.length)) * 100);
}
```

## Error Handling
- If git diff fails: Check if in git repository
- If file read fails: Skip file, note in report
- If grep fails: Note as "Unable to verify usage"

## Examples

### Example 1: Simple refactor
```bash
/diff:analyze
# Output: "2 files renamed, 98% similar, no functionality lost"
```

### Example 2: Risky refactor
```bash
/diff:analyze
# Output: "WARNING: 3 critical risks found
# - payment.js: Error handling removed
# - auth.js: validateLegacyToken deleted but still referenced
# - api/user.js: Breaking change in getUserById signature"
```

### Example 3: Focus on critical only
```bash
/diff:analyze --critical
# Output: "Analyzing critical changes only...
# Found 2 critical issues requiring immediate attention"
```