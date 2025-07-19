"""Simple demonstration of sub-agent prompt with inputs appended."""


def test_client_side_replacement_demo():
    """Demonstrate how the client would replace SUB_AGENT_INPUTS."""

    # This is the prompt template we generate (from the test above)
    prompt_template = """You are a workflow sub-agent. Your role is to execute a specific task by following the
workflow system.

Process:
1. Call workflow.get_next_step with your task_id to get the next atomic action
2. Execute the action exactly as instructed
3. Update state as directed in the step
4. Mark the step complete
5. Repeat until get_next_step returns null

The workflow will guide you through all necessary steps. Simply follow the instructions
provided by each step. Do not make assumptions about what needs to be done - the
workflow will tell you everything.

Context: You are processing item {{ item }} (index {{ index }} of {{ total }}).
Your task_id is: {{ task_id }}

Important:
- Always use your task_id when calling workflow tools
- Follow step instructions exactly
- Update state only as directed
- Report errors immediately
- Do not skip steps or make shortcuts

```json
{
  "inputs": {{ SUB_AGENT_INPUTS }}
}
```

Use the inputs above to execute your workflow steps."""

    # This is the task inputs that would be provided (from the test above)
    task_inputs = {"file_path": "test1.ts"}

    # Client-side replacement
    import json

    inputs_json = json.dumps(task_inputs, indent=2)
    final_prompt = prompt_template.replace("{{ SUB_AGENT_INPUTS }}", inputs_json)

    print("=== FINAL CLIENT PROMPT WITH INPUTS REPLACED ===")
    print(final_prompt)
    print("=" * 60)

    # Validate the replacement worked
    assert "{{ SUB_AGENT_INPUTS }}" not in final_prompt
    assert '"file_path": "test1.ts"' in final_prompt
    assert "```json" in final_prompt

    print("✅ Client-side input replacement demonstration successful!")
    print("✅ The sub-agent prompt correctly includes appended inputs!")


if __name__ == "__main__":
    test_client_side_replacement_demo()
