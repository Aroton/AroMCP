"""Debug tools for the MCP Workflow System."""

import logging
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from ...utils.json_parameter_middleware import json_convert
from ..errors.tracking import ErrorTracker
from ..state.manager import StateManager
from ..state.transformer import TransformationEngine
from ..workflow.executor import WorkflowExecutor
from ..workflow.loader import WorkflowLoader

logger = logging.getLogger(__name__)

# Global instances for debugging
_state_manager: StateManager | None = None
_workflow_executor: WorkflowExecutor | None = None
_workflow_loader: WorkflowLoader | None = None
_error_tracker: ErrorTracker | None = None
_transformation_engine: TransformationEngine | None = None

# Transformation execution tracking
_transformation_traces: dict[str, list[dict[str, Any]]] = {}
_execution_history: dict[str, list[dict[str, Any]]] = {}


def register_debug_tools(mcp: FastMCP):
    """Register debug tools with the MCP server."""

    @mcp.tool
    @json_convert
    def workflow_trace_transformations(
        workflow_id: str,
        field: str | None = None,
        include_timing: bool = True,
    ) -> dict[str, Any]:
        """
        Trace transformation execution with timing information.

        Use this tool when:
        - Debugging computed field calculations
        - Understanding transformation dependency chains
        - Identifying performance bottlenecks in transformations
        - Analyzing transformation inputs and outputs

        Args:
            workflow_id: The workflow to trace transformations for
            field: Specific field to trace (optional, traces all if None)
            include_timing: Whether to include execution timing data

        Example:
            workflow_trace_transformations("wf_123", "computed.ready_batches")
            → {"traces": [{"field": "computed.ready_batches", "duration_ms": 2.5, ...}]}

        Note: Essential for debugging transformation performance and correctness
        """
        try:
            if not _state_manager:
                return {"error": {"code": "NOT_INITIALIZED", "message": "State manager not initialized"}}

            traces = _transformation_traces.get(workflow_id, [])

            # Filter by field if specified
            if field:
                traces = [trace for trace in traces if trace.get("field") == field]

            # Filter out timing if not requested
            if not include_timing:
                for trace in traces:
                    trace.pop("duration_ms", None)
                    trace.pop("timestamp", None)

            # Calculate summary statistics
            summary = {
                "total_transformations": len(traces),
                "unique_fields": len({trace.get("field", "") for trace in traces}),
            }

            if include_timing and traces:
                durations = [trace.get("duration_ms", 0) for trace in traces if "duration_ms" in trace]
                if durations:
                    summary.update({
                        "avg_duration_ms": sum(durations) / len(durations),
                        "max_duration_ms": max(durations),
                        "min_duration_ms": min(durations),
                    })

            return {
                "data": {
                    "workflow_id": workflow_id,
                    "traces": traces,
                    "summary": summary,
                }
            }

        except Exception as e:
            logger.error(f"Error tracing transformations: {e}")
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}

    @mcp.tool
    @json_convert
    def workflow_debug_info(workflow_id: str) -> dict[str, Any]:
        """
        Get comprehensive debug information for a workflow.

        Use this tool when:
        - Investigating workflow execution issues
        - Understanding current workflow state and progress
        - Debugging step execution problems
        - Getting overview of workflow health

        Args:
            workflow_id: The workflow to get debug information for

        Example:
            workflow_debug_info("wf_123")
            → {"current_step": "step_2", "state_size_kb": 45, "execution_time_ms": 1500, ...}

        Note: Provides comprehensive workflow state for troubleshooting
        """
        try:
            debug_info = {
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat(),
            }

            # Get state information
            if _state_manager:
                try:
                    state = _state_manager.read(workflow_id)
                    debug_info["state"] = {
                        "has_state": bool(state),
                        "state_size_kb": len(str(state)) / 1024 if state else 0,
                        "top_level_keys": list(state.keys()) if state else [],
                    }
                except Exception as e:
                    debug_info["state"] = {"error": str(e)}

            # Get execution information
            if _workflow_executor:
                try:
                    next_step = _workflow_executor.get_next_step(workflow_id)
                    debug_info["execution"] = {
                        "has_next_step": next_step is not None,
                        "next_step_id": next_step.get("id") if next_step else None,
                        "next_step_type": next_step.get("type") if next_step else None,
                    }
                except Exception as e:
                    debug_info["execution"] = {"error": str(e)}

            # Get transformation traces
            traces = _transformation_traces.get(workflow_id, [])
            debug_info["transformations"] = {
                "total_traces": len(traces),
                "recent_traces": traces[-5:] if traces else [],
            }

            # Get execution history
            history = _execution_history.get(workflow_id, [])
            debug_info["history"] = {
                "total_steps": len(history),
                "recent_steps": history[-5:] if history else [],
            }

            # Get error information
            if _error_tracker:
                try:
                    error_summary = _error_tracker.history.get_error_summary(workflow_id)
                    debug_info["errors"] = error_summary
                except Exception as e:
                    debug_info["errors"] = {"error": str(e)}

            return {"data": debug_info}

        except Exception as e:
            logger.error(f"Error getting debug info: {e}")
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}

    @mcp.tool
    @json_convert
    def workflow_test_transformation(
        transform: str,
        input_data: Any,
        context: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """
        Test transformations without side effects.

        Use this tool when:
        - Testing transformation logic before applying to workflow
        - Debugging transformation syntax errors
        - Validating transformation outputs with sample data
        - Developing new computed field transformations

        Args:
            transform: The JavaScript transformation code to test
            input: The input value to transform
            context: Additional context variables (optional)

        Example:
            workflow_test_transformation("input * 2", 5)
            → {"output": 10, "execution_time_ms": 0.5, "success": true}

        Note: Safe testing environment for transformation development
        """
        try:
            if not _transformation_engine:
                # Create a temporary transformation engine for testing
                from ..state.transformer import TransformationEngine
                engine = TransformationEngine()
            else:
                engine = _transformation_engine

            # Parse context if it's a string
            parsed_context = {}
            if isinstance(context, str):
                import json
                try:
                    parsed_context = json.loads(context)
                except json.JSONDecodeError:
                    return {"error": {"code": "INVALID_INPUT", "message": "Invalid JSON in context"}}
            elif isinstance(context, dict):
                parsed_context = context

            # Execute transformation with timing
            start_time = datetime.now()
            try:
                # TransformationEngine only accepts transform and input - context not supported
                result = engine.execute(transform, input_data)
                end_time = datetime.now()

                execution_time = (end_time - start_time).total_seconds() * 1000

                return {
                    "data": {
                        "success": True,
                        "output": result,
                        "execution_time_ms": execution_time,
                        "input": input_data,
                        "transform": transform,
                        "context": parsed_context,
                    }
                }

            except Exception as transform_error:
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds() * 1000

                return {
                    "data": {
                        "success": False,
                        "error": str(transform_error),
                        "error_type": type(transform_error).__name__,
                        "execution_time_ms": execution_time,
                        "input": input_data,
                        "transform": transform,
                        "context": parsed_context,
                    }
                }

        except Exception as e:
            logger.error(f"Error testing transformation: {e}")
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}

    @mcp.tool
    @json_convert
    def workflow_explain_plan(
        workflow: str,
        inputs: dict[str, Any] | str,
    ) -> dict[str, Any]:
        """
        Get execution plan before running a workflow.

        Use this tool when:
        - Understanding what a workflow will do before execution
        - Validating workflow logic and step sequences
        - Debugging workflow definition issues
        - Planning resource requirements for execution

        Args:
            workflow: Name of the workflow to explain
            inputs: Input parameters for the workflow

        Example:
            workflow_explain_plan("test:simple", {"name": "test"})
            → {"steps": ["state_update", "user_message"], "estimated_duration": "30s", ...}

        Note: Provides execution preview without actually running the workflow
        """
        try:
            if not _workflow_loader:
                return {"error": {"code": "NOT_INITIALIZED", "message": "Workflow loader not initialized"}}

            # Parse inputs if string
            parsed_inputs = {}
            if isinstance(inputs, str):
                import json
                try:
                    parsed_inputs = json.loads(inputs)
                except json.JSONDecodeError:
                    return {"error": {"code": "INVALID_INPUT", "message": "Invalid JSON in inputs"}}
            elif isinstance(inputs, dict):
                parsed_inputs = inputs

            # Load workflow definition
            try:
                workflow_def = _workflow_loader.load(workflow)
            except Exception as e:
                return {"error": {"code": "NOT_FOUND", "message": f"Workflow '{workflow}' not found: {str(e)}"}}

            # Analyze the workflow plan
            plan = {
                "workflow_name": workflow_def.name,
                "description": workflow_def.description,
                "version": workflow_def.version,
                "inputs": parsed_inputs,
            }

            # Analyze steps
            steps = workflow_def.steps or []
            plan["steps"] = []

            for i, step in enumerate(steps):
                step_info = {
                    "index": i,
                    "id": step.get("id", f"step_{i}"),
                    "type": step.get("type", "unknown"),
                    "description": step.get("description", ""),
                }

                # Add type-specific analysis
                if step.get("type") == "conditional":
                    step_info["condition"] = step.get("condition", "")
                    step_info["has_then"] = bool(step.get("then"))
                    step_info["has_else"] = bool(step.get("else"))
                elif step.get("type") == "while":
                    step_info["condition"] = step.get("condition", "")
                    step_info["max_iterations"] = step.get("max_iterations", "unlimited")
                elif step.get("type") == "foreach":
                    step_info["items"] = step.get("items", "")
                elif step.get("type") == "parallel_foreach":
                    step_info["items"] = step.get("items", "")
                    step_info["max_parallel"] = step.get("max_parallel", 10)
                    step_info["sub_agent_task"] = step.get("sub_agent_task", "")

                plan["steps"].append(step_info)

            # Analyze state schema
            if hasattr(workflow_def, 'state_schema') and workflow_def.state_schema:
                schema = workflow_def.state_schema
                plan["state_schema"] = {
                    "raw_fields": len(schema.get("raw", {})),
                    "computed_fields": len(schema.get("computed", {})),
                    "state_fields": len(schema.get("state", {})),
                }

                # Analyze computed field dependencies
                computed = schema.get("computed", {})
                plan["computed_dependencies"] = {}
                for field_name, field_def in computed.items():
                    if isinstance(field_def, dict):
                        deps = field_def.get("from", [])
                        if isinstance(deps, str):
                            deps = [deps]
                        plan["computed_dependencies"][field_name] = deps

            # Estimate complexity
            plan["complexity"] = {
                "total_steps": len(steps),
                "has_loops": any(step.get("type") in ["while", "foreach"] for step in steps),
                "has_conditionals": any(step.get("type") == "conditional" for step in steps),
                "has_parallel": any(step.get("type") == "parallel_foreach" for step in steps),
                "estimated_duration": "unknown",  # Would need more sophisticated analysis
            }

            return {"data": plan}

        except Exception as e:
            logger.error(f"Error explaining plan: {e}")
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}

    @mcp.tool
    @json_convert
    def workflow_get_dependencies(
        workflow_id: str,
        field: str | None = None,
    ) -> dict[str, Any]:
        """
        Get dependency information for computed fields.

        Use this tool when:
        - Understanding field dependency chains
        - Debugging circular dependency issues
        - Optimizing transformation execution order
        - Analyzing field update cascades

        Args:
            workflow_id: The workflow to analyze dependencies for
            field: Specific field to analyze (optional, analyzes all if None)

        Example:
            workflow_get_dependencies("wf_123", "computed.summary")
            → {"dependencies": ["raw.count", "raw.total"], "depth": 1, ...}

        Note: Essential for understanding computed field relationships
        """
        try:
            if not _state_manager:
                return {"error": {"code": "NOT_INITIALIZED", "message": "State manager not initialized"}}

            # Get the state schema for dependency analysis
            try:
                state = _state_manager.read(workflow_id)
                if not state:
                    return {"error": {"code": "NOT_FOUND", "message": f"Workflow {workflow_id} not found"}}
            except Exception as e:
                return {"error": {"code": "OPERATION_FAILED", "message": f"Could not read workflow state: {str(e)}"}}

            # For now, return basic dependency information
            # In a full implementation, this would analyze the actual state schema
            dependencies = {
                "workflow_id": workflow_id,
                "field": field,
                "analysis": "Dependency analysis not fully implemented yet",
                "available_fields": list(state.keys()) if state else [],
            }

            if field and field in state:
                dependencies["field_value"] = state[field]
                dependencies["field_type"] = type(state[field]).__name__

            return {"data": dependencies}

        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}


def initialize_debug_tools(
    state_manager: StateManager,
    workflow_executor: WorkflowExecutor,
    workflow_loader: WorkflowLoader,
    error_tracker: ErrorTracker,
    transformation_engine: TransformationEngine,
):
    """Initialize debug tools with required components."""
    global _state_manager, _workflow_executor, _workflow_loader, _error_tracker, _transformation_engine

    _state_manager = state_manager
    _workflow_executor = workflow_executor
    _workflow_loader = workflow_loader
    _error_tracker = error_tracker
    _transformation_engine = transformation_engine

    logger.info("Debug tools initialized")


def record_transformation_trace(
    workflow_id: str,
    field: str,
    trigger: str,
    input_data: Any,
    output_data: Any,
    duration_ms: float,
    dependencies: list[str],
):
    """Record a transformation execution trace."""
    if workflow_id not in _transformation_traces:
        _transformation_traces[workflow_id] = []

    trace = {
        "field": field,
        "timestamp": datetime.now().isoformat(),
        "trigger": trigger,
        "input": input_data,
        "output": output_data,
        "duration_ms": duration_ms,
        "dependencies": dependencies,
    }

    _transformation_traces[workflow_id].append(trace)

    # Keep only last 100 traces per workflow
    if len(_transformation_traces[workflow_id]) > 100:
        _transformation_traces[workflow_id] = _transformation_traces[workflow_id][-100:]


def record_execution_step(
    workflow_id: str,
    step_id: str,
    step_type: str,
    status: str,
    duration_ms: float,
    details: dict[str, Any] | None = None,
):
    """Record a workflow step execution."""
    if workflow_id not in _execution_history:
        _execution_history[workflow_id] = []

    record = {
        "step_id": step_id,
        "step_type": step_type,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "duration_ms": duration_ms,
        "details": details or {},
    }

    _execution_history[workflow_id].append(record)

    # Keep only last 100 steps per workflow
    if len(_execution_history[workflow_id]) > 100:
        _execution_history[workflow_id] = _execution_history[workflow_id][-100:]


def get_debug_stats() -> dict[str, Any]:
    """Get debug tool statistics."""
    return {
        "transformation_traces": {
            "workflows_tracked": len(_transformation_traces),
            "total_traces": sum(len(traces) for traces in _transformation_traces.values()),
        },
        "execution_history": {
            "workflows_tracked": len(_execution_history),
            "total_steps": sum(len(steps) for steps in _execution_history.values()),
        },
        "components_initialized": {
            "state_manager": _state_manager is not None,
            "workflow_executor": _workflow_executor is not None,
            "workflow_loader": _workflow_loader is not None,
            "error_tracker": _error_tracker is not None,
            "transformation_engine": _transformation_engine is not None,
        },
    }


# Standalone functions for testing (these mirror the @mcp.tool functions above)

def workflow_trace_transformations(
    workflow_id: str,
    field: str | None = None,
    include_timing: bool = True,
) -> dict[str, Any]:
    """Test-accessible version of workflow trace transformations."""
    try:
        if not _state_manager:
            return {"error": {"code": "NOT_INITIALIZED", "message": "State manager not initialized"}}

        traces = _transformation_traces.get(workflow_id, [])

        # Filter by field if specified
        if field:
            traces = [trace for trace in traces if trace.get("field") == field]

        # Filter out timing if not requested
        if not include_timing:
            for trace in traces:
                trace.pop("duration_ms", None)
                trace.pop("timestamp", None)

        # Calculate summary statistics
        summary = {
            "total_transformations": len(traces),
            "unique_fields": len({trace.get("field", "") for trace in traces}),
        }

        if include_timing and traces:
            durations = [trace.get("duration_ms", 0) for trace in traces if "duration_ms" in trace]
            if durations:
                summary.update({
                    "avg_duration_ms": sum(durations) / len(durations),
                    "max_duration_ms": max(durations),
                    "min_duration_ms": min(durations),
                })

        return {
            "data": {
                "workflow_id": workflow_id,
                "traces": traces,
                "summary": summary,
            }
        }

    except Exception as e:
        logger.error(f"Error tracing transformations: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}


def workflow_debug_info(workflow_id: str) -> dict[str, Any]:
    """Test-accessible version of workflow debug info."""
    try:
        debug_info = {
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat(),
        }

        # Get state information
        if _state_manager:
            try:
                state = _state_manager.read(workflow_id)
                debug_info["state"] = {
                    "has_state": bool(state),
                    "state_size_kb": len(str(state)) / 1024 if state else 0,
                    "top_level_keys": list(state.keys()) if state else [],
                }
            except Exception as e:
                debug_info["state"] = {"error": str(e)}

        # Get execution information
        if _workflow_executor:
            try:
                next_step = _workflow_executor.get_next_step(workflow_id)
                debug_info["execution"] = {
                    "has_next_step": next_step is not None,
                    "next_step_id": next_step.get("id") if next_step else None,
                    "next_step_type": next_step.get("type") if next_step else None,
                }
            except Exception as e:
                debug_info["execution"] = {"error": str(e)}

        # Get transformation traces
        traces = _transformation_traces.get(workflow_id, [])
        debug_info["transformations"] = {
            "total_traces": len(traces),
            "recent_traces": traces[-5:] if traces else [],
        }

        # Get execution history
        history = _execution_history.get(workflow_id, [])
        debug_info["history"] = {
            "total_steps": len(history),
            "recent_steps": history[-5:] if history else [],
        }

        # Get error information
        if _error_tracker:
            try:
                error_summary = _error_tracker.history.get_error_summary(workflow_id)
                debug_info["errors"] = error_summary
            except Exception as e:
                debug_info["errors"] = {"error": str(e)}

        return {"data": debug_info}

    except Exception as e:
        logger.error(f"Error getting debug info: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}


def workflow_test_transformation(
    transform: str,
    input_data: Any,
    context: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Test-accessible version of workflow test transformation."""
    try:
        if not _transformation_engine:
            # Create a temporary transformation engine for testing
            from ..state.transformer import TransformationEngine
            engine = TransformationEngine()
        else:
            engine = _transformation_engine

        # Parse context if it's a string
        parsed_context = {}
        if isinstance(context, str):
            import json
            try:
                parsed_context = json.loads(context)
            except json.JSONDecodeError:
                return {"error": {"code": "INVALID_INPUT", "message": "Invalid JSON in context"}}
        elif isinstance(context, dict):
            parsed_context = context

        # Execute transformation with timing
        start_time = datetime.now()
        try:
            # TransformationEngine only accepts transform and input - context not supported
            result = engine.execute(transform, input_data)
            end_time = datetime.now()

            execution_time = (end_time - start_time).total_seconds() * 1000

            return {
                "data": {
                    "success": True,
                    "output": result,
                    "execution_time_ms": execution_time,
                    "input": input_data,
                    "transform": transform,
                    "context": parsed_context,
                }
            }

        except Exception as transform_error:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds() * 1000

            return {
                "data": {
                    "success": False,
                    "error": str(transform_error),
                    "error_type": type(transform_error).__name__,
                    "execution_time_ms": execution_time,
                    "input": input_data,
                    "transform": transform,
                    "context": parsed_context,
                }
            }

    except Exception as e:
        logger.error(f"Error testing transformation: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}


def workflow_explain_plan(
    workflow: str,
    inputs: dict[str, Any] | str,
) -> dict[str, Any]:
    """Test-accessible version of workflow explain plan."""
    try:
        if not _workflow_loader:
            return {"error": {"code": "NOT_INITIALIZED", "message": "Workflow loader not initialized"}}

        # Parse inputs if string
        parsed_inputs = {}
        if isinstance(inputs, str):
            import json
            try:
                parsed_inputs = json.loads(inputs)
            except json.JSONDecodeError:
                return {"error": {"code": "INVALID_INPUT", "message": "Invalid JSON in inputs"}}
        elif isinstance(inputs, dict):
            parsed_inputs = inputs

        # Load workflow definition
        try:
            workflow_def = _workflow_loader.load(workflow)
        except Exception as e:
            return {"error": {"code": "NOT_FOUND", "message": f"Workflow '{workflow}' not found: {str(e)}"}}

        # Analyze the workflow plan
        plan = {
            "workflow_name": workflow_def.name,
            "description": workflow_def.description,
            "version": workflow_def.version,
            "inputs": parsed_inputs,
        }

        # Analyze steps
        steps = workflow_def.steps or []
        plan["steps"] = []

        for i, step in enumerate(steps):
            step_info = {
                "index": i,
                "id": step.id,
                "type": step.type,
                "description": step.definition.get("description", ""),
            }

            # Add type-specific analysis
            if step.type == "conditional":
                step_info["condition"] = step.definition.get("condition", "")
                step_info["has_then"] = bool(step.definition.get("then"))
                step_info["has_else"] = bool(step.definition.get("else"))
            elif step.type == "while":
                step_info["condition"] = step.definition.get("condition", "")
                step_info["max_iterations"] = step.definition.get("max_iterations", "unlimited")
            elif step.type == "foreach":
                step_info["items"] = step.definition.get("items", "")
            elif step.type == "parallel_foreach":
                step_info["items"] = step.definition.get("items", "")
                step_info["max_parallel"] = step.definition.get("max_parallel", 10)
                step_info["sub_agent_task"] = step.definition.get("sub_agent_task", "")

            plan["steps"].append(step_info)

        # Estimate complexity
        plan["complexity"] = {
            "total_steps": len(steps),
            "has_loops": any(step.type in ["while", "foreach"] for step in steps),
            "has_conditionals": any(step.type == "conditional" for step in steps),
            "has_parallel": any(step.type == "parallel_foreach" for step in steps),
            "estimated_duration": "unknown",  # Would need more sophisticated analysis
        }

        return {"data": plan}

    except Exception as e:
        logger.error(f"Error explaining plan: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}


def workflow_get_dependencies(
    workflow_id: str,
    field: str | None = None,
) -> dict[str, Any]:
    """Test-accessible version of workflow get dependencies."""
    try:
        if not _state_manager:
            return {"error": {"code": "NOT_INITIALIZED", "message": "State manager not initialized"}}

        # Get the state schema for dependency analysis
        try:
            state = _state_manager.read(workflow_id)
            if not state:
                return {"error": {"code": "NOT_FOUND", "message": f"Workflow {workflow_id} not found"}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Could not read workflow state: {str(e)}"}}

        # For now, return basic dependency information
        # In a full implementation, this would analyze the actual state schema
        dependencies = {
            "workflow_id": workflow_id,
            "field": field,
            "analysis": "Dependency analysis not fully implemented yet",
            "available_fields": list(state.keys()) if state else [],
        }

        if field and field in state:
            dependencies["field_value"] = state[field]
            dependencies["field_type"] = type(state[field]).__name__

        return {"data": dependencies}

    except Exception as e:
        logger.error(f"Error getting dependencies: {e}")
        return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}
