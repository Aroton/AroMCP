"""Tests for load_documents_by_pattern implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import load_documents_by_pattern_impl


class TestLoadDocumentsByPattern:
    """Test load_documents_by_pattern implementation."""

    def test_load_markdown_files(self):
        """Test loading multiple markdown files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create markdown files
            docs = {
                "README.md": "# Project\n\nDescription",
                "docs/guide.md": "# Guide\n\nInstructions",
                "docs/api.md": "# API\n\nReference"
            }

            for file_path, content in docs.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            result = load_documents_by_pattern_impl(
                patterns=["**/*.md"],
                project_root=temp_dir
            )

            assert "data" in result
            documents = result["data"]["documents"]
            assert len(documents) == 3

            # Check document types
            for doc in documents.values():
                assert doc["type"] == "markdown"
                assert doc["lines"] > 0

    def test_file_size_limit(self):
        """Test file size limiting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create large file
            large_file = Path(temp_dir) / "large.txt"
            large_content = "x" * 2000  # 2KB content
            large_file.write_text(large_content)

            result = load_documents_by_pattern_impl(
                patterns=["*.txt"],
                project_root=temp_dir,
                max_file_size=1000  # 1KB limit
            )

            assert "data" in result
            assert len(result["data"]["documents"]) == 0
            assert "errors" in result["data"]
            assert any("too large" in error["error"] for error in result["data"]["errors"])

    def test_binary_file_detection(self):
        """Test binary file detection and skipping."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create binary-like file
            binary_file = Path(temp_dir) / "image.jpg"
            binary_file.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF')  # JPEG header

            result = load_documents_by_pattern_impl(
                patterns=["*.*"],
                project_root=temp_dir
            )

            assert "data" in result
            # Binary files should be skipped
            assert len(result["data"]["documents"]) == 0
            assert "errors" in result["data"]
            assert any("binary" in error["error"] for error in result["data"]["errors"])

    def test_encoding_auto_detection(self):
        """Test automatic encoding detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different encodings
            utf8_file = Path(temp_dir) / "utf8.md"
            utf8_file.write_text("# 标题\n\n内容", encoding="utf-8")

            ascii_file = Path(temp_dir) / "ascii.txt"
            ascii_file.write_text("Hello World", encoding="ascii")

            result = load_documents_by_pattern_impl(
                patterns=["*.md", "*.txt"],
                project_root=temp_dir,
                encoding="auto"
            )

            assert "data" in result
            assert len(result["data"]["documents"]) == 2
            assert result["data"]["documents"]["utf8.md"]["content"] == "# 标题\n\n内容"
            assert result["data"]["documents"]["ascii.txt"]["content"] == "Hello World"

    def test_explicit_encoding(self):
        """Test explicit encoding specification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Hello World", encoding="utf-8")

            result = load_documents_by_pattern_impl(
                patterns=["*.txt"],
                project_root=temp_dir,
                encoding="utf-8"
            )

            assert "data" in result
            assert len(result["data"]["documents"]) == 1
            assert result["data"]["documents"]["test.txt"]["encoding"] == "utf-8"

    def test_empty_patterns(self):
        """Test behavior with empty patterns list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = load_documents_by_pattern_impl(
                patterns=[],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["documents"]) == 0
            assert result["data"]["summary"]["total_matched"] == 0
            assert result["data"]["summary"]["patterns_used"] == []

    def test_document_type_classification(self):
        """Test document type classification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files of different types
            files = {
                "script.py": "print('hello')",
                "config.json": '{"key": "value"}',
                "README.md": "# Project",
                "style.css": "body { margin: 0; }",
                "Dockerfile": "FROM python:3.12",
                "package.json": '{"name": "test"}',
                ".env": "SECRET=value"
            }

            for path, content in files.items():
                (Path(temp_dir) / path).write_text(content)

            result = load_documents_by_pattern_impl(
                patterns=["*"],
                project_root=temp_dir
            )

            assert "data" in result
            documents = result["data"]["documents"]

            # Check type classification
            assert documents["script.py"]["type"] == "python"
            assert documents["config.json"]["type"] == "json"
            assert documents["README.md"]["type"] == "markdown"  # README.md is classified as markdown
            assert documents["style.css"]["type"] == "css"
            assert documents["Dockerfile"]["type"] == "dockerfile"
            assert documents["package.json"]["type"] == "json"  # Extension takes precedence over filename
            assert documents[".env"]["type"] == "environment"

    def test_document_metadata(self):
        """Test document metadata extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            content = "Line 1\nLine 2\nHello world test"
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text(content)

            result = load_documents_by_pattern_impl(
                patterns=["*.txt"],
                project_root=temp_dir
            )

            assert "data" in result
            doc = result["data"]["documents"]["test.txt"]

            assert doc["lines"] == 3
            assert doc["words"] == 7  # "Line", "1", "Line", "2", "Hello", "world", "test"
            assert doc["size"] == len(content.encode())
            assert "modified" in doc
            assert "patterns" in doc and "*.txt" in doc["patterns"]

    def test_multiple_pattern_matches(self):
        """Test files matching multiple patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file that matches multiple patterns
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("print('hello')")

            result = load_documents_by_pattern_impl(
                patterns=["*.py", "test.*", "**/*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["documents"]) == 1  # Should not duplicate

            doc = result["data"]["documents"]["test.py"]
            assert len(doc["patterns"]) == 3  # Should track all matching patterns
            assert set(doc["patterns"]) == {"*.py", "test.*", "**/*.py"}
