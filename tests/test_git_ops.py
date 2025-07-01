#!/usr/bin/env python3
"""Tests for git operations module."""

import tempfile
import unittest
from pathlib import Path
import subprocess
import shutil

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing.git_ops import GitCheckpointManager


class TestGitCheckpointManager(unittest.TestCase):
    """Test cases for GitCheckpointManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_path = Path(self.temp_dir) / "test_project"
        self.project_path.mkdir()
        
        # Create some test files
        (self.project_path / "test.py").write_text("print('hello')")
        (self.project_path / "README.md").write_text("# Test Project")
        
        self.checkpoint_mgr = GitCheckpointManager(self.project_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_project_hash_generation(self):
        """Test that project hash is generated correctly."""
        # Hash should be 12 characters
        self.assertEqual(len(self.checkpoint_mgr.project_hash), 12)
        
        # Hash should be consistent for same path
        another_mgr = GitCheckpointManager(self.project_path)
        self.assertEqual(self.checkpoint_mgr.project_hash, another_mgr.project_hash)
    
    def test_validate_checkpoint_hash(self):
        """Test checkpoint hash validation."""
        mgr = self.checkpoint_mgr
        
        # Valid hashes
        self.assertTrue(mgr._validate_checkpoint_hash("abc123"))
        self.assertTrue(mgr._validate_checkpoint_hash("a" * 40))
        
        # Invalid hashes
        self.assertFalse(mgr._validate_checkpoint_hash(""))
        self.assertFalse(mgr._validate_checkpoint_hash("xyz"))  # Non-hex
        self.assertFalse(mgr._validate_checkpoint_hash("a" * 41))  # Too long
    
    def test_sanitize_path(self):
        """Test path sanitization."""
        mgr = self.checkpoint_mgr
        
        # Valid path within project
        valid_path = self.project_path / "subdir" / "file.txt"
        sanitized = mgr._sanitize_path(valid_path)
        self.assertEqual(sanitized, valid_path.resolve())
        
        # Path outside project should raise ValueError
        with self.assertRaises(ValueError):
            mgr._sanitize_path(Path("/etc/passwd"))
    
    def test_validate_metadata_size(self):
        """Test metadata size validation."""
        mgr = self.checkpoint_mgr
        
        # Small metadata should pass
        small_metadata = {"key": "value"}
        self.assertTrue(mgr._validate_metadata_size(small_metadata))
        
        # Large metadata should fail
        large_metadata = {"data": "x" * (2 * 1024 * 1024)}  # 2MB
        self.assertFalse(mgr._validate_metadata_size(large_metadata))
    
    def test_init_project_repo(self):
        """Test project repository initialization."""
        mgr = self.checkpoint_mgr
        
        # Should not be a git repo initially
        self.assertFalse(mgr.is_git_repo())
        
        # Initialize repo
        self.assertTrue(mgr.init_project_repo())
        
        # Should now be a git repo
        self.assertTrue(mgr.is_git_repo())
        
        # Should be idempotent
        self.assertTrue(mgr.init_project_repo())
    
    def test_create_checkpoint(self):
        """Test checkpoint creation."""
        mgr = self.checkpoint_mgr
        
        # Initialize project repo first
        mgr.init_project_repo()
        
        # Create checkpoint
        metadata = {
            "tool_name": "Test",
            "session_id": "test-session",
            "files": ["test.py"]
        }
        
        checkpoint_hash = mgr.create_checkpoint("Test checkpoint", metadata)
        
        # Should return a valid hash
        self.assertIsNotNone(checkpoint_hash)
        self.assertEqual(len(checkpoint_hash), 40)  # Git SHA-1 length
        
        # Checkpoint should be in the list
        checkpoints = mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['hash'], checkpoint_hash)


if __name__ == '__main__':
    unittest.main()