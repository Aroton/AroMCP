# AroMCP Server Test Prompts

Test prompts for each tool in the FileSystem, Standards, and Build servers targeting `/home/aroto/SmallBusinessWebsite`.

## FileSystem Server Tests

### 1. list_files
```
List all JavaScript files in the project

List all files in the src directory

Find all configuration files (*.json, *.config.js) in the project

Show me all test files matching **/*.test.js or **/*.spec.js
```

### 2. read_files
```
Read the package.json file

Show me the contents of README.md and package.json

Read all JavaScript files in the src/components directory

Read the main index.js or index.html file
```

### 3. write_files
```
Create a new file called test-aromcp.txt with the content "Hello from AroMCP!"

Add a new component file src/components/TestComponent.js with a basic React component

Update the test-aromcp.txt file to say "Updated by AroMCP FileSystem Server"

Create a new directory docs/aromcp-test and add a file test.md inside it
```

### 4. extract_method_signatures
```
Extract all function signatures from src/App.js

Show me all the method signatures in the main JavaScript files

Find all React component definitions in the components directory

Extract function signatures from any utility files
```

### 5. find_who_imports
```
Which files import React?

Find all files that import the App component

Show me what imports './utils' or './utils.js'

Which files depend on package.json packages like 'express' or 'react'?
```

## Standards Server Tests

### 1. register_standard
```
Register a React best practices standard for this project

Create a Node.js coding standard with ES6+ requirements

Register a standard for consistent code formatting
```

### 2. add_rule
```
Add an ESLint rule to enforce arrow functions over function declarations

Add a rule requiring semicolons at the end of statements

Add a rule for maximum line length of 100 characters

Add a rule to prevent console.log in production code
```

### 3. add_hint
```
Add a hint about using React hooks properly in functional components

Add a best practice hint for error handling in async functions

Add a hint about keeping components small and focused

Add a performance hint about memoizing expensive calculations
```

### 4. hints_for_file
```
What coding hints apply to src/App.js?

Show me relevant hints for index.js

Get coding suggestions for any React component file

What best practices apply to package.json?
```

### 5. update_rule
```
Update the semicolon rule to make it a warning instead of an error

Change the max line length rule to 120 characters

Update the arrow function rule to allow function declarations for React components
```

### 6. delete_* commands
```
Delete the console.log rule

Remove the hint about memoization

Delete the React best practices standard
```

### 7. check_updates
```
Check if there are any updates to the registered standards

Look for new ESLint rules that might be relevant

Check for updates to React coding standards
```

## Build Server Tests

### 1. lint_project
```
Run ESLint on the entire project

Check for linting errors in the src directory

Run lint checks and show me only errors, not warnings

Lint all JavaScript and JSX files
```

### 2. check_typescript
```
Check for TypeScript errors in the project

Verify TypeScript configuration is valid

Check if there are any type errors in .ts or .tsx files

Run TypeScript compiler checks without emitting files
```

### 3. run_test_suite / run_tests
```
Run all tests in the project

Execute the test suite and show me the results

Run tests matching "App" in their name

Execute npm test and parse the results
```

### 4. quality_check
```
Run a full quality check on the project (lint + tests + TypeScript)

Perform all code quality checks before committing

Do a comprehensive quality assessment of the codebase

Check code quality for the src directory
```

## Progressive Test Sequence

To test all servers systematically:

### Phase 1: Basic FileSystem Operations
1. "List all files in the project"
2. "Read the package.json file"
3. "Create a test file called aromcp-test.txt with 'Hello World'"

### Phase 2: Code Analysis
1. "Find all JavaScript files"
2. "Extract function signatures from the main app file"
3. "Show me what files import React"

### Phase 3: Standards Setup
1. "Register React coding standards for this project"
2. "Add an ESLint rule for consistent arrow functions"
3. "Add a hint about React component best practices"

### Phase 4: Standards Usage
1. "What coding hints apply to App.js?"
2. "Update the arrow function rule to be a warning"
3. "Check for any standards updates"

### Phase 5: Build Checks
1. "Run lint checks on the project"
2. "Execute the test suite"
3. "Perform a full quality check"

### Phase 6: Cleanup
1. "Delete the test file aromcp-test.txt"
2. "Show me the current coding standards"
3. "List recent changes to the project"

## Error Testing

Test error handling with these prompts:

```
Read a file that doesn't exist: nonexistent.js

List files outside the project root: ../../secret.txt

Write to a protected system file: /etc/passwd

Add an invalid ESLint rule

Run tests when no test command exists

Check TypeScript in a non-TypeScript project
```

## Performance Testing

Test with larger operations:

```
Read all files in the project (tests pagination)

List files with pattern **/* (tests large result sets)

Extract signatures from all JavaScript files

Run quality checks on the entire codebase
```