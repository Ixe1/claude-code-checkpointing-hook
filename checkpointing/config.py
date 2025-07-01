#!/usr/bin/env python3
"""Configuration management for the checkpointing system."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class CheckpointConfig:
    """Manages checkpoint configuration from settings.json."""
    
    def __init__(self, settings_path: Optional[Path] = None):
        self.settings_path = settings_path or Path.home() / ".claude" / "settings.json"
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from settings file."""
        if not self.settings_path.exists():
            return self._default_config()
        
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
                config = settings.get('checkpointing', self._default_config())
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
        patterns = config.get('exclude_patterns', defaults['exclude_patterns'])
        if isinstance(patterns, list):
            validated['exclude_patterns'] = [str(p) for p in patterns if p]
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
        import fnmatch
        
        file_str = str(file_path)
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_str, pattern):
                return True
        
        # Check file size
        if file_path.exists() and file_path.is_file():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                return True
        
        return False