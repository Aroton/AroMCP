"""Parse a coding standard to extract enforceable rules.

DEPRECATED: This tool is deprecated in favor of the V2 workflow.
Use extract_templates_from_standards for better structure extraction.
"""

import re
from typing import Any, List, Dict
from pathlib import Path

from .._security import get_project_root


def parse_standard_to_rules_impl(
    standard_content: str,
    standard_id: str,
    extract_examples: bool = True
) -> dict[str, Any]:
    """Parse a coding standard to extract enforceable rules.
    
    DEPRECATED: This tool is deprecated in favor of the V2 workflow.
    Use extract_templates_from_standards for better AI-driven rule generation.
    
    Args:
        standard_content: Markdown content of the coding standard
        standard_id: Unique identifier for the standard
        extract_examples: Whether to extract good/bad code examples
        
    Returns:
        Dict with extracted rules and examples, plus deprecation warning
    """
    
    # Return deprecation warning
    return {
        "error": {
            "code": "DEPRECATED",
            "message": "parse_standard_to_rules is deprecated in favor of V2 workflow",
            "replacement": "extract_templates_from_standards",
            "details": {
                "reason": "Template extraction provides better structure for AI-driven rule generation",
                "migration_guide": "Use extract_templates_from_standards to extract structured data, then use AI to generate ESLint rules",
                "v2_workflow": [
                    "1. Run extract_templates_from_standards() to extract structured data",
                    "2. Run analyze_standards_for_rules() to get generation recipe", 
                    "3. Use AI (Claude Code) to generate rules from templates and context",
                    "4. Use write_generated_rule() and update_rule_manifest() to save results"
                ]
            }
        }
    }
    try:
        # Parse markdown structure
        lines = standard_content.split('\n')
        rules = []
        current_rule = None
        in_code_block = False
        code_block_lang = None
        code_block_content = []
        good_examples = []
        bad_examples = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Handle code blocks
            if line.startswith('```'):
                if not in_code_block:
                    # Starting code block
                    in_code_block = True
                    code_block_lang = line[3:].strip() or 'text'
                    code_block_content = []
                else:
                    # Ending code block
                    in_code_block = False
                    if extract_examples and current_rule and code_block_content:
                        # Split code block by good/bad markers
                        examples = _split_code_block_by_markers(code_block_content, code_block_lang)
                        
                        for example in examples:
                            if example['type'] == 'good':
                                good_examples.append(example)
                            else:
                                bad_examples.append(example)
                    
                    code_block_content = []
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            # Detect rule sections (headers)
            if line.startswith('#'):
                # Save previous rule if exists
                if current_rule:
                    current_rule['examples'] = {
                        'good': good_examples.copy(),
                        'bad': bad_examples.copy()
                    }
                    rules.append(current_rule)
                    good_examples.clear()
                    bad_examples.clear()
                
                # Start new rule
                header_level = len(line.split()[0])  # Count # characters
                if header_level >= 2:  # Only consider h2 and below as rules
                    rule_name = line.lstrip('#').strip()
                    rule_id = _generate_rule_id(standard_id, rule_name)
                    
                    current_rule = {
                        'id': rule_id,
                        'name': rule_name,
                        'description': '',
                        'type': _determine_rule_type(rule_name),
                        'severity': 'error',  # Default severity
                        'fixable': False,  # Will be determined from examples
                        'ast_pattern': {},  # Will be populated later
                        'examples': {'good': [], 'bad': []}
                    }
            
            # Collect description text for current rule
            elif current_rule and line and not line.startswith('```'):
                if current_rule['description']:
                    current_rule['description'] += ' ' + line
                else:
                    current_rule['description'] = line
        
        # Don't forget the last rule
        if current_rule:
            current_rule['examples'] = {
                'good': good_examples.copy(),
                'bad': bad_examples.copy()
            }
            rules.append(current_rule)
        
        # Analyze rules for additional metadata
        for rule in rules:
            rule['fixable'] = _determine_if_fixable(rule)
            rule['ast_pattern'] = _extract_ast_pattern(rule)
        
        return {
            "data": {
                "standard_id": standard_id,
                "rules": rules,
                "total_rules": len(rules),
                "rules_with_examples": len([r for r in rules if r['examples']['good'] or r['examples']['bad']]),
                "fixable_rules": len([r for r in rules if r['fixable']]),
                "summary": {
                    "rule_types": _count_rule_types(rules),
                    "languages": _extract_languages(rules),
                    "complexity": _assess_complexity(rules)
                }
            }
        }
        
    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to parse standard to rules: {str(e)}"
            }
        }


def _split_code_block_by_markers(code_lines: List[str], language: str) -> List[Dict[str, Any]]:
    """Split a code block by good/bad markers within the code.
    
    Args:
        code_lines: Lines of code within the block
        language: Programming language of the code block
        
    Returns:
        List of example dictionaries split by markers
    """
    examples = []
    current_example = None
    current_type = None
    
    for line in code_lines:
        line_lower = line.lower().strip()
        
        # Check for good/bad markers in comments
        if any(marker in line_lower for marker in ['✅', 'good', 'correct', 'right', 'should']):
            # Start good example
            if current_example is not None and any(line.strip() for line in current_example):
                # Save previous example (only if not empty)
                examples.append({
                    'language': language,
                    'code': '\n'.join(current_example),
                    'type': current_type or 'good'
                })
            current_example = []
            current_type = 'good'
            # Don't add the marker line itself to the example
        elif any(marker in line_lower for marker in ['❌', 'bad', 'wrong', 'incorrect', 'avoid', "don't"]):
            # Start bad example
            if current_example is not None and any(line.strip() for line in current_example):
                # Save previous example (only if not empty)
                examples.append({
                    'language': language,
                    'code': '\n'.join(current_example),
                    'type': current_type or 'good'
                })
            current_example = []
            current_type = 'bad'
            # Don't add the marker line itself to the example
        else:
            # Add line to current example (but not marker lines)
            if current_example is None:
                current_example = []
                current_type = 'good'  # Default to good
            current_example.append(line)
    
    # Don't forget the last example
    if current_example and any(line.strip() for line in current_example):  # Only if not empty
        examples.append({
            'language': language,
            'code': '\n'.join(current_example),
            'type': current_type or 'good'
        })
    
    # If no examples were created but we have content, treat it as one good example
    if not examples and code_lines:
        examples.append({
            'language': language,
            'code': '\n'.join(code_lines),
            'type': 'good'
        })
    
    return examples


def _determine_example_type(lines: List[str], code_block_start: int) -> bool:
    """Determine if a code block is a good or bad example.
    
    Args:
        lines: All lines in the document
        code_block_start: Index where the code block starts
        
    Returns:
        True if good example, False if bad example
    """
    # Look for indicators in preceding lines
    search_range = max(0, code_block_start - 5)
    preceding_text = ' '.join(lines[search_range:code_block_start]).lower()
    
    # Good indicators
    good_indicators = ['✅', 'good', 'correct', 'right', 'proper', 'should', 'do this', 'recommended']
    bad_indicators = ['❌', 'bad', 'wrong', 'incorrect', 'avoid', "don't", 'not recommended', 'never']
    
    good_score = sum(1 for indicator in good_indicators if indicator in preceding_text)
    bad_score = sum(1 for indicator in bad_indicators if indicator in preceding_text)
    
    # Default to good if unclear
    return good_score >= bad_score


def _generate_rule_id(standard_id: str, rule_name: str) -> str:
    """Generate a unique rule ID from standard ID and rule name.
    
    Args:
        standard_id: ID of the standard
        rule_name: Name of the rule
        
    Returns:
        Generated rule ID
    """
    # Convert to lowercase and replace spaces/special chars with hyphens
    clean_name = re.sub(r'[^a-zA-Z0-9\s\-_]', '', rule_name)  # Keep hyphens and underscores
    clean_name = re.sub(r'[\s\-_]+', '-', clean_name.strip()).lower()
    return f"{standard_id}-{clean_name}"


def _determine_rule_type(rule_name: str) -> str:
    """Determine the type of rule based on its name.
    
    Args:
        rule_name: Name of the rule
        
    Returns:
        Rule type string
    """
    name_lower = rule_name.lower()
    
    if any(word in name_lower for word in ['naming', 'name', 'convention']):
        return 'naming'
    elif any(word in name_lower for word in ['structure', 'format', 'organization']):
        return 'structure'
    elif any(word in name_lower for word in ['pattern', 'style', 'syntax']):
        return 'pattern'
    elif any(word in name_lower for word in ['security', 'safe', 'vulnerability']):
        return 'security'
    elif any(word in name_lower for word in ['performance', 'optimization', 'efficiency']):
        return 'performance'
    else:
        return 'general'


def _determine_if_fixable(rule: Dict[str, Any]) -> bool:
    """Determine if a rule can be auto-fixed based on its content.
    
    Args:
        rule: Rule dictionary
        
    Returns:
        True if rule appears to be fixable
    """
    # Simple heuristics for fixability
    name_lower = rule['name'].lower()
    description_lower = rule['description'].lower()
    
    # Rules that are typically fixable
    fixable_indicators = [
        'spacing', 'indent', 'quote', 'semicolon', 'comma',
        'format', 'style', 'trailing', 'whitespace'
    ]
    
    # Rules that are typically not fixable
    not_fixable_indicators = [
        'logic', 'algorithm', 'design', 'architecture',
        'security', 'performance', 'complexity'
    ]
    
    text = f"{name_lower} {description_lower}"
    
    has_fixable = any(indicator in text for indicator in fixable_indicators)
    has_not_fixable = any(indicator in text for indicator in not_fixable_indicators)
    
    # If has good/bad examples with simple transformations, likely fixable
    examples = rule.get('examples', {})
    if examples.get('good') and examples.get('bad'):
        # If examples are similar in structure, likely fixable
        return True
    
    return has_fixable and not has_not_fixable


def _extract_ast_pattern(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Extract AST patterns from rule examples.
    
    Args:
        rule: Rule dictionary with examples
        
    Returns:
        AST pattern dictionary
    """
    # This is a placeholder for AST pattern extraction
    # In a full implementation, this would analyze the code examples
    # and generate AST matching patterns
    
    pattern = {
        'type': 'placeholder',
        'description': f"AST pattern for {rule['name']}",
        'selector': '',  # Would contain ESLint selector
        'conditions': [],  # Would contain matching conditions
    }
    
    examples = rule.get('examples', {})
    if examples.get('good') or examples.get('bad'):
        pattern['has_examples'] = True
        pattern['languages'] = list(set(
            ex['language'] for ex in examples.get('good', []) + examples.get('bad', [])
        ))
    else:
        pattern['has_examples'] = False
        pattern['languages'] = []
    
    return pattern


def _count_rule_types(rules: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count rules by type.
    
    Args:
        rules: List of rule dictionaries
        
    Returns:
        Dictionary with counts by rule type
    """
    types = {}
    for rule in rules:
        rule_type = rule.get('type', 'general')
        types[rule_type] = types.get(rule_type, 0) + 1
    return types


def _extract_languages(rules: List[Dict[str, Any]]) -> List[str]:
    """Extract programming languages from rule examples.
    
    Args:
        rules: List of rule dictionaries
        
    Returns:
        List of unique programming languages
    """
    languages = set()
    for rule in rules:
        examples = rule.get('examples', {})
        for example_list in [examples.get('good', []), examples.get('bad', [])]:
            for example in example_list:
                if example.get('language'):
                    languages.add(example['language'])
    return sorted(list(languages))


def _assess_complexity(rules: List[Dict[str, Any]]) -> str:
    """Assess the overall complexity of the rule set.
    
    Args:
        rules: List of rule dictionaries
        
    Returns:
        Complexity level string
    """
    if len(rules) == 0:
        return 'none'
    elif len(rules) <= 2:
        return 'low'
    elif len(rules) <= 6:
        return 'medium'
    else:
        return 'high'