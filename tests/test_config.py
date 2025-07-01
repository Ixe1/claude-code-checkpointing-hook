#!/usr/bin/env python3
"""Tests for the configuration module."""

import json
import tempfile
import unittest
from pathlib import Path

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from checkpointing.config import CheckpointConfig


class TestCheckpointConfig(unittest.TestCase):
    """Test cases for CheckpointConfig class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_path = Path(self.temp_dir) / "settings.json"
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CheckpointConfig(self.settings_path)
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.retention_days, 7)
        self.assertEqual(config.max_file_size_mb, 100)
        self.assertFalse(config.checkpoint_on_stop)
        self.assertTrue(config.auto_cleanup)
    
    def test_load_custom_config(self):
        """Test loading custom configuration."""
        custom_settings = {
            "checkpointing": {
                "enabled": False,
                "retention_days": 14,
                "max_file_size_mb": 50
            }
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(custom_settings, f)
        
        config = CheckpointConfig(self.settings_path)
        
        self.assertFalse(config.enabled)
        self.assertEqual(config.retention_days, 14)
        self.assertEqual(config.max_file_size_mb, 50)
    
    def test_config_validation(self):
        """Test configuration validation."""
        invalid_settings = {
            "checkpointing": {
                "retention_days": -5,  # Should be clamped to 1
                "max_file_size_mb": 2000  # Should be clamped to 1000
            }
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(invalid_settings, f)
        
        config = CheckpointConfig(self.settings_path)
        
        self.assertEqual(config.retention_days, 1)  # Minimum value
        self.assertEqual(config.max_file_size_mb, 1000)  # Maximum value
    
    def test_should_exclude_file(self):
        """Test file exclusion logic."""
        config = CheckpointConfig(self.settings_path)
        
        # Test pattern matching
        self.assertTrue(config.should_exclude_file(Path("test.log")))
        self.assertTrue(config.should_exclude_file(Path("node_modules/package.json")))
        self.assertTrue(config.should_exclude_file(Path(".env")))
        self.assertFalse(config.should_exclude_file(Path("main.py")))
        
        # Test file size exclusion
        # Create a temporary large file
        large_file = Path(self.temp_dir) / "large.bin"
        large_file.write_bytes(b'x' * (101 * 1024 * 1024))  # 101 MB
        self.assertTrue(config.should_exclude_file(large_file))


if __name__ == '__main__':
    unittest.main()