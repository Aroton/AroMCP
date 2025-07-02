"""Pattern matching utilities for file-to-standard mapping."""

import fnmatch
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple


def normalize_path(path: str, project_root: str) -> str:
    """Normalize a file path relative to project root.
    
    Args:
        path: File path to normalize
        project_root: Project root directory
        
    Returns:
        Normalized path relative to project root with forward slashes
    """
    try:
        project_path = Path(project_root).resolve()
        file_path = Path(path)
        
        # Make absolute if not already
        if not file_path.is_absolute():
            file_path = project_path / file_path
        else:
            file_path = file_path.resolve()
        
        # Get relative path from project root
        rel_path = file_path.relative_to(project_path)
        
        # Convert to forward slashes for consistent pattern matching
        return str(rel_path).replace('\\', '/')
        
    except (ValueError, OSError):
        # Fallback to original path if normalization fails
        return str(path).replace('\\', '/')


def calculate_pattern_specificity(pattern: str) -> float:
    """Calculate specificity score for a glob pattern.
    
    More specific patterns get higher scores:
    - Exact matches: 1.0
    - File extensions: 0.8
    - Directory-specific: 0.6-0.9 (based on depth)
    - Wildcards: 0.1-0.5 (based on specificity)
    
    Args:
        pattern: Glob pattern to score
        
    Returns:
        Specificity score between 0.0 and 1.0
    """
    score = 0.0
    
    # Remove leading ./ if present
    pattern = pattern.lstrip('./')
    
    # Exact match (no wildcards)
    if '*' not in pattern and '?' not in pattern and '[' not in pattern:
        return 1.0
    
    # Count directory levels
    path_parts = pattern.split('/')
    dir_levels = len(path_parts) - 1
    
    # Base score from directory depth
    score += min(dir_levels * 0.1, 0.4)
    
    # File extension specificity
    if pattern.endswith(('*.py', '*.js', '*.ts', '*.tsx', '*.jsx')):
        score += 0.3
    elif pattern.endswith(('*.md', '*.json', '*.yaml', '*.yml')):
        score += 0.2
    elif '.*' in pattern:
        score += 0.1
    
    # Directory name specificity
    specific_dirs = ['src/', 'lib/', 'components/', 'api/', 'routes/', 'utils/', 'services/']
    for specific_dir in specific_dirs:
        if specific_dir in pattern:
            score += 0.2
            break
    
    # Penalty for very broad patterns
    if pattern.startswith('**/*'):
        score -= 0.1
    elif pattern == '*':
        score = 0.05
    elif pattern == '**':
        score = 0.01
    
    # Bonus for specific file names
    filename = Path(pattern).name
    if filename and '*' not in filename and '?' not in filename:
        score += 0.2
    
    return min(max(score, 0.01), 1.0)


def match_pattern(file_path: str, pattern: str, project_root: str) -> Tuple[bool, float]:
    """Check if a file path matches a glob pattern.
    
    Args:
        file_path: File path to check
        pattern: Glob pattern to match against
        project_root: Project root directory for path normalization
        
    Returns:
        Tuple of (matches, specificity_score)
    """
    # Normalize both paths
    norm_file = normalize_path(file_path, project_root)
    norm_pattern = pattern.replace('\\', '/')
    
    # Remove leading ./ from pattern if present
    norm_pattern = norm_pattern.lstrip('./')
    
    # Check for exact match first
    if norm_file == norm_pattern:
        return True, 1.0
    
    # Use multiple pattern matching approaches for robustness
    try:
        matches = False
        
        # Approach 1: Use pathlib.Path.match for most patterns with **
        if '**' in norm_pattern:
            try:
                matches = Path(norm_file).match(norm_pattern)
            except (ValueError, TypeError):
                # Pattern might be too complex for pathlib.match
                pass
        
        # Approach 2: If pathlib fails or for simple patterns, use fnmatch
        if not matches:
            # Handle complex patterns by simplifying them
            simplified_pattern = norm_pattern
            
            # Convert complex patterns with multiple ** to simpler ones
            if norm_pattern.count('**') > 1:
                # Convert "**/dir/**/*.ext" to "**/dir/*.ext" 
                # Remove middle ** patterns but keep first and convert pattern to simpler form
                parts = norm_pattern.split('/')
                new_parts = []
                seen_doublestar = False
                
                for i, part in enumerate(parts):
                    if part == '**':
                        if not seen_doublestar:
                            new_parts.append(part)
                            seen_doublestar = True
                        # Skip subsequent ** patterns
                    else:
                        new_parts.append(part)
                
                simplified_pattern = '/'.join(new_parts)
            
            # Try pathlib with simplified pattern
            if '**' in simplified_pattern:
                try:
                    matches = Path(norm_file).match(simplified_pattern)
                except (ValueError, TypeError):
                    pass
            
            # Fallback to fnmatch for simple patterns
            if not matches and '**' not in simplified_pattern:
                matches = fnmatch.fnmatch(norm_file, simplified_pattern)
        
        if matches:
            specificity = calculate_pattern_specificity(norm_pattern)
            return True, specificity
        
        # Also try matching against just the filename for patterns like "*.py"
        if '/' not in norm_pattern:
            filename = Path(norm_file).name
            if fnmatch.fnmatch(filename, norm_pattern):
                specificity = calculate_pattern_specificity(norm_pattern)
                return True, specificity * 0.8  # Slightly lower score for filename-only match
                
    except Exception:
        # If all pattern matching fails, fall back to basic string matching
        pass
    
    return False, 0.0


def find_matching_standards(
    file_path: str, 
    standards: List[Dict[str, Any]], 
    project_root: str,
    include_general: bool = True
) -> List[Dict[str, Any]]:
    """Find all standards that match a given file path.
    
    Args:
        file_path: File path to find standards for
        standards: List of standard dictionaries with metadata
        project_root: Project root directory
        include_general: Whether to include standards without specific patterns
        
    Returns:
        List of matching standards with match information, sorted by specificity
    """
    matches = []
    
    for standard in standards:
        metadata = standard.get('metadata', {})
        patterns = metadata.get('patterns', [])
        
        # Handle standards without patterns (general standards)
        if not patterns:
            if include_general:
                matches.append({
                    'standard': standard,
                    'match_reason': 'Default/general standard',
                    'specificity': 0.1,
                    'pattern_matched': None
                })
            continue
        
        # Check each pattern in the standard
        best_match = None
        best_specificity = 0.0
        
        for pattern in patterns:
            is_match, specificity = match_pattern(file_path, pattern, project_root)
            if is_match and specificity > best_specificity:
                best_match = pattern
                best_specificity = specificity
        
        # Add the best match for this standard
        if best_match:
            matches.append({
                'standard': standard,
                'match_reason': f"Pattern '{best_match}' matched",
                'specificity': best_specificity,
                'pattern_matched': best_match
            })
    
    # Sort by specificity (highest first)
    matches.sort(key=lambda x: x['specificity'], reverse=True)
    
    return matches


def get_file_categories(file_path: str) -> List[str]:
    """Determine categories for a file based on its path and extension.
    
    Args:
        file_path: File path to categorize
        
    Returns:
        List of category strings
    """
    categories = []
    
    # Normalize path
    norm_path = file_path.replace('\\', '/').lower()
    path_obj = Path(norm_path)
    
    # File extension categories
    ext = path_obj.suffix
    if ext in ['.py']:
        categories.append('python')
    elif ext in ['.js', '.jsx']:
        categories.append('javascript')
        if ext == '.jsx':
            categories.append('react')
    elif ext in ['.ts', '.tsx']:
        categories.append('typescript')
        if ext == '.tsx':
            categories.append('react')
    elif ext in ['.md', '.markdown']:
        categories.append('documentation')
    elif ext in ['.json', '.yaml', '.yml']:
        categories.append('configuration')
    elif ext in ['.css', '.scss', '.sass', '.less']:
        categories.append('styles')
    elif ext in ['.html', '.htm']:
        categories.append('markup')
    
    # Directory-based categories
    path_parts = norm_path.split('/')
    
    for part in path_parts:
        if part in ['src', 'source']:
            categories.append('source')
        elif part in ['test', 'tests', '__tests__', 'spec']:
            categories.append('tests')
        elif part in ['component', 'components']:
            categories.append('components')
        elif part in ['api', 'apis']:
            categories.append('api')
        elif part in ['route', 'routes', 'routing']:
            categories.append('routes')
        elif part in ['util', 'utils', 'utilities']:
            categories.append('utilities')
        elif part in ['service', 'services']:
            categories.append('services')
        elif part in ['config', 'configuration', 'configs']:
            categories.append('configuration')
        elif part in ['doc', 'docs', 'documentation']:
            categories.append('documentation')
        elif part in ['style', 'styles', 'css']:
            categories.append('styles')
        elif part in ['asset', 'assets', 'static']:
            categories.append('assets')
    
    # Special file name patterns
    filename = path_obj.name.lower()
    if filename.startswith('test_') or filename.endswith('.test.') or filename.endswith('.spec.'):
        categories.append('tests')
    elif filename in ['index.', 'main.', 'app.']:
        categories.append('entry-point')
    elif filename.startswith('config') or filename.endswith('config'):
        categories.append('configuration')
    elif 'readme' in filename:
        categories.append('documentation')
    
    return list(set(categories))  # Remove duplicates


def create_pattern_report(
    standards: List[Dict[str, Any]], 
    sample_files: List[str] = None,
    project_root: str = '.'
) -> Dict[str, Any]:
    """Create a report showing pattern coverage and potential issues.
    
    Args:
        standards: List of standards with patterns
        sample_files: Optional list of sample files to test patterns against
        project_root: Project root directory
        
    Returns:
        Report dictionary with pattern analysis
    """
    report = {
        'total_standards': len(standards),
        'standards_with_patterns': 0,
        'total_patterns': 0,
        'pattern_specificity': {},
        'overlapping_patterns': [],
        'unused_patterns': [],
        'coverage_analysis': {}
    }
    
    all_patterns = []
    pattern_to_standard = {}
    
    # Collect all patterns
    for standard in standards:
        metadata = standard.get('metadata', {})
        patterns = metadata.get('patterns', [])
        
        if patterns:
            report['standards_with_patterns'] += 1
            report['total_patterns'] += len(patterns)
            
            for pattern in patterns:
                all_patterns.append(pattern)
                pattern_to_standard[pattern] = standard.get('metadata', {}).get('id', 'unknown')
                
                # Calculate specificity
                specificity = calculate_pattern_specificity(pattern)
                report['pattern_specificity'][pattern] = specificity
    
    # Find overlapping patterns (patterns that could match the same files)
    for i, pattern1 in enumerate(all_patterns):
        for pattern2 in all_patterns[i+1:]:
            # Simple overlap detection - could be made more sophisticated
            if pattern1 != pattern2:
                # Check if one pattern is a subset of another
                if (pattern1 in pattern2 or pattern2 in pattern1 or 
                    (pattern1.endswith('*') and pattern2.startswith(pattern1[:-1])) or
                    (pattern2.endswith('*') and pattern1.startswith(pattern2[:-1]))):
                    
                    standard1 = pattern_to_standard.get(pattern1, 'unknown')
                    standard2 = pattern_to_standard.get(pattern2, 'unknown')
                    
                    report['overlapping_patterns'].append({
                        'pattern1': pattern1,
                        'standard1': standard1,
                        'pattern2': pattern2,
                        'standard2': standard2
                    })
    
    # Test patterns against sample files if provided
    if sample_files:
        used_patterns = set()
        file_coverage = {}
        
        for file_path in sample_files:
            matches = find_matching_standards(file_path, standards, project_root, include_general=False)
            file_coverage[file_path] = {
                'match_count': len(matches),
                'patterns': [m['pattern_matched'] for m in matches if m['pattern_matched']]
            }
            
            for match in matches:
                if match['pattern_matched']:
                    used_patterns.add(match['pattern_matched'])
        
        report['unused_patterns'] = [p for p in all_patterns if p not in used_patterns]
        report['coverage_analysis'] = file_coverage
    
    return report