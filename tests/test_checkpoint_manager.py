#!/usr/bin/env python3
"""Tests for the checkpoint manager script."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

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


class TestCheckpointManager(unittest.TestCase):
    """Test cases for checkpoint manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_handle_pre_tool_use_write(self):
        """Test PreToolUse hook for Write tool."""
        input_data = {
            'tool_name': 'Write',
            'tool_input': {
                'file_path': '/test/file.py',
                'content': 'print("hello")'
            },
            'session_id': 'session123'
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                with patch.object(checkpoint_manager, 'CheckpointMetadata') as mock_metadata:
                    # Configure mocks
                    config_instance = MagicMock()
                    config_instance.enabled = True
                    config_instance.should_exclude_file.return_value = False
                    mock_config.return_value = config_instance
                    
                    git_instance = MagicMock()
                    git_instance.is_git_repo.return_value = True
                    git_instance.project_hash = 'abc123'
                    git_instance.create_checkpoint.return_value = 'def456'
                    mock_git.return_value = git_instance
                    
                    metadata_instance = MagicMock()
                    mock_metadata.return_value = metadata_instance
                    
                    # Call the function
                    result = checkpoint_manager.handle_pre_tool_use(input_data)
                    
                    # Verify behavior
                    self.assertEqual(result, 0)
                    git_instance.create_checkpoint.assert_called_once()
                    metadata_instance.add_checkpoint.assert_called_once_with(
                        'abc123', 'def456', 'Write', 
                        input_data['tool_input'], 'session123'
                    )
    
    def test_handle_pre_tool_use_disabled(self):
        """Test PreToolUse hook when checkpointing is disabled."""
        input_data = {
            'tool_name': 'Write',
            'tool_input': {'file_path': '/test/file.py'},
            'session_id': 'session123'
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            # Configure mock to return disabled
            config_instance = MagicMock()
            config_instance.enabled = False
            mock_config.return_value = config_instance
            
            # Call the function
            result = checkpoint_manager.handle_pre_tool_use(input_data)
            
            # Should exit early
            self.assertEqual(result, 0)
    
    def test_handle_pre_tool_use_excluded_file(self):
        """Test PreToolUse hook with excluded file."""
        input_data = {
            'tool_name': 'Write',
            'tool_input': {'file_path': '/test/file.log'},
            'session_id': 'session123'
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                # Configure mocks
                config_instance = MagicMock()
                config_instance.enabled = True
                config_instance.should_exclude_file.return_value = True
                mock_config.return_value = config_instance
                
                # Call the function
                result = checkpoint_manager.handle_pre_tool_use(input_data)
                
                # Should exit early without creating checkpoint
                self.assertEqual(result, 0)
                mock_git.assert_not_called()
    
    def test_handle_pre_tool_use_non_file_tool(self):
        """Test PreToolUse hook with non-file modification tool."""
        input_data = {
            'tool_name': 'Bash',
            'tool_input': {'command': 'ls -la'},
            'session_id': 'session123'
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                # Configure mocks
                config_instance = MagicMock()
                config_instance.enabled = True
                mock_config.return_value = config_instance
                
                # Call the function
                result = checkpoint_manager.handle_pre_tool_use(input_data)
                
                # Should exit early without creating checkpoint
                self.assertEqual(result, 0)
                mock_git.assert_not_called()
    
    def test_handle_pre_tool_use_manual_checkpoint(self):
        """Test PreToolUse hook for manual checkpoint."""
        input_data = {
            'tool_name': 'Manual',
            'tool_input': {'message': 'Before major refactoring'},
            'session_id': 'manual'
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                with patch.object(checkpoint_manager, 'CheckpointMetadata') as mock_metadata:
                    # Configure mocks
                    config_instance = MagicMock()
                    config_instance.enabled = True
                    mock_config.return_value = config_instance
                    
                    git_instance = MagicMock()
                    git_instance.is_git_repo.return_value = True
                    git_instance.project_hash = 'abc123'
                    git_instance.create_checkpoint.return_value = 'manual123'
                    mock_git.return_value = git_instance
                    
                    metadata_instance = MagicMock()
                    mock_metadata.return_value = metadata_instance
                    
                    # Call the function
                    result = checkpoint_manager.handle_pre_tool_use(input_data)
                    
                    # Verify manual checkpoint was created
                    self.assertEqual(result, 0)
                    git_instance.create_checkpoint.assert_called_once()
                    # Check that the custom message was used
                    call_args = git_instance.create_checkpoint.call_args
                    self.assertEqual(call_args[0][0], 'Before major refactoring')
    
    def test_handle_post_tool_use_success(self):
        """Test PostToolUse hook for successful operation."""
        input_data = {
            'tool_name': 'Write',
            'tool_response': {'success': True, 'message': 'File written'}
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                with patch.object(checkpoint_manager, 'CheckpointMetadata') as mock_metadata:
                    # Configure mocks
                    config_instance = MagicMock()
                    config_instance.enabled = True
                    mock_config.return_value = config_instance
                    
                    git_instance = MagicMock()
                    git_instance.project_hash = 'abc123'
                    mock_git.return_value = git_instance
                    
                    metadata_instance = MagicMock()
                    metadata_instance.list_project_checkpoints.return_value = [
                        {'hash': 'latest123', 'timestamp': '2023-01-01T00:00:00'}
                    ]
                    mock_metadata.return_value = metadata_instance
                    
                    # Call the function
                    result = checkpoint_manager.handle_post_tool_use(input_data)
                    
                    # Verify behavior
                    self.assertEqual(result, 0)
                    metadata_instance.update_checkpoint_status.assert_called_once_with(
                        'abc123', 'latest123', 'success', input_data['tool_response']
                    )
    
    def test_handle_post_tool_use_failure(self):
        """Test PostToolUse hook for failed operation."""
        input_data = {
            'tool_name': 'Edit',
            'tool_response': {'success': False, 'error': 'Permission denied'}
        }
        
        with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
            with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                with patch.object(checkpoint_manager, 'CheckpointMetadata') as mock_metadata:
                    # Configure mocks
                    config_instance = MagicMock()
                    config_instance.enabled = True
                    mock_config.return_value = config_instance
                    
                    git_instance = MagicMock()
                    git_instance.project_hash = 'abc123'
                    mock_git.return_value = git_instance
                    
                    metadata_instance = MagicMock()
                    metadata_instance.list_project_checkpoints.return_value = [
                        {'hash': 'latest123', 'timestamp': '2023-01-01T00:00:00'}
                    ]
                    mock_metadata.return_value = metadata_instance
                    
                    # Call the function
                    result = checkpoint_manager.handle_post_tool_use(input_data)
                    
                    # Verify behavior
                    self.assertEqual(result, 0)
                    metadata_instance.update_checkpoint_status.assert_called_once_with(
                        'abc123', 'latest123', 'failed', input_data['tool_response']
                    )
    
    def test_show_status(self):
        """Test showing checkpoint status."""
        with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
            with patch.object(checkpoint_manager, 'CheckpointMetadata') as mock_metadata:
                # Configure mocks
                git_instance = MagicMock()
                git_instance.project_hash = 'abc123'
                mock_git.return_value = git_instance
                
                metadata_instance = MagicMock()
                metadata_instance.get_project_stats.return_value = {
                    'total_checkpoints': 10,
                    'successful': 7,
                    'failed': 2,
                    'pending': 1,
                    'latest_checkpoint': '2023-01-01T00:00:00',
                    'most_modified_files': [
                        ('/src/main.py', 5),
                        ('/src/utils.py', 3)
                    ]
                }
                mock_metadata.return_value = metadata_instance
                
                # Capture output
                with patch('builtins.print') as mock_print:
                    checkpoint_manager.show_status()
                    
                    # Verify output includes statistics
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    self.assertTrue(any('Total Checkpoints: 10' in str(call) for call in print_calls))
                    self.assertTrue(any('Successful: 7' in str(call) for call in print_calls))
                    self.assertTrue(any('Failed: 2' in str(call) for call in print_calls))
    
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
                'tool_input': {'file_path': '/src/main.py'},
                'expected_message': 'Before creating main.py'
            },
            {
                'tool_name': 'Edit',
                'tool_input': {'file_path': '/test/utils.py'},
                'expected_message': 'Before editing utils.py'
            },
            {
                'tool_name': 'MultiEdit',
                'tool_input': {
                    'file_path': '/src/app.py',
                    'edits': [{'old': 'a', 'new': 'b'}, {'old': 'c', 'new': 'd'}]
                },
                'expected_message': 'Before 2 edits to app.py'
            }
        ]
        
        for test_case in test_cases:
            input_data = {
                'tool_name': test_case['tool_name'],
                'tool_input': test_case['tool_input'],
                'session_id': 'test123'
            }
            
            with patch.object(checkpoint_manager, 'CheckpointConfig') as mock_config:
                with patch.object(checkpoint_manager, 'GitCheckpointManager') as mock_git:
                    with patch.object(checkpoint_manager, 'CheckpointMetadata'):
                        # Configure mocks
                        config_instance = MagicMock()
                        config_instance.enabled = True
                        config_instance.should_exclude_file.return_value = False
                        mock_config.return_value = config_instance
                        
                        git_instance = MagicMock()
                        git_instance.is_git_repo.return_value = True
                        git_instance.project_hash = 'abc123'
                        git_instance.create_checkpoint.return_value = 'hash123'
                        mock_git.return_value = git_instance
                        
                        # Call the function
                        checkpoint_manager.handle_pre_tool_use(input_data)
                        
                        # Verify the message
                        call_args = git_instance.create_checkpoint.call_args
                        self.assertEqual(call_args[0][0], test_case['expected_message'])


if __name__ == '__main__':
    unittest.main()