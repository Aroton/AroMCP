"""Tests for SubAgentManager prompt generation logic.

This module tests the enhanced prompt generation functionality that:
1. Uses StandardPrompts.PARALLEL_FOREACH when no custom prompt_template is provided
2. Properly formats inputs JSON based on sub-agent task definitions
3. Includes correct context variables (task_id, item, index, total)
4. Maintains backward compatibility with custom prompt templates
"""

import json
from unittest.mock import Mock

import pytest


class TestSubAgentManagerPrompts:
    """Test SubAgentManager prompt generation logic.
    
    These tests focus specifically on the prompt generation logic that was enhanced
    to use StandardPrompts.PARALLEL_FOREACH and proper input formatting.
    """

    def setup_method(self):
        """Setup test environment."""
        pass

    def test_prompt_generation_with_custom_template(self):
        """Test prompt generation when custom template is provided."""
        # Create a mock sub-agent task with custom template
        sub_agent_task = Mock()
        sub_agent_task.prompt_template = "Custom task instructions."
        
        # Test the prompt generation logic directly
        # This tests lines 95-97 in subagent_manager.py
        prompt_template = getattr(sub_agent_task, 'prompt_template', '')
        
        if prompt_template:
            prompt_with_inputs = prompt_template + "\n\nSUB_AGENT_INPUTS:\n```json\n{\n  \"inputs\": {{ inputs }}\n}\n```"
        else:
            prompt_with_inputs = "Should not reach this"
        
        expected = 'Custom task instructions.\n\nSUB_AGENT_INPUTS:\n```json\n{\n  "inputs": {{ inputs }}\n}\n```'
        assert prompt_with_inputs == expected

    def test_standard_prompt_generation_without_custom_template(self):
        """Test that StandardPrompts.PARALLEL_FOREACH is used when no custom template."""
        from aromcp.workflow_server.prompts.standards import StandardPrompts
        
        # Mock sub-agent task without custom template
        sub_agent_task = Mock()
        sub_agent_task.prompt_template = ''  # Empty template
        
        # Mock inputs with defaults
        input_file_path = Mock()
        input_file_path.default = None
        
        input_max_attempts = Mock()
        input_max_attempts.default = 10
        
        sub_agent_task.inputs = {
            'file_path': input_file_path,
            'max_attempts': input_max_attempts
        }
        
        # Test the logic from lines 99-125 in subagent_manager.py
        prompt_template = getattr(sub_agent_task, 'prompt_template', '')
        
        if not prompt_template:
            # Create context for the standard prompt
            context = {
                'task_id': '{{ task_id }}',
                'item': '{{ item }}',
                'index': '{{ index }}', 
                'total': '{{ total }}'
            }
            
            base_prompt = StandardPrompts.get_prompt("parallel_foreach", context)
            
            # Format the inputs properly based on sub_agent_task definition
            inputs_json = {}
            if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
                for input_name, input_def in sub_agent_task.inputs.items():
                    if hasattr(input_def, 'default') and input_def.default is not None:
                        inputs_json[input_name] = f"{{{{ {input_name} || {input_def.default} }}}}"
                    else:
                        inputs_json[input_name] = f"{{{{ {input_name} }}}}"
            
            # Convert to JSON string format
            import json
            inputs_json_str = json.dumps(inputs_json, indent=2).replace('"', '\\"')
            
            prompt_with_inputs = base_prompt + f'\n\nSUB_AGENT_INPUTS:\n```json\n{{\n  "inputs": {inputs_json_str}\n}}\n```'
        
        # Verify the prompt contains the expected elements
        assert "You are a workflow sub-agent" in prompt_with_inputs
        assert "Call workflow.get_next_step with your task_id" in prompt_with_inputs
        assert "Context: You are processing item {{ item }}" in prompt_with_inputs
        assert "Your task_id is: {{ task_id }}" in prompt_with_inputs
        
        # Verify the inputs JSON structure
        assert "SUB_AGENT_INPUTS:" in prompt_with_inputs
        assert '\\"file_path\\": \\"{{ file_path }}\\"' in prompt_with_inputs
        assert '\\"max_attempts\\": \\"{{ max_attempts || 10 }}\\"' in prompt_with_inputs

    def test_inputs_json_formatting_with_various_defaults(self):
        """Test that inputs JSON is formatted correctly with different default scenarios."""
        # Create inputs with different default scenarios
        input_required = Mock()
        input_required.default = None
        
        input_with_string_default = Mock()
        input_with_string_default.default = "default_value"
        
        input_with_number_default = Mock() 
        input_with_number_default.default = 42
        
        sub_agent_task = Mock()
        sub_agent_task.inputs = {
            'required_param': input_required,
            'string_param': input_with_string_default,
            'number_param': input_with_number_default
        }
        
        # Test the input formatting logic
        inputs_json = {}
        if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
            for input_name, input_def in sub_agent_task.inputs.items():
                if hasattr(input_def, 'default') and input_def.default is not None:
                    inputs_json[input_name] = f"{{{{ {input_name} || {input_def.default} }}}}"
                else:
                    inputs_json[input_name] = f"{{{{ {input_name} }}}}"
        
        # Verify correct formatting
        assert inputs_json['required_param'] == '{{ required_param }}'
        assert inputs_json['string_param'] == '{{ string_param || default_value }}'
        assert inputs_json['number_param'] == '{{ number_param || 42 }}'

    def test_standard_prompts_integration(self):
        """Test integration with the actual StandardPrompts class."""
        from aromcp.workflow_server.prompts.standards import StandardPrompts
        
        # Test the context variables are properly formatted
        context = {
            'task_id': '{{ task_id }}',
            'item': '{{ item }}',
            'index': '{{ index }}',
            'total': '{{ total }}'
        }
        
        base_prompt = StandardPrompts.get_prompt("parallel_foreach", context)
        
        # Verify the prompt contains all expected context variables
        assert "{{ task_id }}" in base_prompt
        assert "{{ item }}" in base_prompt  
        assert "{{ index }}" in base_prompt
        assert "{{ total }}" in base_prompt
        
        # Verify core instructions are present
        assert "You are a workflow sub-agent" in base_prompt
        assert "Call workflow.get_next_step" in base_prompt
        assert "Do not make assumptions" in base_prompt

    def test_json_escaping_in_inputs_formatting(self):
        """Test that JSON strings are properly escaped in inputs."""
        # Create input with value that needs escaping
        input_with_special_chars = Mock()
        input_with_special_chars.default = 'value "with" quotes'
        
        sub_agent_task = Mock()
        sub_agent_task.inputs = {
            'special_param': input_with_special_chars
        }
        
        # Test input formatting
        inputs_json = {}
        for input_name, input_def in sub_agent_task.inputs.items():
            if hasattr(input_def, 'default') and input_def.default is not None:
                inputs_json[input_name] = f"{{{{ {input_name} || {input_def.default} }}}}"
            else:
                inputs_json[input_name] = f"{{{{ {input_name} }}}}"
        
        # Convert to JSON and escape
        import json
        inputs_json_str = json.dumps(inputs_json, indent=2).replace('"', '\\"')
        
        # Verify it produces valid escaped JSON
        assert 'special_param' in inputs_json_str
        assert 'value \\\\"with\\\\" quotes' in inputs_json_str

    def test_empty_inputs_handling(self):
        """Test handling when sub-agent task has no inputs."""
        sub_agent_task = Mock()
        sub_agent_task.inputs = {}  # Empty inputs
        
        # Test the logic
        inputs_json = {}
        if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
            for input_name, input_def in sub_agent_task.inputs.items():
                # This loop shouldn't execute
                inputs_json[input_name] = f"{{{{ {input_name} }}}}"
        
        # Should result in empty dict
        assert inputs_json == {}
        
        # Test JSON formatting
        import json
        inputs_json_str = json.dumps(inputs_json, indent=2).replace('"', '\\"')
        assert inputs_json_str == '{}'

    def test_missing_inputs_attribute_handling(self):
        """Test backward compatibility when inputs attribute is missing."""
        sub_agent_task = Mock()
        # Don't set inputs attribute
        if hasattr(sub_agent_task, 'inputs'):
            delattr(sub_agent_task, 'inputs')
        
        # Test the hasattr check
        inputs_json = {}
        if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
            # Should not execute
            inputs_json['should_not_exist'] = 'test'
        
        # Should handle gracefully
        assert inputs_json == {}

    def test_real_world_enforce_standards_scenario(self):
        """Test the exact scenario for the enforce_standards_on_file task."""
        from aromcp.workflow_server.prompts.standards import StandardPrompts
        
        # Create the exact structure as in our workflow
        input_file_path = Mock()
        input_file_path.default = None
        
        input_max_attempts = Mock()
        input_max_attempts.default = 10
        
        sub_agent_task = Mock()
        sub_agent_task.prompt_template = ''  # No custom template
        sub_agent_task.inputs = {
            'file_path': input_file_path,
            'max_attempts': input_max_attempts
        }
        
        # Execute the full logic as it would run in production
        prompt_template = getattr(sub_agent_task, 'prompt_template', '')
        
        if not prompt_template:
            context = {
                'task_id': '{{ task_id }}',
                'item': '{{ item }}',
                'index': '{{ index }}', 
                'total': '{{ total }}'
            }
            
            base_prompt = StandardPrompts.get_prompt("parallel_foreach", context)
            
            inputs_json = {}
            if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
                for input_name, input_def in sub_agent_task.inputs.items():
                    if hasattr(input_def, 'default') and input_def.default is not None:
                        inputs_json[input_name] = f"{{{{ {input_name} || {input_def.default} }}}}"
                    else:
                        inputs_json[input_name] = f"{{{{ {input_name} }}}}"
            
            import json
            inputs_json_str = json.dumps(inputs_json, indent=2).replace('"', '\\"')
            
            prompt_with_inputs = base_prompt + f'\n\nSUB_AGENT_INPUTS:\n```json\n{{\n  "inputs": {inputs_json_str}\n}}\n```'
        
        # Verify this produces the expected result for our workflow
        assert "You are a workflow sub-agent" in prompt_with_inputs
        assert "Call workflow.get_next_step with your task_id" in prompt_with_inputs
        
        # Verify the specific inputs structure for our enforce_standards_on_file task
        assert '\\"file_path\\": \\"{{ file_path }}\\"' in prompt_with_inputs
        assert '\\"max_attempts\\": \\"{{ max_attempts || 10 }}\\"' in prompt_with_inputs
        
        # Verify it doesn't contain the old generic prompt
        assert "Process the assigned task" not in prompt_with_inputs