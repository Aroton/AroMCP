# FileSystem Tools Usage

The FileSystem tools are currently implemented and provide comprehensive file operations with security validation and batch processing capabilities.

## Available Tools

### 1. `get_target_files`
List files based on git status or path patterns.

**Parameters:**
- `status` (str): Filter mode - "working", "staged", "branch", "commit", or "pattern"
- `patterns` (list[str], optional): File patterns to match (required when status="pattern")
- `project_root` (str): Root directory of the project (default: ".")

**Examples:**
```python
# Get files matching patterns
result = get_target_files(
    status="pattern",
    patterns=["**/*.py", "*.json"],
    project_root="/path/to/project"
)

# Get git working directory changes (requires git repository)
result = get_target_files(status="working")
```

### 2. `read_files_batch`
Read multiple files in one operation with automatic encoding detection.

**Parameters:**
- `file_paths` (list[str]): List of file paths to read (relative to project_root)
- `project_root` (str): Root directory of the project (default: ".")
- `encoding` (str): File encoding - "auto", "utf-8", "ascii", etc. (default: "auto")

**Examples:**
```python
# Read multiple files with auto-encoding detection
result = read_files_batch(
    file_paths=["src/main.py", "README.md", "config.json"],
    project_root="/path/to/project",
    encoding="auto"
)

# Access file contents
for file_path, file_data in result["data"]["files"].items():
    content = file_data["content"]
    encoding = file_data["encoding"]
    lines = file_data["lines"]
```

### 3. `write_files_batch`
Write multiple files atomically with automatic directory creation and backup support.

**Parameters:**
- `files` (dict[str, str]): Dictionary mapping file paths to content
- `project_root` (str): Root directory of the project (default: ".")
- `encoding` (str): File encoding to use (default: "utf-8")
- `create_backup` (bool): Whether to create backups of existing files (default: True)

**Examples:**
```python
# Write multiple files with automatic backup
result = write_files_batch(
    files={
        "src/new_module.py": "def hello(): return 'world'",
        "tests/test_new.py": "def test_hello(): assert hello() == 'world'",
        "docs/api.md": "# API Documentation\n\nNew module API"
    },
    project_root="/path/to/project",
    create_backup=True
)

# Check results
written_files = result["data"]["written"]
backup_location = result["data"]["backup_location"]
```

### 4. `extract_method_signatures`
Parse code files to extract function/method signatures using AST for Python and regex for JavaScript/TypeScript.

**Parameters:**
- `file_path` (str): Path to the code file
- `project_root` (str): Root directory of the project (default: ".")
- `include_docstrings` (bool): Whether to include function docstrings (default: True)
- `include_decorators` (bool): Whether to include function decorators (default: True)

**Examples:**
```python
# Extract Python function signatures
result = extract_method_signatures(
    file_path="src/api.py",
    project_root="/path/to/project",
    include_docstrings=True,
    include_decorators=True
)

# Access signatures
signatures = result["data"]["signatures"]
for sig in signatures:
    print(f"{sig['type']}: {sig['name']} at line {sig['line']}")
    print(f"Signature: {sig['signature']}")
    if sig.get('docstring'):
        print(f"Doc: {sig['docstring']}")
```

### 5. `find_imports_for_files`
Identify which files import the given files (dependency analysis).

**Parameters:**
- `file_paths` (list[str]): List of files to find importers for
- `project_root` (str): Root directory of the project (default: ".")
- `search_patterns` (list[str], optional): File patterns to search in (defaults to common code files)

**Examples:**
```python
# Find all files that import specific modules
result = find_imports_for_files(
    file_paths=["src/utils.py", "src/config.py"],
    project_root="/path/to/project",
    search_patterns=["**/*.py", "**/*.js"]
)

# Access import information
imports = result["data"]["imports"]
for target_file, import_data in imports.items():
    print(f"\n{target_file} is imported by:")
    for importer in import_data["importers"]:
        print(f"  - {importer['file']} ({', '.join(importer['import_types'])})")
```

### 6. `load_documents_by_pattern`
Load multiple documents matching glob patterns with automatic type classification.

**Parameters:**
- `patterns` (list[str]): List of glob patterns to match files
- `project_root` (str): Root directory of the project (default: ".")
- `max_file_size` (int): Maximum file size to load in bytes (default: 1MB)
- `encoding` (str): File encoding - "auto", "utf-8", etc. (default: "auto")

**Examples:**
```python
# Load all documentation and configuration files
result = load_documents_by_pattern(
    patterns=["**/*.md", "**/*.json", "**/*.yaml", "*.txt"],
    project_root="/path/to/project",
    max_file_size=2 * 1024 * 1024,  # 2MB limit
    encoding="auto"
)

# Access documents
documents = result["data"]["documents"]
for file_path, doc_data in documents.items():
    print(f"{file_path} ({doc_data['type']}): {doc_data['lines']} lines, {doc_data['words']} words")
    content = doc_data["content"]
```

### 7. `apply_file_diffs`
Apply multiple diffs to files with validation and rollback support.

**Parameters:**
- `diffs` (list[dict]): List of diff objects with 'file_path' and 'diff_content' keys
- `project_root` (str): Root directory of the project (default: ".")
- `create_backup` (bool): Whether to create backups before applying diffs (default: True)
- `validate_before_apply` (bool): Whether to validate all diffs before applying any (default: True)

**Unified Diff Format:**
The `diff_content` must be in standard unified diff format with:
- File headers: `--- original_file` and `+++ modified_file`
- Hunk headers: `@@ -old_start,old_count +new_start,new_count @@`
- Context lines: Lines starting with ` ` (space)
- Deletions: Lines starting with `-`
- Additions: Lines starting with `+`

**Examples:**
```python
# Apply a single diff with backup
diff = {
    "file_path": "src/main.py",
    "diff_content": """--- src/main.py
+++ src/main.py
@@ -1,3 +1,4 @@
 def main():
     print("Hello")
+    print("Added line")
     return True
"""
}

result = apply_file_diffs(
    diffs=[diff],
    project_root="/path/to/project",
    create_backup=True,
    validate_before_apply=True
)

# Check results
applied_files = result["data"]["applied_files"]
total_applied = result["data"]["total_applied"]
```

**Creating New Files:**
```python
# Create a new file using unified diff format
new_file_diff = {
    "file_path": "src/new_module.py",
    "diff_content": """--- /dev/null
+++ src/new_module.py
@@ -0,0 +1,5 @@
+def new_function():
+    \"\"\"A new function.\"\"\"
+    print("Hello from new module")
+    return "success"
+
"""
}
```

**Complex Multi-Hunk Diff:**
```python
# Apply multiple changes to the same file
complex_diff = {
    "file_path": "src/config.py", 
    "diff_content": """--- src/config.py
+++ src/config.py
@@ -1,4 +1,5 @@
 import os
+import sys
 
 class Config:
     DEBUG = False
@@ -10,6 +11,7 @@ class Config:
 
 class ProductionConfig(Config):
     DEBUG = False
+    TESTING = False
     DATABASE_URI = os.environ.get('DATABASE_URL')
 
 config = {
"""
}
```

### 8. `preview_file_changes`
Show consolidated preview of all pending changes before applying diffs.

**Parameters:**
- `diffs` (list[dict]): List of diff objects with 'file_path' and 'diff_content' keys
- `project_root` (str): Root directory of the project (default: ".")
- `include_full_preview` (bool): Whether to include full diff preview for each file (default: True)
- `max_preview_lines` (int): Maximum lines to show in preview (default: 50)

**Examples:**
```python
# Preview multiple file changes
diffs = [
    {
        "file_path": "src/api.py",
        "diff_content": "--- src/api.py\n+++ src/api.py\n@@ -10,3 +10,4 @@\n def endpoint():\n     return data\n+    # Added comment"
    },
    {
        "file_path": "tests/test_api.py", 
        "diff_content": "--- tests/test_api.py\n+++ tests/test_api.py\n@@ -5,2 +5,3 @@\n def test_endpoint():\n     assert True\n+    # New test"
    }
]

result = preview_file_changes(
    diffs=diffs,
    project_root="/path/to/project",
    include_full_preview=True,
    max_preview_lines=50
)

# Access preview data
total_files = result["data"]["total_files"]
total_changes = result["data"]["total_changes"]
validation_status = result["data"]["validation"]

for file_info in result["data"]["files"]:
    print(f"{file_info['path']}: +{file_info['additions']} -{file_info['deletions']}")
    if file_info["preview"]:
        print(f"Preview:\n{file_info['preview']}")
```

### 9. `validate_diffs`
Pre-validate diffs for conflicts and applicability before applying them.

**Parameters:**
- `diffs` (list[dict]): List of diff objects with 'file_path' and 'diff_content' keys
- `project_root` (str): Root directory of the project (default: ".")
- `check_conflicts` (bool): Whether to check for conflicts between diffs (default: True)
- `check_syntax` (bool): Whether to validate diff syntax (default: True)

**Examples:**
```python
# Validate diffs before applying
diffs = [
    {
        "file_path": "config.json",
        "diff_content": """--- config.json
+++ config.json
@@ -2,3 +2,4 @@
 {
     "name": "app",
+    "version": "1.0.0",
     "debug": false
"""
    }
]

result = validate_diffs(
    diffs=diffs,
    project_root="/path/to/project",
    check_conflicts=True,
    check_syntax=True
)

# Check validation results
overall_valid = result["data"]["overall_valid"]
valid_count = result["data"]["valid_diffs"]
invalid_count = result["data"]["invalid_diffs"]
conflicts = result["data"]["global_conflicts"]

# Review individual results
for result_info in result["data"]["individual_results"]:
    if not result_info["valid"]:
        print(f"Invalid diff for {result_info['file_path']}: {result_info['errors']}")
    if result_info["warnings"]:
        print(f"Warnings for {result_info['file_path']}: {result_info['warnings']}")
```

## Enhanced Diff Operations Workflow

The three new diff tools work together to provide a comprehensive diff management workflow:

```python
# 1. First, validate diffs to catch issues early
validation_result = validate_diffs(diffs, project_root)
if not validation_result["data"]["overall_valid"]:
    print("Validation failed:", validation_result["data"]["individual_results"])
    return

# 2. Preview changes to understand impact
preview_result = preview_file_changes(diffs, project_root)
print(f"Will modify {preview_result['data']['total_files']} files")
print(f"Total changes: {preview_result['data']['total_changes']}")

# 3. Apply diffs with backup and validation
apply_result = apply_file_diffs(
    diffs, 
    project_root, 
    create_backup=True,
    validate_before_apply=True
)

if "data" in apply_result:
    print(f"Successfully applied {apply_result['data']['total_applied']} diffs")
else:
    print(f"Failed to apply diffs: {apply_result['error']['message']}")
```

## Unified Diff Format Specification

All diff operations use the standard unified diff format (also known as "unified context diff"). This format is the same as produced by `git diff` and `diff -u` commands.

### Format Structure

A unified diff consists of:

1. **File Headers** (required):
   ```
   --- original_file_path
   +++ modified_file_path
   ```

2. **Hunk Headers** (one or more required):
   ```
   @@ -old_start,old_count +new_start,new_count @@
   ```
   - `old_start`: Starting line number in the original file
   - `old_count`: Number of lines from original file (optional, defaults to 1)
   - `new_start`: Starting line number in the modified file  
   - `new_count`: Number of lines in modified file (optional, defaults to 1)

3. **Hunk Content** (the actual changes):
   - **Context lines**: Start with ` ` (space) - unchanged lines for context
   - **Deletions**: Start with `-` - lines removed from original
   - **Additions**: Start with `+` - lines added to modified file

### Complete Examples

**Simple Addition:**
```diff
--- src/utils.py
+++ src/utils.py
@@ -15,6 +15,7 @@ def process_data(data):
     if not data:
         return None
     
+    # Validate input data
     result = []
     for item in data:
         if item.is_valid():
```

**Deletion and Modification:**
```diff
--- config/settings.py
+++ config/settings.py
@@ -8,10 +8,9 @@ class Settings:
     def __init__(self):
         self.debug = False
         self.port = 8000
-        self.host = "0.0.0.0"
-        self.workers = 4
+        self.host = "127.0.0.1"
         self.timeout = 30
         
     def validate(self):
```

**Creating a New File:**
```diff
--- /dev/null
+++ src/models/user.py
@@ -0,0 +1,12 @@
+class User:
+    def __init__(self, name, email):
+        self.name = name
+        self.email = email
+        self.active = True
+    
+    def deactivate(self):
+        self.active = False
+    
+    def __str__(self):
+        return f"User({self.name}, {self.email})"
+
```

**Multiple Hunks in One File:**
```diff
--- src/main.py
+++ src/main.py
@@ -1,5 +1,6 @@
 import sys
 import os
+import logging
 
 from app import create_app
 from config import Config
@@ -20,7 +21,9 @@ def main():
     
     app = create_app(config)
     
+    logging.basicConfig(level=logging.INFO)
     print(f"Starting server on port {config.port}")
+    
     app.run(host=config.host, port=config.port)
 
 if __name__ == "__main__":
```

### Validation Rules

Our diff validation enforces these rules:

1. **File headers are required** - Must have both `---` and `+++` lines
2. **Hunk headers are required** - Must have at least one `@@` line
3. **Proper line prefixes** - Each content line must start with ` `, `-`, or `+`
4. **Valid hunk format** - Hunk headers must match the regex pattern
5. **Context matching** - For existing files, context lines should exist in the source
6. **Path security** - File paths must be within the project root

### Common Errors

**Missing file headers:**
```diff
# ❌ Invalid - missing file headers
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("World")
```

**Invalid hunk header:**
```diff
--- file.py
+++ file.py
# ❌ Invalid hunk header format
@ -1,3 +1,4 @
 def hello():
```

**Incorrect line prefixes:**
```diff
--- file.py
+++ file.py
@@ -1,3 +1,4 @@
def hello():        # ❌ Missing space prefix for context line
    print("Hello")  # ❌ Missing space prefix
+    print("World")  # ✅ Correct addition
```

### Generating Unified Diffs

You can generate compatible diffs using:

**Git:**
```bash
git diff > changes.patch
git diff HEAD~1 HEAD > changes.patch
git diff --no-index old_file.py new_file.py > changes.patch
```

**Standard diff command:**
```bash
diff -u original_file.py modified_file.py > changes.patch
```

**Python (programmatically):**
```python
import difflib

original_lines = original_content.splitlines(keepends=True)
modified_lines = modified_content.splitlines(keepends=True)

diff = difflib.unified_diff(
    original_lines,
    modified_lines, 
    fromfile='original.py',
    tofile='modified.py',
    lineterm=''
)

unified_diff = ''.join(diff)
```

## Quick Reference: Valid Unified Diff Format

✅ **Required Format:**
```diff
--- original_file.py
+++ modified_file.py
@@ -start,count +start,count @@
 context line (starts with space)
-deleted line (starts with minus)
+added line (starts with plus)
 context line (starts with space)
```

❌ **Common Invalid Formats:**
```diff
# Missing file headers
@@ -1,3 +1,4 @@
 some content

# Wrong hunk header (single @)
--- file.py
+++ file.py
@ -1,3 +1,4 @
 some content

# Missing line prefixes
--- file.py
+++ file.py
@@ -1,3 +1,4 @@
some content without space prefix
```

## Security Features

All FileSystem tools include built-in security measures:

- **Path Traversal Protection**: All file paths are validated to prevent access outside the project root
- **Input Validation**: Comprehensive validation of all parameters with structured error responses
- **File Size Limits**: Protection against loading excessively large files
- **Encoding Safety**: Automatic encoding detection with fallback handling

## Error Handling

All tools return structured responses with consistent error handling:

```python
# Success response format
{
    "data": {
        # Tool-specific data
    }
}

# Error response format  
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Detailed error message"
    }
}
```

**Common Error Codes:**
- `INVALID_INPUT`: Parameter validation failed
- `NOT_FOUND`: File or directory not found
- `PERMISSION_DENIED`: Security check failed
- `OPERATION_FAILED`: Operation failed to complete
- `TIMEOUT`: Operation timed out
- `UNSUPPORTED`: Feature not supported