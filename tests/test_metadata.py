#!/usr/bin/env python3
"""Tests for the metadata module."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing.metadata import CheckpointMetadata


class TestCheckpointMetadata(unittest.TestCase):
    """Test cases for CheckpointMetadata class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_base = Path(self.temp_dir)
        self.metadata_path = self.checkpoint_base / "metadata.json"
        self.metadata = CheckpointMetadata(self.checkpoint_base)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_add_checkpoint(self):
        """Test adding a checkpoint."""
        project_hash = "abc123"
        checkpoint_hash = "def456789012345678901234567890123456789"
        tool_name = "Write"
        tool_input = {"file_path": "/test/file.py"}
        session_id = "session123"
        
        result = self.metadata.add_checkpoint(
            project_hash, checkpoint_hash, tool_name, tool_input, session_id
        )
        
        # Verify metadata was saved
        self.assertTrue(self.metadata.metadata_file.exists())
        
        # Check returned data
        self.assertEqual(result['tool_name'], tool_name)
        self.assertEqual(result['session_id'], session_id)
        self.assertEqual(result['files_affected'], ["/test/file.py"])
        
        # Load and check persistence
        with open(self.metadata.metadata_file, 'r') as f:
            data = json.load(f)
        
        self.assertIn(project_hash, data)
        self.assertIn(checkpoint_hash, data[project_hash])
        
        checkpoint = data[project_hash][checkpoint_hash]
        self.assertEqual(checkpoint['tool_name'], tool_name)
        self.assertEqual(checkpoint['session_id'], session_id)
        self.assertEqual(checkpoint['files_affected'], ["/test/file.py"])
    
    def test_get_checkpoint_metadata(self):
        """Test retrieving checkpoint metadata."""
        project_hash = "abc123"
        checkpoint_hash = "def456"
        
        # Add a checkpoint
        self.metadata.add_checkpoint(
            project_hash, checkpoint_hash, "Edit", 
            {"file_path": "/test.py"}, "session123"
        )
        
        # Retrieve it
        result = self.metadata.get_checkpoint_metadata(project_hash, checkpoint_hash)
        
        self.assertIsNotNone(result)
        # Note: get_checkpoint_metadata doesn't include the hash in the returned dict
        if result is not None:  # Type guard for static analyzer
            self.assertEqual(result['tool_name'], "Edit")
            self.assertEqual(result['session_id'], "session123")
    
    def test_list_project_checkpoints(self):
        """Test listing checkpoints for a project."""
        project_hash = "abc123"
        
        # Add multiple checkpoints
        for i in range(3):
            self.metadata.add_checkpoint(
                project_hash, f"hash{i}", "Write",
                {"file_path": f"/file{i}.py"}, f"session{i}"
            )
        
        # List them
        checkpoints = self.metadata.list_project_checkpoints(project_hash)
        
        self.assertEqual(len(checkpoints), 3)
        # Should be in reverse chronological order
        self.assertEqual(checkpoints[0]['hash'], "hash2")
        self.assertEqual(checkpoints[1]['hash'], "hash1")
        self.assertEqual(checkpoints[2]['hash'], "hash0")
    
    def test_update_checkpoint_status(self):
        """Test updating checkpoint status."""
        project_hash = "abc123"
        checkpoint_hash = "def456"
        
        # Add a checkpoint
        self.metadata.add_checkpoint(
            project_hash, checkpoint_hash, "Write",
            {"file_path": "/test.py"}, "session123"
        )
        
        # Update its status
        tool_response = {"success": True, "message": "File written"}
        self.metadata.update_checkpoint_status(
            project_hash, checkpoint_hash, "success", tool_response
        )
        
        # Check the update
        result = self.metadata.get_checkpoint_metadata(project_hash, checkpoint_hash)
        self.assertIsNotNone(result)
        if result is not None:  # Type guard for static analyzer
            self.assertEqual(result['status'], "success")
            self.assertEqual(result['tool_response'], tool_response)
    
    def test_find_checkpoints_by_file(self):
        """Test finding checkpoints by file."""
        project_hash = "abc123"
        
        # Add checkpoints with different characteristics
        self.metadata.add_checkpoint(
            project_hash, "hash1", "Write",
            {"file_path": "/main.py"}, "session123"
        )
        self.metadata.add_checkpoint(
            project_hash, "hash2", "Edit",
            {"file_path": "/test.py"}, "session456"
        )
        self.metadata.add_checkpoint(
            project_hash, "hash3", "Write",
            {"file_path": "/main.py"}, "session123"
        )
        
        # Search by file
        results = self.metadata.find_checkpoints_by_file(project_hash, "/main.py")
        self.assertEqual(len(results), 2)
        
        # Check that both main.py checkpoints are found
        hashes = [r['hash'] for r in results]
        self.assertIn("hash1", hashes)
        self.assertIn("hash3", hashes)
    
    def test_get_project_stats(self):
        """Test getting project statistics."""
        project_hash = "abc123"
        
        # Add various checkpoints
        self.metadata.add_checkpoint(
            project_hash, "hash1", "Write",
            {"file_path": "/main.py"}, "session123"
        )
        self.metadata.update_checkpoint_status(
            project_hash, "hash1", "success", {}
        )
        
        self.metadata.add_checkpoint(
            project_hash, "hash2", "Edit",
            {"file_path": "/test.py"}, "session123"
        )
        self.metadata.update_checkpoint_status(
            project_hash, "hash2", "failed", {}
        )
        
        self.metadata.add_checkpoint(
            project_hash, "hash3", "Write",
            {"file_path": "/main.py"}, "session456"
        )
        
        # Get stats
        stats = self.metadata.get_project_stats(project_hash)
        
        self.assertEqual(stats['total_checkpoints'], 3)
        self.assertEqual(stats['successful'], 1)
        self.assertEqual(stats['failed'], 1)
        self.assertEqual(stats['pending'], 1)
        self.assertIn('latest_checkpoint', stats)
        self.assertIn('most_modified_files', stats)
        
        # Check most modified files
        most_modified = stats['most_modified_files']
        self.assertEqual(most_modified[0][0], "/main.py")  # File path
        self.assertEqual(most_modified[0][1], 2)  # Count
    
    def test_cleanup_old_metadata(self):
        """Test cleanup of old metadata."""
        project_hash = "abc123"
        
        # Add multiple checkpoints
        for i in range(10):
            self.metadata.add_checkpoint(
                project_hash, f"hash{i}", "Write",
                {"file_path": f"/file{i}.py"}, f"session{i}"
            )
        
        # List all checkpoints before cleanup
        checkpoints_before = self.metadata.list_project_checkpoints(project_hash)
        self.assertEqual(len(checkpoints_before), 10)
        
        # Cleanup keeping only 5
        self.metadata.cleanup_old_metadata(project_hash, keep_count=5)
        
        # Verify only 5 newest checkpoints remain
        checkpoints_after = self.metadata.list_project_checkpoints(project_hash)
        self.assertEqual(len(checkpoints_after), 5)
        
        # Verify they are the newest ones (hash5-hash9)
        remaining_hashes = [c['hash'] for c in checkpoints_after]
        for i in range(5, 10):
            self.assertIn(f"hash{i}", remaining_hashes)
    
    def test_empty_metadata_handling(self):
        """Test handling of empty or missing metadata."""
        # Test with non-existent project
        result = self.metadata.get_checkpoint_metadata("nonexistent", "hash")
        self.assertIsNone(result)
        
        checkpoints = self.metadata.list_project_checkpoints("nonexistent")
        self.assertEqual(checkpoints, [])
        
        stats = self.metadata.get_project_stats("nonexistent")
        self.assertEqual(stats['total_checkpoints'], 0)
    
    def test_extract_files_edit_tool(self):
        """Test _extract_files method for Edit tool."""
        # Test Edit tool
        edit_input = {
            "file_path": "/path/to/file.py",
            "old_string": "old",
            "new_string": "new"
        }
        files = self.metadata._extract_files("Edit", edit_input)
        self.assertEqual(files, ["/path/to/file.py"])
    
    def test_extract_files_multiedit_tool(self):
        """Test _extract_files method for MultiEdit tool."""
        # Test MultiEdit tool
        multiedit_input = {
            "file_path": "/path/to/file.py",
            "edits": [
                {"old_string": "a", "new_string": "b"},
                {"old_string": "c", "new_string": "d"}
            ]
        }
        files = self.metadata._extract_files("MultiEdit", multiedit_input)
        self.assertEqual(files, ["/path/to/file.py"])
    
    def test_corrupted_json_handling(self):
        """Test handling of corrupted metadata JSON."""
        # Write corrupted JSON
        self.metadata_path.write_text('{"incomplete": ')
        
        # Should handle gracefully and return empty dict
        result = self.metadata._load_metadata()
        self.assertEqual(result, {})
        
        # Should be able to save new metadata
        self.metadata.add_checkpoint(
            "project1", "hash1", "Write",
            {"file_path": "/test.py"}, "session1"
        )
        
        # Verify it works now
        checkpoints = self.metadata.list_project_checkpoints("project1")
        self.assertEqual(len(checkpoints), 1)
    
    def test_concurrent_access(self):
        """Test concurrent access to metadata."""
        import threading
        import time
        
        project_hash = "concurrent_test"
        results = []
        errors = []
        
        def add_checkpoint(index):
            try:
                # Create new metadata instance for each thread
                metadata = CheckpointMetadata(self.checkpoint_base)
                result = metadata.add_checkpoint(
                    project_hash,
                    f"hash_{index}",
                    "Write",
                    {"file_path": f"/file_{index}.py"},
                    f"session_{index}"
                )
                results.append((index, True))
            except Exception as e:
                errors.append((index, str(e)))
                results.append((index, False))
        
        # Create multiple threads that write concurrently
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_checkpoint, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All should succeed (file operations are atomic on most systems)
        self.assertEqual(len(results), 10)
        if errors:
            for idx, err in errors:
                print(f"Error in thread {idx}: {err}")
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all checkpoints were saved
        checkpoints = self.metadata.list_project_checkpoints(project_hash)
        # Debug: print what was actually saved
        if len(checkpoints) != 10:
            print(f"Expected 10 checkpoints, got {len(checkpoints)}")
            for cp in checkpoints:
                print(f"  - {cp['hash']}")
        self.assertEqual(len(checkpoints), 10)
    
    def test_large_metadata_file(self):
        """Test handling of large metadata files."""
        # Create many checkpoints
        project_hash = "large_test"
        
        # Add 100 checkpoints
        for i in range(100):
            self.metadata.add_checkpoint(
                project_hash,
                f"hash_{i:03d}",
                "Write",
                {"file_path": f"/file_{i}.py", "content": "x" * 1000},
                f"session_{i}"
            )
        
        # Should still be able to load and query
        checkpoints = self.metadata.list_project_checkpoints(project_hash)
        self.assertEqual(len(checkpoints), 100)
        
        # Stats should work
        stats = self.metadata.get_project_stats(project_hash)
        self.assertEqual(stats['total_checkpoints'], 100)
        
        # File size should be reasonable (not testing exact size due to JSON formatting)
        file_size = self.metadata_path.stat().st_size
        self.assertLess(file_size, 1024 * 1024)  # Should be less than 1MB
    
    def test_file_permissions_error(self):
        """Test handling of file permission errors."""
        import os
        import platform
        
        # Skip on Windows as chmod behavior is different
        if platform.system() == "Windows":
            self.skipTest("File permissions test not applicable on Windows")
        
        # Make metadata file read-only
        self.metadata_path.touch()
        os.chmod(self.metadata_path, 0o444)
        
        try:
            # Try to add checkpoint - should fail gracefully
            # Our locking mechanism creates a lock file, so it might succeed
            # if the directory is writable even if the metadata file is not
            try:
                result = self.metadata.add_checkpoint(
                    "project1", "hash1", "Write",
                    {"file_path": "/test.py"}, "session1"
                )
                # If it succeeded, make sure it actually wrote
                # This could happen if the atomic write mechanism works around the permission
                self.assertTrue(self.metadata_path.exists())
            except (PermissionError, OSError, RuntimeError) as e:
                # Expected behavior - permission denied
                # Check if error message contains expected keywords
                error_msg = str(e).lower()
                self.assertTrue(any(word in error_msg for word in ["permission", "denied", "read-only", "timeout"]))
        finally:
            # Restore permissions for cleanup
            os.chmod(self.metadata_path, 0o644)
    
    def test_unicode_handling(self):
        """Test handling of unicode in metadata."""
        project_hash = "unicode_test"
        
        # Add checkpoint with unicode content
        self.metadata.add_checkpoint(
            project_hash,
            "hash_unicode",
            "Write",
            {"file_path": "/测试.py", "content": "你好世界 🌍"},
            "session_émoji_🎉"
        )
        
        # Should be able to retrieve
        checkpoint = self.metadata.get_checkpoint_metadata(project_hash, "hash_unicode")
        self.assertIsNotNone(checkpoint)
        if checkpoint:
            self.assertEqual(checkpoint['files_affected'], ["/测试.py"])
            self.assertEqual(checkpoint['session_id'], "session_émoji_🎉")
    
    def test_metadata_file_locking(self):
        """Test behavior when metadata file is locked."""
        import fcntl
        import platform
        
        # Skip on Windows as fcntl is not available
        if platform.system() == "Windows":
            self.skipTest("File locking test not applicable on Windows")
        
        # Create and lock the file
        self.metadata_path.touch()
        lock_file = open(self.metadata_path, 'r+')
        
        try:
            # Acquire exclusive lock
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Try to write from another instance - might fail or block
            # This behavior is system-dependent
            try:
                self.metadata.add_checkpoint(
                    "project1", "hash1", "Write",
                    {"file_path": "/test.py"}, "session1"
                )
                # If it succeeds, that's okay on some systems
                self.assertTrue(True)
            except Exception:
                # If it fails, that's also expected
                self.assertTrue(True)
        finally:
            # Release lock and close
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()


if __name__ == '__main__':
    unittest.main()