"""Common TypeScript/JavaScript AST patterns for ESLint rules."""

from typing import Dict, List, Any, Tuple
import re


def detect_ast_pattern_from_examples(examples: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Detect AST patterns from good/bad code examples.
    
    Args:
        examples: Dictionary with 'good' and 'bad' example lists
        
    Returns:
        Dictionary containing detected AST patterns
    """
    patterns = {
        "selectors": [],
        "conditions": [],
        "type": "unknown",
        "description": ""
    }
    
    all_examples = examples.get("good", []) + examples.get("bad", [])
    if not all_examples:
        return patterns
    
    # Analyze code examples to detect patterns
    for example in all_examples:
        code = example.get("code", "")
        language = example.get("language", "")
        
        if not code.strip():
            continue
            
        # Detect common patterns
        detected = _analyze_code_patterns(code, language)
        patterns["selectors"].extend(detected["selectors"])
        patterns["conditions"].extend(detected["conditions"])
    
    # Remove duplicates and determine primary pattern
    patterns["selectors"] = list(set(patterns["selectors"]))
    patterns["conditions"] = list(set(patterns["conditions"]))
    
    # Determine pattern type based on detected elements
    patterns["type"] = _determine_pattern_type(patterns["selectors"])
    patterns["description"] = _generate_pattern_description(patterns)
    
    return patterns


def _analyze_code_patterns(code: str, language: str) -> Dict[str, List[str]]:
    """Analyze code to detect AST patterns.
    
    Args:
        code: Code snippet to analyze
        language: Programming language
        
    Returns:
        Dictionary with detected selectors and conditions
    """
    selectors = []
    conditions = []
    
    # Function patterns
    if re.search(r'\bfunction\s+\w+\s*\(', code):
        selectors.append("FunctionDeclaration")
        if re.search(r'\basync\s+function', code):
            conditions.append("node.async === true")
    
    if re.search(r'\w+\s*:\s*function\s*\(', code):
        selectors.append("Property[method=true]")
    
    if re.search(r'\(\s*\w*\s*\)\s*=>', code):
        selectors.append("ArrowFunctionExpression")
        if re.search(r'\basync\s*\(', code):
            conditions.append("node.async === true")
    
    # Variable patterns
    if re.search(r'\b(const|let|var)\s+\w+', code):
        selectors.append("VariableDeclarator")
        if re.search(r'\bconst\s+', code):
            conditions.append("node.parent.kind === 'const'")
        elif re.search(r'\blet\s+', code):
            conditions.append("node.parent.kind === 'let'")
    
    # Class patterns
    if re.search(r'\bclass\s+\w+', code):
        selectors.append("ClassDeclaration")
        if re.search(r'\bexport\s+class', code):
            conditions.append("node.parent.type === 'ExportNamedDeclaration'")
    
    # Method patterns
    if re.search(r'\w+\s*\([^)]*\)\s*{', code) and 'class' in code:
        selectors.append("MethodDefinition")
        if re.search(r'\basync\s+\w+\s*\(', code):
            conditions.append("node.value.async === true")
    
    # Import/Export patterns
    if re.search(r'\bimport\s+', code):
        selectors.append("ImportDeclaration")
        if re.search(r'\bimport\s*{', code):
            conditions.append("node.specifiers.some(spec => spec.type === 'ImportSpecifier')")
    
    if re.search(r'\bexport\s+', code):
        selectors.append("ExportNamedDeclaration, ExportDefaultDeclaration")
    
    # Call expression patterns
    if re.search(r'\w+\s*\([^)]*\)', code):
        selectors.append("CallExpression")
        
        # Specific API patterns
        if re.search(r'\.then\s*\(', code):
            conditions.append("node.property && node.property.name === 'then'")
        
        if re.search(r'await\s+\w+', code):
            conditions.append("node.parent.type === 'AwaitExpression'")
    
    # Object/Array patterns
    if re.search(r'\{[^}]*\}', code):
        selectors.append("ObjectExpression")
    
    if re.search(r'\[[^\]]*\]', code):
        selectors.append("ArrayExpression")
    
    # Control flow patterns
    if re.search(r'\bif\s*\(', code):
        selectors.append("IfStatement")
        
    if re.search(r'\bfor\s*\(', code):
        selectors.append("ForStatement")
        
    if re.search(r'\btry\s*{', code):
        selectors.append("TryStatement")
        if re.search(r'catch\s*\(', code):
            conditions.append("node.handler !== null")
    
    # TypeScript specific patterns
    if language in ['typescript', 'tsx'] or ':' in code:
        if re.search(r':\s*\w+(\[\]|\<.*?\>)?', code):
            selectors.append("TSTypeAnnotation")
            
        if re.search(r'\binterface\s+\w+', code):
            selectors.append("TSInterfaceDeclaration")
            
        if re.search(r'\benum\s+\w+', code):
            selectors.append("TSEnumDeclaration")
    
    # React/JSX patterns
    if language in ['jsx', 'tsx'] or '<' in code:
        if re.search(r'<\w+', code):
            selectors.append("JSXElement")
            
        if re.search(r'<\w+[^>]*>', code):
            selectors.append("JSXOpeningElement")
    
    return {
        "selectors": selectors,
        "conditions": conditions
    }


def _determine_pattern_type(selectors: List[str]) -> str:
    """Determine the primary pattern type from selectors.
    
    Args:
        selectors: List of AST selectors
        
    Returns:
        Pattern type string
    """
    if not selectors:
        return "unknown"
    
    # Count different types of patterns
    function_patterns = len([s for s in selectors if 'Function' in s or 'Method' in s])
    variable_patterns = len([s for s in selectors if 'Variable' in s])
    class_patterns = len([s for s in selectors if 'Class' in s])
    import_patterns = len([s for s in selectors if 'Import' in s or 'Export' in s])
    call_patterns = len([s for s in selectors if 'Call' in s])
    
    # Determine primary type
    if function_patterns > 0:
        return "function"
    elif class_patterns > 0:
        return "class"
    elif variable_patterns > 0:
        return "variable"
    elif import_patterns > 0:
        return "import"
    elif call_patterns > 0:
        return "call"
    else:
        return "general"


def _generate_pattern_description(patterns: Dict[str, Any]) -> str:
    """Generate a description of the detected pattern.
    
    Args:
        patterns: Pattern dictionary
        
    Returns:
        Human-readable description
    """
    pattern_type = patterns.get("type", "unknown")
    selectors = patterns.get("selectors", [])
    
    if pattern_type == "function":
        return f"Targets function declarations and expressions: {', '.join(selectors[:3])}"
    elif pattern_type == "class":
        return f"Targets class-related constructs: {', '.join(selectors[:3])}"
    elif pattern_type == "variable":
        return f"Targets variable declarations: {', '.join(selectors[:3])}"
    elif pattern_type == "import":
        return f"Targets import/export statements: {', '.join(selectors[:3])}"
    elif pattern_type == "call":
        return f"Targets function calls and expressions: {', '.join(selectors[:3])}"
    else:
        return f"Targets various AST nodes: {', '.join(selectors[:3])}"


def get_common_selectors() -> Dict[str, str]:
    """Get common AST selectors and their descriptions.
    
    Returns:
        Dictionary mapping selectors to descriptions
    """
    return {
        # Function patterns
        "FunctionDeclaration": "Function declarations (function name() {})",
        "FunctionExpression": "Function expressions (const fn = function() {})",
        "ArrowFunctionExpression": "Arrow functions (() => {})",
        "MethodDefinition": "Class methods",
        
        # Variable patterns
        "VariableDeclarator": "Variable declarations",
        "Identifier": "All identifiers (variable names, function names, etc.)",
        
        # Class patterns
        "ClassDeclaration": "Class declarations",
        "ClassExpression": "Class expressions",
        "NewExpression": "Constructor calls (new Something())",
        
        # Object patterns
        "ObjectExpression": "Object literals ({})",
        "Property": "Object properties",
        "ArrayExpression": "Array literals ([])",
        
        # Control flow
        "IfStatement": "If statements",
        "ForStatement": "For loops",
        "WhileStatement": "While loops",
        "TryStatement": "Try-catch blocks",
        "ThrowStatement": "Throw statements",
        
        # Expressions
        "CallExpression": "Function calls",
        "MemberExpression": "Property access (obj.prop)",
        "AssignmentExpression": "Assignments (a = b)",
        "BinaryExpression": "Binary operations (a + b)",
        "UnaryExpression": "Unary operations (!a, -b)",
        
        # Import/Export
        "ImportDeclaration": "Import statements",
        "ExportNamedDeclaration": "Named exports",
        "ExportDefaultDeclaration": "Default exports",
        
        # TypeScript specific
        "TSTypeAnnotation": "Type annotations",
        "TSInterfaceDeclaration": "Interface declarations",
        "TSEnumDeclaration": "Enum declarations",
        "TSTypeAliasDeclaration": "Type aliases",
        
        # JSX specific
        "JSXElement": "JSX elements",
        "JSXOpeningElement": "JSX opening tags",
        "JSXAttribute": "JSX attributes",
        "JSXFragment": "JSX fragments (<>...</>)"
    }


def get_common_conditions() -> Dict[str, str]:
    """Get common AST conditions and their descriptions.
    
    Returns:
        Dictionary mapping conditions to descriptions
    """
    return {
        # Function conditions
        "node.async === true": "Function is async",
        "node.generator === true": "Function is a generator",
        "node.params.length > 0": "Function has parameters",
        
        # Variable conditions  
        "node.parent.kind === 'const'": "Variable declared with const",
        "node.parent.kind === 'let'": "Variable declared with let",
        "node.parent.kind === 'var'": "Variable declared with var",
        "node.init !== null": "Variable has initializer",
        
        # Class conditions
        "node.superClass !== null": "Class extends another class",
        "node.body.body.length > 0": "Class has members",
        
        # Method conditions
        "node.static === true": "Method is static",
        "node.kind === 'constructor'": "Method is constructor",
        "node.kind === 'get'": "Method is getter",
        "node.kind === 'set'": "Method is setter",
        
        # Import conditions
        "node.source.value.startsWith('.')": "Relative import",
        "node.specifiers.length === 0": "Side-effect import",
        "node.specifiers.some(spec => spec.type === 'ImportDefaultSpecifier')": "Has default import",
        
        # Call expression conditions
        "node.callee.type === 'MemberExpression'": "Method call (obj.method())",
        "node.callee.type === 'Identifier'": "Function call (func())",
        "node.arguments.length === 0": "Call has no arguments",
        
        # TypeScript conditions
        "node.typeAnnotation !== undefined": "Has type annotation",
        "node.optional === true": "Optional property/parameter",
        
        # JSX conditions
        "node.selfClosing === true": "Self-closing JSX element",
        "node.attributes.length > 0": "JSX element has attributes"
    }


def generate_selector_combinations(patterns: List[str]) -> List[str]:
    """Generate useful selector combinations.
    
    Args:
        patterns: List of individual selectors
        
    Returns:
        List of combined selectors
    """
    combinations = []
    
    # Add individual patterns
    combinations.extend(patterns)
    
    # Common useful combinations
    function_selectors = [p for p in patterns if 'Function' in p or 'Method' in p]
    if len(function_selectors) > 1:
        combinations.append(", ".join(function_selectors))
    
    # Variable and function combinations
    if "VariableDeclarator" in patterns and any("Function" in p for p in patterns):
        combinations.append("VariableDeclarator[init.type='FunctionExpression'], VariableDeclarator[init.type='ArrowFunctionExpression']")
    
    # Export combinations
    export_patterns = [p for p in patterns if 'Export' in p]
    if export_patterns:
        combinations.append(", ".join(export_patterns))
    
    return combinations


def optimize_selector_for_performance(selector: str) -> str:
    """Optimize selector for better performance.
    
    Args:
        selector: Original selector
        
    Returns:
        Optimized selector
    """
    # Add specific attribute selectors to narrow down matches
    optimizations = {
        "Identifier": "Identifier[name]",  # Only identifiers with names
        "CallExpression": "CallExpression[callee]",  # Only calls with callees
        "MemberExpression": "MemberExpression[object][property]",  # Complete member expressions
        "Property": "Property[key][value]",  # Complete properties
    }
    
    return optimizations.get(selector, selector)