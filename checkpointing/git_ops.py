#!/usr/bin/env python3
"""Git operations for checkpoint management."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class GitCheckpointManager:
    """Manages git operations for checkpointing."""
    
    def __init__(self, project_path: Path, checkpoint_base: Optional[Path] = None):
        self.project_path = Path(project_path).resolve()
        self.checkpoint_base = checkpoint_base or Path.home() / ".claude" / "checkpoints"
        self.project_hash = self._get_project_hash()
        self.checkpoint_repo = self.checkpoint_base / self.project_hash
    
    def _get_project_hash(self) -> str:
        """Generate a unique hash for the project path."""
        return hashlib.sha256(str(self.project_path).encode()).hexdigest()[:12]
    
    def _run_git(self, args: List[str], cwd: Optional[Path] = None, 
                 capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ['git'] + args
        cwd = cwd or self.project_path
        
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=capture_output,
            text=True,
            timeout=30
        )
    
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
                
                for file in all_files:
                    src = self.project_path / file
                    dst = worktree_path / file
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if src.is_file():
                            dst.write_bytes(src.read_bytes())
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
    
    def _sync_files(self, src: Path, dst: Path):
        """Sync files from source to destination."""
        import shutil
        
        # Read .gitignore if present
        gitignore_patterns = []
        gitignore_path = src / '.gitignore'
        if gitignore_path.exists():
            gitignore_patterns = gitignore_path.read_text().strip().split('\n')
        
        for item in src.iterdir():
            # Skip hidden files and common ignore patterns
            if item.name.startswith('.') and item.name not in ['.gitignore']:
                continue
            
            # Skip gitignored patterns (simplified)
            skip = False
            for pattern in gitignore_patterns:
                if pattern and not pattern.startswith('#'):
                    if pattern.strip() in str(item.relative_to(src)):
                        skip = True
                        break
            
            if skip:
                continue
            
            dst_item = dst / item.name
            
            if item.is_dir():
                dst_item.mkdir(exist_ok=True)
                self._sync_files(item, dst_item)
            else:
                dst_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_item)
    
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
        
        worktree_path = self.checkpoint_repo / 'worktree'
        
        # First, checkout the checkpoint in the worktree
        result = self._run_git(['checkout', checkpoint_hash], cwd=worktree_path)
        if result.returncode != 0:
            return False
        
        if dry_run:
            # Show what would be changed
            print(f"Would restore to checkpoint {checkpoint_hash}")
            return True
        
        # Copy files back to project
        try:
            self._sync_files(worktree_path, self.project_path)
            
            # Switch back to main branch for future operations
            self._run_git(['checkout', 'main'], cwd=worktree_path)
            
            return True
        except Exception:
            return False
    
    def get_checkpoint_diff(self, checkpoint_hash: Optional[str] = None) -> str:
        """Get diff between current state and a checkpoint."""
        if not self.checkpoint_repo.exists():
            return ""
        
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