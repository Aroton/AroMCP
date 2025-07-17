#!/usr/bin/env python3
"""
Demo script for MCP Workflow System Phase 1: Core State Engine

Demonstrates the three-tier state model, reactive transformations, and basic functionality.
"""

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import StateSchema


def demo_basic_state_management():
    """Demonstrate basic state reading and writing"""
    print("=== Basic State Management ===")
    
    manager = StateManager()
    workflow_id = "demo_basic"
    
    # Set initial state
    manager.update(workflow_id, [
        {"path": "raw.counter", "value": 5},
        {"path": "raw.name", "value": "demo"},
        {"path": "state.version", "value": "1.0"}
    ])
    
    # Read flattened state
    state = manager.read(workflow_id)
    print(f"Initial state: {state}")
    
    # Update with different operations
    manager.update(workflow_id, [
        {"path": "raw.counter", "operation": "increment", "value": 3},
        {"path": "raw.items", "value": ["a", "b"], "operation": "set"},
        {"path": "raw.items", "value": "c", "operation": "append"}
    ])
    
    updated_state = manager.read(workflow_id)
    print(f"After updates: {updated_state}")


def demo_reactive_transformations():
    """Demonstrate reactive transformations with cascading updates"""
    print("\n=== Reactive Transformations ===")
    
    # Define schema with computed fields
    schema = {
        "raw": {"value": "number", "multiplier": "number"},
        "computed": {
            "doubled": {"from": "raw.value", "transform": "input * 2"},
            "scaled": {"from": ["computed.doubled", "raw.multiplier"], "transform": "input[0] * input[1]"},
            "summary": {"from": ["raw.value", "computed.scaled"], "transform": "`Value: ${input[0]}, Scaled: ${input[1]}`"}
        }
    }
    
    manager = StateManager(schema)
    workflow_id = "demo_reactive"
    
    # Set initial values
    manager.update(workflow_id, [
        {"path": "raw.value", "value": 5},
        {"path": "raw.multiplier", "value": 3}
    ])
    
    state = manager.read(workflow_id)
    print(f"Initial computed state: {state}")
    
    # Update raw value - should trigger cascading updates
    print("\nUpdating raw.value from 5 to 8...")
    manager.update(workflow_id, [{"path": "raw.value", "value": 8}])
    
    updated_state = manager.read(workflow_id)
    print(f"After cascade: {updated_state}")


def demo_path_validation():
    """Demonstrate path validation for write operations"""
    print("\n=== Path Validation ===")
    
    manager = StateManager()
    
    # Test valid paths
    valid_paths = ["raw.counter", "state.version", "raw.user.name"]
    for path in valid_paths:
        is_valid = manager.validate_update_path(path)
        print(f"Path '{path}': {'✓ valid' if is_valid else '✗ invalid'}")
    
    # Test invalid paths
    invalid_paths = ["computed.value", "invalid.path", "counter", "raw.", ""]
    for path in invalid_paths:
        is_valid = manager.validate_update_path(path)
        print(f"Path '{path}': {'✓ valid' if is_valid else '✗ invalid'}")


def demo_error_handling():
    """Demonstrate error handling in transformations"""
    print("\n=== Error Handling ===")
    
    schema = {
        "raw": {"json_string": "string"},
        "computed": {
            "parsed_safe": {
                "from": "raw.json_string",
                "transform": "JSON.parse(input)",
                "on_error": "use_fallback",
                "fallback": {"error": "invalid_json"}
            },
            "parsed_ignore": {
                "from": "raw.json_string", 
                "transform": "JSON.parse(input)",
                "on_error": "ignore"
            }
        }
    }
    
    manager = StateManager(schema)
    workflow_id = "demo_errors"
    
    # Set valid JSON first
    manager.update(workflow_id, [{"path": "raw.json_string", "value": '{"valid": true}'}])
    state = manager.read(workflow_id)
    print(f"Valid JSON: {state}")
    
    # Set invalid JSON
    manager.update(workflow_id, [{"path": "raw.json_string", "value": "invalid json"}])
    state = manager.read(workflow_id)
    print(f"Invalid JSON with fallback: {state}")


if __name__ == "__main__":
    try:
        demo_basic_state_management()
        demo_reactive_transformations()
        demo_path_validation()
        demo_error_handling()
        
        print("\n🎉 Phase 1 Demo completed successfully!")
        print("\nKey features demonstrated:")
        print("✓ Three-tier state model (raw, computed, state)")
        print("✓ Flattened view for reading")
        print("✓ Path validation for writing")
        print("✓ Reactive transformations")
        print("✓ Cascading updates")
        print("✓ Error handling strategies")
        print("✓ Atomic operations")
        
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()