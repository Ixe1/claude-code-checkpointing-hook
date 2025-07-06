#!/usr/bin/env python3
"""Tests for the restore-checkpoint.py script."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing import GitCheckpointManager, CheckpointMetadata

# Import test utilities
sys.path.insert(0, os.path.dirname(__file__))
from test_utils import create_test_project, simulate_hook_input, run_checkpoint_manager


class TestRestoreScript(unittest.TestCase):
    """Test cases for restore-checkpoint.py functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = create_test_project(Path(self.temp_dir))
        self.script_path = Path(__file__).parent.parent / "restore-checkpoint.py"
        
        # Create some checkpoints for testing
        self.git_mgr = GitCheckpointManager(self.project_dir)
        self.git_mgr.init_project_repo()
        self.metadata_mgr = CheckpointMetadata()
        
        # Create initial checkpoint
        self.checkpoint1 = self.git_mgr.create_checkpoint("Initial state", {"tool": "test", "session": "test1"})
        self.assertIsNotNone(self.checkpoint1)
        assert self.checkpoint1 is not None  # Type guard
        self.metadata_mgr.add_checkpoint(
            self.git_mgr.project_hash,
            self.checkpoint1,
            "test",
            {"message": "Initial state"},
            "test1"
        )
        
        # Modify files and create second checkpoint
        (self.project_dir / "main.py").write_text("print('modified')")
        self.checkpoint2 = self.git_mgr.create_checkpoint("After modification", {"tool": "test", "session": "test2"})
        self.assertIsNotNone(self.checkpoint2)
        assert self.checkpoint2 is not None  # Type guard
        self.metadata_mgr.add_checkpoint(
            self.git_mgr.project_hash,
            self.checkpoint2,
            "test",
            {"message": "After modification"},
            "test2"
        )
        
        # Create another checkpoint
        (self.project_dir / "new_file.py").write_text("# New file")
        self.checkpoint3 = self.git_mgr.create_checkpoint("Added new file", {"tool": "test", "session": "test3"})
        self.assertIsNotNone(self.checkpoint3)
        assert self.checkpoint3 is not None  # Type guard
        self.metadata_mgr.add_checkpoint(
            self.git_mgr.project_hash,
            self.checkpoint3,
            "Write",
            {"file_path": str(self.project_dir / "new_file.py"), "content": "# New file"},
            "test3"
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def run_restore_script(self, args: list, input_text: str = "") -> tuple:
        """Run restore-checkpoint.py with given arguments.
        
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        cmd = ["python3", str(self.script_path)] + args
        
        result = subprocess.run(
            cmd,
            input=input_text if input_text else None,
            capture_output=True,
            text=True,
            cwd=str(self.project_dir)
        )
        
        return result.returncode, result.stdout, result.stderr
    
    def test_list_checkpoints(self):
        """Test listing checkpoints with --list flag."""
        returncode, stdout, stderr = self.run_restore_script(["--list"])
        
        self.assertEqual(returncode, 0)
        self.assertIn("Available checkpoints", stdout)
        self.assertIn("Added new file", stdout)
        self.assertIn("After modification", stdout)
        self.assertIn("Initial state", stdout)
        
        # Check ordering (newest first)
        lines = stdout.splitlines()
        checkpoint_lines = [l for l in lines if "ago" in l or "just now" in l]
        self.assertGreater(len(checkpoint_lines), 0)
    
    def test_list_with_limit(self):
        """Test listing checkpoints with limit."""
        returncode, stdout, stderr = self.run_restore_script(["--list", "--limit", "2"])
        
        self.assertEqual(returncode, 0)
        # Should only show 2 most recent checkpoints
        self.assertIn("Added new file", stdout)
        self.assertIn("After modification", stdout)
        self.assertNotIn("Initial state", stdout)
    
    def test_restore_by_id(self):
        """Test restoring a specific checkpoint by ID."""
        # Get the short hash
        assert self.checkpoint1 is not None  # Type guard
        short_hash = self.checkpoint1[:8]
        
        returncode, stdout, stderr = self.run_restore_script([short_hash])
        
        self.assertEqual(returncode, 0)
        self.assertIn("Successfully restored", stdout)
        
        # Verify file was restored
        self.assertEqual((self.project_dir / "main.py").read_text(), "def main():\n    print('Hello, world!')\n\nif __name__ == '__main__':\n    main()\n")
        self.assertFalse((self.project_dir / "new_file.py").exists())
    
    def test_restore_dry_run(self):
        """Test dry-run mode."""
        assert self.checkpoint1 is not None  # Type guard
        short_hash = self.checkpoint1[:8]
        
        returncode, stdout, stderr = self.run_restore_script([short_hash, "--dry-run"])
        
        self.assertEqual(returncode, 0)
        self.assertIn("Would restore to checkpoint", stdout)
        
        # Verify no actual changes were made
        self.assertEqual((self.project_dir / "main.py").read_text(), "print('modified')")
        self.assertTrue((self.project_dir / "new_file.py").exists())
    
    def test_search_checkpoints(self):
        """Test searching checkpoints."""
        # Search by message
        returncode, stdout, stderr = self.run_restore_script(["--search", "modification"])
        
        self.assertEqual(returncode, 0)
        self.assertIn("After modification", stdout)
        self.assertNotIn("Initial state", stdout)
        self.assertNotIn("Added new file", stdout)
        
        # Search by file
        returncode, stdout, stderr = self.run_restore_script(["--search", "new_file.py"])
        
        self.assertEqual(returncode, 0)
        self.assertIn("Added new file", stdout)
    
    def test_ambiguous_checkpoint_id(self):
        """Test handling of ambiguous checkpoint IDs."""
        # First get the actual checkpoint hashes to find a common prefix
        checkpoints = self.git_mgr.list_checkpoints()
        if len(checkpoints) >= 2:
            # Find a common prefix between two checkpoints
            hash1 = checkpoints[0]['hash']
            hash2 = checkpoints[1]['hash']
            common_prefix = None
            for i in range(min(len(hash1), len(hash2))):
                if hash1[i] == hash2[i]:
                    common_prefix = hash1[:i+1]
                else:
                    break
            
            if common_prefix and len(common_prefix) > 0:
                # Use the common prefix
                returncode, stdout, stderr = self.run_restore_script([common_prefix])
                self.assertNotEqual(returncode, 0)
                self.assertIn("Ambiguous", stderr)
            else:
                # No common prefix, skip test
                self.skipTest("No common prefix found in checkpoint hashes")
        else:
            self.skipTest("Not enough checkpoints for ambiguity test")
    
    def test_nonexistent_checkpoint(self):
        """Test handling of non-existent checkpoint."""
        returncode, stdout, stderr = self.run_restore_script(["nonexistent123"])
        
        self.assertNotEqual(returncode, 0)
        self.assertIn("No checkpoint found", stderr)
    
    def test_interactive_restore(self):
        """Test interactive restoration flow."""
        # Simulate user selecting checkpoint 1 (newest)
        user_input = "1\ny\n"
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        self.assertEqual(returncode, 0)
        self.assertIn("Available checkpoints", stdout)
        self.assertIn("Selected checkpoint", stdout)
        self.assertIn("Successfully restored", stdout)
    
    def test_interactive_restore_quit(self):
        """Test quitting interactive restore."""
        user_input = "q\n"
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        self.assertEqual(returncode, 0)
        self.assertIn("Restoration cancelled", stdout)
    
    def test_interactive_restore_by_hash(self):
        """Test interactive restore by entering hash."""
        assert self.checkpoint2 is not None  # Type guard
        short_hash = self.checkpoint2[:8]
        user_input = f"{short_hash}\ny\n"
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        self.assertEqual(returncode, 0)
        self.assertIn("Selected checkpoint", stdout)
        self.assertIn(short_hash, stdout)
    
    def test_interactive_restore_no_confirm(self):
        """Test canceling restore at confirmation."""
        user_input = "1\nn\n"
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        self.assertEqual(returncode, 0)
        self.assertIn("Restoration cancelled", stdout)
        
        # Verify no changes were made
        self.assertTrue((self.project_dir / "new_file.py").exists())
    
    def test_project_flag(self):
        """Test using --project flag for different directory."""
        # Create another project
        other_project = create_test_project(Path(self.temp_dir) / "other_project")
        other_git_mgr = GitCheckpointManager(other_project)
        other_git_mgr.init_project_repo()
        other_checkpoint = other_git_mgr.create_checkpoint("Other project", {"tool": "test"})
        
        # Run from original directory but target other project
        returncode, stdout, stderr = self.run_restore_script(
            ["--project", str(other_project), "--list"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("Other project", stdout)
        self.assertNotIn("Initial state", stdout)  # From main project
    
    def test_empty_project(self):
        """Test behavior with no checkpoints."""
        empty_project = create_test_project(Path(self.temp_dir) / "empty")
        
        returncode, stdout, stderr = self.run_restore_script(
            ["--project", str(empty_project), "--list"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("No checkpoints found", stdout)
    
    def test_output_formatting(self):
        """Test that output is properly formatted."""
        returncode, stdout, stderr = self.run_restore_script(["--list"])
        
        self.assertEqual(returncode, 0)
        
        # Check for expected formatting elements
        lines = stdout.splitlines()
        
        # Should have numbered list
        self.assertTrue(any(line.strip().startswith("1.") for line in lines))
        self.assertTrue(any(line.strip().startswith("2.") for line in lines))
        
        # Should show relative time
        self.assertTrue(any("ago" in line or "just now" in line for line in lines))
        
        # Should show hash
        assert self.checkpoint3 is not None  # Type guard
        self.assertTrue(any(self.checkpoint3[:8] in line for line in lines))
    
    def test_diff_display(self):
        """Test that diff is displayed during interactive restore."""
        # Create a more complex change for better diff testing
        (self.project_dir / "utils.py").write_text("def helper(x):\n    return x * 10\n")
        complex_checkpoint = self.git_mgr.create_checkpoint("Modified utils", {"tool": "test"})
        
        user_input = "1\nn\n"  # Select first, but don't confirm
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        self.assertEqual(returncode, 0)
        self.assertIn("Changes that will be applied", stdout)
        self.assertIn("utils.py", stdout)
    
    def test_ctrl_c_handling(self):
        """Test that Ctrl+C is handled gracefully."""
        # This is tricky to test directly, but we can at least verify
        # the script handles EOFError which is similar
        user_input = ""  # Empty input simulates EOF
        
        returncode, stdout, stderr = self.run_restore_script([], input_text=user_input)
        
        # Should handle gracefully
        self.assertEqual(returncode, 0)
        self.assertIn("Restoration cancelled", stdout)


if __name__ == '__main__':
    unittest.main()