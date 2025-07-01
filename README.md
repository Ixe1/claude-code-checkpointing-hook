# Claude Code Checkpointing Hook

Automatic git-based checkpointing system for Claude Code that creates snapshots before file modifications.

## Overview

This hook integrates with Claude Code to automatically create git checkpoints (snapshots) of your code before any file modifications. It provides a safety net allowing you to easily restore previous states if needed, without interfering with your main git repository.

## Features

- **Automatic Checkpoints**: Created before Write, Edit, and MultiEdit operations
- **Shadow Repositories**: Uses separate git repos to avoid cluttering your project
- **Easy Restoration**: Interactive restore with diff preview
- **Efficient Storage**: Uses git's delta compression
- **Configurable**: Retention periods, exclude patterns, size limits
- **Search & Filter**: Find checkpoints by file, message, or time
- **Session Tracking**: Links checkpoints to Claude Code sessions

## Installation

1. Copy this entire directory to `~/.claude/hooks/`
2. Ensure the main scripts are at:
   - `~/.claude/hooks/checkpoint-manager.py`
   - `~/.claude/hooks/restore-checkpoint.py`
   - `~/.claude/hooks/cleanup-checkpoints.py`
3. The `checkpointing/` module should be at `~/.claude/hooks/checkpointing/`
4. Source the aliases (optional): `source ~/.claude/hooks/checkpoint-aliases.sh`

## Quick Start

### Using Claude Code Commands

```bash
/restore                  # Interactive restoration
/restore abc123          # Restore specific checkpoint
/checkpoints             # List all checkpoints
/checkpoint-diff         # Show changes since last checkpoint
```

### Using Shell Commands

```bash
# First, source the aliases
source ~/.claude/hooks/checkpoint-aliases.sh

# Then use:
restore-checkpoint       # Interactive restoration
list-checkpoints        # List all checkpoints
checkpoint-status       # Show statistics
checkpoint-diff         # Show recent changes
cleanup-checkpoints     # Clean old checkpoints
```

## Configuration

Configure in `~/.claude/settings.json`:

```json
{
  "checkpointing": {
    "enabled": true,              // Enable/disable checkpointing
    "retention_days": 7,          // Keep checkpoints for N days
    "exclude_patterns": [         // Files to exclude
      "*.log",
      "node_modules/",
      ".env",
      "__pycache__/"
    ],
    "max_file_size_mb": 100      // Skip large files
  }
}
```

## How It Works

1. **PreToolUse Hook**: Before file modifications, creates a git commit in a shadow repository
2. **Shadow Repository**: Stored in `~/.claude/checkpoints/{project_hash}/`
3. **Metadata Tracking**: JSON file stores tool info, session ID, and affected files
4. **PostToolUse Hook**: Updates checkpoint status based on operation success
5. **Restoration**: Copies files from shadow repo back to your project

## File Structure

```
checkpointing/
├── __init__.py      # Package initialization
├── config.py        # Configuration management
├── git_ops.py       # Git operations wrapper
└── metadata.py      # Checkpoint metadata handling

checkpoint-manager.py     # Main hook script
restore-checkpoint.py    # Interactive restoration tool
cleanup-checkpoints.py   # Maintenance utility
checkpoint-aliases.sh    # Convenient shell aliases
```

## Restoration Process

When restoring a checkpoint:
1. Shows a list of available checkpoints with timestamps
2. Displays what files will change
3. Shows a diff preview
4. Asks for confirmation
5. Restores files to their checkpoint state
6. Your current work remains in the shadow repo's git history

## Architecture

### Shadow Repositories
- One shadow repo per project (identified by hash)
- Located in `~/.claude/checkpoints/{project_hash}/`
- Contains full git history of all checkpoints
- Separate from your main project's git repo

### Metadata Storage
- JSON file in `~/.claude/checkpoints/metadata/`
- Tracks checkpoint details, session IDs, and tool operations
- Enables searching and filtering checkpoints

### Automatic Cleanup
- Respects retention settings
- Removes old checkpoints automatically
- Can remove orphaned repos (projects no longer on disk)

## Maintenance

### Automatic Cleanup
Old checkpoints are cleaned based on retention settings during normal operation.

### Manual Cleanup
```bash
# Remove old checkpoints
cleanup-checkpoints

# Preview what would be cleaned
cleanup-checkpoints --dry-run

# Remove orphaned repos
cleanup-checkpoints --orphaned
```

## Troubleshooting

### No checkpoints found
- Check if checkpointing is enabled in settings
- Verify the project directory is correct
- Ensure git is installed: `which git`

### Checkpoint creation failed
- Check disk space: `df -h ~/.claude/checkpoints`
- Verify permissions: `ls -la ~/.claude/checkpoints`
- Check exclude patterns in settings

### Can't restore checkpoint
- Ensure write permissions to project files
- Check if files are locked by other processes
- Verify the checkpoint exists in the shadow repo

### Performance issues
- Large binary files slow down checkpointing
- Use exclude patterns for generated files
- Increase `max_file_size_mb` to skip large files

## Advanced Usage

### Manual Checkpoint Creation
```python
echo '{"tool_name":"Manual","tool_input":{},"session_id":"manual"}' | \
python3 ~/.claude/hooks/checkpoint-manager.py
```

### Direct Shadow Repo Access
```bash
# Find your project's shadow repo
ls ~/.claude/checkpoints/

# Examine checkpoint history
cd ~/.claude/checkpoints/{project_hash}
git log --oneline
```

## Security Considerations

- Checkpoints may contain sensitive data (API keys, passwords)
- Shadow repos have same permissions as your user account
- Consider encrypting `~/.claude/checkpoints/` if needed
- Add sensitive files to exclude patterns

## License

This checkpointing system is provided as-is for use with Claude Code. Feel free to modify and extend it for your needs.