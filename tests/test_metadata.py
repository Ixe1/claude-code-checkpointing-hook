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
        self.metadata_path = Path(self.temp_dir) / "metadata.json"
        self.metadata = CheckpointMetadata(self.metadata_path)
    
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


if __name__ == '__main__':
    unittest.main()