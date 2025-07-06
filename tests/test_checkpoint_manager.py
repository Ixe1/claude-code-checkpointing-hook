#!/usr/bin/env python3
"""Tests for the checkpoint manager script."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import shutil

import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import main module with hyphenated name
import importlib.util
spec = importlib.util.spec_from_file_location(
    "checkpoint_manager", 
    os.path.join(os.path.dirname(__file__), '..', 'checkpoint-manager.py')
)
if spec and spec.loader:
    checkpoint_manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checkpoint_manager)
else:
    raise ImportError("Could not load checkpoint-manager module")

from checkpointing import CheckpointConfig, GitCheckpointManager, CheckpointMetadata

# Import test utilities
sys.path.insert(0, os.path.dirname(__file__))
from test_utils import create_test_project, simulate_hook_input, run_checkpoint_manager


class TestCheckpointManager(unittest.TestCase):
    """Test cases for checkpoint manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = create_test_project(Path(self.temp_dir))
        self.original_cwd = os.getcwd()
        os.chdir(str(self.project_dir))
        
        # Create a config file with test settings
        self.config_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
        self.config_backup = None
        if (self.config_dir / "config.json").exists():
            self.config_backup = (self.config_dir / "config.json").read_text()
        
        # Create test config
        self.config_dir.mkdir(parents=True, exist_ok=True)
        test_config = {
            "enabled": True,
            "retention_days": 7,
            "exclude_patterns": ["*.log", "node_modules/"],
            "max_file_size_mb": 100,
            "checkpoint_on_stop": False,
            "auto_cleanup": True
        }
        (self.config_dir / "config.json").write_text(json.dumps(test_config))
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
        
        # Restore original config if it existed
        if self.config_backup:
            (self.config_dir / "config.json").write_text(self.config_backup)
        
        # Clean up any test checkpoints
        checkpoint_base = self.config_dir / "checkpoints"
        if checkpoint_base.exists():
            for project_dir in checkpoint_base.iterdir():
                if project_dir.is_dir() and "test_project" in str(project_dir):
                    shutil.rmtree(project_dir)
    
    def test_handle_pre_tool_use_write_real(self):
        """Test PreToolUse hook for Write tool with real operations."""
        # Create a test file to be modified
        test_file = self.project_dir / "test_file.py"
        test_file.write_text("# Original content")
        
        input_data = simulate_hook_input(
            'Write',
            {'file_path': str(test_file), 'content': 'print("hello")'},
            'session123'
        )
        
        # Run the actual checkpoint manager
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        
        # Verify behavior
        self.assertEqual(result, 0)
        
        # Check that checkpoint was actually created
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertIn("Before creating test_file.py", checkpoints[0]['message'])
        
        # Check metadata was stored
        metadata_mgr = CheckpointMetadata()
        project_checkpoints = metadata_mgr.list_project_checkpoints(git_mgr.project_hash)
        self.assertEqual(len(project_checkpoints), 1)
        self.assertEqual(project_checkpoints[0]['tool_name'], 'Write')
        self.assertEqual(project_checkpoints[0]['session_id'], 'session123')
    
    def test_handle_pre_tool_use_disabled(self):
        """Test PreToolUse hook when checkpointing is disabled."""
        # Disable checkpointing in config
        test_config = json.loads((self.config_dir / "config.json").read_text())
        test_config["enabled"] = False
        (self.config_dir / "config.json").write_text(json.dumps(test_config))
        
        input_data = simulate_hook_input(
            'Write',
            {'file_path': str(self.project_dir / "test.py"), 'content': 'test'},
            'session123'
        )
        
        # Call the function
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        
        # Should exit early
        self.assertEqual(result, 0)
        
        # Verify no checkpoint was created
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 0)
    
    def test_handle_pre_tool_use_excluded_file(self):
        """Test PreToolUse hook with excluded file."""
        # .log files are in our exclude patterns
        input_data = simulate_hook_input(
            'Write',
            {'file_path': str(self.project_dir / "test.log"), 'content': 'log data'},
            'session123'
        )
        
        # Capture stderr to verify the skip message
        with patch('sys.stderr', new_callable=MagicMock) as mock_stderr:
            result = checkpoint_manager.handle_pre_tool_use(input_data)
        
        # Should exit early without creating checkpoint
        self.assertEqual(result, 0)
        
        # Verify skip message was printed to stderr
        stderr_content = ''.join(call.args[0] for call in mock_stderr.write.call_args_list if call.args)
        self.assertIn("Skipping checkpoint for excluded file", stderr_content)
        
        # Verify no checkpoint was created
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 0)
    
    def test_handle_pre_tool_use_non_file_tool(self):
        """Test PreToolUse hook with non-file modification tool."""
        input_data = simulate_hook_input(
            'Bash',
            {'command': 'ls -la'},
            'session123'
        )
        
        # Call the function
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        
        # Should exit early without creating checkpoint
        self.assertEqual(result, 0)
        
        # Verify no checkpoint was created
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 0)
    
    def test_handle_pre_tool_use_manual_checkpoint(self):
        """Test PreToolUse hook for manual checkpoint."""
        input_data = simulate_hook_input(
            'Manual',
            {'message': 'Before major refactoring'},
            'manual'
        )
        
        # Call the function
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        
        # Verify manual checkpoint was created
        self.assertEqual(result, 0)
        
        # Check that checkpoint was created with custom message
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['message'], 'Before major refactoring')
        
        # Check metadata
        metadata_mgr = CheckpointMetadata()
        project_checkpoints = metadata_mgr.list_project_checkpoints(git_mgr.project_hash)
        self.assertEqual(len(project_checkpoints), 1)
        self.assertEqual(project_checkpoints[0]['tool_name'], 'Manual')
        self.assertEqual(project_checkpoints[0]['session_id'], 'manual')
    
    def test_handle_post_tool_use_success(self):
        """Test PostToolUse hook for successful operation."""
        # First create a checkpoint
        pre_input = simulate_hook_input(
            'Write',
            {'file_path': str(self.project_dir / "test.py"), 'content': 'test'},
            'session123'
        )
        checkpoint_manager.handle_pre_tool_use(pre_input)
        
        # Now test post hook
        post_input = {
            'tool_name': 'Write',
            'tool_response': {'success': True, 'message': 'File written'}
        }
        
        # Call the function
        result = checkpoint_manager.handle_post_tool_use(post_input)
        
        # Verify behavior
        self.assertEqual(result, 0)
        
        # Check that metadata was updated
        git_mgr = GitCheckpointManager(self.project_dir)
        metadata_mgr = CheckpointMetadata()
        checkpoints = metadata_mgr.list_project_checkpoints(git_mgr.project_hash)
        
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['status'], 'success')
        self.assertEqual(checkpoints[0]['tool_response']['message'], 'File written')
    
    def test_handle_post_tool_use_failure(self):
        """Test PostToolUse hook for failed operation."""
        # First create a checkpoint
        pre_input = simulate_hook_input(
            'Edit',
            {'file_path': str(self.project_dir / "test.py"), 'old_string': 'old', 'new_string': 'new'},
            'session123'
        )
        checkpoint_manager.handle_pre_tool_use(pre_input)
        
        # Now test post hook with failure
        post_input = {
            'tool_name': 'Edit',
            'tool_response': {'success': False, 'error': 'Permission denied'}
        }
        
        # Call the function
        result = checkpoint_manager.handle_post_tool_use(post_input)
        
        # Verify behavior
        self.assertEqual(result, 0)
        
        # Check that metadata was updated with failure
        git_mgr = GitCheckpointManager(self.project_dir)
        metadata_mgr = CheckpointMetadata()
        checkpoints = metadata_mgr.list_project_checkpoints(git_mgr.project_hash)
        
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['status'], 'failed')
        self.assertEqual(checkpoints[0]['tool_response']['error'], 'Permission denied')
    
    def test_show_status(self):
        """Test showing checkpoint status."""
        # Create some checkpoints with different statuses
        git_mgr = GitCheckpointManager(self.project_dir)
        metadata_mgr = CheckpointMetadata()
        
        # Create successful checkpoint
        input1 = simulate_hook_input('Write', {'file_path': str(self.project_dir / "file1.py"), 'content': 'test'}, 'session1')
        checkpoint_manager.handle_pre_tool_use(input1)
        checkpoint_manager.handle_post_tool_use({'tool_name': 'Write', 'tool_response': {'success': True}})
        
        # Create failed checkpoint  
        input2 = simulate_hook_input('Edit', {'file_path': str(self.project_dir / "file2.py"), 'old_string': 'a', 'new_string': 'b'}, 'session2')
        checkpoint_manager.handle_pre_tool_use(input2)
        checkpoint_manager.handle_post_tool_use({'tool_name': 'Edit', 'tool_response': {'success': False, 'error': 'Not found'}})
        
        # Create pending checkpoint (no post hook)
        input3 = simulate_hook_input('Write', {'file_path': str(self.project_dir / "file1.py"), 'content': 'updated'}, 'session3')
        checkpoint_manager.handle_pre_tool_use(input3)
        
        # Capture output
        with patch('builtins.print') as mock_print:
            checkpoint_manager.show_status()
            
            # Verify output includes statistics
            print_output = '\n'.join(str(call) for call in mock_print.call_args_list)
            self.assertIn('Total Checkpoints: 3', print_output)
            self.assertIn('Successful: 1', print_output)
            self.assertIn('Failed: 1', print_output)
            self.assertIn('Pending: 1', print_output)
    
    def test_main_with_status_flag(self):
        """Test main function with --status flag."""
        test_args = ['checkpoint-manager.py', '--status']
        
        with patch('sys.argv', test_args):
            with patch.object(checkpoint_manager, 'show_status') as mock_show_status:
                result = checkpoint_manager.main()
                
                self.assertEqual(result, 0)
                mock_show_status.assert_called_once()
    
    def test_main_with_invalid_json(self):
        """Test main function with invalid JSON input."""
        test_args = ['checkpoint-manager.py']
        
        with patch('sys.argv', test_args):
            with patch('sys.stdin.read', return_value='invalid json'):
                with patch('json.load', side_effect=json.JSONDecodeError('msg', 'doc', 0)):
                    result = checkpoint_manager.main()
                    
                    self.assertEqual(result, 1)
    
    def test_checkpoint_message_generation(self):
        """Test checkpoint message generation for different tools."""
        test_cases = [
            {
                'tool_name': 'Write',
                'tool_input': {'file_path': str(self.project_dir / 'src' / 'main.py')},
                'expected_message': 'Before creating main.py'
            },
            {
                'tool_name': 'Edit',
                'tool_input': {'file_path': str(self.project_dir / 'test' / 'utils.py'), 'old_string': 'a', 'new_string': 'b'},
                'expected_message': 'Before editing utils.py'
            },
            {
                'tool_name': 'MultiEdit',
                'tool_input': {
                    'file_path': str(self.project_dir / 'src' / 'app.py'),
                    'edits': [{'old_string': 'a', 'new_string': 'b'}, {'old_string': 'c', 'new_string': 'd'}]
                },
                'expected_message': 'Before 2 edits to app.py'
            }
        ]
        
        git_mgr = GitCheckpointManager(self.project_dir)
        
        for test_case in test_cases:
            # Create the necessary directories
            file_path = Path(test_case['tool_input']['file_path'])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            input_data = simulate_hook_input(
                test_case['tool_name'],
                test_case['tool_input'],
                'test123'
            )
            
            # Call the function
            checkpoint_manager.handle_pre_tool_use(input_data)
            
            # Get the latest checkpoint and verify the message
            checkpoints = git_mgr.list_checkpoints()
            self.assertGreater(len(checkpoints), 0)
            self.assertEqual(checkpoints[0]['message'], test_case['expected_message'])
    
    def test_edit_tool_integration(self):
        """Test Edit tool with actual file modifications."""
        # Create a file with content
        test_file = self.project_dir / "test_edit.py"
        test_file.write_text("def hello():\n    print('Hello')\n")
        
        # Create checkpoint before edit
        input_data = simulate_hook_input(
            'Edit',
            {
                'file_path': str(test_file),
                'old_string': "print('Hello')",
                'new_string': "print('Hello, World!')"
            },
            'edit-session'
        )
        
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        self.assertEqual(result, 0)
        
        # Simulate the edit
        content = test_file.read_text()
        new_content = content.replace("print('Hello')", "print('Hello, World!')")
        test_file.write_text(new_content)
        
        # Run post hook
        post_result = checkpoint_manager.handle_post_tool_use({
            'tool_name': 'Edit',
            'tool_response': {'success': True}
        })
        self.assertEqual(post_result, 0)
        
        # Verify we can restore to the checkpoint
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        
        # Restore and verify content
        git_mgr.restore_checkpoint(checkpoints[0]['hash'])
        restored_content = test_file.read_text()
        self.assertEqual(restored_content, "def hello():\n    print('Hello')\n")
    
    def test_multiedit_tool_integration(self):
        """Test MultiEdit tool with multiple edits."""
        # Create a file with content
        test_file = self.project_dir / "multi_edit.py"
        test_file.write_text("a = 1\nb = 2\nc = 3\n")
        
        # Create checkpoint before multi-edit
        input_data = simulate_hook_input(
            'MultiEdit',
            {
                'file_path': str(test_file),
                'edits': [
                    {'old_string': 'a = 1', 'new_string': 'a = 10'},
                    {'old_string': 'b = 2', 'new_string': 'b = 20'},
                    {'old_string': 'c = 3', 'new_string': 'c = 30'}
                ]
            },
            'multiedit-session'
        )
        
        result = checkpoint_manager.handle_pre_tool_use(input_data)
        self.assertEqual(result, 0)
        
        # Verify checkpoint message
        git_mgr = GitCheckpointManager(self.project_dir)
        checkpoints = git_mgr.list_checkpoints()
        self.assertEqual(checkpoints[0]['message'], 'Before 3 edits to multi_edit.py')


if __name__ == '__main__':
    unittest.main()