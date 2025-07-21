"""Enhanced error tracking utilities for workflow system."""

import inspect
import traceback
from typing import Any, Dict


def get_error_location() -> Dict[str, Any]:
    """Get the file and line number where an error occurred."""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        # Go up one level to get the actual error location
        caller_frame = frame.f_back
        return {
            "file": caller_frame.f_code.co_filename.split('/')[-1],  # Just filename, not full path
            "line": caller_frame.f_lineno,
            "function": caller_frame.f_code.co_name
        }
    return {"file": "unknown", "line": 0, "function": "unknown"}


def create_error_response(message: str, code: str = "OPERATION_FAILED", extra_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a standardized error response with location tracking."""
    location = get_error_location()
    
    error_data = {
        "code": code,
        "message": message,
        "location": {
            "file": location["file"],
            "line": location["line"],
            "function": location["function"]
        }
    }
    
    if extra_data:
        error_data.update(extra_data)
    
    return {"error": error_data}


def create_workflow_error(message: str, workflow_id: str = None, step_id: str = None, 
                         code: str = "WORKFLOW_ERROR") -> Dict[str, Any]:
    """Create a workflow-specific error response with context."""
    location = get_error_location()
    
    error_data = {
        "code": code,
        "message": message,
        "location": {
            "file": location["file"],
            "line": location["line"],
            "function": location["function"]
        }
    }
    
    if workflow_id:
        error_data["workflow_id"] = workflow_id
    if step_id:
        error_data["step_id"] = step_id
    
    return {"error": error_data}


def enhance_exception_message(e: Exception, context: str = "") -> str:
    """Enhance an exception message with location and context information."""
    location = get_error_location()
    
    base_message = str(e)
    if context:
        base_message = f"{context}: {base_message}"
    
    return f"{base_message} [at {location['file']}:{location['line']} in {location['function']}()]"


def log_exception_with_location(e: Exception, context: str = "") -> None:
    """Log an exception with full traceback and location information."""
    location = get_error_location()
    
    print(f"ERROR at {location['file']}:{location['line']} in {location['function']}()")
    if context:
        print(f"Context: {context}")
    print(f"Exception: {type(e).__name__}: {e}")
    print("Traceback:")
    traceback.print_exc()