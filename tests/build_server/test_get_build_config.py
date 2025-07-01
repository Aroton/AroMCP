"""Tests for get_build_config tool in Build Tools."""

import json
import tempfile
import pytest
from pathlib import Path

from aromcp.build_server.tools.get_build_config import get_build_config_impl


class TestGetBuildConfig:
    """Test class for get_build_config tool."""

    def test_basic_functionality(self):
        """Test basic config extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a package.json
            package_json = {
                "name": "test-project",
                "version": "1.0.0",
                "scripts": {
                    "build": "next build",
                    "dev": "next dev",
                    "test": "jest"
                },
                "dependencies": {
                    "next": "^13.0.0",
                    "react": "^18.0.0"
                },
                "devDependencies": {
                    "typescript": "^4.0.0",
                    "jest": "^28.0.0"
                }
            }
            
            (temp_path / "package.json").write_text(json.dumps(package_json, indent=2))
            
            # Create tsconfig.json to trigger typescript detection
            tsconfig = {"compilerOptions": {"target": "es2020"}}
            (temp_path / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2))
            
            # Create jest config to trigger jest detection
            jest_config = {"testEnvironment": "node"}
            (temp_path / "jest.config.js").write_text(f"module.exports = {json.dumps(jest_config)}")
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "config_files" in result["data"]
            assert "detected_tools" in result["data"]
            assert "build_info" in result["data"]
            
            # Check package.json was parsed
            assert "package.json" in result["data"]["config_files"]
            config = result["data"]["config_files"]["package.json"]
            assert config["type"] == "json"
            assert config["content"]["name"] == "test-project"
            
            # Check tool detection
            detected_tools = result["data"]["detected_tools"]
            assert "npm" in detected_tools
            assert "node" in detected_tools
            assert "nextjs" in detected_tools
            assert "typescript" in detected_tools
            assert "jest" in detected_tools

    def test_typescript_config(self):
        """Test TypeScript config extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            tsconfig = {
                "compilerOptions": {
                    "target": "es2018",
                    "module": "esnext",
                    "lib": ["dom", "es2018"],
                    "strict": True,
                    "outDir": "./dist"
                },
                "include": ["src/**/*"],
                "exclude": ["node_modules"]
            }
            
            (temp_path / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2))
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "tsconfig.json" in result["data"]["config_files"]
            
            config = result["data"]["config_files"]["tsconfig.json"]
            assert config["type"] == "json"
            assert config["content"]["compilerOptions"]["target"] == "es2018"
            
            # Check TypeScript tool detection
            assert "typescript" in result["data"]["detected_tools"]
            
            # Check build info extraction
            ts_info = result["data"]["build_info"]["typescript"]
            assert ts_info["target"] == "es2018"
            assert ts_info["module"] == "esnext"
            assert ts_info["strict"] is True
            assert ts_info["outDir"] == "./dist"

    def test_next_config_detection(self):
        """Test Next.js config detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create next.config.js
            next_config = """/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
}

module.exports = nextConfig"""
            
            (temp_path / "next.config.js").write_text(next_config)
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "next.config.js" in result["data"]["config_files"]
            assert "nextjs" in result["data"]["detected_tools"]

    def test_eslint_config_detection(self):
        """Test ESLint config detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            eslint_config = {
                "extends": ["eslint:recommended", "@typescript-eslint/recommended"],
                "parser": "@typescript-eslint/parser",
                "rules": {
                    "no-console": "warn"
                }
            }
            
            (temp_path / ".eslintrc.json").write_text(json.dumps(eslint_config, indent=2))
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert ".eslintrc.json" in result["data"]["config_files"]
            assert "eslint" in result["data"]["detected_tools"]

    def test_custom_config_files(self):
        """Test extraction with custom config file list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create custom config
            custom_config = {"custom": "config"}
            (temp_path / "custom.json").write_text(json.dumps(custom_config))
            
            result = get_build_config_impl(
                project_root=temp_dir,
                config_files=["custom.json"]
            )
            
            assert "data" in result
            assert "custom.json" in result["data"]["config_files"]
            assert result["data"]["config_files"]["custom.json"]["content"]["custom"] == "config"

    def test_non_json_files(self):
        """Test handling of non-JSON config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Dockerfile
            dockerfile_content = """FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production"""
            
            (temp_path / "Dockerfile").write_text(dockerfile_content)
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "Dockerfile" in result["data"]["config_files"]
            assert "docker" in result["data"]["detected_tools"]
            
            config = result["data"]["config_files"]["Dockerfile"]
            assert config["type"] == "text"
            assert "FROM node:16-alpine" in config["content"]

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create invalid JSON
            (temp_path / "package.json").write_text("{ invalid json }")
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "package.json" in result["data"]["config_files"]
            
            config = result["data"]["config_files"]["package.json"]
            assert config["type"] == "text"
            assert "parse_error" in config
            assert config["parse_error"] == "Invalid JSON"

    def test_empty_directory(self):
        """Test behavior with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert result["data"]["config_files"] == {}
            assert result["data"]["detected_tools"] == []
            assert result["data"]["build_info"] == {}

    def test_large_file_truncation(self):
        """Test that large files are truncated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a large text file
            large_content = "x" * 2000  # Larger than 1000 char limit
            (temp_path / "large.txt").write_text(large_content)
            
            result = get_build_config_impl(
                project_root=temp_dir,
                config_files=["large.txt"]
            )
            
            assert "data" in result
            assert "large.txt" in result["data"]["config_files"]
            
            config = result["data"]["config_files"]["large.txt"]
            assert len(config["content"]) == 1000  # Truncated

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = get_build_config_impl(project_root="/../../invalid/path")
        
        # The function doesn't fail on invalid paths - it just returns empty results
        assert "data" in result
        assert result["data"]["config_files"] == {}
        assert result["data"]["detected_tools"] == []

    def test_rust_project_detection(self):
        """Test Rust project detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            cargo_toml = """[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0" """
            
            (temp_path / "Cargo.toml").write_text(cargo_toml)
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "Cargo.toml" in result["data"]["config_files"]
            assert "rust" in result["data"]["detected_tools"]

    def test_python_project_detection(self):
        """Test Python project detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            pyproject_toml = """[build-system]
requires = ["setuptools", "wheel"]

[project]
name = "test-project"
version = "0.1.0" """
            
            (temp_path / "pyproject.toml").write_text(pyproject_toml)
            
            result = get_build_config_impl(project_root=temp_dir)
            
            assert "data" in result
            assert "pyproject.toml" in result["data"]["config_files"]
            assert "python" in result["data"]["detected_tools"]