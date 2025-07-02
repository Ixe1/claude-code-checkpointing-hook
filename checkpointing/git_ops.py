#!/usr/bin/env python3
"""Git operations for checkpoint management."""

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

from .logger import logger


class GitCheckpointManager:
    """Manages git operations for checkpointing."""
    
    def __init__(self, project_path: Path, checkpoint_base: Optional[Path] = None):
        self.project_path = Path(project_path).resolve()
        # Default to checkpoints directory within the hook's installation
        hook_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
        self.checkpoint_base = checkpoint_base or hook_dir / "checkpoints"
        self.project_hash = self._get_project_hash()
        self.checkpoint_repo = self.checkpoint_base / self.project_hash
    
    def _get_project_hash(self) -> str:
        """Generate a unique hash for the project path."""
        return hashlib.sha256(str(self.project_path).encode()).hexdigest()[:12]
    
    def _validate_checkpoint_hash(self, checkpoint_hash: str) -> bool:
        """Validate checkpoint hash format."""
        if not checkpoint_hash:
            return False
        # Git commit hash should be 40 hex characters (or prefix)
        return bool(re.match(r'^[a-f0-9]{1,40}$', checkpoint_hash.lower()))
    
    def _sanitize_path(self, path: Path) -> Path:
        """Sanitize file path to prevent directory traversal."""
        # Resolve to absolute path and ensure it's within project
        resolved = path.resolve()
        try:
            resolved.relative_to(self.project_path)
            return resolved
        except ValueError:
            # Path is outside project directory
            raise ValueError(f"Path {path} is outside project directory")
    
    def _validate_metadata_size(self, metadata: Dict) -> bool:
        """Check if metadata size is within limits."""
        # Convert to JSON to check size
        json_str = json.dumps(metadata)
        # Limit metadata to 1MB
        return len(json_str.encode('utf-8')) <= 1024 * 1024
    
    def _run_git(self, args: List[str], cwd: Optional[Path] = None, 
                 capture_output: bool = True, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a git command with proper error handling."""
        cmd = ['git'] + args
        cwd = cwd or self.project_path
        
        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            # Return a failed result on timeout
            result = subprocess.CompletedProcess(cmd, 1, '', 'Command timed out')
            return result
        except Exception as e:
            # Return a failed result on other errors
            result = subprocess.CompletedProcess(cmd, 1, '', str(e))
            return result
    
    def is_git_repo(self) -> bool:
        """Check if the project directory is a git repository."""
        result = self._run_git(['rev-parse', '--git-dir'], capture_output=True)
        return result.returncode == 0
    
    def init_project_repo(self) -> bool:
        """Initialize the project directory as a git repo if needed."""
        if self.is_git_repo():
            return True
        
        result = self._run_git(['init'])
        if result.returncode != 0:
            return False
        
        # Create initial commit
        self._run_git(['add', '-A'])
        self._run_git(['commit', '-m', 'Initial checkpoint commit'])
        return True
    
    def init_checkpoint_repo(self) -> bool:
        """Initialize the checkpoint repository."""
        if self.checkpoint_repo.exists():
            return True
        
        try:
            self.checkpoint_repo.mkdir(parents=True, exist_ok=True)
            
            # Initialize as a bare repository
            result = self._run_git(['init', '--bare'], cwd=self.checkpoint_repo)
            if result.returncode != 0:
                return False
            
            # Set up the worktree
            worktree_path = self.checkpoint_repo / 'worktree'
            if not worktree_path.exists():
                # Clone the project repo into the checkpoint worktree
                if self.is_git_repo():
                    self._run_git(['clone', str(self.project_path), str(worktree_path)])
                else:
                    # If not a git repo, create a new one
                    worktree_path.mkdir(exist_ok=True)
                    self._run_git(['init'], cwd=worktree_path)
            
            return True
        except Exception:
            return False
    
    def create_checkpoint(self, message: str, metadata: Dict) -> Optional[str]:
        """Create a new checkpoint."""
        if not self.init_checkpoint_repo():
            return None
        
        # Validate metadata size
        if not self._validate_metadata_size(metadata):
            logger.warning("Metadata too large, truncating")
            # Truncate metadata to essential fields only
            metadata = {
                'tool_name': metadata.get('tool_name', ''),
                'session_id': metadata.get('session_id', ''),
                'files': metadata.get('files', [])[:10]  # Limit files list
            }
        
        worktree_path = self.checkpoint_repo / 'worktree'
        
        try:
            # Sync project files to worktree
            if self.is_git_repo():
                # Get both tracked and untracked files
                # First get tracked files
                tracked_result = self._run_git(['ls-files', '-z'])
                tracked_files = set()
                if tracked_result.returncode == 0 and tracked_result.stdout:
                    tracked_files = set(f for f in tracked_result.stdout.strip('\0').split('\0') if f)
                
                # Then get untracked files (excluding ignored)
                untracked_result = self._run_git(['ls-files', '-z', '--others', '--exclude-standard'])
                untracked_files = set()
                if untracked_result.returncode == 0 and untracked_result.stdout:
                    untracked_files = set(f for f in untracked_result.stdout.strip('\0').split('\0') if f)
                
                # Combine all files
                all_files = tracked_files | untracked_files
                
                # Batch process files for better performance
                self._batch_sync_files(all_files, self.project_path, worktree_path)
            else:
                # Copy all files (respecting gitignore if present)
                self._sync_files(self.project_path, worktree_path)
            
            # Create checkpoint commit
            self._run_git(['add', '-A'], cwd=worktree_path)
            
            timestamp = datetime.now().isoformat()
            commit_message = f"CHECKPOINT: {message} [{timestamp}]"
            
            result = self._run_git(
                ['commit', '-m', commit_message, '--allow-empty'],
                cwd=worktree_path
            )
            
            if result.returncode != 0:
                return None
            
            # Get commit hash
            result = self._run_git(['rev-parse', 'HEAD'], cwd=worktree_path)
            if result.returncode != 0:
                return None
            
            commit_hash = result.stdout.strip()
            
            # Add metadata as git note
            metadata_json = json.dumps(metadata, indent=2)
            self._run_git(
                ['notes', 'add', '-m', metadata_json, commit_hash],
                cwd=worktree_path
            )
            
            # Ensure we're back on main branch for future checkpoints
            self._run_git(['checkout', 'main'], cwd=worktree_path)
            
            return commit_hash
            
        except Exception:
            return None
    
    def _batch_sync_files(self, files: set, src_root: Path, dst_root: Path, batch_size: int = 100):
        """Sync files in batches for better performance."""
        import shutil
        
        file_list = list(files)
        total_files = len(file_list)
        
        if total_files > 100:
            logger.info(f"Syncing {total_files} files to checkpoint...")
        
        for i in range(0, total_files, batch_size):
            batch = file_list[i:i + batch_size]
            
            for file in batch:
                src = src_root / file
                dst = dst_root / file
                
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_file():
                        try:
                            # Use shutil for better performance on large files
                            shutil.copy2(src, dst)
                        except Exception as e:
                            logger.warning(f"Failed to copy {file}: {e}")
            
            # Log progress for large operations
            if total_files > 100 and (i + batch_size) % 500 == 0:
                progress = min(100, int((i + batch_size) / total_files * 100))
                logger.info(f"Progress: {progress}% ({i + batch_size}/{total_files} files)")
        
        if total_files > 100:
            logger.info("File sync completed")
    
    def _sync_files(self, src: Path, dst: Path):
        """Sync files from source to destination."""
        import shutil
        
        # Read .gitignore if present
        gitignore_patterns = []
        gitignore_path = src / '.gitignore'
        if gitignore_path.exists():
            gitignore_patterns = gitignore_path.read_text().strip().split('\n')
        
        # Collect all files first for batch processing
        files_to_sync = []
        
        def collect_files(current_src: Path, current_dst: Path, base_src: Path):
            for item in current_src.iterdir():
                # Skip hidden files and common ignore patterns
                if item.name.startswith('.') and item.name not in ['.gitignore']:
                    continue
                
                # Skip gitignored patterns (simplified)
                skip = False
                for pattern in gitignore_patterns:
                    if pattern and not pattern.startswith('#'):
                        if pattern.strip() in str(item.relative_to(base_src)):
                            skip = True
                            break
                
                if skip:
                    continue
                
                if item.is_dir():
                    collect_files(item, current_dst / item.name, base_src)
                else:
                    files_to_sync.append((item, current_dst / item.name))
        
        # Collect all files
        collect_files(src, dst, src)
        
        # Batch sync for better performance
        total_files = len(files_to_sync)
        if total_files > 100:
            logger.info(f"Syncing {total_files} files...")
        
        for i, (src_file, dst_file) in enumerate(files_to_sync):
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            
            # Progress logging for large operations
            if total_files > 100 and (i + 1) % 100 == 0:
                progress = int((i + 1) / total_files * 100)
                logger.info(f"Progress: {progress}% ({i + 1}/{total_files} files)")
        
        if total_files > 100:
            logger.info("File sync completed")
    
    def _full_restore_sync(self, src: Path, dst: Path) -> None:
        """Full sync for restoration - removes files that don't exist in source."""
        import shutil
        
        # First, collect all files in the checkpoint (source)
        checkpoint_files = set()
        
        def collect_checkpoint_files(current_src: Path, base_src: Path):
            for item in current_src.iterdir():
                # Skip hidden files except .gitignore
                if item.name.startswith('.') and item.name not in ['.gitignore']:
                    continue
                    
                if item.is_dir():
                    collect_checkpoint_files(item, base_src)
                else:
                    # Store relative path
                    rel_path = item.relative_to(base_src)
                    checkpoint_files.add(rel_path)
        
        # Collect all files in checkpoint
        collect_checkpoint_files(src, src)
        
        # Now collect all files in the project (destination)
        project_files = set()
        
        def collect_project_files(current_dst: Path, base_dst: Path):
            if not current_dst.exists():
                return
                
            for item in current_dst.iterdir():
                # Skip hidden files and directories
                if item.name.startswith('.'):
                    continue
                    
                if item.is_dir():
                    collect_project_files(item, base_dst)
                else:
                    # Store relative path
                    rel_path = item.relative_to(base_dst)
                    project_files.add(rel_path)
        
        # Collect all files in project
        collect_project_files(dst, dst)
        
        # Find files to delete (in project but not in checkpoint)
        files_to_delete = project_files - checkpoint_files
        
        # Delete files that shouldn't exist
        for rel_path in files_to_delete:
            file_path = dst / rel_path
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Removed file not in checkpoint: {rel_path}")
                print(f"Removed: {rel_path}")
                
                # Remove empty directories
                parent = file_path.parent
                while parent != dst and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
        
        # Now sync files from checkpoint to project
        self._sync_files(src, dst)
    
    def list_checkpoints(self) -> List[Dict]:
        """List all checkpoints for the current project."""
        if not self.checkpoint_repo.exists():
            return []
        
        worktree_path = self.checkpoint_repo / 'worktree'
        
        # Get commit log from all branches
        result = self._run_git(
            ['log', '--all', '--pretty=format:%H|%ai|%s', '--notes'],
            cwd=worktree_path
        )
        
        if result.returncode != 0:
            return []
        
        checkpoints = []
        for line in result.stdout.strip().split('\n'):
            if line and 'CHECKPOINT:' in line:
                parts = line.split('|', 2)
                if len(parts) >= 3:
                    commit_hash, timestamp, message = parts
                    
                    # Get metadata from notes
                    notes_result = self._run_git(
                        ['notes', 'show', commit_hash],
                        cwd=worktree_path
                    )
                    
                    metadata = {}
                    if notes_result.returncode == 0:
                        try:
                            metadata = json.loads(notes_result.stdout)
                        except json.JSONDecodeError:
                            pass
                    
                    # Extract the descriptive message and timestamp
                    checkpoint_msg = message.replace('CHECKPOINT: ', '')
                    # For new format: "Before Write operation on file.txt [2025-07-01T...]"
                    # For old format: just the timestamp
                    if '[' in checkpoint_msg and ']' in checkpoint_msg:
                        desc_part = checkpoint_msg.split('[')[0].strip()
                        time_part = checkpoint_msg.split('[')[1].rstrip(']')
                    else:
                        # Old format - just timestamp
                        desc_part = checkpoint_msg
                        time_part = checkpoint_msg
                    
                    checkpoints.append({
                        'hash': commit_hash,
                        'timestamp': timestamp,
                        'message': desc_part,
                        'metadata': metadata
                    })
        
        return checkpoints
    
    def restore_checkpoint(self, checkpoint_hash: str, dry_run: bool = False) -> bool:
        """Restore files from a checkpoint."""
        if not self.checkpoint_repo.exists():
            return False
        
        # Validate checkpoint hash
        if not self._validate_checkpoint_hash(checkpoint_hash):
            print(f"Error: Invalid checkpoint hash format: {checkpoint_hash}", file=sys.stderr)
            logger.error(f"Invalid checkpoint hash format: {checkpoint_hash}")
            return False
        
        worktree_path = self.checkpoint_repo / 'worktree'
        
        # First, checkout the checkpoint in the worktree
        result = self._run_git(['checkout', checkpoint_hash], cwd=worktree_path)
        if result.returncode != 0:
            print(f"Error: Failed to checkout checkpoint: {result.stderr}", file=sys.stderr)
            logger.error(f"Failed to checkout checkpoint: {result.stderr}")
            return False
        
        if dry_run:
            # Show what would be changed
            print(f"Would restore to checkpoint {checkpoint_hash}")
            return True
        
        # Copy files back to project with full restoration (including deletions)
        try:
            self._full_restore_sync(worktree_path, self.project_path)
            
            # Switch back to main branch for future operations
            self._run_git(['checkout', 'main'], cwd=worktree_path)
            
            return True
        except Exception as e:
            logger.error(f"Restoration failed: {e}")
            return False
    
    def get_checkpoint_diff(self, checkpoint_hash: Optional[str] = None) -> str:
        """Get diff between current state and a checkpoint."""
        if not self.checkpoint_repo.exists():
            return ""
        
        # Validate checkpoint hash if provided
        if checkpoint_hash and not self._validate_checkpoint_hash(checkpoint_hash):
            return f"Error: Invalid checkpoint hash format: {checkpoint_hash}"
        
        worktree_path = self.checkpoint_repo / 'worktree'
        
        # Update worktree with current state
        self._sync_files(self.project_path, worktree_path)
        
        if checkpoint_hash:
            result = self._run_git(
                ['diff', checkpoint_hash, '--stat'],
                cwd=worktree_path
            )
        else:
            # Diff against last checkpoint
            result = self._run_git(
                ['diff', 'HEAD', '--stat'],
                cwd=worktree_path
            )
        
        return result.stdout if result.returncode == 0 else ""