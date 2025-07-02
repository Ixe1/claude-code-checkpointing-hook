#!/usr/bin/env python3
"""
Main checkpoint manager script for Claude Code hooks.
This script is called by PreToolUse and PostToolUse hooks.
"""

import argparse
import json
import sys
from pathlib import Path

# Add the hooks directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from checkpointing import CheckpointConfig, GitCheckpointManager, CheckpointMetadata, logger


def handle_pre_tool_use(input_data: dict) -> int:
    """Handle PreToolUse hook for creating checkpoints."""
    # Load configuration
    config = CheckpointConfig()
    
    if not config.enabled:
        return 0
    
    # Extract hook data
    tool_name = input_data.get('tool_name', '')
    tool_input = input_data.get('tool_input', {})
    session_id = input_data.get('session_id', '')
    
    # Only checkpoint for file modification tools and manual checkpoints
    if tool_name not in ['Write', 'Edit', 'MultiEdit', 'Manual']:
        return 0
    
    # Get project path (current working directory)
    project_path = Path.cwd()
    
    # Check if we should skip this file
    if 'file_path' in tool_input:
        file_path = Path(tool_input['file_path'])
        if config.should_exclude_file(file_path):
            print(f"Skipping checkpoint for excluded file: {file_path}", file=sys.stderr)
            logger.info(f"Skipping checkpoint for excluded file: {file_path}")
            return 0
    
    # Initialize checkpoint manager
    checkpoint_mgr = GitCheckpointManager(project_path)
    
    # Initialize project repo if needed
    if not checkpoint_mgr.is_git_repo():
        if not checkpoint_mgr.init_project_repo():
            logger.warning("Could not initialize git repository")
            # Continue anyway - don't block the operation
            return 0
    
    # Create checkpoint with descriptive message
    if tool_name == 'Write':
        if 'file_path' in tool_input:
            filename = Path(tool_input['file_path']).name
            message = f"Before creating {filename}"
        else:
            message = "Before creating new file"
    elif tool_name == 'Edit':
        if 'file_path' in tool_input:
            filename = Path(tool_input['file_path']).name
            message = f"Before editing {filename}"
        else:
            message = "Before editing file"
    elif tool_name == 'MultiEdit':
        if 'file_path' in tool_input:
            filename = Path(tool_input['file_path']).name
            edit_count = len(tool_input.get('edits', []))
            message = f"Before {edit_count} edits to {filename}"
        else:
            message = "Before multi-edit operation"
    elif tool_name == 'Manual':
        # For manual checkpoints, use the message from tool_input if provided
        message = tool_input.get('message', 'Manual checkpoint')
    else:
        message = f"Before {tool_name} operation"
    
    metadata = {
        'tool_name': tool_name,
        'session_id': session_id,
        'files': [tool_input.get('file_path', '')] if 'file_path' in tool_input else []
    }
    
    checkpoint_hash = checkpoint_mgr.create_checkpoint(message, metadata)
    
    if checkpoint_hash:
        # Store metadata
        metadata_mgr = CheckpointMetadata()
        metadata_mgr.add_checkpoint(
            checkpoint_mgr.project_hash,
            checkpoint_hash,
            tool_name,
            tool_input,
            session_id
        )
        
        print(f"Created checkpoint: {checkpoint_hash[:8]}", file=sys.stderr)
        logger.info(f"Created checkpoint: {checkpoint_hash[:8]}")
        return 0
    else:
        print("Warning: Could not create checkpoint", file=sys.stderr)
        logger.warning("Could not create checkpoint")
        # Don't block the operation
        return 0


def handle_post_tool_use(input_data: dict) -> int:
    """Handle PostToolUse hook for updating checkpoint status."""
    # Load configuration
    config = CheckpointConfig()
    
    if not config.enabled:
        return 0
    
    # Extract hook data
    tool_name = input_data.get('tool_name', '')
    tool_response = input_data.get('tool_response', {})
    
    # Only process for file modification tools
    if tool_name not in ['Write', 'Edit', 'MultiEdit']:
        return 0
    
    # Get project path
    project_path = Path.cwd()
    checkpoint_mgr = GitCheckpointManager(project_path)
    
    # Update checkpoint status
    metadata_mgr = CheckpointMetadata()
    
    # Get the latest checkpoint for this project
    checkpoints = metadata_mgr.list_project_checkpoints(checkpoint_mgr.project_hash)
    if checkpoints:
        latest_checkpoint = checkpoints[0]
        
        # Determine status based on tool response
        status = 'success' if tool_response.get('success', True) else 'failed'
        
        metadata_mgr.update_checkpoint_status(
            checkpoint_mgr.project_hash,
            latest_checkpoint['hash'],
            status,
            tool_response
        )
    
    return 0


def show_status():
    """Show checkpoint status for the current project."""
    project_path = Path.cwd()
    checkpoint_mgr = GitCheckpointManager(project_path)
    metadata_mgr = CheckpointMetadata()
    
    stats = metadata_mgr.get_project_stats(checkpoint_mgr.project_hash)
    
    print(f"Checkpoint Status for: {project_path}")
    print(f"Project Hash: {checkpoint_mgr.project_hash}")
    print("-" * 50)
    print(f"Total Checkpoints: {stats['total_checkpoints']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Pending: {stats['pending']}")
    
    if stats.get('latest_checkpoint'):
        print(f"Latest Checkpoint: {stats['latest_checkpoint']}")
    
    if stats.get('most_modified_files'):
        print("\nMost Modified Files:")
        for file, count in stats['most_modified_files']:
            print(f"  {file}: {count} times")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Checkpoint manager for Claude Code')
    parser.add_argument('--status', action='store_true', help='Show checkpoint status')
    parser.add_argument('--update-status', action='store_true', 
                       help='Update checkpoint status (PostToolUse)')
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return 0
    
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        return 1
    
    # Determine if this is pre or post tool use
    if args.update_status or 'tool_response' in input_data:
        return handle_post_tool_use(input_data)
    else:
        return handle_pre_tool_use(input_data)


if __name__ == '__main__':
    sys.exit(main())