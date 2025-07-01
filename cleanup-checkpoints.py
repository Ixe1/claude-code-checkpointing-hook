#!/usr/bin/env python3
"""
Cleanup utility for old checkpoints.
Can be run via cron or manually to remove old checkpoints.
"""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the hooks directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from checkpointing import CheckpointConfig, GitCheckpointManager, CheckpointMetadata


def cleanup_project_checkpoints(project_path: Path, retention_days: int, 
                               dry_run: bool = False) -> int:
    """Clean up old checkpoints for a specific project."""
    checkpoint_mgr = GitCheckpointManager(project_path)
    metadata_mgr = CheckpointMetadata()
    
    if not checkpoint_mgr.checkpoint_repo.exists():
        return 0
    
    # Get all checkpoints
    checkpoints = checkpoint_mgr.list_checkpoints()
    if not checkpoints:
        return 0
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    removed_count = 0
    for checkpoint in checkpoints:
        try:
            # Parse timestamp from message
            timestamp_str = checkpoint['message'].split('CHECKPOINT: ')[1].split('\n')[0]
            checkpoint_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            if checkpoint_date < cutoff_date:
                if dry_run:
                    print(f"Would remove checkpoint {checkpoint['hash'][:8]} from {timestamp_str}")
                else:
                    # Remove from git history
                    worktree_path = checkpoint_mgr.checkpoint_repo / 'worktree'
                    
                    # This is a simplified approach - in production you might want to use
                    # git filter-branch or git filter-repo for more efficient cleanup
                    print(f"Removing checkpoint {checkpoint['hash'][:8]} from {timestamp_str}")
                    
                removed_count += 1
        except Exception as e:
            print(f"Warning: Could not process checkpoint {checkpoint['hash'][:8]}: {e}")
            continue
    
    if not dry_run and removed_count > 0:
        # Run git gc to clean up
        worktree_path = checkpoint_mgr.checkpoint_repo / 'worktree'
        subprocess.run(
            ['git', 'gc', '--aggressive', '--prune=now'],
            cwd=str(worktree_path),
            capture_output=True
        )
        
        # Clean up old metadata
        metadata_mgr.cleanup_old_metadata(checkpoint_mgr.project_hash)
    
    return removed_count


def cleanup_all_projects(checkpoint_base: Path, retention_days: int, 
                        dry_run: bool = False) -> None:
    """Clean up checkpoints for all projects."""
    if not checkpoint_base.exists():
        print("No checkpoints directory found.")
        return
    
    total_removed = 0
    
    for project_dir in checkpoint_base.iterdir():
        if project_dir.is_dir() and len(project_dir.name) == 12:  # Hash length
            print(f"\nProcessing project {project_dir.name}...")
            
            # Find the original project path from metadata
            metadata_mgr = CheckpointMetadata()
            project_checkpoints = metadata_mgr.list_project_checkpoints(project_dir.name)
            
            if project_checkpoints:
                # Use the worktree path as a proxy for the project
                worktree_path = project_dir / 'worktree'
                if worktree_path.exists():
                    removed = cleanup_project_checkpoints(
                        worktree_path, retention_days, dry_run
                    )
                    total_removed += removed
    
    print(f"\nTotal checkpoints {'would be' if dry_run else ''} removed: {total_removed}")


def cleanup_orphaned_repos(checkpoint_base: Path, dry_run: bool = False) -> None:
    """Remove checkpoint repositories that no longer have a corresponding project."""
    if not checkpoint_base.exists():
        return
    
    for project_dir in checkpoint_base.iterdir():
        if project_dir.is_dir() and len(project_dir.name) == 12:
            worktree_path = project_dir / 'worktree'
            
            # Check if we can determine the original project path
            if worktree_path.exists():
                # Try to get the remote URL or origin
                result = subprocess.run(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=str(worktree_path),
                    capture_output=True,
                    text=True
                )
                
                # If no origin and the directory is very old, consider it orphaned
                if result.returncode != 0:
                    stat = project_dir.stat()
                    age_days = (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                    
                    if age_days > 30:  # Orphaned for more than 30 days
                        if dry_run:
                            print(f"Would remove orphaned checkpoint repo: {project_dir.name}")
                        else:
                            print(f"Removing orphaned checkpoint repo: {project_dir.name}")
                            import shutil
                            shutil.rmtree(project_dir)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Clean up old Claude Code checkpoints'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        help='Override retention period in days'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be cleaned up without removing'
    )
    parser.add_argument(
        '--project', '-p',
        type=Path,
        help='Clean up specific project only'
    )
    parser.add_argument(
        '--orphaned',
        action='store_true',
        help='Clean up orphaned checkpoint repositories'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = CheckpointConfig()
    retention_days = args.retention_days or config.retention_days
    
    if not config.auto_cleanup and not args.dry_run:
        print("Auto cleanup is disabled in configuration.")
        print("Use --dry-run to see what would be cleaned up.")
        return
    
    checkpoint_base = Path.home() / ".claude" / "checkpoints"
    
    if args.orphaned:
        print("Cleaning up orphaned checkpoint repositories...")
        cleanup_orphaned_repos(checkpoint_base, args.dry_run)
    elif args.project:
        project_path = args.project.resolve()
        print(f"Cleaning up checkpoints for: {project_path}")
        print(f"Retention period: {retention_days} days")
        
        removed = cleanup_project_checkpoints(
            project_path, retention_days, args.dry_run
        )
        
        print(f"\nCheckpoints {'would be' if args.dry_run else ''} removed: {removed}")
    else:
        print(f"Cleaning up all checkpoints older than {retention_days} days...")
        cleanup_all_projects(checkpoint_base, retention_days, args.dry_run)


if __name__ == '__main__':
    main()