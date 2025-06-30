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