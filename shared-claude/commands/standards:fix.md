# Standards Fix Command

**Purpose**: Automatically fix coding standards violations and lint issues in changed files by applying hints_for_file guidance and running lint fixes on the current changeset.

## Usage
- `/standards:fix` - Fix current changeset (staged + unstaged changes)
- `/standards:fix branch` - Fix all changes against tracking branch
- `/standards:fix [file-path]` - Fix specific file
- `/standards:fix [commit-id]` - Fix files in specific commit

## Quick Reference
- **Detection**: Automatically finds files in current changeset or vs tracking branch
- **Fixing**: Uses `hints_for_file` + `lint_project` + direct file modifications
- **Batch Processing**: Processes and fixes files efficiently in groups
- **Output**: Clear summary of fixes applied with before/after status

## What Standards Fix Does
This command performs comprehensive standards fixing:
- **Identifies changed files** automatically from current changeset or branch comparison
- **Applies coding standards** using hints_for_file guidance to modify files directly
- **Fixes lint issues** using automated lint fixes and manual corrections
- **Modifies files in place** with proper standards-compliant code
- **Supports multiple scopes** - all changes, specific files, or commit ranges

## Critical Rules

### 1. File Detection Strategy
**Automatically detect tracking branch:**
```javascript
// Get the tracking branch for current branch
const trackingResult = await Bash("git for-each-ref --format='%(upstream:short)' $(git symbolic-ref -q HEAD)");
const trackingBranch = trackingResult.stdout.trim();

// Fallback to main/master if no tracking branch
let baseBranch = trackingBranch;
if (!baseBranch) {
  const mainExists = await Bash("git rev-parse --verify main 2>/dev/null");
  baseBranch = mainExists.exit_code === 0 ? "main" : "master";
}
```

### 2. Skip These Files
- `*.min.js`, `*.bundle.js` (minified/bundled)
- `**/node_modules/**`, `**/.next/**`, `**/dist/**`
- `*.generated.*`, `*.d.ts`
- Files with `// @no-verify` or `/* eslint-disable */`
- Non-code files (images, docs, config unless specifically requested)

### 3. Tools Integration
**Use existing MCP tools efficiently:**
```javascript
// Use hints_for_file for standards checking
const hintsResult = await hints_for_file({
  file_paths: filesToCheck,
  project_root: projectRoot
});

// Use lint_project for code quality
const lintResult = await lint_project({
  target_files: filesToCheck,
  project_root: projectRoot
});
```

## Execution Process

### 1. Initialize and Detect Files

**Determine scope based on arguments:**
```javascript
let filesToCheck = [];

if (!args || args.length === 0) {
  // Default: current changeset (staged + unstaged changes)
  const stagedResult = await Bash("git diff --cached --name-only");
  const unstagedResult = await Bash("git diff --name-only");
  
  const stagedFiles = stagedResult.exit_code === 0 ? stagedResult.stdout.trim().split('\n').filter(Boolean) : [];
  const unstagedFiles = unstagedResult.exit_code === 0 ? unstagedResult.stdout.trim().split('\n').filter(Boolean) : [];
  
  // Combine and deduplicate
  filesToCheck = [...new Set([...stagedFiles, ...unstagedFiles])];
  
  if (filesToCheck.length === 0) {
    console.log("No changes found in current changeset");
    return;
  }
} else if (args.length === 1) {
  const arg = args[0];
  
  if (arg === "branch") {
    // Compare against tracking branch
    const trackingResult = await Bash("git for-each-ref --format='%(upstream:short)' $(git symbolic-ref -q HEAD)");
    const trackingBranch = trackingResult.stdout.trim() || "main";
    
    const diffResult = await Bash(`git diff --name-only ${trackingBranch}...HEAD`);
    if (diffResult.exit_code === 0 && diffResult.stdout.trim()) {
      filesToCheck = diffResult.stdout.trim().split('\n').filter(Boolean);
    }
  } else if (arg.match(/^[a-f0-9]{7,40}$/)) {
    // Commit hash
    const diffResult = await Bash(`git diff --name-only ${arg}^..${arg}`);
    if (diffResult.exit_code === 0) {
      filesToCheck = diffResult.stdout.trim().split('\n').filter(Boolean);
    }
  } else {
    // File path or directory
    const stat = await Bash(`test -e "${arg}" && echo "exists"`);
    if (stat.stdout.includes("exists")) {
      filesToCheck = [arg];
    } else {
      console.error(`File or directory not found: ${arg}`);
      return;
    }
  }
}

// Filter to code files only
const codeExtensions = ['.ts', '.tsx', '.js', '.jsx', '.py', '.java', '.go', '.rs', '.cpp', '.c', '.h'];
filesToCheck = filesToCheck.filter(file => 
  codeExtensions.some(ext => file.endsWith(ext)) &&
  !file.includes('node_modules') &&
  !file.includes('.next') &&
  !file.includes('dist/') &&
  !file.endsWith('.min.js') &&
  !file.endsWith('.d.ts')
);

if (filesToCheck.length === 0) {
  console.log("No code files found to fix");
  return;
}

console.log(`🔧 Found ${filesToCheck.length} files to fix standards compliance`);
```

### 2. Process Files in Batches for Parallel Fixing

**Execute fixes using batched processing for efficiency:**
```javascript
console.log("🔧 Running standards fixes...");

// Split files into batches for parallel processing
const batchSize = 3; // Process 3 files per batch for manageable task size
const numBatches = Math.ceil(filesToCheck.length / batchSize);

console.log(`Processing ${filesToCheck.length} files in ${numBatches} batches`);

// Create tasks for all batches
const batchTasks = [];
for (let batchNum = 0; batchNum < numBatches; batchNum++) {
  const startIdx = batchNum * batchSize;
  const endIdx = Math.min(startIdx + batchSize, filesToCheck.length);
  const batchFiles = filesToCheck.slice(startIdx, endIdx);

  // Create comprehensive task prompt for this batch
  const batchTaskPrompt = `Fix coding standards violations and lint issues for batch ${batchNum + 1}/${numBatches}.

**BATCH CONTENTS (${batchFiles.length} files):**
${batchFiles.map(file => `- ${file}`).join('\n')}

**FIXING INSTRUCTIONS**:

1. **Read all files in this batch using read_files tool**

2. **Get coding standards hints for guidance using hints_for_file tool**:
   - Use file_paths: ${JSON.stringify(batchFiles)}
   - Focus on high-priority violations and standards issues

3. **Apply standards fixes based on hints**:
   - For each hint with priority 'high' or type 'violation'
   - Modify file content to comply with the standards guidance
   - Track which files are modified and what fixes are applied

4. **Apply automated lint fixes using lint_project tool**:
   - Use target_files: ${JSON.stringify(batchFiles)}
   - Enable fix: true for auto-fix mode
   - Count the fixes applied

5. **Write all modified files back using write_files tool**:
   - Only write files that were actually modified
   - Ensure proper file structure and formatting

**OUTPUT STRUCTURE**:
Return a summary object with:
\`\`\`javascript
{
  batch_number: ${batchNum + 1},
  files_processed: ${batchFiles.length},
  files_modified: ["file1.ts", "file2.tsx"], // List of modified files
  standards_fixes: 5, // Count of standards violations fixed
  lint_fixes: 12, // Count of lint issues auto-fixed
  total_fixes: 17, // Sum of standards + lint fixes
  success: true,
  errors: [] // Any errors encountered
}
\`\`\`

**IMPORTANT REQUIREMENTS**:
- ALWAYS read files first before attempting any modifications
- Only modify files that actually have standards violations or lint issues
- Use the exact file paths provided in the batch
- Apply fixes incrementally and track changes carefully
- Ensure all modified files are written back properly
- Report detailed statistics for this batch only

Process this batch independently and report the results.`;

  // Launch AI agent to process this batch
  const batchTask = Task({
    description: `Fix batch ${batchNum + 1}`,
    prompt: batchTaskPrompt
  });
  batchTasks.push(batchTask);
}

console.log(`✅ Launched ${batchTasks.length} fixing tasks in parallel`);

// Collect results from all batches
const batchResults = await Promise.all(batchTasks);
const fixesSummary = {
  standards_fixes: 0,
  lint_fixes: 0,
  files_modified: [],
  total_batches: numBatches,
  successful_batches: 0,
  errors: []
};

// Aggregate results from all batches
for (const result of batchResults) {
  if (result.success) {
    fixesSummary.successful_batches++;
    fixesSummary.standards_fixes += result.standards_fixes || 0;
    fixesSummary.lint_fixes += result.lint_fixes || 0;
    
    // Add modified files (avoid duplicates)
    if (result.files_modified) {
      for (const file of result.files_modified) {
        if (!fixesSummary.files_modified.includes(file)) {
          fixesSummary.files_modified.push(file);
        }
      }
    }
  } else {
    fixesSummary.errors.push(`Batch ${result.batch_number}: ${result.error}`);
  }
}

console.log(`📊 Batch processing complete: ${fixesSummary.successful_batches}/${fixesSummary.total_batches} successful`);
```

### 3. Final Validation and Summary

**Files are already written by each batch task, now run final validation:**
```javascript
// Note: Files are already written by individual batch tasks during processing

// Run final validation to check remaining issues across all processed files
console.log("🔍 Running final validation...");
const finalLintResult = await lint_project({
  target_files: filesToCheck
});

const remainingIssues = finalLintResult.data?.issues?.length || 0;
const totalFixes = fixesSummary.standards_fixes + fixesSummary.lint_fixes;
const filesModified = fixesSummary.files_modified.length;

console.log("\n" + "=".repeat(60));
console.log("🔧 STANDARDS FIX REPORT");
console.log("=".repeat(60));

if (totalFixes === 0) {
  console.log("✅ No issues found - all files already comply with standards!");
  console.log(`📁 Files checked: ${filesToCheck.length}`);
  console.log("🎉 No fixes needed");
  return;
}

// Report fixes applied across all batches
console.log(`🔧 Applied ${totalFixes} fixes to ${filesModified} files:`);
console.log(`   📋 Standards fixes: ${fixesSummary.standards_fixes}`);
console.log(`   🔧 Lint fixes: ${fixesSummary.lint_fixes}`);
console.log(`   📁 Files modified: ${filesModified}`);
console.log(`   📦 Batches processed: ${fixesSummary.successful_batches}/${fixesSummary.total_batches}`);

// Report any batch errors
if (fixesSummary.errors.length > 0) {
  console.log(`\n⚠️  Batch processing errors:`);
  fixesSummary.errors.forEach(error => console.log(`   - ${error}`));
}

if (remainingIssues > 0) {
  console.log(`\n⚠️  ${remainingIssues} issues still require manual attention`);
} else {
  console.log("\n✅ All automated fixes applied successfully!");
}
console.log("");

Object.entries(issuesByFile).forEach(([file, issues]) => {
  console.log(`📄 ${file}:`);
  issues.forEach(issue => {
    const icon = issue.type === 'standards' ? '📋' : '🔧';
    const location = issue.line ? `:${issue.line}` : '';
    console.log(`   ${icon} ${issue.issue}${location}`);
  });
  console.log("");
});

// Provide next steps
console.log("🔧 RECOMMENDED ACTIONS:");
if (standardsViolations > 0) {
  console.log("1. Review coding standards hints and apply recommended changes");
  console.log("2. Use `/standards:update` to refresh standards if needed");
}
if (lintErrors > 0) {
  console.log("3. Run linter with --fix flag to auto-resolve style issues");
  console.log("4. Address remaining lint errors manually");
}
console.log("5. Re-run `/standards:fix` to apply additional fixes if needed");

console.log("\n" + "=".repeat(60));
```

### 4. Exit Codes and Integration

**Support CI/CD integration:**
```javascript
// Set appropriate exit code for CI systems
if (totalIssues > 0) {
  console.log(`\n💡 TIP: This command found ${totalIssues} remaining issues.`);
  console.log("Review the remaining issues and run the command again if needed.");
  
  // In a CI environment, you might want to fail the build
  // process.exit(1);
} else {
  console.log("\n✅ Standards fixes applied successfully!");
  // process.exit(0);
}
```

## Integration with Existing Tools

This command leverages the existing MCP infrastructure:

- **hints_for_file**: Provides context-aware coding standards guidance
- **lint_project**: Runs project-specific linting rules
- **File detection**: Uses git commands to identify changed files
- **Batch processing**: Efficiently handles multiple files

## Usage Examples

```bash
# Fix current changeset (default)
/standards:fix

# Fix against tracking branch
/standards:fix branch

# Fix specific file
/standards:fix src/components/UserProfile.tsx

# Fix files in a specific commit
/standards:fix a1b2c3d

# Fix all files in a directory
/standards:fix src/services/
```

## Performance Considerations

- **Efficient file detection**: Only processes actually changed files
- **Parallel batch processing**: Processes files in batches of 3 for optimal performance
- **Task-based architecture**: Uses Task tool for parallel execution across batches
- **Smart filtering**: Excludes non-code files and build artifacts
- **Incremental fixing**: Each batch handles its own read-fix-write cycle independently
- **Clear output**: Focuses on actionable feedback with batch-level progress tracking

## Notes

- This command is designed to be **fast and focused** compared to the comprehensive `/project:simplify` command
- It **automatically modifies files** to fix detected standards violations and lint issues
- Works with **any git repository** and **any project structure**
- Can be easily integrated into **pre-commit hooks** or **CI pipelines**
- Uses the **same standards system** as other standards commands for consistency