"""Agent response step processor for MCP Workflow System.

Handles processing and validation of agent responses with state updates.
"""

from typing import Any

from ..models import WorkflowStep


class AgentResponseProcessor:
    """Processes agent response workflow steps."""
    
    def process_agent_response(
        self, step: WorkflowStep, agent_response: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process an agent_response step.
        
        Args:
            step: The agent response step to process
            agent_response: Response data from the agent
            state: Current workflow state (flattened view)
            
        Returns:
            Dictionary containing processing result and state updates
        """
        definition = step.definition
        response_schema = definition.get("response_schema")
        state_updates = definition.get("state_updates", [])
        store_response = definition.get("store_response")
        validation_rules = definition.get("validation")
        error_handling = definition.get("error_handling", {"strategy": "fail"})
        
        # Validate the response
        validation_result = self._validate_response(agent_response, response_schema, validation_rules)
        
        if not validation_result["valid"]:
            # Handle validation errors based on error handling strategy
            strategy = error_handling.get("strategy", "fail")
            
            if strategy == "continue":
                # Continue execution despite validation failure
                return {
                    "executed": True,
                    "id": step.id,
                    "type": "agent_response",
                    "validation_error": validation_result["error"],
                    "strategy": "continued_on_error"
                }
            elif strategy == "fallback":
                # Use fallback value
                fallback_value = error_handling.get("fallback_value")
                agent_response = fallback_value
            elif strategy == "retry":
                # Request retry (client should handle this)
                max_retries = error_handling.get("max_retries", 3)
                return {
                    "executed": False,
                    "id": step.id,
                    "type": "agent_response",
                    "validation_error": validation_result["error"],
                    "strategy": "retry_requested",
                    "max_retries": max_retries
                }
            else:  # "fail" or unknown strategy
                return {
                    "error": {
                        "code": "VALIDATION_FAILED",
                        "message": f"Agent response validation failed: {validation_result['error']}"
                    }
                }
        
        # Process state updates from the response
        updates_to_apply = []
        
        # Apply defined state updates
        for update in state_updates:
            path = update.get("path", "")
            value_expr = update.get("value", "")
            operation = update.get("operation", "set")
            
            if not path:
                continue
                
            # Extract value from response using the value expression
            try:
                if isinstance(value_expr, str) and value_expr.startswith("response."):
                    # Extract from agent response
                    field_path = value_expr[9:]  # Remove "response." prefix
                    value = self._get_nested_value(agent_response, field_path)
                elif isinstance(value_expr, str) and value_expr.startswith("state."):
                    # Extract from current state
                    field_path = value_expr[6:]  # Remove "state." prefix  
                    value = self._get_nested_value(state, field_path)
                else:
                    # Use literal value
                    value = value_expr
                
                updates_to_apply.append({
                    "path": path,
                    "value": value,
                    "operation": operation
                })
            except Exception as e:
                # Handle extraction errors based on error handling strategy
                if error_handling.get("strategy") == "continue":
                    continue
                else:
                    return {
                        "error": {
                            "code": "STATE_UPDATE_FAILED",
                            "message": f"Failed to extract value for '{path}': {str(e)}"
                        }
                    }
        
        # Store full response if requested
        if store_response:
            updates_to_apply.append({
                "path": store_response,
                "value": agent_response,
                "operation": "set"
            })
        
        return {
            "executed": True,
            "id": step.id,
            "type": "agent_response", 
            "result": {
                "status": "success",
                "response_validated": validation_result["valid"],
                "updates_applied": len(updates_to_apply)
            },
            "state_updates": updates_to_apply
        }
    
    def _validate_response(
        self, response: dict[str, Any], schema: dict[str, Any] | None, 
        validation_rules: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Validate agent response against schema and additional rules.
        
        Args:
            response: The agent response to validate
            schema: Response schema definition
            validation_rules: Additional validation rules
            
        Returns:
            Validation result with valid flag and optional error message
        """
        if not schema and not validation_rules:
            # No validation rules, accept response
            return {"valid": True}
        
        try:
            # Basic schema validation
            if schema:
                schema_validation = self._validate_against_schema(response, schema)
                if not schema_validation["valid"]:
                    return schema_validation
            
            # Additional validation rules
            if validation_rules:
                rules_validation = self._validate_against_rules(response, validation_rules)
                if not rules_validation["valid"]:
                    return rules_validation
            
            return {"valid": True}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }
    
    def _validate_against_schema(self, response: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        """Validate response against a basic schema."""
        response_type = schema.get("type")
        required_fields = schema.get("required", [])
        
        if response_type == "object":
            if not isinstance(response, dict):
                return {
                    "valid": False,
                    "error": f"Expected object, got {type(response).__name__}"
                }
            
            # Check required fields
            for field in required_fields:
                if field not in response:
                    return {
                        "valid": False,
                        "error": f"Required field '{field}' missing"
                    }
        
        elif response_type == "array":
            if not isinstance(response, list):
                return {
                    "valid": False,
                    "error": f"Expected array, got {type(response).__name__}"
                }
        
        elif response_type and response_type in ["string", "number", "boolean"]:
            expected_types = {
                "string": str,
                "number": (int, float),
                "boolean": bool
            }
            
            if not isinstance(response, expected_types[response_type]):
                return {
                    "valid": False,
                    "error": f"Expected {response_type}, got {type(response).__name__}"
                }
        
        return {"valid": True}
    
    def _validate_against_rules(self, response: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
        """Validate response against custom validation rules."""
        try:
            # Check minimum length rules
            min_length = rules.get("min_length")
            if min_length and isinstance(response, (str, list, dict)):
                if len(response) < min_length:
                    return {
                        "valid": False,
                        "error": f"Response length {len(response)} is less than minimum {min_length}"
                    }
            
            # Check maximum length rules  
            max_length = rules.get("max_length")
            if max_length and isinstance(response, (str, list, dict)):
                if len(response) > max_length:
                    return {
                        "valid": False,
                        "error": f"Response length {len(response)} exceeds maximum {max_length}"
                    }
            
            # Check allowed values
            allowed_values = rules.get("allowed_values")
            if allowed_values and response not in allowed_values:
                return {
                    "valid": False,
                    "error": f"Response value '{response}' not in allowed values: {allowed_values}"
                }
            
            # Check pattern matching for strings
            pattern = rules.get("pattern")
            if pattern and isinstance(response, str):
                import re
                if not re.match(pattern, response):
                    return {
                        "valid": False,
                        "error": f"Response does not match required pattern: {pattern}"
                    }
            
            # Check custom validation function
            custom_validator = rules.get("custom_validator")
            if custom_validator and callable(custom_validator):
                try:
                    if not custom_validator(response):
                        return {
                            "valid": False,
                            "error": "Response failed custom validation"
                        }
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Custom validation error: {str(e)}"
                    }
            
            return {"valid": True}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation rules processing error: {str(e)}"
            }
    
    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """
        Get value from nested dictionary using dot notation path.
        
        Args:
            data: Dictionary to extract from
            path: Dot-separated path (e.g., "user.name")
            
        Returns:
            The value at the specified path
            
        Raises:
            KeyError: If path doesn't exist
        """
        if not path:
            return data
            
        keys = path.split(".")
        value = data
        
        for i, key in enumerate(keys):
            if isinstance(value, dict):
                if key not in value:
                    current_path = ".".join(keys[:i+1])
                    raise KeyError(f"Key '{key}' not found at path '{current_path}'")
                value = value[key]
            elif isinstance(value, list):
                # Handle array access with integer keys
                try:
                    index = int(key)
                    if index < 0 or index >= len(value):
                        current_path = ".".join(keys[:i+1])
                        raise KeyError(f"Array index '{key}' out of bounds at path '{current_path}'")
                    value = value[index]
                except ValueError:
                    current_path = ".".join(keys[:i+1])
                    raise KeyError(f"Invalid array index '{key}' at path '{current_path}'")
            else:
                current_path = ".".join(keys[:i+1])
                raise KeyError(f"Cannot access '{key}' on {type(value).__name__} value at path '{current_path}'")
        
        return value