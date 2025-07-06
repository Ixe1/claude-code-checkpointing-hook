#!/usr/bin/env python3
"""Metadata management for checkpoints."""

import json
import os
import tempfile
import time
import fcntl
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CheckpointMetadata:
    """Manages checkpoint metadata."""
    
    def __init__(self, checkpoint_base: Optional[Path] = None):
        # Default to checkpoints directory within the hook's installation
        hook_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
        self.checkpoint_base = checkpoint_base or hook_dir / "checkpoints"
        self.metadata_file = self.checkpoint_base / "metadata.json"
        self.lock_file = self.checkpoint_base / ".metadata.lock"
        self._use_file_locking = platform.system() != "Windows"
    
    def _load_metadata(self) -> Dict:
        """Load metadata from file."""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_metadata(self, metadata: Dict):
        """Save metadata to file with atomic write to prevent corruption."""
        self.checkpoint_base.mkdir(parents=True, exist_ok=True)
        
        # Use atomic write to prevent corruption during concurrent access
        # Write to a temporary file first, then rename it
        temp_fd, temp_path = tempfile.mkstemp(dir=str(self.checkpoint_base), prefix='.metadata', suffix='.tmp')
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            # Atomic rename (on POSIX systems)
            os.replace(temp_path, str(self.metadata_file))
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def add_checkpoint(self, project_hash: str, checkpoint_hash: str, 
                      tool_name: str, tool_input: Dict, session_id: str) -> Dict:
        """Add metadata for a new checkpoint with file locking for concurrent access."""
        self.checkpoint_base.mkdir(parents=True, exist_ok=True)
        
        # Use a simple lock file approach
        max_wait_time = 5.0  # Maximum time to wait for lock
        wait_interval = 0.05  # 50ms between checks
        start_time = time.time()
        
        while True:
            try:
                # Try to create lock file exclusively
                lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                # Lock file exists, another process has the lock
                if time.time() - start_time > max_wait_time:
                    # Clean up stale lock if it's too old
                    try:
                        if self.lock_file.exists():
                            lock_stat = self.lock_file.stat()
                            if time.time() - lock_stat.st_mtime > 10:  # 10 seconds old
                                self.lock_file.unlink()
                                continue
                    except:
                        pass
                    raise RuntimeError("Timeout waiting for metadata lock")
                time.sleep(wait_interval)
        
        try:
            # We have the lock, perform the operation
            os.close(lock_fd)
            
            metadata = self._load_metadata()
            
            if project_hash not in metadata:
                metadata[project_hash] = {}
            
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'tool_name': tool_name,
                'tool_input': tool_input,
                'session_id': session_id,
                'status': 'pending',
                'files_affected': self._extract_files(tool_name, tool_input)
            }
            
            metadata[project_hash][checkpoint_hash] = checkpoint_data
            self._save_metadata(metadata)
            
            return checkpoint_data
        finally:
            # Always release the lock
            try:
                self.lock_file.unlink()
            except:
                pass
    
    def update_checkpoint_status(self, project_hash: str, checkpoint_hash: str, 
                                status: str, tool_response: Optional[Dict] = None):
        """Update the status of a checkpoint with file locking."""
        self.checkpoint_base.mkdir(parents=True, exist_ok=True)
        
        # Use same locking approach
        max_wait_time = 5.0
        wait_interval = 0.05
        start_time = time.time()
        
        while True:
            try:
                lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.time() - start_time > max_wait_time:
                    try:
                        if self.lock_file.exists():
                            lock_stat = self.lock_file.stat()
                            if time.time() - lock_stat.st_mtime > 10:
                                self.lock_file.unlink()
                                continue
                    except:
                        pass
                    raise RuntimeError("Timeout waiting for metadata lock")
                time.sleep(wait_interval)
        
        try:
            os.close(lock_fd)
            
            metadata = self._load_metadata()
            
            if project_hash in metadata and checkpoint_hash in metadata[project_hash]:
                metadata[project_hash][checkpoint_hash]['status'] = status
                metadata[project_hash][checkpoint_hash]['status_updated'] = datetime.now().isoformat()
                
                if tool_response:
                    metadata[project_hash][checkpoint_hash]['tool_response'] = tool_response
                
                self._save_metadata(metadata)
        finally:
            try:
                self.lock_file.unlink()
            except:
                pass
    
    def get_checkpoint_metadata(self, project_hash: str, 
                               checkpoint_hash: str) -> Optional[Dict]:
        """Get metadata for a specific checkpoint."""
        metadata = self._load_metadata()
        
        if project_hash in metadata and checkpoint_hash in metadata[project_hash]:
            return metadata[project_hash][checkpoint_hash]
        
        return None
    
    def list_project_checkpoints(self, project_hash: str) -> List[Dict]:
        """List all checkpoints for a project."""
        metadata = self._load_metadata()
        
        if project_hash not in metadata:
            return []
        
        checkpoints = []
        for checkpoint_hash, data in metadata[project_hash].items():
            checkpoint_info = data.copy()
            checkpoint_info['hash'] = checkpoint_hash
            checkpoints.append(checkpoint_info)
        
        # Sort by timestamp, newest first
        checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return checkpoints
    
    def cleanup_old_metadata(self, project_hash: str, keep_count: int = 50):
        """Remove old checkpoint metadata, keeping the most recent ones."""
        # Use locking for cleanup operation
        max_wait_time = 5.0
        wait_interval = 0.05
        start_time = time.time()
        
        while True:
            try:
                lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.time() - start_time > max_wait_time:
                    try:
                        if self.lock_file.exists():
                            lock_stat = self.lock_file.stat()
                            if time.time() - lock_stat.st_mtime > 10:
                                self.lock_file.unlink()
                                continue
                    except:
                        pass
                    raise RuntimeError("Timeout waiting for metadata lock")
                time.sleep(wait_interval)
        
        try:
            os.close(lock_fd)
            
            metadata = self._load_metadata()
            
            if project_hash not in metadata:
                return
            
            checkpoints = list(metadata[project_hash].items())
            checkpoints.sort(key=lambda x: x[1]['timestamp'], reverse=True)
            
            if len(checkpoints) > keep_count:
                # Remove old entries
                for checkpoint_hash, _ in checkpoints[keep_count:]:
                    del metadata[project_hash][checkpoint_hash]
                
                self._save_metadata(metadata)
        finally:
            try:
                self.lock_file.unlink()
            except:
                pass
    
    def _extract_files(self, tool_name: str, tool_input: Dict) -> List[str]:
        """Extract affected file paths from tool input."""
        files = []
        
        if tool_name in ['Write', 'Edit', 'MultiEdit']:
            if 'file_path' in tool_input:
                files.append(tool_input['file_path'])
            elif 'edits' in tool_input:
                # MultiEdit case
                for edit in tool_input.get('edits', []):
                    if 'file_path' in edit:
                        files.append(edit['file_path'])
        
        return files
    
    def find_checkpoints_by_file(self, project_hash: str, file_path: str) -> List[Dict]:
        """Find all checkpoints that affected a specific file."""
        checkpoints = self.list_project_checkpoints(project_hash)
        
        matching = []
        for checkpoint in checkpoints:
            if file_path in checkpoint.get('files_affected', []):
                matching.append(checkpoint)
        
        return matching
    
    def get_project_stats(self, project_hash: str) -> Dict:
        """Get statistics about checkpoints for a project."""
        checkpoints = self.list_project_checkpoints(project_hash)
        
        if not checkpoints:
            return {
                'total_checkpoints': 0,
                'successful': 0,
                'failed': 0,
                'pending': 0
            }
        
        stats = {
            'total_checkpoints': len(checkpoints),
            'successful': sum(1 for c in checkpoints if c.get('status') == 'success'),
            'failed': sum(1 for c in checkpoints if c.get('status') == 'failed'),
            'pending': sum(1 for c in checkpoints if c.get('status') == 'pending'),
            'most_modified_files': self._get_most_modified_files(checkpoints),
            'latest_checkpoint': checkpoints[0]['timestamp'] if checkpoints else None
        }
        
        return stats
    
    def _get_most_modified_files(self, checkpoints: List[Dict], limit: int = 5) -> List[Tuple[str, int]]:
        """Get the most frequently modified files."""
        file_counts = {}
        
        for checkpoint in checkpoints:
            for file in checkpoint.get('files_affected', []):
                file_counts[file] = file_counts.get(file, 0) + 1
        
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_files[:limit]