"""
Basic tests for incremental analysis change detection - TDD approach.

These tests focus on the fundamental change detection functionality
that needs to be implemented first.
"""

import os
import time
from pathlib import Path

import pytest

from aromcp.analysis_server.tools.incremental_analyzer import (
    FileModificationTracker,
    ChangeDetector,
    IncrementalAnalyzer,
)


class TestBasicChangeDetection:
    """Test basic file change detection capabilities."""
    
    def test_detect_file_modification_by_timestamp(self, tmp_path):
        """Test that we can detect when a file's timestamp changes."""
        # Create a test file
        test_file = tmp_path / "test.ts"
        test_file.write_text("export const value = 1;")
        
        # Create tracker and record initial state
        tracker = FileModificationTracker(str(tmp_path))
        tracker.scan_project()
        
        # Get initial metadata
        initial_metadata = tracker.get_file_metadata(str(test_file))
        assert initial_metadata is not None
        initial_mtime = initial_metadata.modification_time
        
        # Modify the file
        time.sleep(0.01)  # Ensure timestamp changes
        test_file.write_text("export const value = 2;")
        
        # Detect changes
        changes = tracker.detect_changes()
        
        # Should detect the modification
        assert len(changes.modified_files) == 1
        assert str(test_file) in changes.modified_files
        
        # Metadata should be updated
        updated_metadata = tracker.get_file_metadata(str(test_file))
        assert updated_metadata.modification_time > initial_mtime
    
    def test_detect_file_modification_by_content(self, tmp_path):
        """Test that we detect changes even when timestamp doesn't change."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("export const value = 1;")
        
        tracker = FileModificationTracker(str(tmp_path))
        tracker.scan_project()
        
        # Get initial hash
        initial_metadata = tracker.get_file_metadata(str(test_file))
        initial_hash = initial_metadata.content_hash
        
        # Modify content without changing timestamp
        # (In practice, this simulates very fast modifications)
        test_file.write_text("export const value = 2;")
        
        # Force same modification time
        stat = os.stat(str(test_file))
        os.utime(str(test_file), (stat.st_atime, initial_metadata.modification_time))
        
        # Should still detect change via content hash
        changes = tracker.detect_changes()
        
        assert len(changes.modified_files) == 1
        assert str(test_file) in changes.modified_files
        
        # Hash should have changed
        updated_metadata = tracker.get_file_metadata(str(test_file))
        assert updated_metadata.content_hash != initial_hash
    
    def test_track_file_dependencies(self, tmp_path):
        """Test that we can track dependencies between files."""
        # Create files with dependencies
        core_file = tmp_path / "core.ts"
        core_file.write_text("export interface Core { id: string; }")
        
        user_file = tmp_path / "user.ts"
        user_file.write_text("import { Core } from './core';\nexport interface User extends Core { name: string; }")
        
        analyzer = IncrementalAnalyzer(str(tmp_path))
        analyzer.analyze_full()
        
        # Get dependency graph
        dep_graph = analyzer.get_dependency_graph()
        
        # user.ts should depend on core.ts
        user_deps = dep_graph.get_dependencies(str(user_file))
        assert str(core_file) in user_deps
        
        # core.ts should have user.ts as a dependent
        core_dependents = dep_graph.get_dependents(str(core_file))
        assert str(user_file) in core_dependents
    
    def test_incremental_analysis_only_analyzes_changed_files(self, tmp_path):
        """Test that incremental analysis only processes changed files."""
        # Create multiple files
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.ts"
            f.write_text(f"export const value{i} = {i};")
            files.append(f)
        
        analyzer = IncrementalAnalyzer(str(tmp_path))
        
        # Initial full analysis
        full_result = analyzer.analyze_full()
        assert full_result.files_analyzed == 5
        
        # Modify one file
        time.sleep(0.01)
        files[2].write_text("export const value2 = 999;")
        
        # Incremental analysis
        inc_result = analyzer.analyze_incremental()
        
        # Should only analyze the changed file
        assert inc_result.files_analyzed == 1
        assert str(files[2]) in inc_result.analyzed_files
        assert inc_result.files_skipped == 4
    
    def test_change_detector_strategies(self, tmp_path):
        """Test different change detection strategies."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("export const value = 1;")
        
        # Test timestamp strategy
        ts_detector = ChangeDetector(strategy="timestamp")
        ts_detector.record_file_state(str(test_file))
        
        # No change yet
        assert not ts_detector.has_changed(str(test_file))
        
        # Touch file to update timestamp
        time.sleep(0.01)
        test_file.touch()
        
        # Should detect change by timestamp
        assert ts_detector.has_changed(str(test_file))
        
        # Test content hash strategy
        content_detector = ChangeDetector(strategy="content_hash")
        content_detector.record_file_state(str(test_file))
        
        # Touch without content change
        time.sleep(0.01)
        test_file.touch()
        
        # Should NOT detect change (content unchanged)
        assert not content_detector.has_changed(str(test_file))
        
        # Change content
        test_file.write_text("export const value = 2;")
        
        # Should detect change
        assert content_detector.has_changed(str(test_file))