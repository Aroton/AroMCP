#!/usr/bin/env python3
"""
Workflow Validation Script

Validates MCP workflow YAML files for correctness and completeness.
"""

import sys
import yaml
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aromcp.workflow_server.workflow.validator import WorkflowValidator


def validate_file(file_path: Path) -> bool:
    """Validate a workflow YAML file.
    
    Args:
        file_path: Path to the workflow file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with open(file_path, 'r') as f:
            workflow = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML syntax: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        return False
    
    validator = WorkflowValidator()
    is_valid = validator.validate(workflow)
    
    if validator.errors:
        print("❌ Validation FAILED")
        print("\nErrors:")
        for error in validator.errors:
            print(f"  - {error}")
    else:
        print("✅ Validation PASSED")
        
    if validator.warnings:
        print("\nWarnings:")
        for warning in validator.warnings:
            print(f"  - {warning}")
            
    if not validator.errors and not validator.warnings:
        print("\nWorkflow is valid and follows best practices!")
        
    return is_valid


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validate_workflow.py <workflow.yaml> [workflow2.yaml ...]")
        print("\nValidates MCP workflow YAML files for correctness.")
        sys.exit(1)
        
    all_valid = True
    
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        
        print(f"\nValidating: {path}")
        print("=" * (len(str(path)) + 12))
        
        if not path.exists():
            print(f"❌ File not found: {path}")
            all_valid = False
            continue
            
        is_valid = validate_file(path)
        
        if not is_valid:
            all_valid = False
            
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()