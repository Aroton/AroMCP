"""
Write or update an AI context section in the context file.

This tool manages AI context sections with markers to enable updates on regeneration.
"""

import os
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from ...utils.json_parameter_middleware import json_convert
from ...filesystem_server._security import get_project_root, validate_file_path


def write_ai_context_section_impl(
    context_content: str,
    section_id: str,
    section_title: str,
    context_file: str = ".aromcp/generated-rules/ai-context.md",
    project_root: str | None = None
) -> dict[str, Any]:
    """Write or update an AI context section in the context file.
    
    Uses section markers to enable updates on regeneration:
    <!-- aromcp:section:start:component-isolation -->
    ... content ...
    <!-- aromcp:section:end:component-isolation -->
    
    Args:
        context_content: The context content to write
        section_id: Unique identifier for the section
        section_title: Human-readable title for the section
        context_file: Path to AI context file
        project_root: Project root directory (auto-resolved if None)
        
    Returns:
        Dict with write operation results
    """
    if project_root is None:
        project_root = get_project_root()
        
    try:
        # Validate inputs
        if not context_content or not context_content.strip():
            return {"error": {"code": "INVALID_INPUT", "message": "Context content cannot be empty"}}
            
        if not section_id or not _is_valid_section_id(section_id):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid section ID format"}}
            
        if not section_title or not section_title.strip():
            return {"error": {"code": "INVALID_INPUT", "message": "Section title cannot be empty"}}
            
        # Get full context file path
        full_context_path = os.path.join(project_root, context_file)
        context_dir = os.path.dirname(full_context_path)
        
        # Create directory if it doesn't exist
        os.makedirs(context_dir, exist_ok=True)
        
        # Validate path
        validation_result = validate_file_path(full_context_path, project_root)
        if not validation_result["valid"]:
            return {"error": {"code": "PERMISSION_DENIED", "message": validation_result["error"]}}
            
        # Load existing content or create new file
        existing_content = ""
        if os.path.exists(full_context_path):
            with open(full_context_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
                
        # Update or add section
        updated_content = _update_section_in_content(
            existing_content, section_id, section_title, context_content
        )
        
        # Write updated content
        with open(full_context_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
        # Get file stats
        file_stats = os.stat(full_context_path)
        
        return {
            "data": {
                "section_id": section_id,
                "section_title": section_title,
                "file_path": context_file,
                "absolute_path": full_context_path,
                "file_size": file_stats.st_size,
                "updated_at": _get_timestamp(),
                "action": "updated" if section_id in existing_content else "created",
                "success": True
            }
        }
        
    except Exception as e:
        return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to write AI context section: {str(e)}"}}


def _is_valid_section_id(section_id: str) -> bool:
    """Validate section ID format."""
    import re
    # Section ID should be lowercase with hyphens, no special characters
    return bool(re.match(r'^[a-z0-9-]+$', section_id)) and len(section_id) > 0


def _update_section_in_content(existing_content: str, section_id: str, section_title: str, new_content: str) -> str:
    """Update or add a section in the existing content."""
    # Create section markers
    start_marker = f"<!-- aromcp:section:start:{section_id} -->"
    end_marker = f"<!-- aromcp:section:end:{section_id} -->"
    
    # Create new section content
    section_content = f"""{start_marker}
## {section_title}

{new_content.strip()}

{end_marker}"""
    
    # Check if section already exists
    section_pattern = rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}"
    section_match = re.search(section_pattern, existing_content, re.DOTALL)
    
    if section_match:
        # Replace existing section
        updated_content = re.sub(section_pattern, section_content, existing_content, flags=re.DOTALL)
    else:
        # Add new section
        if existing_content.strip():
            # Add to end with proper spacing
            updated_content = existing_content.rstrip() + "\n\n" + section_content + "\n"
        else:
            # Create new file with header
            file_header = """# AI Context for Code Standards

This file contains coding standards and patterns that require human judgment and cannot be enforced through automated ESLint rules.

"""
            updated_content = file_header + section_content + "\n"
            
    return updated_content


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.now().isoformat()


def register_write_ai_context_section(mcp: FastMCP):
    """Register the write_ai_context_section tool with FastMCP."""
    
    @mcp.tool
    @json_convert
    def write_ai_context_section(
        context_content: str,
        section_id: str,
        section_title: str,
        context_file: str = ".aromcp/generated-rules/ai-context.md",
        project_root: str | None = None
    ) -> dict[str, Any]:
        """Write or update an AI context section in the context file.
        
        Uses section markers to enable updates on regeneration:
        <!-- aromcp:section:start:component-isolation -->
        ... content ...
        <!-- aromcp:section:end:component-isolation -->
        
        Args:
            context_content: The context content to write
            section_id: Unique identifier for the section
            section_title: Human-readable title for the section
            context_file: Path to AI context file
            project_root: Project root directory (auto-resolved if None)
            
        Returns:
            Dict with write operation results
        """
        return write_ai_context_section_impl(context_content, section_id, section_title, context_file, project_root)