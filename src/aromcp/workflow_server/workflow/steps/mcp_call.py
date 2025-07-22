"""MCP call step processor for workflow execution."""

from typing import Any


class MCPCallProcessor:
    """Processes MCP tool call steps."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Format an MCP call for agent execution.

        Args:
            step_definition: Step definition with tool and parameters
            workflow_id: ID of the workflow instance
            state_manager: State manager (not used for formatting)

        Returns:
            Formatted MCP call for agent execution
        """
        tool = step_definition.get("tool")
        if not tool:
            return {"status": "failed", "error": "Missing 'tool' in mcp_call step"}

        parameters = step_definition.get("parameters", {})
        state_update = step_definition.get("state_update")
        store_result = step_definition.get("store_result")

        # Format for agent execution
        mcp_call = {"type": "mcp_call", "tool": tool, "parameters": parameters}

        # Add state update instructions if specified
        if state_update:
            mcp_call["state_update"] = state_update
        
        # Add store_result instructions if specified
        if store_result:
            mcp_call["store_result"] = store_result

        return {"status": "success", "agent_action": mcp_call, "execution_type": "agent"}


class InternalMCPCallProcessor:
    """Processes MCP calls that should be executed internally by the workflow system."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager, mcp_registry=None) -> dict[str, Any]:
        """Execute an MCP call internally.

        Args:
            step_definition: Step definition with tool and parameters
            workflow_id: ID of the workflow instance
            state_manager: State manager for updates
            mcp_registry: Registry of available MCP tools (optional)

        Returns:
            Execution result from the MCP tool
        """
        tool = step_definition.get("tool")
        if not tool:
            return {"status": "failed", "error": "Missing 'tool' in internal_mcp_call step"}

        parameters = step_definition.get("parameters", {})
        state_update = step_definition.get("state_update")
        store_result = step_definition.get("store_result")

        try:
            # For now, we'll format this for agent execution since we don't have
            # the MCP registry integrated yet. In Phase 3+, this would call
            # tools directly through the registry.

            # TODO: In future phases, integrate with MCP tool registry:
            # if mcp_registry and tool in mcp_registry:
            #     result = mcp_registry.call_tool(tool, parameters)
            #     if state_update and result.get('status') == 'success':
            #         # Apply state update based on result
            #         pass
            #     return result

            # For Phase 2, treat as agent action
            agent_action = {
                "type": "mcp_call",
                "tool": tool,
                "parameters": parameters,
                "execution_mode": "internal",
            }
            
            if state_update:
                agent_action["state_update"] = state_update
            if store_result:
                agent_action["store_result"] = store_result
                
            return {
                "status": "success",
                "agent_action": agent_action,
                "execution_type": "agent",
            }

        except Exception as e:
            return {"status": "failed", "error": f"Internal MCP call failed: {e}"}
