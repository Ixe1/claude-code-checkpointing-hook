#!/usr/bin/env python3
"""
Git-based checkpointing system for Claude Code.
Provides automatic snapshots before file modifications.
"""

from .config import CheckpointConfig
from .git_ops import GitCheckpointManager
from .metadata import CheckpointMetadata
from .logger import logger

__version__ = "1.2.0"
__all__ = ["CheckpointConfig", "GitCheckpointManager", "CheckpointMetadata", "logger"]