#!/usr/bin/env python3
"""
Git-based checkpointing system for Claude Code.
Provides automatic snapshots before file modifications.
"""

from .config import CheckpointConfig
from .git_ops import GitCheckpointManager
from .metadata import CheckpointMetadata

__version__ = "1.0.0"
__all__ = ["CheckpointConfig", "GitCheckpointManager", "CheckpointMetadata"]