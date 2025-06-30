"""Get target files implementation."""

import os
import subprocess
import time
from pathlib import Path
from typing import Any


def get_target_files_impl(
    status: str = "working",
    patterns: list[str] | None = None,
    project_root: str = "."
) -> dict[str, Any]:
    """List files based on git status or path patterns.
    
    Args:
        status: Git status filter - "working", "staged", "branch", "commit", or "pattern"
        patterns: File patterns to match (used when status="pattern")
        project_root: Root directory of the project
        
    Returns:
        Dictionary with file list and metadata
    """
    start_time = time.time()

    try:
        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root does not exist: {project_root}"
                }
            }

        os.chdir(project_path)

        files = []

        if status == "pattern":
            if not patterns:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "Patterns required when status='pattern'"
                    }
                }
            files = _get_files_by_pattern(patterns, project_path)

        elif status in ["working", "staged", "branch", "commit"]:
            # Check if we're in a git repository
            try:
                subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "Not in a git repository"
                    }
                }

            files = _get_files_by_git_status(status)

        else:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Invalid status: {status}. Must be one of: working, staged, branch, commit, pattern"
                }
            }

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": {
                "files": files,
                "count": len(files),
                "status_filter": status,
                "patterns": patterns
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to get target files: {str(e)}"
            }
        }


def _get_files_by_pattern(patterns: list[str], project_path: Path) -> list[dict[str, Any]]:
    """Get files matching glob patterns."""
    files = []

    for pattern in patterns:
        # Use pathlib's glob for pattern matching
        if pattern.startswith('/'):
            # Absolute pattern within project
            glob_path = project_path / pattern[1:]
            matches = list(project_path.glob(pattern[1:]))
        else:
            # Relative pattern
            matches = list(project_path.rglob(pattern))

        for match in matches:
            if match.is_file():
                rel_path = match.relative_to(project_path)
                stat = match.stat()
                files.append({
                    "path": str(rel_path),
                    "absolute_path": str(match),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "pattern": pattern
                })

    # Remove duplicates based on path
    seen_paths = set()
    unique_files = []
    for file_info in files:
        if file_info["path"] not in seen_paths:
            seen_paths.add(file_info["path"])
            unique_files.append(file_info)

    return sorted(unique_files, key=lambda x: x["path"])


def _get_files_by_git_status(status: str) -> list[dict[str, Any]]:
    """Get files based on git status."""
    files = []

    try:
        if status == "working":
            # Get modified, added, deleted files in working directory
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                git_status = line[:2]
                file_path = line[3:]

                # Skip renamed files (they have -> in the path)
                if ' -> ' in file_path:
                    # Handle renames: "old_path -> new_path"
                    old_path, new_path = file_path.split(' -> ')
                    files.append({
                        "path": new_path.strip(),
                        "git_status": git_status,
                        "status_description": _get_git_status_description(git_status),
                        "renamed_from": old_path.strip()
                    })
                else:
                    files.append({
                        "path": file_path,
                        "git_status": git_status,
                        "status_description": _get_git_status_description(git_status)
                    })

        elif status == "staged":
            # Get staged files
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-status"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) >= 2:
                    git_status = parts[0]
                    file_path = parts[1]
                    files.append({
                        "path": file_path,
                        "git_status": git_status,
                        "status_description": _get_git_status_description(git_status),
                        "staged": True
                    })

        elif status == "branch":
            # Get files different from main/master branch
            try:
                # Try to find the default branch
                result = subprocess.run(
                    ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                default_branch = result.stdout.strip().split('/')[-1]
            except subprocess.CalledProcessError:
                # Fallback to common branch names
                for branch in ["main", "master"]:
                    try:
                        subprocess.run(
                            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
                            capture_output=True,
                            check=True
                        )
                        default_branch = branch
                        break
                    except subprocess.CalledProcessError:
                        continue
                else:
                    default_branch = "HEAD~1"  # Fallback to previous commit

            result = subprocess.run(
                ["git", "diff", "--name-status", default_branch],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) >= 2:
                    git_status = parts[0]
                    file_path = parts[1]
                    files.append({
                        "path": file_path,
                        "git_status": git_status,
                        "status_description": _get_git_status_description(git_status),
                        "compared_to": default_branch
                    })

    except subprocess.CalledProcessError as e:
        raise Exception(f"Git command failed: {e}")

    return files


def _get_git_status_description(status_code: str) -> str:
    """Convert git status codes to human-readable descriptions."""
    status_map = {
        'A': 'Added',
        'M': 'Modified',
        'D': 'Deleted',
        'R': 'Renamed',
        'C': 'Copied',
        'U': 'Unmerged',
        '??': 'Untracked',
        'AM': 'Added, Modified',
        'MM': 'Modified, Modified',
        'AD': 'Added, Deleted',
        'MD': 'Modified, Deleted'
    }
    return status_map.get(status_code, f'Unknown ({status_code})')
