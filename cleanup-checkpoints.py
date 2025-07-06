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
    
    # Check if project has any checkpoints
    project_hash = checkpoint_mgr.project_hash
    checkpoints_meta = metadata_mgr.list_project_checkpoints(project_hash)
    
    if not checkpoints_meta:
        return 0
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    removed_count = 0
    checkpoints_to_remove = []
    
    for checkpoint in checkpoints_meta:
        try:
            # Parse timestamp from metadata
            timestamp_str = checkpoint.get('timestamp', '')
            if not timestamp_str:
                continue
                
            checkpoint_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            if checkpoint_date < cutoff_date:
                if dry_run:
                    print(f"Would remove checkpoint {checkpoint['hash'][:8]} from {timestamp_str}")
                else:
                    print(f"Removing checkpoint {checkpoint['hash'][:8]} from {timestamp_str}")
                    checkpoints_to_remove.append(checkpoint['hash'])
                    
                removed_count += 1
        except Exception as e:
            print(f"Warning: Could not process checkpoint {checkpoint.get('hash', 'unknown')[:8]}: {e}")
            continue
    
    if not dry_run and checkpoints_to_remove:
        # Remove checkpoints from metadata
        metadata = metadata_mgr._load_metadata()
        if project_hash in metadata:
            for checkpoint_hash in checkpoints_to_remove:
                if checkpoint_hash in metadata[project_hash]:
                    del metadata[project_hash][checkpoint_hash]
            metadata_mgr._save_metadata(metadata)
        
        # Note: We're not actually removing the git commits here as that would require
        # rewriting history which is complex. The metadata cleanup is sufficient
        # for most purposes. Git gc will eventually clean up unreferenced objects.
    
    return removed_count


def cleanup_all_projects(checkpoint_base: Path, retention_days: int, 
                        dry_run: bool = False) -> None:
    """Clean up checkpoints for all projects."""
    metadata_mgr = CheckpointMetadata()
    metadata = metadata_mgr._load_metadata()
    
    if not metadata:
        print("No checkpoints found.")
        return
    
    total_removed = 0
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    for project_hash, project_checkpoints in metadata.items():
        print(f"\nProcessing project {project_hash}...")
        
        removed_count = 0
        checkpoints_to_remove = []
        
        for checkpoint_hash, checkpoint_data in project_checkpoints.items():
            try:
                timestamp_str = checkpoint_data.get('timestamp', '')
                if not timestamp_str:
                    continue
                    
                checkpoint_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                if checkpoint_date < cutoff_date:
                    if dry_run:
                        print(f"  Would remove checkpoint {checkpoint_hash[:8]} from {timestamp_str}")
                    else:
                        print(f"  Removing checkpoint {checkpoint_hash[:8]} from {timestamp_str}")
                        checkpoints_to_remove.append(checkpoint_hash)
                        
                    removed_count += 1
            except Exception as e:
                print(f"  Warning: Could not process checkpoint {checkpoint_hash[:8]}: {e}")
                continue
        
        if not dry_run and checkpoints_to_remove:
            # Remove from metadata
            for checkpoint_hash in checkpoints_to_remove:
                del metadata[project_hash][checkpoint_hash]
            
        total_removed += removed_count
    
    if not dry_run and total_removed > 0:
        # Save updated metadata
        metadata_mgr._save_metadata(metadata)
    
    print(f"\nTotal checkpoints {'would be' if dry_run else ''} removed: {total_removed}")


def cleanup_orphaned_repos(checkpoint_base: Path, dry_run: bool = False) -> None:
    """Remove checkpoint repositories that no longer have a corresponding project."""
    if not checkpoint_base.exists():
        print("No checkpoints directory found.")
        return
    
    metadata_mgr = CheckpointMetadata()
    metadata = metadata_mgr._load_metadata()
    
    # Get all project hashes from metadata
    known_projects = set(metadata.keys())
    orphaned_count = 0
    
    # Check physical directories
    for project_dir in checkpoint_base.iterdir():
        if project_dir.is_dir() and len(project_dir.name) == 12:
            if project_dir.name not in known_projects:
                # This is an orphaned directory
                if dry_run:
                    print(f"Would remove orphaned checkpoint repo: {project_dir.name}")
                else:
                    print(f"Removing orphaned checkpoint repo: {project_dir.name}")
                    import shutil
                    shutil.rmtree(project_dir)
                orphaned_count += 1
    
    if orphaned_count == 0:
        print("No orphaned checkpoint repositories found.")
    else:
        print(f"\nFound {orphaned_count} orphaned checkpoint {'repository' if orphaned_count == 1 else 'repositories'}")


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
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Clean up all projects (default if no project specified)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = CheckpointConfig()
    retention_days = args.retention_days or config.retention_days
    
    if not config.auto_cleanup and not args.dry_run:
        print("Auto cleanup is disabled in configuration.")
        print("Use --dry-run to see what would be cleaned up.")
        return
    
    # Get the correct checkpoint base path from config
    hook_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
    checkpoint_base = hook_dir / "checkpoints"
    
    if args.orphaned:
        print("Cleaning up orphaned checkpoint repositories...")
        cleanup_orphaned_repos(checkpoint_base, args.dry_run)
    elif args.project:
        project_path = args.project.resolve()
        print(f"Cleaning up checkpoints for: {project_path}")
        print(f"Retention period: {retention_days} days")
        
        # Check if checkpoint repo exists for this project
        git_mgr = GitCheckpointManager(project_path)
        if not git_mgr.checkpoint_repo.exists():
            print("No checkpoint repository found for this project.")
            return
        
        removed = cleanup_project_checkpoints(
            project_path, retention_days, args.dry_run
        )
        
        print(f"\nCleaned up {removed} checkpoint{'s' if removed != 1 else ''}")
    else:
        print(f"Cleaning up all checkpoints older than {retention_days} days...")
        cleanup_all_projects(checkpoint_base, retention_days, args.dry_run)


if __name__ == '__main__':
    main()