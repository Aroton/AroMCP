"""Wait step processor for client-driven workflow synchronization."""

from typing import Any


class WaitStepProcessor:
    """Processes wait steps that pause workflow execution until client continues."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Process a wait step.
        
        Wait steps signal that the workflow should pause and wait for the client
        to call get_next_step before continuing. This is useful for polling loops
        where we want to avoid server-side spinning.
        
        Args:
            step_definition: Step definition (may contain optional message)
            workflow_id: ID of the workflow instance
            state_manager: State manager (not used for wait steps)
            
        Returns:
            Wait step indicator for client
        """
        # Optional message to display to client with graceful handling
        raw_message = step_definition.get("message", "Waiting for next client request...")
        
        # Handle message gracefully - convert non-strings to strings
        if isinstance(raw_message, str):
            message = raw_message
        elif raw_message is None:
            message = "Waiting for next client request..."
        else:
            # Convert non-string types to string representation
            message = str(raw_message)
        
        # Handle empty string case
        if not message.strip():
            message = "Waiting for next client request..."
        
        # Return a wait indicator - this tells the queue executor to pause
        return {
            "status": "wait",
            "wait_for_client": True,
            "message": message,
            "execution_type": "wait"
        }