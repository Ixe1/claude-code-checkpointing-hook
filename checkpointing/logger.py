#!/usr/bin/env python3
"""Logging configuration for the checkpointing system."""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class CheckpointLogger:
    """Manages logging for the checkpoint system."""
    
    _instance: Optional['CheckpointLogger'] = None
    _logger: logging.Logger
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def __init__(self):
        """Initialize logger if not already done."""
        # Logger is set up in __new__ to ensure it's always initialized
        pass
    
    def _setup_logger(self):
        """Set up the logger with appropriate handlers."""
        self._logger = logging.getLogger('checkpoint')
        self._logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        self._logger.handlers.clear()
        
        # Console handler for errors only (to stderr)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        self._logger.addHandler(console_handler)
        
        # File handler for detailed logs (if in debug mode)
        if self._is_debug_mode():
            log_dir = Path.home() / '.claude' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / 'checkpoint.log'
            
            # Use rotating file handler: max 10MB per file, keep 3 backups
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self._logger.addHandler(file_handler)
            
            # Also increase console verbosity in debug mode
            console_handler.setLevel(logging.DEBUG)
            self._logger.setLevel(logging.DEBUG)
    
    def _is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        import os
        return os.environ.get('CHECKPOINT_DEBUG', '').lower() in ('1', 'true', 'yes')
    
    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger
    
    def debug(self, message: str):
        """Log debug message."""
        self._logger.debug(message)
    
    def info(self, message: str):
        """Log info message."""
        self._logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self._logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self._logger.error(message)
    
    def exception(self, message: str):
        """Log exception with traceback."""
        self._logger.exception(message)


# Global logger instance
logger = CheckpointLogger()