"""Agent prompt step processor for MCP Workflow System.

Handles agent task instructions with context, response schemas, and timeout support.
"""

from typing import Any

from ..models import WorkflowStep


class AgentPromptProcessor:
    """Processes agent prompt workflow steps."""

    def process_agent_prompt(self, step: WorkflowStep, state: dict[str, Any]) -> dict[str, Any]:
        """
        Process an agent_prompt step.

        Args:
            step: The agent prompt step to process
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing agent prompt instructions
        """
        definition = step.definition
        prompt = definition.get("prompt", "")
        context = definition.get("context", {})
        expected_response = definition.get("expected_response")
        timeout = definition.get("timeout", 300)  # 5 minutes default
        max_retries = definition.get("max_retries", 3)

        if not prompt:
            return {"error": f"Agent prompt step {step.id} missing required 'prompt' field"}

        # Build the response instruction
        result = {
            "id": step.id,
            "type": "agent_prompt",
            "definition": {"prompt": prompt, "context": context, "timeout": timeout, "max_retries": max_retries},
        }

        # Add expected response schema if provided
        if expected_response:
            result["definition"]["expected_response"] = expected_response

        return result

    def validate_agent_response(self, step: WorkflowStep, agent_response: dict[str, Any]) -> dict[str, Any]:
        """
        Validate agent response against expected schema.

        Args:
            step: The agent prompt step
            agent_response: Response from the agent

        Returns:
            Validation result with success/error information
        """
        definition = step.definition
        expected_response = definition.get("expected_response")

        if not expected_response:
            # No validation schema, accept any response
            return {"valid": True, "response": agent_response}

        # Basic validation based on expected response schema
        try:
            response_type = expected_response.get("type")
            required_fields = expected_response.get("required", [])

            if response_type == "object":
                if not isinstance(agent_response, dict):
                    return {"valid": False, "error": f"Expected object response, got {type(agent_response).__name__}"}

                # Check required fields
                for field in required_fields:
                    if field not in agent_response:
                        return {"valid": False, "error": f"Required field '{field}' missing from response"}

            elif response_type == "array":
                if not isinstance(agent_response, list):
                    return {"valid": False, "error": f"Expected array response, got {type(agent_response).__name__}"}

            elif response_type == "string":
                if not isinstance(agent_response, str):
                    return {"valid": False, "error": f"Expected string response, got {type(agent_response).__name__}"}

            elif response_type == "number":
                if not isinstance(agent_response, (int, float)):
                    return {"valid": False, "error": f"Expected number response, got {type(agent_response).__name__}"}

            elif response_type == "boolean":
                if not isinstance(agent_response, bool):
                    return {"valid": False, "error": f"Expected boolean response, got {type(agent_response).__name__}"}

            return {"valid": True, "response": agent_response}

        except Exception as e:
            return {"valid": False, "error": f"Response validation error: {str(e)}"}
