"""Example generation utilities for standards server v2."""

from typing import Any

from ..models.enhanced_rule import EnhancedRule


def generate_minimal_example(rule: EnhancedRule) -> str:
    """Generate minimal example from full example."""
    if not rule.examples.full:
        return f"// Apply {rule.metadata.pattern_type} pattern"

    # Pattern-specific minimal examples
    pattern_generators = {
        "validation": _generate_validation_minimal,
        "error-handling": _generate_error_handling_minimal,
        "routing": _generate_routing_minimal,
        "component": _generate_component_minimal,
        "api": _generate_api_minimal,
        "state": _generate_state_minimal,
        "async": _generate_async_minimal,
        "security": _generate_security_minimal,
        "performance": _generate_performance_minimal,
        "testing": _generate_testing_minimal
    }

    generator = pattern_generators.get(rule.metadata.pattern_type)
    if generator:
        result = generator(rule.examples.full)
        if result:
            return result

    # Fallback: extract meaningful pattern
    return _extract_core_pattern(rule.examples.full)


def generate_standard_example(rule: EnhancedRule) -> str:
    """Generate standard example from full example."""
    if not rule.examples.full:
        return f"// {rule.metadata.pattern_type} implementation"

    # Extract core implementation (first 10 lines of meaningful code)
    lines = rule.examples.full.split('\n')
    core_lines = []
    brace_count = 0
    in_function = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments in extraction
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            continue

        # Track function/class boundaries
        if any(keyword in stripped for keyword in ['function', 'const', 'export', 'class', 'interface']):
            in_function = True

        if in_function:
            core_lines.append(line)

            # Count braces to find complete blocks
            brace_count += stripped.count('{') - stripped.count('}')

            # Stop at complete function/block or after reasonable length
            if (brace_count == 0 and len(core_lines) > 3) or len(core_lines) >= 10:
                break

    if core_lines:
        return '\n'.join(core_lines)
    else:
        # Fallback to first 10 lines
        return '\n'.join(lines[:10])


def _generate_validation_minimal(full_example: str) -> str:
    """Generate minimal validation example."""
    if "zod" in full_example.lower():
        return "z.object({ field: z.string() }).parse(data)"
    elif "joi" in full_example.lower():
        return "Joi.object({ field: Joi.string() }).validate(data)"
    elif "yup" in full_example.lower():
        return "yup.object({ field: yup.string() }).validate(data)"
    else:
        return "validate(data, schema)"


def _generate_error_handling_minimal(full_example: str) -> str:
    """Generate minimal error handling example."""
    if "try" in full_example and "catch" in full_example:
        return "try { action() } catch (e) { handleError(e) }"
    elif "throw" in full_example:
        return "throw new Error('message')"
    else:
        return "handleError(error)"


def _generate_routing_minimal(full_example: str) -> str:
    """Generate minimal routing example."""
    if "app/" in full_example:
        return "// app/route/page.tsx"
    elif "pages/" in full_example:
        return "// pages/api/route.ts"
    elif "router" in full_example.lower():
        return "router.get('/path', handler)"
    else:
        return "route('/path', handler)"


def _generate_component_minimal(full_example: str) -> str:
    """Generate minimal component example."""
    if "function" in full_example and "return" in full_example:
        return "function Component() { return <div /> }"
    elif "const" in full_example and "=>" in full_example:
        return "const Component = () => <div />"
    else:
        return "<Component />"


def _generate_api_minimal(full_example: str) -> str:
    """Generate minimal API example."""
    if "GET" in full_example:
        return "export async function GET() { return Response.json(data) }"
    elif "POST" in full_example:
        return "export async function POST(req) { return Response.json(result) }"
    elif "fetch" in full_example:
        return "const res = await fetch('/api/endpoint')"
    else:
        return "api.get('/endpoint')"


def _generate_state_minimal(full_example: str) -> str:
    """Generate minimal state example."""
    if "useState" in full_example:
        return "const [state, setState] = useState(initial)"
    elif "useReducer" in full_example:
        return "const [state, dispatch] = useReducer(reducer, initial)"
    elif "context" in full_example.lower():
        return "const value = useContext(Context)"
    else:
        return "setState(newValue)"


def _generate_async_minimal(full_example: str) -> str:
    """Generate minimal async example."""
    if "async" in full_example and "await" in full_example:
        return "const result = await asyncFunction()"
    elif "Promise" in full_example:
        return "Promise.resolve(value)"
    elif ".then" in full_example:
        return "promise.then(result => {})"
    else:
        return "await operation()"


def _generate_security_minimal(full_example: str) -> str:
    """Generate minimal security example."""
    if "auth" in full_example.lower():
        return "if (!isAuthenticated) throw new Error('Unauthorized')"
    elif "sanitize" in full_example.lower():
        return "sanitize(userInput)"
    elif "csrf" in full_example.lower():
        return "validateCSRFToken(token)"
    else:
        return "validateInput(data)"


def _generate_performance_minimal(full_example: str) -> str:
    """Generate minimal performance example."""
    if "useMemo" in full_example:
        return "const memoized = useMemo(() => expensive(), deps)"
    elif "useCallback" in full_example:
        return "const callback = useCallback(() => {}, deps)"
    elif "lazy" in full_example:
        return "const Component = lazy(() => import('./Component'))"
    else:
        return "// Optimize performance"


def _generate_testing_minimal(full_example: str) -> str:
    """Generate minimal testing example."""
    if "test(" in full_example or "it(" in full_example:
        return "test('description', () => { expect(result).toBe(expected) })"
    elif "describe(" in full_example:
        return "describe('Component', () => { test('works', () => {}) })"
    else:
        return "expect(actual).toBe(expected)"


def _extract_core_pattern(full_example: str) -> str:
    """Extract core pattern from full example as fallback."""
    lines = full_example.split('\n')

    # Find the first meaningful line of code
    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            continue

        # Look for key patterns
        if any(keyword in stripped for keyword in ['const', 'function', 'export', 'import', 'class']):
            return stripped

    # If no meaningful pattern found, return first non-empty line
    for line in lines:
        if line.strip():
            return line.strip()

    return "// Apply pattern"


def generate_context_variant(rule: EnhancedRule, context_type: str) -> str | None:
    """Generate context-specific variant of example."""
    if not rule.examples.full:
        return None

    base_example = rule.examples.standard or rule.examples.full

    if context_type == "app_router":
        return _adapt_for_app_router(base_example)
    elif context_type == "pages_router":
        return _adapt_for_pages_router(base_example)
    elif context_type == "server_component":
        return _adapt_for_server_component(base_example)
    elif context_type == "client_component":
        return _adapt_for_client_component(base_example)
    else:
        return base_example


def _adapt_for_app_router(example: str) -> str:
    """Adapt example for App Router context."""
    if "pages/" in example:
        example = example.replace("pages/", "app/")
    if "getServerSideProps" in example:
        example = example.replace("getServerSideProps", "// Use server components instead")
    return example


def _adapt_for_pages_router(example: str) -> str:
    """Adapt example for Pages Router context."""
    if "app/" in example:
        example = example.replace("app/", "pages/")
    if "export default function Page" in example:
        example = example.replace("export default function Page", "export default function")
    return example


def _adapt_for_server_component(example: str) -> str:
    """Adapt example for Server Component context."""
    if "'use client'" in example:
        example = example.replace("'use client'\n", "")
    if "useState" in example:
        example = example.replace("useState", "// Use server state instead")
    return example


def _adapt_for_client_component(example: str) -> str:
    """Adapt example for Client Component context."""
    if not example.startswith("'use client'"):
        example = "'use client'\n\n" + example
    return example


def enhance_example_with_imports(example: str, import_map: list[dict[str, Any]]) -> str:
    """Enhance example with necessary imports."""
    if not import_map:
        return example

    # Extract existing imports
    existing_imports = set()
    for line in example.split('\n'):
        if line.strip().startswith('import'):
            existing_imports.add(line.strip())

    # Add missing imports
    new_imports = []
    for imp in import_map:
        import_line = f"import {imp.get('import', '')} from '{imp.get('from', '')}'"
        if import_line not in existing_imports:
            new_imports.append(import_line)

    if new_imports:
        return '\n'.join(new_imports) + '\n\n' + example
    else:
        return example


def truncate_example(example: str, max_lines: int = 15) -> str:
    """Truncate example to maximum number of lines."""
    lines = example.split('\n')
    if len(lines) <= max_lines:
        return example

    # Keep important lines (imports, function declarations, etc.)
    important_lines = []
    other_lines = []

    for line in lines:
        stripped = line.strip()
        if (stripped.startswith('import') or
            any(keyword in stripped for keyword in ['function', 'const', 'export', 'class', 'interface'])):
            important_lines.append(line)
        else:
            other_lines.append(line)

    # Combine important lines with truncated other lines
    available_lines = max_lines - len(important_lines)
    if available_lines > 0:
        result_lines = important_lines + other_lines[:available_lines]
    else:
        result_lines = important_lines[:max_lines]

    if len(lines) > len(result_lines):
        result_lines.append("  // ... more code")

    return '\n'.join(result_lines)
