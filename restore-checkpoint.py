#!/usr/bin/env python3
"""
Interactive checkpoint restoration utility for Claude Code.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the hooks directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from checkpointing import GitCheckpointManager, CheckpointMetadata


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        
        if delta < timedelta(minutes=1):
            return "just now"
        elif delta < timedelta(hours=1):
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delta < timedelta(days=1):
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = delta.days
            return f"{days} day{'s' if days != 1 else ''} ago"
    except:
        return timestamp_str


def list_checkpoints(project_path: Path, limit: int = 20) -> None:
    """List available checkpoints."""
    checkpoint_mgr = GitCheckpointManager(project_path)
    metadata_mgr = CheckpointMetadata()
    
    checkpoints = checkpoint_mgr.list_checkpoints()
    if not checkpoints:
        print("No checkpoints found for this project.")
        return
    
    print(f"\nAvailable checkpoints for: {project_path}")
    print("=" * 80)
    
    for i, checkpoint in enumerate(checkpoints[:limit]):
        checkpoint_meta = metadata_mgr.get_checkpoint_metadata(
            checkpoint_mgr.project_hash, 
            checkpoint['hash']
        )
        
        status = checkpoint_meta.get('status', 'unknown') if checkpoint_meta else 'unknown'
        status_icon = {
            'success': '✓',
            'failed': '✗',
            'pending': '⋯',
            'unknown': '?'
        }.get(status, '?')
        
        timestamp = checkpoint.get('timestamp', '')
        relative_time = format_timestamp(timestamp)
        
        files = checkpoint_meta.get('files_affected', []) if checkpoint_meta else []
        files_str = ', '.join(files) if files else 'unknown files'
        
        print(f"{i+1}. [{status_icon}] {checkpoint['hash'][:8]} - {relative_time}")
        print(f"   {checkpoint['message']}")
        if files:
            print(f"   Files: {files_str}")
        print()
    
    if len(checkpoints) > limit:
        print(f"Showing {limit} most recent checkpoints out of {len(checkpoints)} total.")


def interactive_restore(project_path: Path) -> None:
    """Interactive checkpoint restoration."""
    checkpoint_mgr = GitCheckpointManager(project_path)
    checkpoints = checkpoint_mgr.list_checkpoints()
    
    if not checkpoints:
        print("No checkpoints found for this project.")
        return
    
    # Show checkpoint list
    list_checkpoints(project_path)
    
    # Get user selection
    while True:
        try:
            choice = input("\nEnter checkpoint number, ID, or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                print("Restoration cancelled.")
                return
            
            # Try to parse as number
            try:
                index = int(choice) - 1
                if 0 <= index < len(checkpoints):
                    selected_checkpoint = checkpoints[index]
                    break
                else:
                    print(f"Invalid number. Please enter 1-{len(checkpoints)}.")
                    continue
            except ValueError:
                # Try to find by hash prefix
                matching = [cp for cp in checkpoints if cp['hash'].startswith(choice)]
                if len(matching) == 1:
                    selected_checkpoint = matching[0]
                    break
                elif len(matching) > 1:
                    print(f"Ambiguous checkpoint ID. Matches: {[cp['hash'][:8] for cp in matching]}")
                    continue
                else:
                    print("No matching checkpoint found.")
                    continue
                    
        except (EOFError, KeyboardInterrupt):
            print("\nRestoration cancelled.")
            return
    
    # Show what will be restored
    print(f"\nSelected checkpoint: {selected_checkpoint['hash'][:8]}")
    print(f"Message: {selected_checkpoint['message']}")
    
    # Show diff
    print("\nFetching changes...")
    diff = checkpoint_mgr.get_checkpoint_diff(selected_checkpoint['hash'])
    if diff:
        print("Changes that will be applied:")
        print("-" * 80)
        print(diff)
        print("-" * 80)
    
    # Confirm restoration
    confirm = input("\nRestore to this checkpoint? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Restoration cancelled.")
        return
    
    # Perform restoration
    print("Restoring checkpoint...")
    if checkpoint_mgr.restore_checkpoint(selected_checkpoint['hash']):
        print(f"Successfully restored to checkpoint {selected_checkpoint['hash'][:8]}")
    else:
        print("Error: Failed to restore checkpoint.", file=sys.stderr)
        sys.exit(1)


def restore_by_id(project_path: Path, checkpoint_id: str, dry_run: bool = False) -> None:
    """Restore a specific checkpoint by ID."""
    checkpoint_mgr = GitCheckpointManager(project_path)
    checkpoints = checkpoint_mgr.list_checkpoints()
    
    # Find matching checkpoint
    matching = [cp for cp in checkpoints if cp['hash'].startswith(checkpoint_id)]
    
    if not matching:
        print(f"Error: No checkpoint found matching '{checkpoint_id}'", file=sys.stderr)
        sys.exit(1)
    
    if len(matching) > 1:
        print(f"Error: Ambiguous checkpoint ID. Matches:", file=sys.stderr)
        for cp in matching:
            print(f"  - {cp['hash'][:8]}: {cp['message']}", file=sys.stderr)
        sys.exit(1)
    
    selected_checkpoint = matching[0]
    
    if dry_run:
        print(f"Would restore to checkpoint: {selected_checkpoint['hash'][:8]}")
        print(f"Message: {selected_checkpoint['message']}")
        return
    
    # Perform restoration
    print(f"Restoring to checkpoint {selected_checkpoint['hash'][:8]}...")
    if checkpoint_mgr.restore_checkpoint(selected_checkpoint['hash']):
        print("Successfully restored checkpoint.")
    else:
        print("Error: Failed to restore checkpoint.", file=sys.stderr)
        sys.exit(1)


def search_checkpoints(project_path: Path, search_term: str) -> None:
    """Search checkpoints by various criteria."""
    checkpoint_mgr = GitCheckpointManager(project_path)
    metadata_mgr = CheckpointMetadata()
    
    checkpoints = checkpoint_mgr.list_checkpoints()
    matching = []
    
    # Search in messages and file paths
    for checkpoint in checkpoints:
        if search_term.lower() in checkpoint['message'].lower():
            matching.append(checkpoint)
            continue
        
        # Check metadata
        checkpoint_meta = metadata_mgr.get_checkpoint_metadata(
            checkpoint_mgr.project_hash, 
            checkpoint['hash']
        )
        if checkpoint_meta:
            files = checkpoint_meta.get('files_affected', [])
            if any(search_term.lower() in f.lower() for f in files):
                matching.append(checkpoint)
    
    if not matching:
        print(f"No checkpoints found matching '{search_term}'")
        return
    
    print(f"\nCheckpoints matching '{search_term}':")
    print("=" * 80)
    
    for checkpoint in matching[:10]:
        print(f"{checkpoint['hash'][:8]} - {checkpoint['message']}")
        print(f"  Timestamp: {checkpoint['timestamp']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Restore from Claude Code checkpoints'
    )
    parser.add_argument(
        'checkpoint_id', 
        nargs='?',
        help='Checkpoint ID or hash to restore (interactive if not provided)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available checkpoints'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be restored without making changes'
    )
    parser.add_argument(
        '--project', '-p',
        type=Path,
        default=Path.cwd(),
        help='Project directory (default: current directory)'
    )
    parser.add_argument(
        '--search', '-s',
        help='Search checkpoints by message or file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Limit number of checkpoints shown (default: 20)'
    )
    
    args = parser.parse_args()
    project_path = args.project.resolve()
    
    if args.search:
        search_checkpoints(project_path, args.search)
    elif args.list:
        list_checkpoints(project_path, args.limit)
    elif args.checkpoint_id:
        restore_by_id(project_path, args.checkpoint_id, args.dry_run)
    else:
        interactive_restore(project_path)


if __name__ == '__main__':
    main()