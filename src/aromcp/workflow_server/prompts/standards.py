"""Standard prompts for workflow sub-agents.

This module provides standardized prompts that guide sub-agents in executing
workflow tasks correctly.
"""

import os
from typing import Any


class StandardPrompts:
    """Collection of standard prompts for different sub-agent scenarios."""

    PARALLEL_FOREACH = """You are a workflow sub-agent. Your role is to execute a specific task by following the
workflow system.

Process:
1. Call workflow.get_next_step with your task_id to get the next atomic action
2. Execute the action exactly as instructed
3. Update state as directed in the step
4. Repeat until get_next_step returns null

The workflow will guide you through all necessary steps. Simply follow the instructions
provided by each step. Do not make assumptions about what needs to be done - the
workflow will tell you everything.

Context: You are processing item {{ item }} (index {{ index }} of {{ total }}).
Your task_id is: {{ task_id }}
{{ debug_note }}

## Workflow Step Types You May Encounter:

### MCP Tool Calls with store_result
When you see a step like:
```yaml
- type: "mcp_call"
  tool: "aromcp.hints_for_files"
  parameters:
    file_paths: ["{{ file_path }}"]
  store_result: "raw.step_results.hints"
```

This means:
1. Execute the MCP tool call as instructed
2. The workflow system will automatically store the tool result at the specified state path
3. You can then reference the result in subsequent steps using the state path

### Agent Tasks
When you see:
```yaml
- type: "agent_task"
  prompt: "Fix any linting errors found in the file"
```

This is an instruction for YOU to execute. Follow the prompt and use your available tools.

### State Management
- Use `store_result: "raw.some_path"` to store MCP tool results in workflow state
- Use `state_update` steps to manually set state values
- Reference stored results using template syntax: `{{ raw.some_path.field }}`

Important:
- Always use your task_id when calling workflow tools
- Follow step instructions exactly
- Update state only as directed
- Report errors immediately
- Do not skip steps or make shortcuts"""

    SUB_AGENT_BASE = """You are a workflow sub-agent executing a specific task within a larger workflow.

Your responsibilities:
1. Call workflow.get_next_step with your unique task_id
2. Execute each step exactly as instructed
3. Update workflow state only as directed
4. Continue until workflow.get_next_step returns null

Key principles:
- Follow workflow instructions precisely
- Use your assigned task_id for all workflow operations
- Do not modify state outside of directed updates
- Report any errors through workflow state or return to main agent
- Trust the workflow to provide all necessary context

Your task_id: {{ task_id }}
Workflow context: {{ context }}"""

    BATCH_PROCESSOR = """You are a batch processing sub-agent for a workflow system.

Your task: Process a batch of items according to workflow instructions.

Process:
1. Call workflow.get_next_step with task_id="{{ task_id }}"
2. The workflow will provide specific processing steps for your batch
3. Execute each step in sequence
4. Update shared state as instructed
5. Continue until workflow.get_next_step returns null

Your batch contains {{ batch_size }} items.
Batch context: {{ context }}

Remember:
- Process items according to workflow steps, not your own logic
- Use the exact task_id provided: {{ task_id }}
- Follow state update instructions precisely
- Continue execution by calling workflow.get_next_step"""

    QUALITY_CHECK_AGENT = """You are a quality assurance sub-agent for workflow execution.

Your role: Execute quality checks on a specific subset of work.

Workflow process:
1. Call workflow.get_next_step with task_id="{{ task_id }}"
2. Receive specific quality check instructions
3. Execute checks as directed by workflow steps
4. Record results in workflow state as instructed
5. Continue until workflow.get_next_step returns null

Quality scope: {{ scope }}
Check context: {{ context }}

Guidelines:
- Follow workflow-provided check procedures exactly
- Use task_id="{{ task_id }}" for all workflow calls
- Record findings only as directed by workflow steps
- Do not make assumptions about what to check
- Report issues through proper workflow channels"""

    ERROR_RECOVERY_AGENT = """You are an error recovery sub-agent for workflow systems.

Purpose: Handle error recovery for failed workflow steps.

Recovery process:
1. Call workflow.get_next_step with task_id="{{ task_id }}"
2. Receive specific recovery instructions from workflow
3. Execute recovery actions exactly as specified
4. Update state to reflect recovery progress
5. Continue until workflow indicates recovery is complete

Error context: {{ error_context }}
Recovery scope: {{ scope }}

Critical rules:
- Follow workflow recovery procedures only
- Use exact task_id: {{ task_id }}
- Do not attempt unauthorized fixes
- Update state only as workflow directs
- Escalate unrecoverable errors through workflow state or return to main agent"""

    @classmethod
    def _get_debug_note(cls) -> str:
        """Get debug mode note if enabled."""
        if os.getenv("AROMCP_WORKFLOW_DEBUG", "").lower() == "serial":
            return "\n🐛 DEBUG MODE: Execute as TODOs in main agent instead of spawning sub-agents. Process each item serially for easier debugging."
        return ""

    @classmethod
    def get_prompt(cls, prompt_type: str, context: dict[str, Any] | None = None) -> str:
        """Get a standard prompt with context variables replaced.

        Args:
            prompt_type: Type of prompt (e.g., "parallel_foreach", "batch_processor")
            context: Variables to substitute in the prompt

        Returns:
            Formatted prompt string
        """
        context = context or {}

        prompt_map = {
            "parallel_foreach": cls.PARALLEL_FOREACH,
            "sub_agent_base": cls.SUB_AGENT_BASE,
            "batch_processor": cls.BATCH_PROCESSOR,
            "quality_check": cls.QUALITY_CHECK_AGENT,
            "error_recovery": cls.ERROR_RECOVERY_AGENT,
        }

        prompt_template = prompt_map.get(prompt_type)
        if not prompt_template:
            raise ValueError(f"Unknown prompt type: {prompt_type}")

        # Add debug note if in debug mode
        context = dict(context)  # Make a copy
        if "debug_note" not in context:
            context["debug_note"] = cls._get_debug_note()

        # Simple template replacement for {{ variable }} patterns
        formatted_prompt = prompt_template
        for key, value in context.items():
            placeholder = f"{{{{ {key} }}}}"
            formatted_prompt = formatted_prompt.replace(placeholder, str(value))

        return formatted_prompt

    @classmethod
    def get_available_prompts(cls) -> list[str]:
        """Get list of available prompt types."""
        return ["parallel_foreach", "sub_agent_base", "batch_processor", "quality_check", "error_recovery"]

    @classmethod
    def create_sub_agent_prompt(
        cls,
        task_id: str,
        task_type: str = "parallel_foreach",
        context: dict[str, Any] | None = None,
        custom_instructions: str | None = None,
    ) -> str:
        """Create a complete sub-agent prompt with context.

        Args:
            task_id: Unique identifier for the sub-agent task
            task_type: Type of task (determines base prompt)
            context: Additional context variables
            custom_instructions: Custom instructions to append

        Returns:
            Complete formatted prompt
        """
        base_context = {"task_id": task_id}
        if context:
            base_context.update(context)

        prompt = cls.get_prompt(task_type, base_context)

        if custom_instructions:
            prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"

        return prompt


class PromptValidator:
    """Validates prompt templates and context variables."""

    @staticmethod
    def validate_prompt_context(prompt_template: str, context: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate that all required context variables are provided.

        Returns:
            (is_valid, missing_variables)
        """
        import re

        # Find all {{ variable }} patterns
        placeholders = re.findall(r"\{\{\s*(\w+)\s*\}\}", prompt_template)
        missing = [var for var in placeholders if var not in context]

        return len(missing) == 0, missing

    @staticmethod
    def preview_prompt(prompt_type: str, context: dict[str, Any]) -> dict[str, Any]:
        """Preview how a prompt will look with given context.

        Returns:
            {
                "formatted_prompt": str,
                "is_valid": bool,
                "missing_variables": list[str],
                "used_variables": list[str]
            }
        """
        try:
            prompt_template = getattr(StandardPrompts, prompt_type.upper())
        except AttributeError:
            return {
                "error": f"Unknown prompt type: {prompt_type}",
                "is_valid": False,
                "missing_variables": [],
                "used_variables": [],
            }

        is_valid, missing = PromptValidator.validate_prompt_context(prompt_template, context)

        # Find used variables
        import re

        all_vars = re.findall(r"\{\{\s*(\w+)\s*\}\}", prompt_template)
        used_vars = [var for var in all_vars if var in context]

        formatted_prompt = StandardPrompts.get_prompt(prompt_type, context) if is_valid else prompt_template

        return {
            "formatted_prompt": formatted_prompt,
            "is_valid": is_valid,
            "missing_variables": missing,
            "used_variables": used_vars,
        }
