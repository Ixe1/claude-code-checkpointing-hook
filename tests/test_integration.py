#!/usr/bin/env python3
"""Integration tests for the checkpointing system."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import shutil
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing import GitCheckpointManager, CheckpointMetadata, CheckpointConfig

# Import test utilities
sys.path.insert(0, os.path.dirname(__file__))
from test_utils import (
    create_test_project, simulate_hook_input, run_checkpoint_manager,
    TempProjectContext, init_git_repo, measure_operation_time
)


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests for the checkpointing system."""
    
    def test_full_checkpoint_restore_cycle(self):
        """Test complete workflow: create project → modify → checkpoint → restore."""
        with TempProjectContext() as project_dir:
            # Initialize as git repo to test both git and non-git projects
            init_git_repo(project_dir)
            
            # Original file content
            main_file = project_dir / "main.py"
            original_content = main_file.read_text()
            
            # Create checkpoint before modification
            pre_input = simulate_hook_input(
                'Write',
                {'file_path': str(main_file), 'content': 'print("Modified content")'},
                'test-session-1'
            )
            
            return_code, stdout, stderr = run_checkpoint_manager(pre_input, cwd=project_dir)
            self.assertEqual(return_code, 0)
            
            # Modify the file
            main_file.write_text('print("Modified content")')
            
            # Mark checkpoint as successful
            post_input = simulate_hook_input(
                'Write',
                {},
                'test-session-1',
                tool_response={'success': True}
            )
            return_code, _, _ = run_checkpoint_manager(post_input, cwd=project_dir)
            self.assertEqual(return_code, 0)
            
            # Verify file was modified
            self.assertEqual(main_file.read_text(), 'print("Modified content")')
            
            # Get checkpoint info
            git_mgr = GitCheckpointManager(project_dir)
            checkpoints = git_mgr.list_checkpoints()
            self.assertEqual(len(checkpoints), 1)
            
            # Restore checkpoint
            restored = git_mgr.restore_checkpoint(checkpoints[0]['hash'])
            self.assertTrue(restored)
            
            # Verify file was restored
            self.assertEqual(main_file.read_text(), original_content)
    
    def test_multiple_checkpoints_different_tools(self):
        """Test creating multiple checkpoints with different tools."""
        with TempProjectContext() as project_dir:
            git_mgr = GitCheckpointManager(project_dir)
            
            # Test Write tool
            write_file = project_dir / "new_file.py"
            write_input = simulate_hook_input(
                'Write',
                {'file_path': str(write_file), 'content': 'def func(): pass'},
                'session-write'
            )
            run_checkpoint_manager(write_input, cwd=project_dir)
            write_file.write_text('def func(): pass')
            
            # Test Edit tool
            main_file = project_dir / "main.py"
            edit_input = simulate_hook_input(
                'Edit',
                {
                    'file_path': str(main_file),
                    'old_string': 'Hello, world!',
                    'new_string': 'Hello, Python!'
                },
                'session-edit'
            )
            run_checkpoint_manager(edit_input, cwd=project_dir)
            content = main_file.read_text()
            main_file.write_text(content.replace('Hello, world!', 'Hello, Python!'))
            
            # Test MultiEdit tool
            utils_file = project_dir / "utils.py"
            multiedit_input = simulate_hook_input(
                'MultiEdit',
                {
                    'file_path': str(utils_file),
                    'edits': [
                        {'old_string': 'return x * 2', 'new_string': 'return x * 3'},
                        {'old_string': 'def helper', 'new_string': 'def utility'}
                    ]
                },
                'session-multiedit'
            )
            run_checkpoint_manager(multiedit_input, cwd=project_dir)
            
            # Manual checkpoint
            manual_input = simulate_hook_input(
                'Manual',
                {'message': 'After refactoring'},
                'manual'
            )
            run_checkpoint_manager(manual_input, cwd=project_dir)
            
            # Verify all checkpoints were created
            checkpoints = git_mgr.list_checkpoints()
            self.assertEqual(len(checkpoints), 4)
            
            # Verify checkpoint messages
            messages = [cp['message'] for cp in checkpoints]
            self.assertIn('After refactoring', messages)
            self.assertIn('Before 2 edits to utils.py', messages)
            self.assertIn('Before editing main.py', messages)
            self.assertIn('Before creating new_file.py', messages)
    
    def test_file_deletion_and_restoration(self):
        """Test that deleted files are restored correctly."""
        with TempProjectContext() as project_dir:
            # Create additional files
            temp_file = project_dir / "temp.txt"
            temp_file.write_text("Temporary content")
            
            config_file = project_dir / "config.json"
            config_file.write_text('{"key": "value"}')
            
            # Create checkpoint
            manual_input = simulate_hook_input('Manual', {'message': 'Before deletion'}, 'manual')
            run_checkpoint_manager(manual_input, cwd=project_dir)
            
            git_mgr = GitCheckpointManager(project_dir)
            checkpoints = git_mgr.list_checkpoints()
            checkpoint_hash = checkpoints[0]['hash']
            
            # Delete files
            temp_file.unlink()
            config_file.unlink()
            
            # Verify files are gone
            self.assertFalse(temp_file.exists())
            self.assertFalse(config_file.exists())
            
            # Restore checkpoint
            git_mgr.restore_checkpoint(checkpoint_hash)
            
            # Verify files are restored
            self.assertTrue(temp_file.exists())
            self.assertTrue(config_file.exists())
            self.assertEqual(temp_file.read_text(), "Temporary content")
            self.assertEqual(config_file.read_text(), '{"key": "value"}')
    
    def test_nested_directory_handling(self):
        """Test checkpointing with nested directory structures."""
        with TempProjectContext() as project_dir:
            # Create nested structure
            deep_dir = project_dir / "src" / "components" / "ui" / "buttons"
            deep_dir.mkdir(parents=True)
            
            button_file = deep_dir / "primary_button.py"
            button_file.write_text("class PrimaryButton: pass")
            
            # Create checkpoint
            edit_input = simulate_hook_input(
                'Edit',
                {
                    'file_path': str(button_file),
                    'old_string': 'pass',
                    'new_string': 'def __init__(self): self.color = "blue"'
                },
                'nested-test'
            )
            run_checkpoint_manager(edit_input, cwd=project_dir)
            
            # Modify file
            button_file.write_text('class PrimaryButton: def __init__(self): self.color = "blue"')
            
            # Create another file in different nested directory
            another_dir = project_dir / "tests" / "unit" / "components"
            another_dir.mkdir(parents=True)
            test_file = another_dir / "test_button.py"
            test_file.write_text("import unittest")
            
            # Restore and verify nested structure is preserved
            git_mgr = GitCheckpointManager(project_dir)
            checkpoints = git_mgr.list_checkpoints()
            git_mgr.restore_checkpoint(checkpoints[0]['hash'])
            
            # Original file should be restored
            self.assertEqual(button_file.read_text(), "class PrimaryButton: pass")
            # New file should be removed (wasn't in checkpoint)
            self.assertFalse(test_file.exists())
    
    @measure_operation_time
    def test_large_project_performance(self):
        """Test performance with a large number of files."""
        with TempProjectContext() as project_dir:
            # Create 100 files
            for i in range(100):
                subdir = project_dir / f"module_{i // 10}"
                subdir.mkdir(exist_ok=True)
                file_path = subdir / f"file_{i}.py"
                file_path.write_text(f"# File {i}\ndef func_{i}(): return {i}")
            
            # Time checkpoint creation
            start = time.time()
            manual_input = simulate_hook_input('Manual', {'message': 'Large project checkpoint'}, 'perf-test')
            return_code, _, _ = run_checkpoint_manager(manual_input, cwd=project_dir)
            checkpoint_time = time.time() - start
            
            self.assertEqual(return_code, 0)
            self.assertLess(checkpoint_time, 5.0, "Checkpoint took too long for 100 files")
            
            # Modify several files
            for i in range(0, 100, 10):
                file_path = project_dir / f"module_{i // 10}" / f"file_{i}.py"
                file_path.write_text(f"# Modified file {i}\ndef func_{i}(): return {i} * 2  # modified")
            
            # Time restoration
            git_mgr = GitCheckpointManager(project_dir)
            checkpoints = git_mgr.list_checkpoints()
            
            start = time.time()
            restored = git_mgr.restore_checkpoint(checkpoints[0]['hash'])
            restore_time = time.time() - start
            
            self.assertTrue(restored)
            self.assertLess(restore_time, 5.0, "Restore took too long for 100 files")
            
            # Verify files were restored
            for i in range(0, 100, 10):
                file_path = project_dir / f"module_{i // 10}" / f"file_{i}.py"
                content = file_path.read_text()
                self.assertIn(f"return {i}", content)
                self.assertNotIn("# modified", content)
    
    def test_concurrent_checkpoints(self):
        """Test handling of concurrent checkpoint operations."""
        with TempProjectContext() as project_dir:
            # Simulate multiple sessions creating checkpoints concurrently
            inputs = []
            for i in range(5):
                file_path = project_dir / f"concurrent_{i}.py"
                inputs.append(simulate_hook_input(
                    'Write',
                    {'file_path': str(file_path), 'content': f'print({i})'},
                    f'session-{i}'
                ))
            
            # Run checkpoints in parallel using subprocess
            processes = []
            for input_data in inputs:
                script_path = Path(__file__).parent.parent / "checkpoint-manager.py"
                proc = subprocess.Popen(
                    ['python3', str(script_path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(project_dir)
                )
                processes.append((proc, json.dumps(input_data)))
            
            # Wait for all to complete
            for proc, input_str in processes:
                stdout, stderr = proc.communicate(input=input_str)
                self.assertEqual(proc.returncode, 0)
            
            # Verify all checkpoints were created
            git_mgr = GitCheckpointManager(project_dir)
            checkpoints = git_mgr.list_checkpoints()
            self.assertGreaterEqual(len(checkpoints), 5)
            
            # Verify metadata integrity
            metadata_mgr = CheckpointMetadata()
            project_checkpoints = metadata_mgr.list_project_checkpoints(git_mgr.project_hash)
            self.assertGreaterEqual(len(project_checkpoints), 5)
    
    def test_checkpoint_with_gitignore(self):
        """Test that gitignore patterns are respected."""
        with TempProjectContext() as project_dir:
            # Create .gitignore
            gitignore = project_dir / ".gitignore"
            gitignore.write_text("*.pyc\n__pycache__/\n.env\nbuild/\n*.log")
            
            # Create files that should be ignored
            (project_dir / "test.pyc").write_text("compiled")
            (project_dir / "debug.log").write_text("log data")
            (project_dir / ".env").write_text("SECRET=value")
            
            pycache_dir = project_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "module.cpython-39.pyc").write_text("cached")
            
            # Create files that should be included
            (project_dir / "included.py").write_text("print('included')")
            
            # Initialize git repo first to ensure gitignore is respected
            git_mgr = GitCheckpointManager(project_dir)
            git_mgr.init_project_repo()
            
            # Create checkpoint
            manual_input = simulate_hook_input('Manual', {'message': 'Test gitignore'}, 'gitignore-test')
            run_checkpoint_manager(manual_input, cwd=project_dir)
            
            # Modify included file and add new ignored file
            (project_dir / "included.py").write_text("print('modified')")
            (project_dir / "new.log").write_text("new log")
            
            # Restore
            checkpoints = git_mgr.list_checkpoints()
            
            git_mgr.restore_checkpoint(checkpoints[0]['hash'])
            
            # Verify included file was restored
            self.assertEqual((project_dir / "included.py").read_text(), "print('included')")
            
            # Verify that gitignored files that existed at checkpoint time still exist
            # (they're untracked, so git doesn't remove them)
            self.assertTrue((project_dir / ".env").exists())
            
            # But files created after the checkpoint should be removed
            self.assertFalse((project_dir / "new.log").exists())
            
            # Other gitignored files that were in subdirs might be removed if the subdir was tracked
            # The behavior depends on git's handling of directories
    
    def test_error_recovery(self):
        """Test system behavior when errors occur."""
        with TempProjectContext() as project_dir:
            # Test with non-existent file path
            bad_input = simulate_hook_input(
                'Edit',
                {
                    'file_path': str(project_dir / "nonexistent" / "deeply" / "nested.py"),
                    'old_string': 'old',
                    'new_string': 'new'
                },
                'error-test'
            )
            
            return_code, stdout, stderr = run_checkpoint_manager(bad_input, cwd=project_dir)
            # Should still succeed (checkpoint created even if file doesn't exist)
            self.assertEqual(return_code, 0)
            
            # Test with very large metadata
            large_metadata_input = {
                'tool_name': 'Write',
                'tool_input': {
                    'file_path': str(project_dir / "test.py"),
                    'content': 'x' * (2 * 1024 * 1024)  # 2MB content
                },
                'session_id': 'large-metadata'
            }
            
            return_code, stdout, stderr = run_checkpoint_manager(large_metadata_input, cwd=project_dir)
            # Should handle gracefully
            self.assertEqual(return_code, 0)


if __name__ == '__main__':
    unittest.main()