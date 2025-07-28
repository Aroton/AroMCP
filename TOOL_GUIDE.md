# AroMCP Tool Selection Guide

This guide helps AI agents and developers choose the right tools for specific tasks.

## 🎯 Quick Tool Finder

### "I need to..."

#### **...explore a project**
- `list_files` - Find files by pattern
- `read_files` - Read file contents
- `detect_build_tools` - Understand build setup
- `check_dependencies` - See installed packages

#### **...check code quality**
- `lint_project` - Run ESLint/Prettier
- `check_typescript` - Find type errors
- `run_tests` - Execute test suite
- `lint_project` + `check_typescript` + `run_tests` - Individual quality checks

#### **...modify code**
- `read_files` - Always read first!
- `write_files` - Create/update files
- `lint_project` - Verify after changes

#### **...analyze dependencies**
- `find_who_imports` - Who uses this file?
- `find_import_cycles` - Circular dependencies
- `find_dead_code` - Unused code
- `check_dependencies` - Package issues

#### **...run builds/commands**
- `execute_command` - Run npm/yarn/git
- `run_tests` - Test with coverage
- `run_nextjs_build` - Next.js specific

#### **...work with documentation**
- `load_project_documents` - Read .md/.json/.yaml
- `extract_api_endpoints` - Document APIs
- `extract_code_structure` - Map functions/classes

## 📊 Tool Decision Tree

```
What do you want to do?
│
├─ Understand existing code?
│  ├─ Browse files → list_files
│  ├─ Read source → read_files  
│  ├─ Read docs → load_project_documents
│  └─ Analyze structure → extract_code_structure
│
├─ Check code quality?
│  ├─ Style issues → lint_project
│  ├─ Type errors → check_typescript
│  ├─ Test failures → run_tests
│  └─ All checks → lint_project + check_typescript + run_tests
│
├─ Make changes?
│  ├─ New files → write_files
│  └─ Update files → read_files → write_files
│
├─ Analyze project health?
│  ├─ Unused code → find_dead_code
│  ├─ Circular imports → find_import_cycles
│  ├─ Dependencies → check_dependencies
│  └─ Who uses file → find_who_imports
│
└─ Get coding hints?
   ├─ For current file → hints_for_file
   ├─ Register standards → register_standard
   └─ Add ESLint rules → add_rule
```

## 🔄 Common Workflows

### Pre-commit Check
```
1. lint_project()      # Check code style
2. check_typescript()  # Verify types
3. run_tests()        # Ensure tests pass
```

### Safe Refactoring
```
1. find_who_imports("target.js")  # Check dependencies
2. read_files("target.js")        # Understand current code
3. write_files({...})             # Make changes
4. lint_project()                 # Verify quality
```

### Project Exploration
```
1. list_files("**/*.{js,ts}")     # Find source files
2. read_files("README.md")        # Understand project
3. detect_build_tools()           # Check build setup
4. check_dependencies()           # Review packages
```

### Code Cleanup
```
1. find_dead_code()               # Find unused code
2. find_import_cycles()           # Check circular deps
3. check_dependencies()           # Find unused packages
```

## 💡 Pro Tips

### Use Simplified Tools
Prefer these simplified versions:
- ✅ `list_files` instead of `get_target_files`
- ✅ `read_files` instead of `read_files_batch`
- ✅ `lint_project` instead of `parse_lint_results`
- ✅ `check_typescript` instead of `parse_typescript_errors`

### Always Read Before Writing
```javascript
// ❌ BAD - might overwrite important content
write_files({"config.js": "export default {}"})

// ✅ GOOD - preserves existing content
const content = read_files("config.js")
// ...modify content...
write_files({"config.js": modifiedContent})
```

### Check Dependencies Before Deleting
```javascript
// ❌ BAD - might break other files
// delete utils/helper.js

// ✅ GOOD - check first
const importers = find_who_imports("utils/helper.js")
if (importers.data.imported_by.length === 0) {
  // Safe to delete
}
```

### Use the Right Tool for the Job
- **Source code**: `read_files`
- **Documentation**: `load_project_documents` 
- **Style issues**: `lint_project`
- **Type errors**: `check_typescript`
- **Unused code**: `find_dead_code`

## 🤖 For AI Agents

### Tool Discovery
```javascript
// Don't know what tools exist?
tool_categories()

// Need help choosing?
suggest_tools("I want to check for TypeScript errors")
```

### Common Patterns
```javascript
// Pattern: Always validate after changes
async function safeModification(file, newContent) {
  await read_files(file)           // Understand current
  await write_files({[file]: newContent})  // Make change
  await lint_project()             // Verify quality
}

// Pattern: Explore before modifying
async function understandFirst(pattern) {
  const files = await list_files(pattern)
  const contents = await read_files(files.data.items[0].path)
  const structure = await extract_code_structure(files.data.items[0].path)
  // Now you understand the code
}
```

## 📚 Tool Categories

### 1. **Code Exploration**
Understanding existing code structure
- Primary: `list_files`, `read_files`, `find_who_imports`
- Advanced: `extract_code_structure`, `get_target_files`

### 2. **Code Quality**
Checking and improving code quality
- Primary: `lint_project`, `check_typescript`, `run_tests`
- Advanced: `parse_lint_results`, `parse_typescript_errors`

### 3. **Code Modification**
Making changes to files
- Primary: `write_files`
- Advanced: (deprecated diff tools removed)

### 4. **Dependency Analysis**
Understanding project dependencies
- Primary: `find_who_imports`, `find_dead_code`, `check_dependencies`
- Advanced: `find_import_cycles`, `find_imports_for_files`

### 5. **Build & Test**
Running builds and tests
- Primary: `execute_command`, `run_tests`
- Advanced: `run_command`, `run_test_suite`, `run_nextjs_build`

### 6. **Documentation**
Working with docs and APIs
- Primary: `load_project_documents`, `extract_api_endpoints`
- Advanced: `load_documents_by_pattern`

### 7. **Standards Management**
Coding guidelines and hints
- Primary: `hints_for_file`, `register_standard`, `add_rule`
- Advanced: `check_standard_updates`, `analyze_coding_context`

## 🚨 Common Mistakes to Avoid

### ❌ Using the wrong reader
```javascript
// Wrong - read_files for documentation
read_files("README.md")  

// Right - load_project_documents for non-code
load_project_documents("**/*.md")
```

### ❌ Not checking before deleting
```javascript
// Wrong - delete without checking
delete_file("old-utils.js")

// Right - check dependencies first
find_who_imports("old-utils.js")
```

### ❌ Running wrong tool for task
```javascript
// Wrong - find_dead_code for style issues
find_dead_code()  // This finds unused code, not style problems

// Right - lint_project for style issues
lint_project()
```

## 🎉 Remember

1. **Start simple** - Use the primary tools first
2. **Read before write** - Always understand existing code
3. **Check dependencies** - Before moving or deleting
4. **Verify changes** - Run quality checks after modifications
5. **Use guidance** - Call `suggest_tools()` when unsure

Happy coding! 🚀