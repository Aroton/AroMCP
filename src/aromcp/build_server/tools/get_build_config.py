"""Get build config tool implementation for Build Tools."""

import json
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path


def get_build_config_impl(
    project_root: str | None = None,
    config_files: list[str] | None = None
) -> dict[str, Any]:
    """Extract build configuration from various sources.
    
    Args:
        project_root: Directory to search for config files (defaults to MCP_FILE_ROOT)
        config_files: Specific config files to read (defaults to common build configs)
        
    Returns:
        Dictionary with extracted configuration and detected tools
    """
    try:
        # Resolve project root
        if project_root is None:
            project_root = get_project_root()

        # Validate project root path
        validation_result = validate_file_path(project_root, project_root)
        if not validation_result.get("valid", False):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": validation_result.get("error", "Invalid project root path")
                }
            }

        project_path = Path(project_root)

        # Default config files to check
        if config_files is None:
            config_files = [
                "package.json",
                "tsconfig.json",
                "next.config.js",
                "next.config.mjs",
                "vite.config.js",
                "vite.config.ts",
                "webpack.config.js",
                "rollup.config.js",
                "babel.config.js",
                ".babelrc",
                "eslint.config.js",
                ".eslintrc.js",
                ".eslintrc.json",
                "prettier.config.js",
                ".prettierrc",
                "jest.config.js",
                "vitest.config.js",
                "tailwind.config.js",
                "postcss.config.js",
                "Dockerfile",
                "docker-compose.yml",
                "Makefile",
                "pyproject.toml",
                "setup.py",
                "requirements.txt",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
                "build.gradle"
            ]

        configs = {}
        detected_tools = []

        # Read each config file that exists
        for config_file in config_files:
            config_path = project_path / config_file

            if config_path.exists() and config_path.is_file():
                try:
                    content = config_path.read_text(encoding='utf-8')

                    # Try to parse JSON files
                    if config_file.endswith('.json'):
                        try:
                            parsed_content = json.loads(content)
                            configs[config_file] = {
                                "type": "json",
                                "content": parsed_content,
                                "raw": content[:1000] if len(content) > 1000 else content
                            }
                        except json.JSONDecodeError:
                            configs[config_file] = {
                                "type": "text",
                                "content": content[:1000] if len(content) > 1000 else content,
                                "parse_error": "Invalid JSON"
                            }
                    else:
                        # Store as text for other file types
                        configs[config_file] = {
                            "type": "text",
                            "content": content[:1000] if len(content) > 1000 else content
                        }

                    # Detect tools based on config files
                    if config_file == "package.json":
                        detected_tools.extend(["npm", "node"])
                        if "scripts" in configs[config_file].get("content", {}):
                            scripts = configs[config_file]["content"]["scripts"]
                            if any("next" in script for script in scripts.values()):
                                detected_tools.append("nextjs")
                            if any("react" in script for script in scripts.values()):
                                detected_tools.append("react")
                            if any("vue" in script for script in scripts.values()):
                                detected_tools.append("vue")

                    elif config_file.startswith("next.config"):
                        detected_tools.append("nextjs")
                    elif config_file.startswith("vite.config"):
                        detected_tools.append("vite")
                    elif config_file.startswith("webpack.config"):
                        detected_tools.append("webpack")
                    elif config_file == "tsconfig.json":
                        detected_tools.append("typescript")
                    elif config_file.startswith("eslint") or config_file.startswith(".eslint"):
                        detected_tools.append("eslint")
                    elif config_file.startswith("jest.config"):
                        detected_tools.append("jest")
                    elif config_file.startswith("vitest.config"):
                        detected_tools.append("vitest")
                    elif config_file == "Dockerfile":
                        detected_tools.append("docker")
                    elif config_file == "Cargo.toml":
                        detected_tools.append("rust")
                    elif config_file == "go.mod":
                        detected_tools.append("go")
                    elif config_file == "pyproject.toml":
                        detected_tools.append("python")

                except Exception as e:
                    configs[config_file] = {
                        "type": "error",
                        "error": f"Failed to read file: {str(e)}"
                    }

        # Extract key build information
        build_info = {}

        # Extract package.json info
        if "package.json" in configs and configs["package.json"]["type"] == "json":
            pkg = configs["package.json"]["content"]
            build_info.update({
                "name": pkg.get("name"),
                "version": pkg.get("version"),
                "scripts": pkg.get("scripts", {}),
                "dependencies": list(pkg.get("dependencies", {}).keys()),
                "devDependencies": list(pkg.get("devDependencies", {}).keys()),
                "engines": pkg.get("engines", {})
            })

        # Extract TypeScript config
        if "tsconfig.json" in configs and configs["tsconfig.json"]["type"] == "json":
            ts_config = configs["tsconfig.json"]["content"]
            build_info["typescript"] = {
                "target": ts_config.get("compilerOptions", {}).get("target"),
                "module": ts_config.get("compilerOptions", {}).get("module"),
                "strict": ts_config.get("compilerOptions", {}).get("strict"),
                "outDir": ts_config.get("compilerOptions", {}).get("outDir")
            }

        # Remove duplicates from detected tools
        detected_tools = list(set(detected_tools))

        return {
            "data": {
                "config_files": configs,
                "detected_tools": detected_tools,
                "build_info": build_info,
                "project_root": str(project_path)
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to extract build configuration: {str(e)}"
            }
        }
