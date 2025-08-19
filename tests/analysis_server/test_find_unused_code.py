"""
Test find_unused_code tool implementation.

Minimal validation tests focusing on core functionality and error handling.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aromcp.analysis_server.tools.find_unused_code import find_unused_code_impl


class TestFindUnusedCode:
    """Test cases for find_unused_code tool implementation."""

    def test_knip_not_installed_error(self):
        """Test error handling when Knip is not installed."""
        with patch("aromcp.analysis_server.tools.find_unused_code._detect_knip_installation") as mock_detect:
            mock_detect.return_value = (None, "")
            
            with patch("aromcp.filesystem_server._security.get_project_root") as mock_root:
                mock_root.return_value = "/tmp/test"
                
                result = find_unused_code_impl()
                
                assert not result.success
                assert len(result.errors) == 1
                assert result.errors[0].code == "KNIP_NOT_FOUND"
                assert "Knip is not installed" in result.errors[0].message
                assert result.total_issues == 0
                assert result.execution_stats.installation_method == "none"

    def test_knip_execution_with_mock_output(self):
        """Test successful Knip execution with mocked JSON output."""
        mock_json_output = '''{"files": ["unused-file.ts"], "exports": [{"file": "src/utils.ts", "symbol": "unusedFunction", "line": 5}], "dependencies": ["unused-package"]}'''
        
        with patch("aromcp.analysis_server.tools.find_unused_code._detect_knip_installation") as mock_detect:
            mock_detect.return_value = (["knip"], "global")
            
            with patch("aromcp.analysis_server.tools.find_unused_code._get_knip_version") as mock_version:
                mock_version.return_value = "3.0.0"
                
                with patch("subprocess.run") as mock_run:
                    mock_process = Mock()
                    mock_process.returncode = 1  # Knip returns 1 when unused code is found
                    mock_process.stdout = mock_json_output
                    mock_process.stderr = ""
                    mock_run.return_value = mock_process
                    
                    with patch("aromcp.filesystem_server._security.get_project_root") as mock_root:
                        mock_root.return_value = "/tmp/test"
                        
                        with patch("aromcp.analysis_server.tools.find_unused_code._count_analyzed_files") as mock_count:
                            mock_count.return_value = 10
                            
                            result = find_unused_code_impl()
                            
                            assert result.success
                            assert len(result.errors) == 0
                            assert result.total_issues == 3  # 1 file + 1 export + 1 dependency
                            assert len(result.unused_items) == 3
                            
                            # Verify different issue types are detected
                            issue_types = {item.issue_type for item in result.unused_items}
                            assert "file" in issue_types
                            assert "export" in issue_types
                            assert "dependency" in issue_types
                            
                            # Verify execution stats
                            assert result.execution_stats.knip_version == "3.0.0"
                            assert result.execution_stats.installation_method == "global"
                            assert result.execution_stats.exit_code == 1
                            assert result.execution_stats.files_analyzed == 10

    def test_knip_timeout_error(self):
        """Test timeout handling during Knip execution."""
        from subprocess import TimeoutExpired
        
        with patch("aromcp.analysis_server.tools.find_unused_code._detect_knip_installation") as mock_detect:
            mock_detect.return_value = (["knip"], "npx")
            
            with patch("aromcp.analysis_server.tools.find_unused_code._get_knip_version") as mock_version:
                mock_version.return_value = "3.0.0"
                
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = TimeoutExpired(["knip"], 300)
                    
                    with patch("aromcp.filesystem_server._security.get_project_root") as mock_root:
                        mock_root.return_value = "/tmp/test"
                        
                        result = find_unused_code_impl()
                        
                        assert not result.success
                        assert len(result.errors) == 1
                        assert result.errors[0].code == "TIMEOUT"
                        assert "timed out" in result.errors[0].message
                        assert result.total_issues == 0
                        assert result.execution_stats.exit_code == -1


if __name__ == "__main__":
    pytest.main([__file__])