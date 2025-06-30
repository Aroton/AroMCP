"""Load documents by pattern implementation."""

import time
from pathlib import Path
from typing import Any

import chardet


def load_documents_by_pattern_impl(
    patterns: list[str],
    project_root: str = ".",
    max_file_size: int = 1024 * 1024,  # 1MB default
    encoding: str = "auto"
) -> dict[str, Any]:
    """Load multiple documents matching glob patterns.
    
    Args:
        patterns: List of glob patterns to match files
        project_root: Root directory of the project
        max_file_size: Maximum file size to load (bytes)
        encoding: File encoding ("auto", "utf-8", etc.)
        
    Returns:
        Dictionary with loaded documents and metadata
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

        if not patterns:
            return {
                "data": {
                    "documents": {},
                    "summary": {
                        "total_matched": 0,
                        "total_loaded": 0,
                        "total_size": 0,
                        "patterns_used": []
                    }
                }
            }

        # Find all matching files
        matched_files = {}
        for pattern in patterns:
            pattern_matches = _find_files_by_pattern(pattern, project_path)
            for file_path, file_info in pattern_matches.items():
                if file_path not in matched_files:
                    matched_files[file_path] = file_info
                    matched_files[file_path]["patterns"] = [pattern]
                else:
                    matched_files[file_path]["patterns"].append(pattern)

        # Load documents
        documents = {}
        errors = []
        total_size = 0
        loaded_count = 0

        for rel_path, file_info in matched_files.items():
            try:
                abs_path = file_info["abs_path"]
                file_size = file_info["size"]

                # Check file size
                if file_size > max_file_size:
                    errors.append({
                        "file": rel_path,
                        "error": f"File too large ({file_size} bytes > {max_file_size} bytes)",
                        "size": file_size
                    })
                    continue

                # Skip binary files based on extension
                if _is_likely_binary(abs_path):
                    errors.append({
                        "file": rel_path,
                        "error": "Skipped binary file",
                        "type": "binary"
                    })
                    continue

                # Load file content
                content, detected_encoding = _load_file_content(abs_path, encoding)

                documents[rel_path] = {
                    "content": content,
                    "encoding": detected_encoding,
                    "size": file_size,
                    "modified": file_info["modified"],
                    "patterns": file_info["patterns"],
                    "type": _classify_document_type(abs_path),
                    "lines": len(content.splitlines()) if content else 0,
                    "words": len(content.split()) if content else 0
                }

                total_size += file_size
                loaded_count += 1

            except Exception as e:
                errors.append({
                    "file": rel_path,
                    "error": str(e)
                })

        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "data": {
                "documents": documents,
                "summary": {
                    "total_matched": len(matched_files),
                    "total_loaded": loaded_count,
                    "total_failed": len(errors),
                    "total_size": total_size,
                    "patterns_used": patterns,
                    "document_types": _get_document_type_summary(documents)
                }
            }
        }

        if errors:
            result["data"]["errors"] = errors

        return result

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to load documents: {str(e)}"
            }
        }


def _find_files_by_pattern(pattern: str, project_path: Path) -> dict[str, dict[str, Any]]:
    """Find files matching a single pattern."""
    files = {}

    try:
        # Handle different pattern types
        if pattern.startswith('/'):
            # Absolute pattern within project
            matches = project_path.glob(pattern[1:])
        else:
            # Relative pattern - use rglob for recursive matching
            if '**' in pattern:
                matches = project_path.glob(pattern)
            else:
                matches = project_path.rglob(pattern)

        for match in matches:
            if match.is_file():
                try:
                    rel_path = match.relative_to(project_path)
                    stat = match.stat()

                    files[str(rel_path)] = {
                        "abs_path": match,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    }
                except (OSError, ValueError):
                    # Skip files we can't access or that are outside project
                    continue

        return files

    except Exception:
        return {}


def _is_likely_binary(file_path: Path) -> bool:
    """Check if a file is likely binary based on extension."""

    # Common binary file extensions
    binary_extensions = {
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp',
        # Audio/Video
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.ogg',
        # Archives
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
        # Executables
        '.exe', '.dll', '.so', '.dylib', '.bin',
        # Documents (binary formats)
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Fonts
        '.ttf', '.otf', '.woff', '.woff2',
        # Other
        '.pyc', '.pyo', '.class', '.o', '.obj'
    }

    return file_path.suffix.lower() in binary_extensions


def _load_file_content(file_path: Path, encoding: str = "auto") -> tuple[str, str]:
    """Load file content with encoding detection."""

    # Read raw bytes first
    raw_content = file_path.read_bytes()

    if len(raw_content) == 0:
        return "", "utf-8"

    # Check for binary content by looking for null bytes
    if b'\x00' in raw_content[:1024]:  # Check first 1KB
        raise ValueError("File appears to be binary")

    if encoding == "auto":
        # Try UTF-8 first (most common)
        try:
            content = raw_content.decode('utf-8')
            return content, "utf-8"
        except UnicodeDecodeError:
            pass

        # Use chardet for detection
        detected = chardet.detect(raw_content)
        detected_encoding = detected.get('encoding', 'utf-8')
        confidence = detected.get('confidence', 0)

        # If confidence is low, try common encodings
        if confidence < 0.8:
            for fallback_encoding in ['iso-8859-1', 'windows-1252', 'ascii']:
                try:
                    content = raw_content.decode(fallback_encoding)
                    return content, fallback_encoding
                except UnicodeDecodeError:
                    continue

        # Use detected encoding
        try:
            content = raw_content.decode(detected_encoding)
            return content, detected_encoding
        except (UnicodeDecodeError, TypeError):
            # Last resort: decode with errors='replace'
            content = raw_content.decode('utf-8', errors='replace')
            return content, "utf-8-with-errors"

    else:
        # Use specified encoding
        try:
            content = raw_content.decode(encoding)
            return content, encoding
        except UnicodeDecodeError:
            # Fallback with error replacement
            content = raw_content.decode(encoding, errors='replace')
            return content, f"{encoding}-with-errors"


def _classify_document_type(file_path: Path) -> str:
    """Classify document type based on file extension."""

    extension = file_path.suffix.lower()

    # Programming languages
    code_extensions = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'react',
        '.tsx': 'react-typescript',
        '.vue': 'vue',
        '.svelte': 'svelte',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.kt': 'kotlin',
        '.swift': 'swift',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c-header',
        '.hpp': 'cpp-header',
        '.cs': 'csharp',
        '.php': 'php',
        '.rb': 'ruby',
        '.scala': 'scala',
        '.clj': 'clojure',
        '.hs': 'haskell'
    }

    # Markup and data formats
    markup_extensions = {
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'xml',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'config',
        '.conf': 'config'
    }

    # Documentation
    doc_extensions = {
        '.md': 'markdown',
        '.rst': 'restructuredtext',
        '.txt': 'text',
        '.rtf': 'rtf',
        '.tex': 'latex'
    }

    # Stylesheets
    style_extensions = {
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.styl': 'stylus'
    }

    # Scripts and configs
    script_extensions = {
        '.sh': 'shell',
        '.bash': 'bash',
        '.zsh': 'zsh',
        '.fish': 'fish',
        '.ps1': 'powershell',
        '.bat': 'batch',
        '.cmd': 'batch'
    }

    # Check each category
    for category_map in [code_extensions, markup_extensions, doc_extensions,
                        style_extensions, script_extensions]:
        if extension in category_map:
            return category_map[extension]

    # Special cases based on filename
    filename = file_path.name.lower()

    if filename in ['dockerfile', 'dockerfile.dev', 'dockerfile.prod']:
        return 'dockerfile'
    elif filename in ['makefile', 'gnumakefile']:
        return 'makefile'
    elif filename in ['rakefile']:
        return 'rakefile'
    elif filename.startswith('.env'):
        return 'environment'
    elif filename in ['package.json', 'composer.json', 'cargo.toml', 'pyproject.toml']:
        return 'package-config'
    elif filename in ['readme', 'readme.txt'] or filename.startswith('readme.'):
        return 'readme'
    elif filename in ['license', 'licence'] or filename.startswith(('license.', 'licence.')):
        return 'license'
    elif filename.startswith('.git'):
        return 'git-config'

    # Default
    return 'unknown'


def _get_document_type_summary(documents: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Get summary of document types."""
    type_counts = {}

    for doc_info in documents.values():
        doc_type = doc_info.get("type", "unknown")
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    return type_counts
