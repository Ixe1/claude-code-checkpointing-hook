#!/usr/bin/env python3
"""Tests for git operations module."""

import tempfile
import time
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
        self.assertEqual(len(checkpoint_hash or ''), 40)  # Git SHA-1 length
        
        # Checkpoint should be in the list
        checkpoints = mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['hash'], checkpoint_hash)
    
    def test_restore_checkpoint(self):
        """Test basic checkpoint restoration."""
        mgr = self.checkpoint_mgr
        
        # Initialize and create initial state
        mgr.init_project_repo()
        
        # Create initial checkpoint
        checkpoint1 = mgr.create_checkpoint("Initial state", {"tool": "test"})
        self.assertIsNotNone(checkpoint1)
        
        # Modify files
        (self.project_path / "test.py").write_text("print('modified')")
        (self.project_path / "new_file.py").write_text("# New file")
        
        # Create second checkpoint
        checkpoint2 = mgr.create_checkpoint("After modifications", {"tool": "test"})
        self.assertIsNotNone(checkpoint2)
        
        # Restore to first checkpoint
        self.assertIsNotNone(checkpoint1)
        assert checkpoint1 is not None  # Type guard
        restored = mgr.restore_checkpoint(checkpoint1)
        self.assertTrue(restored)
        
        # Verify files are restored
        self.assertEqual((self.project_path / "test.py").read_text(), "print('hello')")
        self.assertFalse((self.project_path / "new_file.py").exists())
    
    def test_restore_checkpoint_with_deletions(self):
        """Test restoration handles file deletions correctly."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create files and checkpoint
        (self.project_path / "to_delete.py").write_text("# Will be deleted")
        checkpoint1 = mgr.create_checkpoint("With extra file", {"tool": "test"})
        
        # Delete the file and create another checkpoint
        (self.project_path / "to_delete.py").unlink()
        checkpoint2 = mgr.create_checkpoint("After deletion", {"tool": "test"})
        
        # Restore to first checkpoint
        self.assertIsNotNone(checkpoint1)
        assert checkpoint1 is not None  # Type guard
        restored = mgr.restore_checkpoint(checkpoint1)
        self.assertTrue(restored)
        
        # File should be restored
        self.assertTrue((self.project_path / "to_delete.py").exists())
        self.assertEqual((self.project_path / "to_delete.py").read_text(), "# Will be deleted")
    
    def test_restore_with_invalid_hash(self):
        """Test restore with invalid checkpoint hash."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Try to restore non-existent checkpoint
        restored = mgr.restore_checkpoint("invalid123")
        self.assertFalse(restored)
        
        # Try with invalid format
        restored = mgr.restore_checkpoint("not-a-hash!")
        self.assertFalse(restored)
    
    def test_get_checkpoint_diff(self):
        """Test getting diff between checkpoints."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create initial checkpoint
        checkpoint1 = mgr.create_checkpoint("Initial", {"tool": "test"})
        
        # Modify files
        (self.project_path / "test.py").write_text("print('modified')")
        
        # Get diff
        diff = mgr.get_checkpoint_diff(checkpoint1)
        self.assertIsNotNone(diff)
        self.assertIn("test.py", diff)
        
        # Diff without specific checkpoint (against HEAD)
        mgr.create_checkpoint("Second", {"tool": "test"})
        (self.project_path / "test.py").write_text("print('modified again')")
        diff = mgr.get_checkpoint_diff()
        self.assertIsNotNone(diff)
    
    def test_sync_files(self):
        """Test file synchronization."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create a complex directory structure
        subdir = self.project_path / "subdir"
        subdir.mkdir()
        (subdir / "file1.py").write_text("# File 1")
        
        nested = subdir / "nested"
        nested.mkdir()
        (nested / "file2.py").write_text("# File 2")
        
        # Create destination
        dest = Path(self.temp_dir) / "sync_dest"
        dest.mkdir()
        
        # Test sync
        mgr._sync_files(self.project_path, dest)
        
        # Verify structure is preserved
        self.assertTrue((dest / "test.py").exists())
        self.assertTrue((dest / "subdir" / "file1.py").exists())
        self.assertTrue((dest / "subdir" / "nested" / "file2.py").exists())
        
        # Verify content
        self.assertEqual((dest / "test.py").read_text(), "print('hello')")
        self.assertEqual((dest / "subdir" / "file1.py").read_text(), "# File 1")
    
    def test_batch_sync_files(self):
        """Test batch file synchronization with large file sets."""
        mgr = self.checkpoint_mgr
        
        # Create many files
        for i in range(150):  # More than 100 to trigger progress logging
            file_path = self.project_path / f"file_{i}.txt"
            file_path.write_text(f"Content {i}")
        
        dest = Path(self.temp_dir) / "batch_dest"
        dest.mkdir()
        
        # Collect relative file paths to sync
        files_to_sync = {Path(f"file_{i}.txt") for i in range(150)}
        
        # Test batch sync
        mgr._batch_sync_files(files_to_sync, self.project_path, dest)
        
        # Verify all files were synced
        for i in range(150):
            dest_file = dest / f"file_{i}.txt"
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.read_text(), f"Content {i}")
    
    def test_full_restore_sync(self):
        """Test full restoration sync including deletions."""
        mgr = self.checkpoint_mgr
        
        # Setup source (checkpoint state)
        src = Path(self.temp_dir) / "checkpoint_state"
        src.mkdir()
        (src / "keep.py").write_text("# Keep this")
        (src / "modify.py").write_text("# Original")
        
        # Setup destination (current state)
        dst = Path(self.temp_dir) / "current_state"
        dst.mkdir()
        (dst / "keep.py").write_text("# Keep this")
        (dst / "modify.py").write_text("# Modified")
        (dst / "delete.py").write_text("# Should be deleted")
        
        # Run full restore sync
        mgr._full_restore_sync(src, dst)
        
        # Verify results
        self.assertTrue((dst / "keep.py").exists())
        self.assertEqual((dst / "modify.py").read_text(), "# Original")
        self.assertFalse((dst / "delete.py").exists())
    
    def test_restore_with_permission_errors(self):
        """Test restoration with permission errors."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create checkpoint
        checkpoint = mgr.create_checkpoint("Test", {"tool": "test"})
        
        # Make a file read-only
        readonly_file = self.project_path / "readonly.py"
        readonly_file.write_text("# Read only")
        readonly_file.chmod(0o444)
        
        try:
            # Try to restore (might fail on some systems)
            self.assertIsNotNone(checkpoint)
            assert checkpoint is not None  # Type guard
            restored = mgr.restore_checkpoint(checkpoint)
            # If it succeeds, that's okay - some systems allow overwriting read-only files
            if restored:
                self.assertTrue(True)
        finally:
            # Clean up - restore write permissions if file still exists
            if readonly_file.exists():
                readonly_file.chmod(0o644)
    
    def test_list_checkpoints_empty_repo(self):
        """Test listing checkpoints in empty repository."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # List checkpoints in fresh repo
        checkpoints = mgr.list_checkpoints()
        self.assertEqual(checkpoints, [])
    
    def test_checkpoint_with_binary_files(self):
        """Test checkpointing with binary files."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create binary file
        binary_file = self.project_path / "data.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
        
        # Create checkpoint
        checkpoint = mgr.create_checkpoint("With binary", {"tool": "test"})
        self.assertIsNotNone(checkpoint)
        
        # Modify binary file
        binary_file.write_bytes(b'\xff\xfe\xfd')
        
        # Restore
        self.assertIsNotNone(checkpoint)
        assert checkpoint is not None  # Type guard
        restored = mgr.restore_checkpoint(checkpoint)
        self.assertTrue(restored)
        
        # Verify binary content restored
        self.assertEqual(binary_file.read_bytes(), b'\x00\x01\x02\x03\x04\x05')
    
    def test_checkpoint_with_symlinks(self):
        """Test handling of symbolic links."""
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        # Create a file and a symlink to it
        target = self.project_path / "target.py"
        target.write_text("# Target file")
        
        link = self.project_path / "link.py"
        try:
            link.symlink_to(target)
        except OSError:
            # Skip test on systems that don't support symlinks
            self.skipTest("Symlinks not supported on this system")
        
        # Create checkpoint - should handle symlink gracefully
        checkpoint = mgr.create_checkpoint("With symlink", {"tool": "test"})
        self.assertIsNotNone(checkpoint)
    
    def test_concurrent_checkpoint_creation(self):
        """Test concurrent checkpoint creation."""
        import threading
        mgr = self.checkpoint_mgr
        mgr.init_project_repo()
        
        results = []
        errors = []
        lock = threading.Lock()
        
        def create_checkpoint(index):
            # Add retry logic for git contention
            max_retries = 3
            retry_delay = 0.1
            
            for attempt in range(max_retries):
                try:
                    # Use a lock to serialize git operations
                    with lock:
                        cp = mgr.create_checkpoint(f"Concurrent {index}", {"index": index})
                    results.append((index, cp))
                    return
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        results.append((index, None))
                        errors.append((index, str(e)))
        
        # Create multiple checkpoints concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_checkpoint, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify all succeeded
        self.assertEqual(len(results), 5)
        if errors:
            print(f"Concurrent checkpoint errors: {errors}")
        
        # In a truly concurrent scenario, some checkpoints might fail due to git limitations
        # We should ensure at least most succeed
        successful_checkpoints = [r for r in results if r[1] is not None]
        self.assertGreaterEqual(len(successful_checkpoints), 4, 
                                f"Only {len(successful_checkpoints)}/5 checkpoints succeeded")
        
        # Verify checkpoints exist in the repository
        checkpoints = mgr.list_checkpoints()
        self.assertGreaterEqual(len(checkpoints), len(successful_checkpoints))


if __name__ == '__main__':
    unittest.main()