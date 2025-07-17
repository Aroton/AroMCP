"""Enhanced workflow execution engine with control flow support.

This executor extends the basic sequential executor with support for conditionals,
loops, user input, and advanced workflow control structures.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from ..state.manager import StateManager
from .context import ExecutionContext, context_manager
from .control_flow import ControlFlowError
from .expressions import ExpressionEvaluator
from .models import StepExecution, WorkflowDefinition, WorkflowExecutionError, WorkflowInstance
from .steps.break_continue import BreakContinueProcessor
from .steps.conditional import ConditionalProcessor
from .steps.foreach import ForEachProcessor
from .steps.user_input import UserInputProcessor
from .steps.while_loop import WhileLoopProcessor


class VariableReplacer:
    """Handles variable interpolation in workflow step definitions."""

    @staticmethod
    def replace(step_definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Replace variables in step definition with state values.

        Args:
            step_definition: Step definition with potential variables
            state: Flattened state to use for replacement

        Returns:
            Step definition with variables replaced
        """
        # Deep copy to avoid modifying original
        import copy

        result = copy.deepcopy(step_definition)

        # Replace variables recursively
        return VariableReplacer._replace_recursive(result, state)

    @staticmethod
    def _replace_recursive(obj: Any, state: dict[str, Any]) -> Any:
        """Recursively replace variables in nested objects."""
        if isinstance(obj, dict):
            return {k: VariableReplacer._replace_recursive(v, state) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [VariableReplacer._replace_recursive(item, state) for item in obj]
        elif isinstance(obj, str):
            return VariableReplacer._replace_string(obj, state)
        else:
            return obj

    @staticmethod
    def _replace_string(text: str, state: dict[str, Any]) -> str:
        """Replace variables in a string using {{ variable }} syntax."""
        # Find all {{ variable }} patterns
        pattern = r"\{\{\s*([^}]+)\s*\}\}"

        def replace_match(match):
            var_name = match.group(1).strip()
            return str(state.get(var_name, f"{{{{ {var_name} }}}}"))  # Keep original if not found

        return re.sub(pattern, replace_match, text)


class WorkflowExecutor:
    """Enhanced workflow executor with control flow support."""

    def __init__(self, state_manager: StateManager | None = None):
        """Initialize the enhanced workflow executor.

        Args:
            state_manager: State manager instance (creates new if None)
        """
        self.state_manager = state_manager or StateManager()
        self.workflows: dict[str, WorkflowInstance] = {}
        self.step_executions: dict[str, list[StepExecution]] = {}
        self.expression_evaluator = ExpressionEvaluator()

        # Initialize step processors
        self.conditional_processor = ConditionalProcessor()
        self.while_loop_processor = WhileLoopProcessor()
        self.foreach_processor = ForEachProcessor()
        self.user_input_processor = UserInputProcessor()
        self.break_continue_processor = BreakContinueProcessor()

    def start(self, workflow_def: WorkflowDefinition, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Initialize and start a workflow instance with control flow support.

        Args:
            workflow_def: Workflow definition to execute
            inputs: Input values for the workflow

        Returns:
            Dictionary with workflow_id and initial state

        Raises:
            WorkflowExecutionError: If workflow initialization fails
        """
        try:
            # Generate unique workflow ID
            workflow_id = f"wf_{uuid.uuid4().hex[:8]}"

            # Create workflow instance
            instance = WorkflowInstance(
                id=workflow_id,
                workflow_name=workflow_def.name,
                definition=workflow_def,
                current_step_index=0,
                status="running",
                created_at=datetime.now(UTC).isoformat(),
            )

            # Initialize state with defaults
            initial_state = workflow_def.default_state.copy()

            # Apply inputs to state
            if inputs:
                if "raw" not in initial_state:
                    initial_state["raw"] = {}
                initial_state["raw"].update(inputs)

            # Initialize state manager with schema
            if not hasattr(self.state_manager, "_schema") or self.state_manager._schema != workflow_def.state_schema:
                self.state_manager._schema = workflow_def.state_schema
                self.state_manager._setup_transformations()

            # Set initial state by applying updates
            if initial_state:
                updates = []
                for tier_name, tier_data in initial_state.items():
                    if tier_name in ["raw", "state"] and isinstance(tier_data, dict):
                        for key, value in tier_data.items():
                            updates.append({"path": f"{tier_name}.{key}", "value": value})

                if updates:
                    self.state_manager.update(workflow_id, updates)

            # Create execution context
            context = context_manager.create_context(workflow_id)

            # Create initial workflow frame
            workflow_frame = context.create_workflow_frame(workflow_def.steps)
            context.push_frame(workflow_frame)

            # Store workflow instance
            self.workflows[workflow_id] = instance
            self.step_executions[workflow_id] = []

            # Get current flattened state
            try:
                current_state = self.state_manager.read(workflow_id)
            except Exception:
                current_state = {}

            return {
                "workflow_id": workflow_id,
                "state": current_state,
                "status": "running",
                "total_steps": len(workflow_def.steps),
                "execution_context": context.get_execution_summary(),
            }

        except Exception as e:
            raise WorkflowExecutionError(f"Failed to start workflow: {e}") from e

    def get_next_step(self, workflow_id: str, _recursion_depth: int = 0) -> dict[str, Any] | None:
        """Get the next step to execute for a workflow with control flow support.

        Args:
            workflow_id: ID of the workflow instance
            _recursion_depth: Internal recursion depth counter

        Returns:
            Next step to execute or None if workflow complete

        Raises:
            WorkflowExecutionError: If workflow not found or in invalid state
        """
        # Prevent infinite recursion
        if _recursion_depth > 50:
            raise WorkflowExecutionError("Maximum recursion depth exceeded in workflow execution")
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]

        if instance.status != "running":
            return None

        # Get execution context
        context = context_manager.get_context(workflow_id)
        if not context:
            raise WorkflowExecutionError(f"Execution context not found for workflow {workflow_id}")

        # Check for completed sub-agent tasks first
        completed_tasks = context.get_completed_sub_agent_tasks()
        if completed_tasks:
            # Process completed sub-agent results
            return self._process_completed_sub_agent_tasks(workflow_id, context, completed_tasks)

        # Check if we need to handle loop continuation
        # Only check continuation if we're at the end of a loop frame
        if context.is_in_loop():
            current_frame = context.current_frame()
            if current_frame and current_frame.frame_type == "loop" and not current_frame.has_more_steps():
                loop_result = self._check_loop_continuation(workflow_id, context, _recursion_depth)
                if loop_result:
                    return loop_result

        # Get next step from context
        if not context.has_next_step():
            # No more steps in current frame
            if len(context.execution_stack) > 1:
                # Pop completed frame and advance parent step
                completed_frame = context.pop_frame()

                # If this was a control flow frame, advance the parent step
                if completed_frame and completed_frame.frame_type in ("conditional", "loop"):
                    parent_frame = context.current_frame()
                    if parent_frame:
                        parent_frame.advance_step()

                return self.get_next_step(workflow_id, _recursion_depth + 1)  # Recursive call
            else:
                # Workflow complete
                instance.status = "completed"
                instance.completed_at = datetime.now(UTC).isoformat()
                context_manager.remove_context(workflow_id)
                return None

        step = context.get_next_step()
        if not step:
            return None

        # Get current state for variable replacement and expression evaluation
        current_state = self.state_manager.read(workflow_id)

        # Process control flow steps internally
        if step.type == "conditional":
            return self._process_conditional_step(step, context, current_state, workflow_id, _recursion_depth)
        elif step.type == "while_loop":
            return self._process_while_loop_step(step, context, current_state, workflow_id, _recursion_depth)
        elif step.type == "foreach":
            return self._process_foreach_step(step, context, current_state, workflow_id, _recursion_depth)
        elif step.type == "break":
            return self._process_break_step(step, context, current_state, workflow_id, _recursion_depth)
        elif step.type == "continue":
            return self._process_continue_step(step, context, current_state, workflow_id, _recursion_depth)
        elif step.type == "user_input":
            return self._process_user_input_step(step, context, current_state)
        elif step.type == "parallel_foreach":
            return self._process_parallel_foreach_step(step, context, current_state)
        else:
            # Regular step - advance context and return to agent
            context.advance_step()
            return self._prepare_step_for_agent(step, workflow_id, current_state)

    def _process_conditional_step(self, step, context, state, workflow_id, recursion_depth):
        """Process a conditional step internally."""
        try:
            result = self.conditional_processor.process_conditional(step, context, state)

            # Don't advance the main step yet - the conditional frame handles the branching
            # We'll advance when the conditional frame is popped

            # If we have steps to execute, get the first one from the conditional frame
            if result.get("steps_to_execute", 0) > 0:
                return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)
            else:
                # No steps to execute, advance main step and continue
                context.advance_step()
                return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"Conditional error: {str(e)}")

    def _process_while_loop_step(self, step, context, state, workflow_id, recursion_depth):
        """Process a while loop step internally."""
        try:
            result = self.while_loop_processor.process_while_loop(step, context, state)

            # Don't advance the main step yet - the loop frame handles this

            if result["type"] == "while_loop_started":
                # Get first step of loop body
                return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)
            else:
                # Loop was skipped, advance main step and continue
                context.advance_step()
                return self.get_next_step(workflow_id, recursion_depth + 1)

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"While loop error: {str(e)}")

    def _process_foreach_step(self, step, context, state, workflow_id, recursion_depth):
        """Process a foreach step internally."""
        try:
            result = self.foreach_processor.process_foreach(step, context, state)

            # Don't advance the main step yet - the loop frame handles this

            if result["type"] == "foreach_started":
                # Get first step of loop body
                return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)
            else:
                # Loop was skipped, advance main step and continue
                context.advance_step()
                return self.get_next_step(workflow_id, recursion_depth + 1)

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"ForEach error: {str(e)}")

    def _process_break_step(self, step, context, state, workflow_id, recursion_depth):
        """Process a break step internally."""
        try:
            self.break_continue_processor.process_break(step, context, state)

            # Break jumps to end of current frame, triggering loop exit
            return self.get_next_step(workflow_id, recursion_depth + 1)

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"Break error: {str(e)}")

    def _process_continue_step(self, step, context, state, workflow_id, recursion_depth):
        """Process a continue step internally."""
        try:
            self.break_continue_processor.process_continue(step, context, state)

            # Continue jumps to end of current frame, triggering loop continuation
            return self.get_next_step(workflow_id, recursion_depth + 1)

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"Continue error: {str(e)}")

    def _process_user_input_step(self, step, context, state):
        """Process a user input step."""
        try:
            result = self.user_input_processor.process_user_input(step, context, state)

            # Don't advance step yet - wait for user input completion
            return {
                "step": {
                    "id": step.id,
                    "type": "user_input",
                    "definition": result,
                    "instructions": result["instructions"],
                },
                "workflow_id": context.workflow_id,
                "execution_context": context.get_execution_summary(),
            }

        except ControlFlowError as e:
            return self._create_error_response(step.id, f"User input error: {str(e)}")

    def _process_parallel_foreach_step(self, step, context, state):
        """Process a parallel foreach step by delegating to sub-agents."""
        definition = step.definition
        items_expression = definition.get("items", "")
        sub_agent_task = definition.get("sub_agent_task", "")
        max_parallel = definition.get("max_parallel", 10)

        try:
            # Evaluate items expression
            items = self._evaluate_expression(items_expression, state, context)

            if not isinstance(items, list):
                raise ControlFlowError(f"Parallel foreach items must be an array, got {type(items)}")

            # Create sub-agent contexts for each item
            sub_agent_contexts = []
            for i, item in enumerate(items[:max_parallel]):  # Limit to max_parallel
                task_context = context.create_sub_agent_context(
                    task_name=sub_agent_task, context_data={"item": item, "index": i, "parent_step_id": step.id}
                )
                sub_agent_contexts.append(task_context)

            # Advance step since we've initiated parallel processing
            context.advance_step()

            return {
                "step": {
                    "id": step.id,
                    "type": "parallel_foreach",
                    "definition": {
                        "sub_agent_tasks": [
                            {"task_id": ctx.task_id, "task_name": ctx.task_name, "context": ctx.context_data}
                            for ctx in sub_agent_contexts
                        ],
                        "total_items": len(items),
                        "parallel_limit": max_parallel,
                    },
                },
                "workflow_id": context.workflow_id,
                "execution_context": context.get_execution_summary(),
            }

        except Exception as e:
            return self._create_error_response(step.id, f"Parallel foreach error: {str(e)}")

    def _check_loop_continuation(self, workflow_id, context, recursion_depth):
        """Check if a loop should continue or exit."""
        current_loop = context.current_loop()
        if not current_loop:
            return None

        current_state = self.state_manager.read(workflow_id)

        try:
            if current_loop.loop_type == "while":
                result = self.while_loop_processor.check_loop_continuation(context, current_state)
            elif current_loop.loop_type == "foreach":
                result = self.foreach_processor.check_foreach_continuation(context, current_state)
            else:
                return None

            if result["type"].endswith("_exited"):
                # Loop exited, continue to next step
                return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)
            elif result["type"].endswith("_continue"):
                # Loop continues, get first step from current loop body without reprocessing the loop
                # Reset the loop frame to the beginning and get the first step
                current_frame = context.current_frame()
                if current_frame and current_frame.frame_type == "loop":
                    current_frame.current_step_index = 0
                    return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)
                else:
                    return self.get_next_step(workflow_id, recursion_depth + 1)

        except ControlFlowError:
            # Error in loop continuation, exit loop
            context.exit_loop()
            context.pop_frame()
            return self._get_simple_next_step(workflow_id, context, recursion_depth + 1)

        return None

    def _get_simple_next_step(
        self, workflow_id: str, context: ExecutionContext, recursion_depth: int = 0
    ) -> dict[str, Any] | None:
        """Get the next step without performing loop continuation checks.

        This is used internally by control flow processors to avoid infinite recursion.
        """
        # Prevent infinite recursion
        if recursion_depth > 50:
            raise WorkflowExecutionError("Maximum recursion depth exceeded in workflow execution")

        # Get next step from context
        if not context.has_next_step():
            # No more steps in current frame
            if len(context.execution_stack) > 1:
                # Pop completed frame and advance parent step
                completed_frame = context.pop_frame()

                # If this was a control flow frame, advance the parent step
                if completed_frame and completed_frame.frame_type in ("conditional", "loop"):
                    parent_frame = context.current_frame()
                    if parent_frame:
                        parent_frame.advance_step()

                return self.get_next_step(workflow_id, recursion_depth + 1)  # Recursive call
            else:
                # Workflow complete
                instance = self.workflows.get(workflow_id)
                if instance:
                    instance.status = "completed"
                    instance.completed_at = datetime.now(UTC).isoformat()
                context_manager.remove_context(workflow_id)
                return None

        step = context.get_next_step()
        if not step:
            return None

        # Get current state for variable replacement and expression evaluation
        current_state = self.state_manager.read(workflow_id)

        # Handle control flow steps
        if step.type == "conditional":
            return self._process_conditional_step(step, context, current_state, workflow_id, recursion_depth)
        elif step.type == "while_loop":
            return self._process_while_loop_step(step, context, current_state, workflow_id, recursion_depth)
        elif step.type == "foreach":
            return self._process_foreach_step(step, context, current_state, workflow_id, recursion_depth)
        elif step.type == "parallel_foreach":
            return self._process_parallel_foreach_step(step, context, current_state)
        else:
            # Regular step - advance context and return to agent
            context.advance_step()
            return self._prepare_step_for_agent(step, workflow_id, current_state)

    def _process_completed_sub_agent_tasks(self, workflow_id, context, completed_tasks):
        """Process results from completed sub-agent tasks."""
        # For now, just continue to next step
        # In a full implementation, this would collect results and update state
        return self.get_next_step(workflow_id, 0)  # Reset recursion depth for sub-agent processing

    def _prepare_step_for_agent(self, step, workflow_id, state):
        """Prepare a regular step for agent execution."""
        # Get execution context to merge with state
        context = context_manager.get_context(workflow_id)

        # Merge state with context variables for variable replacement
        replacement_context = dict(state)
        if context:
            replacement_context.update(context.get_all_variables())

        # Replace variables in step definition
        processed_definition = VariableReplacer.replace(step.definition, replacement_context)

        # Create step execution record
        step_execution = StepExecution(
            workflow_id=workflow_id,
            step_id=step.id,
            step_index=0,  # Context-based execution doesn't use simple indices
            status="pending",
            started_at=datetime.now(UTC).isoformat(),
        )

        self.step_executions[workflow_id].append(step_execution)

        return {
            "step": {"id": step.id, "type": step.type, "definition": processed_definition},
            "workflow_id": workflow_id,
            "execution_context": context_manager.get_context(workflow_id).get_execution_summary(),
        }

    def _create_error_response(self, step_id, error_message):
        """Create an error response for step processing failures."""
        return {
            "step": {
                "id": step_id,
                "type": "error",
                "definition": {
                    "error": error_message,
                    "instructions": f"Error processing step {step_id}: {error_message}",
                },
            },
            "error": error_message,
        }

    def _evaluate_expression(self, expression, state, context):
        """Evaluate an expression with current state and context."""
        # Clean the expression
        cleaned_expression = expression.strip()
        if cleaned_expression.startswith("{{") and cleaned_expression.endswith("}}"):
            cleaned_expression = cleaned_expression[2:-2].strip()

        # Merge state with context variables
        evaluation_context = dict(state)
        evaluation_context.update(context.get_all_variables())

        return self.expression_evaluator.evaluate(cleaned_expression, evaluation_context)

    def step_complete(
        self,
        workflow_id: str,
        step_id: str,
        status: str = "success",
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Mark a step as complete and advance workflow with control flow support.

        Args:
            workflow_id: ID of the workflow instance
            step_id: ID of the completed step
            status: "success" or "failed"
            result: Optional result data from step execution
            error_message: Error message if step failed

        Returns:
            Updated workflow status
        """
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]
        context = context_manager.get_context(workflow_id)

        # Find and update step execution record
        step_executions = self.step_executions[workflow_id]
        step_execution = None
        for exec_record in reversed(step_executions):
            if exec_record.step_id == step_id:
                step_execution = exec_record
                break

        if step_execution:
            step_execution.status = "completed" if status == "success" else "failed"
            step_execution.completed_at = datetime.now(UTC).isoformat()
            step_execution.result = result
            step_execution.error_message = error_message

        if status == "failed":
            instance.status = "failed"
            instance.completed_at = datetime.now(UTC).isoformat()
            instance.error_message = error_message or "Step execution failed"

            if context:
                context_manager.remove_context(workflow_id)

            return {"status": "failed", "error": error_message, "completed_at": instance.completed_at}

        # For user input steps, validate and store the input
        if result and "user_input" in result:
            current_step = context.get_next_step() if context else None
            if current_step and current_step.type == "user_input":
                validation_result = self.user_input_processor.validate_and_store_input(
                    current_step, result["user_input"], context
                )

                if not validation_result["valid"]:
                    # Input validation failed, retry
                    return {"status": "retry", "error": validation_result["error"], "retry_step": True}

                # Input was valid, advance step
                if context:
                    context.advance_step()

        # Check workflow completion
        if context and context.is_complete():
            instance.status = "completed"
            instance.completed_at = datetime.now(UTC).isoformat()
            context_manager.remove_context(workflow_id)

        return {
            "status": instance.status,
            "completed_at": instance.completed_at if instance.status == "completed" else None,
            "execution_context": context.get_execution_summary() if context else None,
        }

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get current status of a workflow with control flow information."""
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]
        current_state = self.state_manager.read(workflow_id)
        context = context_manager.get_context(workflow_id)

        result = {
            "workflow_id": workflow_id,
            "workflow_name": instance.workflow_name,
            "status": instance.status,
            "created_at": instance.created_at,
            "completed_at": instance.completed_at,
            "error_message": instance.error_message,
            "state": current_state,
        }

        if context:
            result["execution_context"] = context.get_execution_summary()

        return result

    def update_workflow_state(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update workflow state (same as base executor)."""
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        try:
            self.state_manager.update(workflow_id, updates)
            return self.state_manager.read(workflow_id)
        except Exception as e:
            raise WorkflowExecutionError(f"Failed to update workflow state: {e}") from e

    def list_active_workflows(self) -> list[dict[str, Any]]:
        """List all active workflow instances with control flow information."""
        result = []
        for workflow_id, instance in self.workflows.items():
            context = context_manager.get_context(workflow_id)

            workflow_info = {
                "workflow_id": workflow_id,
                "workflow_name": instance.workflow_name,
                "status": instance.status,
                "created_at": instance.created_at,
                "completed_at": instance.completed_at,
            }

            if context:
                workflow_info["execution_context"] = context.get_execution_summary()

            result.append(workflow_info)

        return result
