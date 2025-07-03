# Generate Standards and Templates

**Command**: `generate-standards-and-templates`

**Description**: Generates ESLint rules and AI context from standardized coding standards using the Analysis + Recipe pattern.

## Usage

```bash
# Generate rules from all standards in .aromcp/standards/
claude generate-standards-and-templates

# Generate from specific standards directory
claude generate-standards-and-templates --standards-dir=custom/standards

# Generate to custom output directory
claude generate-standards-and-templates --output-dir=custom/rules
```

## Parameters

- `--standards-dir` (optional): Directory containing markdown standards files (default: `.aromcp/standards`)
- `--output-dir` (optional): Output directory for generated rules (default: `.aromcp/generated-rules`)
- `--project-root` (optional): Project root path (auto-detected if not specified)

## Process Overview

This command follows the "Analysis + Recipe" pattern:

1. **Template Extraction**: Parse standardized markdown files and extract structured data
2. **Standards Analysis**: Analyze project context and create generation recipe
3. **AI Decision Making**: For each standard, decide between ESLint rule or AI context
4. **Rule Generation**: Generate project-specific ESLint rules from templates
5. **Context Creation**: Create AI context documentation for complex patterns
6. **Configuration Generation**: Generate ESLint configuration files (handled within each task)

## Implementation Steps

### Step 1: Discover All Standards Files

```python
# Find all markdown files in standards directory
standards_files = mcp.get_target_files(
    patterns=[".aromcp/standards/**/*.md"]
)
print(f"Found {len(standards_files['data']['items'])} markdown files to process")
```

### Step 2: Process Each Standards File Using Task Tool

```python
# Create comprehensive task prompts - each handles the ENTIRE process for one file
file_paths = [f['path'] for f in standards_files['data']['items']]

# Create task prompts for complete end-to-end processing
complete_processing_tasks = []

for i, file_path in enumerate(file_paths):
    task_prompt = f"""Process the standards file at {file_path} following the complete workflow:

**COMPLETE WORKFLOW FOR {file_path}:**

1. **Extract Templates**: Use extract_templates_from_standards with standards_dir="{file_path}"
2. **Analyze Standards**: Use analyze_standards_for_rules with standards_dir="{file_path}"
3. **Process Each Standard**: For each standard in the analysis results:
   - **Decision Point**: Determine if ESLint rule or AI context based on analysis hints
   - **ESLint Rule Path**:
     * Generate/adapt rule content using AI
     * Use write_generated_rule(rule_content, rule_id) to write rule file
     * Use update_rule_manifest(rule_id, metadata) to update manifest.json and auto-generate ESLint configs
   - **AI Context Path**:
     * Generate context content using AI
     * Use write_ai_context_section(context_content, section_id, section_title) to append to ai-context.md

**PROJECT CONTEXT:**
- Standards directory: .aromcp/standards
- Generated rules directory: .aromcp/generated-rules
- Project root: .

**IMPORTANT:** Follow the exact workflow - extract templates first, analyze standards, then for each standard decide between ESLint rule or AI context generation. Complete ALL steps including file generation and manifest updates."""

    complete_processing_tasks.append({
        'file_path': file_path,
        'task_prompt': task_prompt
    })

# Launch all complete processing tasks in parallel
print(f"Launching {len(complete_processing_tasks)} complete processing tasks...")

# Each task follows the complete workflow
for i, task_info in enumerate(complete_processing_tasks):
    Task(
        description=f"Process standards file {i+1}",
        prompt=task_info['task_prompt']
    )

print(f"✅ Completed processing {len(complete_processing_tasks)} standards files")
print(f"🔧 All rules, context, and manifest updates handled following complete workflow")
```

## Helper Functions

### Categorize Standards for Generation

```python
def categorize_standards_for_generation(standards):
    """Categorize standards based on their suitability for ESLint rule generation."""

    generation_hints = {
        'eslint_capable': [],
        'ai_context_only': [],
        'hybrid': []
    }

    for standard in standards:
        standard_id = standard.get('id')
        if not standard_id:
            continue

        # Check enforcement type from standard metadata
        enforcement_type = standard.get('enforcement_type', [])

        if 'ESLint Rule' in enforcement_type or 'eslint_rule' in enforcement_type:
            if 'Hybrid' in enforcement_type or 'hybrid' in enforcement_type:
                generation_hints['hybrid'].append(standard_id)
            else:
                generation_hints['eslint_capable'].append(standard_id)
        elif 'AI Context' in enforcement_type or 'ai_context' in enforcement_type:
            generation_hints['ai_context_only'].append(standard_id)
        else:
            # Default categorization based on pattern detection capability
            if has_detectable_patterns(standard):
                generation_hints['eslint_capable'].append(standard_id)
            else:
                generation_hints['ai_context_only'].append(standard_id)

    return generation_hints

def has_detectable_patterns(standard):
    """Check if a standard has patterns that can be detected by ESLint."""

    # Check for pattern detection hints in the standard
    pattern_indicators = [
        'import_contains', 'function_name', 'class_name',
        'variable_pattern', 'file_pattern', 'ast_node'
    ]

    standard_content = str(standard).lower()

    # Look for pattern detection indicators
    for indicator in pattern_indicators:
        if indicator in standard_content:
            return True

    # Check applies_to patterns - structural patterns are more ESLint-friendly
    applies_to = standard.get('applies_to', [])
    for pattern in applies_to:
        if any(ext in pattern for ext in ['.js', '.ts', '.jsx', '.tsx']):
            return True

    return False
```

## Helper Functions

### Generate ESLint Rule from Template

```python
def generate_eslint_rule_from_template(standard, template_data, project_context):
    """Generate ESLint rule content from standard and template data."""

    # Base rule structure
    rule_content = f'''/**
 * ESLint rule: {standard['name']}
 * Generated from: {standard['file_path']}
 * Severity: {standard.get('severity', 'error')}
 */

module.exports = {{
    meta: {{
        type: '{get_rule_type(standard)}',
        docs: {{
            description: '{standard.get('description', standard['name'])}',
            category: '{get_rule_category(standard)}',
            recommended: {str(standard.get('severity') == 'error').lower()}
        }},
        fixable: {str(template_data.get('fixable', False) if template_data else False).lower()},
        schema: []
    }},

    create(context) {{
        return {{
            {generate_rule_visitors(standard, template_data, project_context)}
        }};
    }}
}};'''

    return rule_content

def generate_rule_visitors(standard, template_data, project_context):
    """Generate AST visitor methods based on pattern detection."""

    if not template_data or 'detect' not in template_data:
        return generate_basic_visitors(standard)

    visitors = []

    for pattern in template_data['detect']:
        if 'import_contains' in pattern:
            visitors.append(generate_import_visitor(pattern, standard))
        elif 'function_name' in pattern:
            visitors.append(generate_function_visitor(pattern, standard))
        # Add more pattern types as needed

    return ',\\n            '.join(visitors)
```

### Generate AI Context (Using write_ai_context_section Tool)

```python
def generate_ai_context_for_standard(standard, project_context):
    """Generate AI context documentation for complex standards."""

    context = f"""## {standard['name']}

**Category**: {standard.get('category', 'General')}
**Applies to**: {', '.join(standard.get('applies_to', ['All files']))}

### Description
{standard.get('description', 'No description available')}

### Project Context
- **Framework**: {project_context.get('framework', 'Unknown')}
- **Architecture**: {project_context.get('architecture_patterns', [])}
- **Conventions**: {project_context.get('naming_conventions', {})}

### Implementation Guidelines
{generate_implementation_guidelines(standard, project_context)}

### Common Patterns
{generate_common_patterns(standard, project_context)}

### Edge Cases and Considerations
{generate_edge_cases(standard)}
"""

    # Use the actual MCP tool to write the context section
    section_id = standard['id']  # Use the standard's ID as section ID
    write_ai_context_section(
        context_content=context,
        section_id=section_id,
        section_title=standard['name']
    )

    return context
```