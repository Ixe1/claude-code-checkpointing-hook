#!/usr/bin/env python3
"""Configuration management for the checkpointing system."""

import json
import os
import re
import fnmatch
import glob
from pathlib import Path, PurePath
from typing import Dict, List, Optional


class CheckpointConfig:
    """Manages checkpoint configuration from dedicated config.json file."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Default to config.json in the hook's directory
        if config_path is None:
            # Determine the hook's installation directory
            hook_dir = Path.home() / ".claude" / "hooks" / "ixe1" / "claude-code-checkpointing-hook"
            config_path = hook_dir / "config.json"
        
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from config file."""
        if not self.config_path.exists():
            return self._default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return self._validate_config(config)
        except (json.JSONDecodeError, IOError):
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            'enabled': True,
            'retention_days': 7,
            'exclude_patterns': ['*.log', 'node_modules/', '.env', '__pycache__/'],
            'max_file_size_mb': 100,
            'checkpoint_on_stop': False,
            'auto_cleanup': True
        }
    
    def _validate_config(self, config: Dict) -> Dict:
        """Validate and sanitize configuration values."""
        defaults = self._default_config()
        validated = {}
        
        # Validate enabled (boolean)
        validated['enabled'] = bool(config.get('enabled', defaults['enabled']))
        
        # Validate retention_days (positive integer)
        retention = config.get('retention_days', defaults['retention_days'])
        try:
            retention = int(retention)
            validated['retention_days'] = max(1, min(retention, 365))  # 1-365 days
        except (ValueError, TypeError):
            validated['retention_days'] = defaults['retention_days']
        
        # Validate exclude_patterns (list of strings)
        if 'exclude_patterns' in config:
            patterns = config['exclude_patterns']
            if patterns is None:
                # Explicitly handle None as empty list
                validated['exclude_patterns'] = []
            elif isinstance(patterns, list):
                validated['exclude_patterns'] = [str(p) for p in patterns if p]
            else:
                validated['exclude_patterns'] = defaults['exclude_patterns']
        else:
            validated['exclude_patterns'] = defaults['exclude_patterns']
        
        # Validate max_file_size_mb (positive number)
        max_size = config.get('max_file_size_mb', defaults['max_file_size_mb'])
        try:
            max_size = float(max_size)
            validated['max_file_size_mb'] = max(0.1, min(max_size, 1000))  # 0.1-1000 MB
        except (ValueError, TypeError):
            validated['max_file_size_mb'] = defaults['max_file_size_mb']
        
        # Validate checkpoint_on_stop (boolean)
        validated['checkpoint_on_stop'] = bool(config.get('checkpoint_on_stop', defaults['checkpoint_on_stop']))
        
        # Validate auto_cleanup (boolean)
        validated['auto_cleanup'] = bool(config.get('auto_cleanup', defaults['auto_cleanup']))
        
        return validated
    
    @property
    def enabled(self) -> bool:
        """Check if checkpointing is enabled."""
        return self._config.get('enabled', True)
    
    @property
    def retention_days(self) -> int:
        """Get retention period in days."""
        return int(self._config.get('retention_days', 7))
    
    @property
    def exclude_patterns(self) -> List[str]:
        """Get patterns to exclude from checkpoints."""
        return self._config.get('exclude_patterns', [])
    
    @property
    def max_file_size_mb(self) -> float:
        """Get maximum file size in MB to include in checkpoints."""
        return float(self._config.get('max_file_size_mb', 100))
    
    @property
    def checkpoint_on_stop(self) -> bool:
        """Check if checkpoint should be created on Stop hook."""
        return self._config.get('checkpoint_on_stop', False)
    
    @property
    def auto_cleanup(self) -> bool:
        """Check if automatic cleanup is enabled."""
        return self._config.get('auto_cleanup', True)
    
    def should_exclude_file(self, file_path: Path) -> bool:
        """Check if a file should be excluded from checkpointing."""
        
        # Normalize the file path
        file_path = Path(file_path)
        
        # Convert to string for pattern matching
        # Use forward slashes for consistency
        file_str = str(file_path).replace('\\', '/')
        
        for pattern in self.exclude_patterns:
            # Skip empty patterns
            if not pattern:
                continue
                
            # Handle patterns with braces like *.{tmp,bak,swp}
            if '{' in pattern and '}' in pattern:
                # Expand brace patterns
                match = re.search(r'\{([^}]+)\}', pattern)
                if match:
                    options = match.group(1).split(',')
                    base_pattern = pattern[:match.start()] + '{}' + pattern[match.end():]
                    for option in options:
                        expanded = base_pattern.format(option.strip())
                        if self._match_pattern(file_path, file_str, expanded):
                            return True
                    continue
            
            # Check pattern matching
            if self._match_pattern(file_path, file_str, pattern):
                return True
        
        # Check file size
        if file_path.exists() and file_path.is_file():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                return True
        
        return False
    
    def _match_pattern(self, file_path: Path, file_str: str, pattern: str) -> bool:
        """Match a single pattern against a file path."""
        
        # Normalize pattern
        pattern = pattern.replace('\\', '/')
        
        # Handle directory patterns (ending with /)
        if pattern.endswith('/'):
            dir_pattern = pattern.rstrip('/')
            # Check if file is in this directory
            if file_str == dir_pattern or file_str.startswith(dir_pattern + '/'):
                return True
            # Also check each parent directory
            for parent in file_path.parents:
                parent_str = str(parent).replace('\\', '/')
                if parent_str == dir_pattern or parent_str.endswith('/' + dir_pattern):
                    return True
                if fnmatch.fnmatch(parent.name, dir_pattern):
                    return True
        
        # Handle ** patterns using pathlib's match which supports them properly
        elif '**' in pattern:
            # Special handling for patterns ending with /**/* or /**
            if pattern.endswith('/**/*'):
                # Pattern like build/**/* - match anything under build/
                prefix = pattern[:-5]  # Remove /**/*
                if file_str.startswith(prefix + '/'):
                    return True
            elif pattern.endswith('/**'):
                # Pattern like something/** - match directory and everything under it
                prefix = pattern[:-3]
                if file_str == prefix or file_str.startswith(prefix + '/'):
                    return True
            
            # For patterns ending with / that contain **, treat as directory pattern
            elif pattern.endswith('/') and '**' in pattern:
                # Pattern like **/__pycache__/ - match files in any __pycache__ directory
                if pattern == '**/__pycache__/':
                    # Special case for common pattern
                    return '__pycache__' in file_path.parts
                elif pattern.startswith('**/') and pattern.endswith('/'):
                    # Extract directory name between **/ and /
                    dir_name = pattern[3:-1]
                    # Check if file is inside this directory at any level
                    for parent in file_path.parents:
                        if parent.name == dir_name:
                            return True
                else:
                    # Other patterns with ** and trailing /
                    # Just check if any parent directory would match the pattern without /
                    pattern_without_slash = pattern.rstrip('/')
                    path_parts = file_path.parts
                    for i in range(len(path_parts)):
                        partial_path = '/'.join(path_parts[:i+1])
                        if fnmatch.fnmatch(partial_path, pattern_without_slash):
                            return True
            
            # Try direct pathlib match
            try:
                # pathlib.match() supports ** patterns
                if file_path.match(pattern):
                    return True
            except ValueError:
                pass
            
            # For patterns like **/something, check from any parent
            if pattern.startswith('**/'):
                suffix = pattern[3:]
                # Check against filename
                if fnmatch.fnmatch(file_path.name, suffix):
                    return True
                # Check all path suffixes
                path_parts = file_path.parts
                for i in range(len(path_parts)):
                    suffix_path = '/'.join(path_parts[i:])
                    if fnmatch.fnmatch(suffix_path, suffix):
                        return True
            
            # For patterns with ** in the middle
            else:
                # Use regex conversion as fallback
                regex_pattern = self._glob_to_regex(pattern)
                if re.match(regex_pattern, file_str):
                    return True
        
        # Simple patterns without **
        else:
            # Try matching the full path
            if fnmatch.fnmatch(file_str, pattern):
                return True
            # Try matching just the filename
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
            # For patterns like "build/*", check if any parent dir matches "build"
            if '/' in pattern:
                # Check if the pattern matches from any starting point in the path
                path_parts = file_str.split('/')
                for i in range(len(path_parts)):
                    path_suffix = '/'.join(path_parts[i:])
                    if fnmatch.fnmatch(path_suffix, pattern):
                        return True
        
        return False
    
    def _glob_to_regex(self, pattern: str) -> str:
        """Convert a glob pattern with ** to a regex pattern."""
        
        # Start with the original pattern
        regex = pattern
        
        # Escape special regex characters except *, ?, and /
        regex = re.sub(r'([.+^${}()|[\]\\])', r'\\\1', regex)
        
        # Convert glob patterns to regex
        # Replace ** with .* (matches any number of directories)
        regex = regex.replace('**/', '(.*/)?')
        regex = regex.replace('/**', '(/.*)?')
        regex = regex.replace('**', '.*')
        
        # Replace * with [^/]* (matches within a directory)
        regex = regex.replace('*', '[^/]*')
        
        # Replace ? with [^/] (matches single character)
        regex = regex.replace('?', '[^/]')
        
        # Ensure the pattern matches the entire path
        if not regex.startswith('^'):
            # If pattern doesn't start with /, allow matching from any directory
            if not regex.startswith('/'):
                regex = '(^|.*/)'  + regex
            else:
                regex = '^' + regex
        
        if not regex.endswith('$'):
            regex = regex + '$'
        
        return regex