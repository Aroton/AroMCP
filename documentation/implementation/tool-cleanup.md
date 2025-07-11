# MCP Server Cleanup Testing Tracker

## Overview
This document tracks the testing results for MCP server cleanup functions. Functions are categorized by implementation priority.

---

## Common Tasks Across Multiple Functions

### 1. Pagination Simplification (Affects 8+ functions) ✅ COMPLETED
**Implementation Pattern:**
```python
def simplify_pagination(items, page, max_tokens, total_items):
    # For small results, skip pagination entirely
    if total_items <= 10:
        return {"items": items}

    # For larger results, use minimal pagination
    return {
        "items": items,
        "page": page,
        "has_more": len(items) == max_tokens,
        "total": total_items if total_items < 100 else "100+"  # Avoid expensive counts
    }
```

**Affected Functions:** ✅ ALL COMPLETED
- ✅ parse_typescript_errors
- ✅ parse_lint_results (all 3 linter variants)
- ✅ get_target_files (+ added `details` parameter for output reduction)
- ✅ read_files_batch
- ✅ extract_method_signatures
- ✅ find_imports_for_files

**Implementation Notes:**
- Maintains token-based pagination internally for MCP transmission limits
- Simplified output format: small results skip pagination, large results use minimal metadata
- All functions preserve deterministic sorting and existing functionality
- Added to `/home/aroto/AroMCP/src/aromcp/utils/pagination.py` as `simplify_pagination()` function

### 2. Description Template for Better Agent Usage
**Template:**
```
"""[Core purpose in one line]

Use this tool when:
- [Specific trigger scenario 1]
- [Specific trigger scenario 2]
- [Specific trigger scenario 3]

Token efficiency: [If applicable, mention token savings]

Args:
    [args with clear descriptions]

Example:
    [Concrete example with expected output]

Note: [Any important caveats or related tools]
"""
```

### 3. Output Field Reduction Pattern
**Principle:** Only include fields that affect agent decision-making
- Remove: absolute paths, modification times, file sizes (unless specifically requested)
- Keep: relative paths, content, error messages, line numbers

---

## 1. Keep As Is
These functions work well and need no changes.

### find_import_cycles
**Status:** ✅ WORKING
- Successfully analyzes 444 files for circular dependencies
- Provides valuable architecture insights
- No changes needed

### write_files_batch
**Status:** ✅ WORKING
- Used frequently by agents
- Atomic operations with auto directory creation
- No changes needed

### read_files_batch
**Status:** ✅ WORKING
- Essential for batch file operations
- Glob pattern support works well
- Consider only pagination simplification (see Common Tasks)

---

## 2. Minor Updates
These functions work but need small improvements.

### parse_typescript_errors
**Status:** ✅ WORKING (Minor Output Cleanup)

**Work Required:**
1. Apply pagination simplification pattern (see Common Tasks)
2. Consider adding `severity_filter` parameter to reduce noise:
   ```python
   def parse_typescript_errors(
       # ... existing params ...
       severity_filter: list[str] | None = None  # ["error"] to skip warnings
   )
   ```
3. Test that error grouping by file is working efficiently

**Time Estimate:** 1 hour

### get_target_files
**Status:** ✅ WORKING (Output Reduction)

**Work Required:**
1. Remove redundant fields:
   ```python
   # Current output
   {
       "path": "src/app/api/auth/[...nextauth]/route.ts",
       "absolute_path": "/home/aroto/...",  # REMOVE
       "size": 541,  # REMOVE unless requested
       "modified": 1752186723.2894452,  # REMOVE unless requested
       "pattern": "src/app/api/**/*"
   }

   # New compact output
   {
       "path": "src/app/api/auth/[...nextauth]/route.ts",
       "matched_pattern": "src/app/api/**/*"
   }
   ```

2. Add `details` parameter:
   ```python
   def get_target_files(
       # ... existing params ...
       details: bool = False  # Set True to include size, modified, etc.
   )
   ```

3. Apply pagination simplification

**Time Estimate:** 1.5 hours

### apply_file_diffs
**Status:** ✅ WORKING (Description Update)

**Work Required:**
1. Update description with token efficiency focus:
   ```python
   """Apply small edits efficiently using unified diff format (10-50x fewer tokens).

   Use this tool when:
   - Editing less than 20 lines in a file (saves 95%+ tokens)
   - Updating specific functions or methods
   - Fixing bugs or typos in existing code
   - Making any change affecting <30% of file content

   Token efficiency: 5-line edit = ~50 tokens vs 2000+ for full file rewrite

   Args:
       diffs: List of diffs with 'file_path' and 'diff_content' (unified diff format)
       project_root: Root directory (defaults to MCP_FILE_ROOT)
       create_backup: Create .bak files before applying (default: True)
       validate_before_apply: Validate all diffs first (default: True)

   Example:
       apply_file_diffs([{
           "file_path": "src/utils.js",
           "diff_content": "@@ -10,3 +10,3 @@\n-const oldValue = 5;\n+const newValue = 10;"
       }])

   Note: For new files or >50% rewrites, use write_files_batch instead.
   """
   ```

2. Add token usage to response:
   ```python
   return {
       "applied": [...],
       "tokens_saved": estimated_tokens_saved  # Add this
   }
   ```

**Time Estimate:** 1 hour

---

## 3. Major Updates
These functions need significant changes to be useful.

### extract_method_signatures → extract_exports
**Status:** ⚠️ PARTIALLY WORKING (Major Refactor)

**Work Required:**
1. **Rename function** to `extract_exports`

2. **Expand parsing** to include all exports:
   ```python
   # Current: Only functions
   # New: Parse these patterns
   - export function/const/let/var
   - export class/interface/type/enum
   - export default
   - export { ... } from
   - module.exports (CommonJS)
   ```

3. **Simplify output structure**:
   ```python
   # Current (verbose)
   {
       "name": "ListIdeasPipelineContext",
       "type": "type_alias",
       "line": 13,
       "signature": "type ListIdeasPipelineContext = {",
       "definition": "{",  # Often redundant
       "file_path": "...",
       "file_type": "ts"
   }

   # New (concise)
   {
       "name": "ListIdeasPipelineContext",
       "kind": "type",  # function|class|interface|type|const|enum
       "line": 13,
       "exported": true,
       "signature": "type ListIdeasPipelineContext = { ... }"  # Full one-liner
   }
   ```

4. **Update description**:
   ```python
   """Extract all exported symbols from files for API discovery and refactoring.

   Use this tool when:
   - Understanding what a module/file exports
   - Planning API changes or refactoring
   - Generating documentation
   - Finding unused exports

   Extracts: functions, classes, interfaces, types, constants, enums
   """
   ```

**Time Estimate:** 4 hours

### find_imports_for_files → find_file_dependents
**Status:** ✅ WORKING (Major Output Cleanup + Description)

**Work Required:**
1. **Rename function** to `find_file_dependents`

2. **Simplify output dramatically**:
   ```python
   # Remove these fields:
   - module_names array (8 variations is excessive)
   - imports_by_file (duplicates items)
   - import_types array

   # New simple output:
   {
       "target_file": "src/app/api/ideas/pipelines/listIdeasPipeline.ts",
       "dependents": [
           {
               "file": "src/app/api/ideas/route.ts",
               "imports": ["listIdeasPipelineConfig"],
               "line": 2
           }
       ],
       "total_dependents": 1
   }
   ```

3. **Update description**:
   ```python
   """Find all files that import/depend on the specified files.

   Use this tool when:
   - Planning to move or rename files (see impact)
   - Refactoring exports (find all consumers)
   - Deleting code (ensure it's safe)
   - Understanding dependency chains

   This is reverse dependency analysis - finds who imports FROM these files.
   """
   ```

4. **Add impact analysis**:
   ```python
   # Add to output
   "impact_summary": {
       "safe_to_modify": true,  # If few dependents
       "risk_level": "low|medium|high",
       "suggestion": "Safe to refactor" | "Update 3 files" | "High impact - 50+ files"
   }
   ```

**Time Estimate:** 3 hours

### extract_api_endpoints
**Status:** ⚠️ PARTIALLY WORKING (Pattern Fix)

**Work Required:**
1. **Add framework detection**:
   ```python
   def detect_framework(project_root):
       # Check for Next.js App Router
       if exists("app") and exists("next.config.js"):
           return "nextjs-app"
       # Check for Next.js Pages Router
       if exists("pages/api"):
           return "nextjs-pages"
       # Check for Express
       if "express" in package_json.dependencies:
           return "express"
       # etc...
   ```

2. **Fix patterns for modern frameworks**:
   ```python
   FRAMEWORK_PATTERNS = {
       "nextjs-app": {
           "routes": ["app/**/route.{js,ts}", "app/**/route.{js,ts}x"],
           "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
           "extractor": extract_nextjs_app_routes
       },
       "express": {
           "routes": ["**/*routes*.{js,ts}", "**/*router*.{js,ts}"],
           "methods": ["get", "post", "put", "delete", "patch"],
           "extractor": extract_express_routes
       }
   }
   ```

3. **Add pattern override parameter**:
   ```python
   def extract_api_endpoints(
       # ... existing params ...
       framework: str = "auto",  # "nextjs-app", "express", etc.
       custom_patterns: list[str] | None = None  # Override patterns
   )
   ```

4. **Update description with examples**:
   ```python
   """Extract HTTP endpoints from Next.js, Express, FastAPI route files.

   Use this tool when:
   - Generating API documentation
   - Auditing API surface for security
   - Finding all endpoints in a project
   - Checking REST convention compliance

   Supports:
   - Next.js App Router (route.ts files)
   - Next.js Pages Router (/pages/api)
   - Express routers
   - FastAPI routes

   Example patterns for custom frameworks:
   - Hono: "src/routes/**/*.ts"
   - Custom: "api/**/*Controller.js"
   """
   ```

**Time Estimate:** 3 hours

---

## 4. Bug Fixes
These functions are broken and need fixes to work properly.

### Implementation Order:

#### 1. parse_lint_results (Quick Fix - 1 hour)
**Status:** ⚠️ PARTIALLY WORKING

**Root Cause:** Custom ESLint rule crashes on undefined value

**Fix Required:**
```javascript
// File: .aromcp/eslint/rules/data-fetching-patterns-require-cache-wrapper.js
// Line 18 - Add null check:

// Current (crashes):
if (someNode.startsWith('...')) { }

// Fixed:
if (someNode && typeof someNode === 'string' && someNode.startsWith('...')) { }
```

**Testing:**
1. Run with `use_standards_eslint=false` (should work)
2. Run with `use_standards_eslint=true` (should now work)
3. Verify all custom rules have proper null checks

**Additional Work:**
- Audit all custom ESLint rules for similar issues
- Add try-catch wrapper in rule execution

#### 2. run_test_suite (Medium Fix - 2-3 hours)
**Status:** ❌ FAILED

**Root Cause:** Trying to execute 'jest' directly instead of using npx or npm scripts

**Fixes Required:**
1. **Fix command execution**:
   ```python
   def get_test_command(project_root, test_framework):
       package_json = read_package_json(project_root)

       # First try npm scripts
       if "scripts" in package_json:
           if "test" in package_json["scripts"]:
               return "npm test"

       # Then try npx
       if test_framework == "jest":
           return "npx jest"
       elif test_framework == "vitest":
           return "npx vitest run"

       # Fallback to direct command
       return test_framework
   ```

2. **Implement single-file error reporting**:
   ```python
   def filter_test_results(results, max_failing_files=1):
       """Only return errors from first failing test file to minimize context"""
       failing_files = get_failing_files(results)
       if len(failing_files) > max_failing_files:
           results = filter_to_files(results, failing_files[:max_failing_files])
           results["truncated"] = True
           results["total_failing_files"] = len(failing_files)
       return results
   ```

3. **Add better framework detection**:
   ```python
   def detect_test_framework(project_root):
       package_json = read_package_json(project_root)
       deps = {**package_json.get("dependencies", {}),
               **package_json.get("devDependencies", {})}

       if "jest" in deps:
           return "jest"
       elif "vitest" in deps:
           return "vitest"
       elif "mocha" in deps:
           return "mocha"
       elif "pytest" in find_files("**/*.py"):
           return "pytest"
   ```

#### 3. find_dead_code (Major Fix - 4+ hours)
**Status:** ❌ FAILED

**Potential Issues:** Memory usage, recursive analysis, missing error handling

**Investigation Plan:**
1. **Add comprehensive error handling**:
   ```python
   def find_dead_code_impl(...):
       try:
           # Wrap entire implementation
       except MemoryError:
           return {"error": "Project too large, try with subdirectories"}
       except RecursionError:
           return {"error": "Circular dependencies detected"}
       except Exception as e:
           logger.error(f"Dead code analysis failed: {e}")
           return {"error": f"Analysis failed: {str(e)}"}
   ```

2. **Add resource limits**:
   ```python
   # Limit file analysis
   MAX_FILES_TO_ANALYZE = 10000
   MAX_FILE_SIZE = 1024 * 1024  # 1MB

   # Add progress reporting
   def analyze_with_progress(files):
       for i, file in enumerate(files):
           if i % 100 == 0:
               logger.info(f"Analyzed {i}/{len(files)} files")
   ```

3. **Implement chunked analysis**:
   ```python
   def find_dead_code_chunked(project_root, chunk_size=1000):
       all_files = get_analyzable_files(project_root)
       dead_code_items = []

       for chunk in chunks(all_files, chunk_size):
           result = analyze_chunk(chunk)
           dead_code_items.extend(result)
           gc.collect()  # Force garbage collection between chunks

       return aggregate_results(dead_code_items)
   ```

**Time Estimate:** 4-6 hours (including investigation)

---

## Functions Marked for Removal

### Remove These Unnecessary Wrappers:
1. **run_command** - Agents can run commands directly
2. **get_build_config** - Not useful enough
3. **check_dependencies** - NPM commands are sufficient
4. **run_nextjs_build** - Too specific, never used
5. **load_documents_by_pattern** - Just use search + read
6. **preview_file_changes** - Git does this better
7. **validate_diffs** - Part of unused diff workflow

**Removal Process:**
1. Comment out @mcp.tool decorators first (easy rollback)
2. Add deprecation notice in descriptions
3. After 1 week, remove completely
4. Update any internal dependencies

---

## Summary Statistics
- **Total Functions Tested:** 19
- **Keep As Is:** 3 (16%)
- **Minor Updates:** 3 (16%)
- **Major Updates:** 3 (16%)
- **Bug Fixes:** 3 (16%)
- **Remove:** 7 (36%)

## Implementation Timeline
1. **Day 1-2**: Bug Fixes (prioritize parse_lint_results and run_test_suite)
2. **Day 3**: Minor Updates + Common Tasks
3. **Day 4-5**: Major Updates
4. **Day 6**: Remove deprecated functions + final testing

## Testing Strategy
- Create test harness for each function category
- Test pagination changes across all affected functions
- Verify agent usage improves with description updates
- Monitor token usage before/after output reductions