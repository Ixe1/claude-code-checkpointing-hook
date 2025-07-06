#!/usr/bin/env python3
"""Tests for the cleanup-checkpoints.py script."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing import GitCheckpointManager, CheckpointMetadata, CheckpointConfig

# Import test utilities
sys.path.insert(0, os.path.dirname(__file__))
from test_utils import create_test_project


class TestCleanupScript(unittest.TestCase):
    """Test cases for cleanup-checkpoints.py functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = create_test_project(Path(self.temp_dir))
        self.script_path = Path(__file__).parent.parent / "cleanup-checkpoints.py"
        
        # Create config directory
        self.config_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup existing config if any
        self.config_backup = None
        if (self.config_dir / "config.json").exists():
            self.config_backup = (self.config_dir / "config.json").read_text()
        
        # Create test config
        test_config = {
            "enabled": True,
            "retention_days": 7,
            "exclude_patterns": [],
            "max_file_size_mb": 100,
            "checkpoint_on_stop": False,
            "auto_cleanup": True
        }
        (self.config_dir / "config.json").write_text(json.dumps(test_config))
        
        # Initialize git and create checkpoints
        self.git_mgr = GitCheckpointManager(self.project_dir)
        self.git_mgr.init_project_repo()
        self.metadata_mgr = CheckpointMetadata()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
        
        # Restore original config
        if self.config_backup:
            (self.config_dir / "config.json").write_text(self.config_backup)
        
        # Clean up test checkpoints
        checkpoint_base = self.config_dir / "checkpoints"
        if checkpoint_base.exists():
            for project_dir in checkpoint_base.iterdir():
                if project_dir.is_dir() and "test_project" in str(project_dir):
                    shutil.rmtree(project_dir)
    
    def run_cleanup_script(self, args: list) -> tuple:
        """Run cleanup-checkpoints.py with given arguments.
        
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        cmd = ["python3", str(self.script_path)] + args
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_dir)
        )
        
        return result.returncode, result.stdout, result.stderr
    
    def create_old_checkpoint(self, message: str, days_old: int) -> str:
        """Create a checkpoint that appears to be days_old days in the past."""
        # Create checkpoint
        checkpoint_hash = self.git_mgr.create_checkpoint(message, {"tool": "test"})
        self.assertIsNotNone(checkpoint_hash)
        assert checkpoint_hash is not None  # Type guard
        
        # Add checkpoint to metadata first
        project_hash = self.git_mgr.project_hash
        self.metadata_mgr.add_checkpoint(
            project_hash,
            checkpoint_hash,
            "test",
            {"message": message},
            "test-session"
        )
        
        # Now update the timestamp to make it appear old
        metadata = self.metadata_mgr._load_metadata()
        if project_hash in metadata and checkpoint_hash in metadata[project_hash]:
            old_timestamp = (datetime.now() - timedelta(days=days_old)).isoformat()
            metadata[project_hash][checkpoint_hash]['timestamp'] = old_timestamp
            self.metadata_mgr._save_metadata(metadata)
        
        return checkpoint_hash
    
    def test_cleanup_old_checkpoints_project(self):
        """Test cleaning up old checkpoints for current project."""
        # Create checkpoints of various ages
        old_checkpoint = self.create_old_checkpoint("Old checkpoint", 10)
        recent_checkpoint = self.create_old_checkpoint("Recent checkpoint", 2)
        
        # Verify checkpoints were created
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        self.assertEqual(len(project_checkpoints), 2, f"Expected 2 checkpoints, got {len(project_checkpoints)}")
        
        # Run cleanup with 7 day retention
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "7"]
        )
        
        if returncode != 0:
            print(f"Cleanup failed with stderr: {stderr}")
        
        self.assertEqual(returncode, 0)
        self.assertIn("Cleaned up", stdout)
        self.assertIn("1 checkpoint", stdout)
        
        # Verify old checkpoint was removed from metadata
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        checkpoint_hashes = [cp['hash'] for cp in project_checkpoints]
        self.assertNotIn(old_checkpoint, checkpoint_hashes)
        self.assertIn(recent_checkpoint, checkpoint_hashes)
    
    def test_cleanup_dry_run(self):
        """Test dry-run mode."""
        # Create old checkpoint
        old_checkpoint = self.create_old_checkpoint("Old checkpoint", 10)
        
        # Run cleanup in dry-run mode
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "7", "--dry-run"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("Would remove checkpoint", stdout)
        self.assertIn(old_checkpoint[:8], stdout)
        
        # Verify checkpoint still exists
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        checkpoint_hashes = [cp['hash'] for cp in project_checkpoints]
        self.assertIn(old_checkpoint, checkpoint_hashes)
    
    def test_cleanup_all_projects(self):
        """Test cleaning up all projects."""
        # Create another project
        other_project = create_test_project(Path(self.temp_dir) / "other_project")
        other_git_mgr = GitCheckpointManager(other_project)
        other_git_mgr.init_project_repo()
        
        # Create old checkpoints in both projects
        old_checkpoint1 = self.create_old_checkpoint("Old in project 1", 10)
        
        # Switch to other project and create checkpoint
        os.chdir(str(other_project))
        other_checkpoint = other_git_mgr.create_checkpoint("Old in project 2", {"tool": "test"})
        self.assertIsNotNone(other_checkpoint)
        assert other_checkpoint is not None  # Type guard
        
        # Add to metadata
        self.metadata_mgr.add_checkpoint(
            other_git_mgr.project_hash,
            other_checkpoint,
            "test",
            {"message": "Old in project 2"},
            "test-session"
        )
        
        # Make it old
        metadata = self.metadata_mgr._load_metadata()
        if other_git_mgr.project_hash in metadata and other_checkpoint in metadata[other_git_mgr.project_hash]:
            old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
            metadata[other_git_mgr.project_hash][other_checkpoint]['timestamp'] = old_timestamp
            self.metadata_mgr._save_metadata(metadata)
        
        # Run cleanup for all projects
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--all", "--retention-days", "7"]
        )
        
        if returncode != 0:
            print(f"Cleanup all failed with stderr: {stderr}")
        
        self.assertEqual(returncode, 0)
        self.assertIn("Processing", stdout)
        self.assertIn("project", stdout)
    
    def test_cleanup_orphaned_repos(self):
        """Test cleaning up orphaned repositories."""
        # Create a checkpoint repo without corresponding project
        checkpoint_base = self.config_dir / "checkpoints"
        checkpoint_base.mkdir(parents=True, exist_ok=True)
        
        # Create fake orphaned repo with proper hash length (12 chars)
        orphaned_repo = checkpoint_base / "abc123def456"  # 12 character hash
        if orphaned_repo.exists():
            import shutil
            shutil.rmtree(orphaned_repo)
        orphaned_repo.mkdir()
        (orphaned_repo / "test.txt").write_text("orphaned")
        
        # Run cleanup for orphaned repos
        returncode, stdout, stderr = self.run_cleanup_script(["--orphaned"])
        
        self.assertEqual(returncode, 0)
        # Should find at least the one we created
        self.assertIn("orphaned checkpoint", stdout)
        
        # Verify our specific orphaned repo was removed
        self.assertFalse(orphaned_repo.exists())
    
    def test_cleanup_respects_config(self):
        """Test that cleanup respects config file settings."""
        # Update config to have shorter retention
        test_config = {
            "enabled": True,
            "retention_days": 3,
            "auto_cleanup": True
        }
        (self.config_dir / "config.json").write_text(json.dumps(test_config))
        
        # Create checkpoints
        old_checkpoint = self.create_old_checkpoint("4 days old", 4)
        recent_checkpoint = self.create_old_checkpoint("2 days old", 2)
        
        # Run cleanup without specifying retention (should use config)
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir)]
        )
        
        self.assertEqual(returncode, 0)
        
        # Verify 4-day-old checkpoint was removed
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        checkpoint_hashes = [cp['hash'] for cp in project_checkpoints]
        self.assertNotIn(old_checkpoint, checkpoint_hashes)
        self.assertIn(recent_checkpoint, checkpoint_hashes)
    
    def test_cleanup_no_checkpoints(self):
        """Test cleanup when no checkpoints exist."""
        empty_project = create_test_project(Path(self.temp_dir) / "empty")
        
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(empty_project)]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("No checkpoint repository found", stdout)
    
    def test_cleanup_all_checkpoints_old(self):
        """Test when all checkpoints are old."""
        # Create only old checkpoints
        old1 = self.create_old_checkpoint("Old 1", 10)
        old2 = self.create_old_checkpoint("Old 2", 15)
        old3 = self.create_old_checkpoint("Old 3", 20)
        
        # Run cleanup
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "7"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("3 checkpoint", stdout)
        
        # All should be removed
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        self.assertEqual(len(project_checkpoints), 0)
    
    def test_cleanup_no_old_checkpoints(self):
        """Test when no checkpoints are old enough to clean."""
        # Create only recent checkpoints
        recent1 = self.create_old_checkpoint("Recent 1", 1)
        recent2 = self.create_old_checkpoint("Recent 2", 2)
        recent3 = self.create_old_checkpoint("Recent 3", 3)
        
        # Run cleanup
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "7"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("Cleaned up 0 checkpoint", stdout)
        
        # All should remain
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        self.assertEqual(len(project_checkpoints), 3)
    
    def test_cleanup_invalid_retention_days(self):
        """Test with invalid retention days."""
        # Negative retention days
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--retention-days", "-5"]
        )
        
        # Should handle gracefully (likely use minimum of 1)
        self.assertEqual(returncode, 0)
    
    def test_cleanup_very_large_retention(self):
        """Test with very large retention period."""
        # Create old checkpoint
        old_checkpoint = self.create_old_checkpoint("Old checkpoint", 100)
        
        # Run with 1000 day retention
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "1000"]
        )
        
        self.assertEqual(returncode, 0)
        self.assertIn("Cleaned up 0 checkpoint", stdout)
        
        # Should not remove anything
        project_checkpoints = self.metadata_mgr.list_project_checkpoints(self.git_mgr.project_hash)
        checkpoint_hashes = [cp['hash'] for cp in project_checkpoints]
        self.assertIn(old_checkpoint, checkpoint_hashes)
    
    def test_cleanup_output_formatting(self):
        """Test that output is properly formatted."""
        # Create some checkpoints to clean
        self.create_old_checkpoint("Old 1", 10)
        self.create_old_checkpoint("Old 2", 15)
        
        returncode, stdout, stderr = self.run_cleanup_script(
            ["--project", str(self.project_dir), "--retention-days", "7", "--dry-run"]
        )
        
        self.assertEqual(returncode, 0)
        
        # Check output has expected format
        lines = stdout.splitlines()
        self.assertTrue(any("Would remove checkpoint" in line for line in lines))
        self.assertTrue(any("from" in line for line in lines))
        
        # Should show checkpoint hashes
        self.assertTrue(any(len([p for p in line.split() if len(p) == 8 and all(c in '0123456789abcdef' for c in p)]) > 0 
                           for line in lines))


if __name__ == '__main__':
    unittest.main()