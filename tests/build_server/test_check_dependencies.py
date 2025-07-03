"""Tests for check_dependencies tool in Build Tools."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from aromcp.build_server.tools.check_dependencies import check_dependencies_impl


class TestCheckDependencies:
    """Test class for check_dependencies tool."""

    def test_basic_functionality(self):
        """Test basic dependency analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create package.json
            package_json = {
                "name": "test-project",
                "version": "1.0.0",
                "dependencies": {
                    "react": "^18.0.0",
                    "next": "^13.0.0"
                },
                "devDependencies": {
                    "typescript": "^4.0.0",
                    "jest": "^28.0.0"
                },
                "peerDependencies": {
                    "react-dom": "^18.0.0"
                },
                "optionalDependencies": {
                    "fsevents": "^2.0.0"
                },
                "engines": {
                    "node": ">=16.0.0",
                    "npm": ">=8.0.0"
                }
            }

            (temp_path / "package.json").write_text(json.dumps(package_json, indent=2))

            with patch('subprocess.run') as mock_run:
                # Mock successful command runs
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=False
                )

            assert "data" in result

            # Check package manager detection
            assert result["data"]["package_manager"] == "npm"  # Default when no lock files

            # Check dependencies structure
            deps = result["data"]["dependencies"]
            assert "production" in deps
            assert "development" in deps
            assert "peer" in deps
            assert "optional" in deps
            assert "total_count" in deps

            assert len(deps["production"]) == 2
            assert "react" in deps["production"]
            assert "next" in deps["production"]

            assert len(deps["development"]) == 2
            assert "typescript" in deps["development"]
            assert "jest" in deps["development"]

            assert len(deps["peer"]) == 1
            assert "react-dom" in deps["peer"]

            assert deps["total_count"] == 6  # 2 + 2 + 1 + 1 = 6 dependencies total

            # Check engines
            assert result["data"]["engines"]["node"] == ">=16.0.0"
            assert result["data"]["engines"]["npm"] == ">=8.0.0"

    def test_package_manager_detection(self):
        """Test package manager auto-detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create package.json
            package_json = {"name": "test", "dependencies": {}}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            # Test yarn detection
            (temp_path / "yarn.lock").write_text("# Yarn lock file")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=False
                )

            assert result["data"]["package_manager"] == "yarn"

            # Test pnpm detection
            (temp_path / "yarn.lock").unlink()
            (temp_path / "pnpm-lock.yaml").write_text("# PNPM lock file")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=False
                )

            assert result["data"]["package_manager"] == "pnpm"

            # Test npm detection
            (temp_path / "pnpm-lock.yaml").unlink()
            (temp_path / "package-lock.json").write_text("{}")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=False
                )

            assert result["data"]["package_manager"] == "npm"

    def test_outdated_packages_npm(self):
        """Test outdated package detection for npm."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            package_json = {"name": "test", "dependencies": {"react": "^17.0.0"}}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            # Mock npm outdated output
            outdated_output = json.dumps({
                "react": {
                    "current": "17.0.2",
                    "wanted": "17.0.3",
                    "latest": "18.2.0",
                    "location": "node_modules/react"
                }
            })

            with patch('subprocess.run') as mock_run:
                def mock_command(*args, **kwargs):
                    cmd = args[0]
                    if "outdated" in cmd:
                        return Mock(stdout=outdated_output, stderr="", returncode=0)
                    else:
                        return Mock(stdout="", stderr="", returncode=0)

                mock_run.side_effect = mock_command

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=True,
                    check_security=False
                )

            assert "data" in result
            assert len(result["data"]["outdated"]) == 1

            outdated = result["data"]["outdated"][0]
            assert outdated["package"] == "react"
            assert outdated["current"] == "17.0.2"
            assert outdated["wanted"] == "17.0.3"
            assert outdated["latest"] == "18.2.0"

    def test_security_audit_npm(self):
        """Test security audit for npm."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            package_json = {"name": "test", "dependencies": {"lodash": "^4.0.0"}}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            # Mock npm audit output
            audit_output = json.dumps({
                "advisories": {
                    "1065": {
                        "title": "Prototype Pollution",
                        "severity": "high",
                        "vulnerable_versions": "<4.17.12",
                        "patched_versions": ">=4.17.12",
                        "module_name": "lodash"
                    }
                },
                "metadata": {
                    "vulnerabilities": {
                        "total": 1,
                        "low": 0,
                        "moderate": 0,
                        "high": 1,
                        "critical": 0
                    }
                }
            })

            with patch('subprocess.run') as mock_run:
                def mock_command(*args, **kwargs):
                    cmd = args[0]
                    if "audit" in cmd:
                        return Mock(stdout=audit_output, stderr="", returncode=0)
                    else:
                        return Mock(stdout="", stderr="", returncode=0)

                mock_run.side_effect = mock_command

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=True
                )

            assert "data" in result
            security = result["data"]["security"]

            assert security["summary"]["total"] == 1
            assert security["summary"]["high"] == 1
            assert len(security["vulnerabilities"]) == 1

            vuln = security["vulnerabilities"][0]
            assert vuln["title"] == "Prototype Pollution"
            assert vuln["severity"] == "high"
            assert vuln["module_name"] == "lodash"

    def test_missing_package_json(self):
        """Test handling when package.json is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = check_dependencies_impl(project_root=temp_dir)

            assert "error" in result
            assert result["error"]["code"] == "NOT_FOUND"
            assert "package.json not found" in result["error"]["message"]

    def test_invalid_package_json(self):
        """Test handling of invalid package.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid JSON
            (temp_path / "package.json").write_text("{ invalid json }")

            result = check_dependencies_impl(project_root=temp_dir)

            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Failed to parse package.json" in result["error"]["message"]

    def test_command_timeout_handling(self):
        """Test handling of command timeouts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            package_json = {"name": "test", "dependencies": {}}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            with patch('subprocess.run') as mock_run:
                def mock_command(*args, **kwargs):
                    cmd = args[0]
                    if "outdated" in cmd:
                        raise subprocess.TimeoutExpired("npm", 60)
                    else:
                        return Mock(stdout="", stderr="", returncode=0)

                mock_run.side_effect = mock_command

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=True
                )

            assert "data" in result
            assert "error" in result["data"]["outdated"]

    def test_empty_dependencies(self):
        """Test handling of package.json with no dependencies."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            package_json = {"name": "test", "version": "1.0.0"}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    check_outdated=False,
                    check_security=False
                )

            assert "data" in result
            deps = result["data"]["dependencies"]
            assert deps["total_count"] == 0
            assert len(deps["production"]) == 0
            assert len(deps["development"]) == 0

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = check_dependencies_impl(project_root="/../../invalid/path")

        assert "error" in result
        # The function actually returns NOT_FOUND when package.json is missing
        assert result["error"]["code"] == "NOT_FOUND"

    def test_explicit_package_manager(self):
        """Test using explicit package manager instead of auto-detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            package_json = {"name": "test", "dependencies": {}}
            (temp_path / "package.json").write_text(json.dumps(package_json))

            # Create yarn.lock but specify npm
            (temp_path / "yarn.lock").write_text("# Yarn lock")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

                result = check_dependencies_impl(
                    project_root=temp_dir,
                    package_manager="npm",
                    check_outdated=False,
                    check_security=False
                )

            assert result["data"]["package_manager"] == "npm"
