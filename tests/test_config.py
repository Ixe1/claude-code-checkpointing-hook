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
            "enabled": False,
            "retention_days": 14,
            "max_file_size_mb": 50
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
            "retention_days": -5,  # Should be clamped to 1
            "max_file_size_mb": 2000  # Should be clamped to 1000
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
    
    def test_missing_config_file(self):
        """Test handling when config file doesn't exist."""
        # Remove the config file if it exists
        if self.settings_path.exists():
            self.settings_path.unlink()
        
        # Should use defaults
        config = CheckpointConfig(self.settings_path)
        self.assertTrue(config.enabled)
        self.assertEqual(config.retention_days, 7)
        self.assertEqual(config.max_file_size_mb, 100)
        
        # Default exclude patterns should be set
        self.assertIn("*.log", config.exclude_patterns)
        self.assertIn("node_modules/", config.exclude_patterns)
    
    def test_invalid_json_config(self):
        """Test handling of invalid JSON in config file."""
        # Write invalid JSON
        self.settings_path.write_text("{ invalid json here }")
        
        # Should use defaults and not crash
        config = CheckpointConfig(self.settings_path)
        self.assertTrue(config.enabled)
        self.assertEqual(config.retention_days, 7)
    
    def test_partial_config_file(self):
        """Test config with only some fields specified."""
        partial_config = {
            "enabled": False,
            "retention_days": 14
            # Missing other fields
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(partial_config, f)
        
        config = CheckpointConfig(self.settings_path)
        
        # Specified values should be used
        self.assertFalse(config.enabled)
        self.assertEqual(config.retention_days, 14)
        
        # Missing values should use defaults
        self.assertEqual(config.max_file_size_mb, 100)
        self.assertTrue(config.auto_cleanup)
        self.assertIsInstance(config.exclude_patterns, list)
    
    def test_complex_glob_patterns(self):
        """Test complex glob pattern matching."""
        custom_settings = {
            "exclude_patterns": [
                "**/*.pyc",
                "**/test_*.py",
                "src/**/temp_*",
                "*.{tmp,bak,swp}",
                "build/**/*",
                ".git/",
                "venv*/",
                "**/__pycache__/"
            ]
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(custom_settings, f)
        
        config = CheckpointConfig(self.settings_path)
        
        # Test various patterns
        self.assertTrue(config.should_exclude_file(Path("module.pyc")))
        self.assertTrue(config.should_exclude_file(Path("deep/nested/file.pyc")))
        self.assertTrue(config.should_exclude_file(Path("test_module.py")))
        self.assertTrue(config.should_exclude_file(Path("src/subdir/temp_file.txt")))
        self.assertTrue(config.should_exclude_file(Path("document.tmp")))
        self.assertTrue(config.should_exclude_file(Path("backup.bak")))
        self.assertTrue(config.should_exclude_file(Path(".file.swp")))
        self.assertTrue(config.should_exclude_file(Path("build/output.js")))
        self.assertTrue(config.should_exclude_file(Path("venv/lib/python3.9/site-packages/module.py")))
        self.assertTrue(config.should_exclude_file(Path("src/__pycache__/module.pyc")))
        
        # These should NOT be excluded
        self.assertFalse(config.should_exclude_file(Path("main.py")))
        self.assertFalse(config.should_exclude_file(Path("src/app.py")))
        self.assertFalse(config.should_exclude_file(Path("README.md")))
    
    def test_config_type_validation(self):
        """Test that config values are properly validated and converted."""
        invalid_types_config = {
            "enabled": "yes",  # Should be boolean
            "retention_days": "seven",  # Should be int
            "max_file_size_mb": [100],  # Should be int
            "exclude_patterns": "*.log",  # Should be list
            "auto_cleanup": 1  # Should be boolean
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(invalid_types_config, f)
        
        # Should handle gracefully and use defaults for invalid types
        config = CheckpointConfig(self.settings_path)
        self.assertIsInstance(config.enabled, bool)
        self.assertIsInstance(config.retention_days, int)
        self.assertIsInstance(config.max_file_size_mb, (int, float))
        self.assertIsInstance(config.exclude_patterns, list)
        self.assertIsInstance(config.auto_cleanup, bool)
    
    def test_config_file_permissions(self):
        """Test handling when config file has permission issues."""
        import os
        import platform
        
        # Skip on Windows as chmod behavior is different
        if platform.system() == "Windows":
            self.skipTest("File permissions test not applicable on Windows")
        
        # Create config file and make it unreadable
        self.settings_path.write_text('{"enabled": true}')
        os.chmod(self.settings_path, 0o000)
        
        try:
            # Should use defaults when can't read
            config = CheckpointConfig(self.settings_path)
            self.assertTrue(config.enabled)  # Default value
        finally:
            # Restore permissions for cleanup
            os.chmod(self.settings_path, 0o644)
    
    def test_edge_case_values(self):
        """Test edge case configuration values."""
        edge_cases = {
            "retention_days": 0,  # Should be clamped to 1
            "max_file_size_mb": 0,  # Should be clamped to 0.1
            "exclude_patterns": None  # Should become empty list
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(edge_cases, f)
        
        config = CheckpointConfig(self.settings_path)
        
        self.assertEqual(config.retention_days, 1)  # Minimum
        self.assertEqual(config.max_file_size_mb, 0.1)  # Minimum
        self.assertEqual(config.exclude_patterns, [])  # Empty list
    
    def test_exclude_patterns_normalization(self):
        """Test that exclude patterns are normalized correctly."""
        patterns_config = {
            "exclude_patterns": [
                "*.log",  # Simple pattern
                "temp/",  # Directory pattern
                "./local/*",  # Relative path
                "//double//slashes//",  # Multiple slashes
                " spaces.txt ",  # Spaces
                "",  # Empty pattern
                None  # None pattern
            ]
        }
        
        with open(self.settings_path, 'w') as f:
            json.dump(patterns_config, f)
        
        config = CheckpointConfig(self.settings_path)
        
        # Empty and None patterns should be filtered out
        self.assertNotIn("", config.exclude_patterns)
        self.assertNotIn(None, config.exclude_patterns)
        
        # Patterns should work correctly
        self.assertTrue(config.should_exclude_file(Path("test.log")))
        self.assertTrue(config.should_exclude_file(Path("temp/file.txt")))


if __name__ == '__main__':
    unittest.main()