# Claude Code Git Checkpointing System

## Overview

The git checkpointing system automatically creates snapshots of your code before Claude Code makes any file modifications. This provides a safety net allowing you to easily restore previous states if needed.

## Features

- **Automatic Checkpoints**: Created before Write, Edit, and MultiEdit operations
- **Easy Restoration**: Use `/restore` command or shell aliases
- **Efficient Storage**: Uses git's delta compression in shadow repositories
- **Configurable**: Enable/disable, set retention periods, exclude patterns
- **Search & Filter**: Find checkpoints by file, message, or time

## Quick Start

### Using Slash Commands (Recommended)

```bash
/restore                  # Interactive restoration
/restore abc123          # Restore specific checkpoint
/checkpoints             # List all checkpoints
/checkpoint-diff         # Show changes since last checkpoint
```

### Using Shell Commands

First, source the aliases:
```bash
source ~/.claude/hooks/checkpoint-aliases.sh
```

Then use:
```bash
restore-checkpoint       # Interactive restoration
list-checkpoints        # List all checkpoints
checkpoint-status       # Show statistics
checkpoint-diff         # Show recent changes
```

## Configuration

Edit `~/.claude/settings.json` to configure:

```json
{
  "checkpointing": {
    "enabled": true,              // Enable/disable checkpointing
    "retention_days": 7,          // Keep checkpoints for N days
    "exclude_patterns": [         // Files to exclude
      "*.log",
      "node_modules/",
      ".env"
    ],
    "max_file_size_mb": 100      // Skip large files
  }
}
```

## How It Works

1. **PreToolUse Hook**: Before file modifications, creates a git commit in a shadow repository
2. **Shadow Repository**: Stored in `~/.claude/checkpoints/{project_hash}/`
3. **Metadata Tracking**: Stores tool information, session ID, and file paths
4. **PostToolUse Hook**: Updates checkpoint status based on operation success

## Restoration Process

When you restore a checkpoint:
1. The system shows you what will change
2. You confirm the restoration
3. Files are restored to their state at that checkpoint
4. Your current work remains in git history

## Maintenance

### Automatic Cleanup
Old checkpoints are automatically cleaned up based on retention settings.

### Manual Cleanup
```bash
cleanup-checkpoints              # Clean old checkpoints
cleanup-checkpoints --dry-run    # Preview what would be cleaned
cleanup-checkpoints --orphaned   # Remove orphaned repos
```

## Troubleshooting

### No checkpoints found
- Check if checkpointing is enabled in settings
- Verify the project directory is correct
- Ensure git is installed

### Checkpoint creation failed
- Check disk space
- Verify write permissions to `~/.claude/checkpoints/`
- Check if files are excluded by patterns

### Can't restore checkpoint
- Ensure you have write permissions to project files
- Check if the checkpoint still exists (not cleaned up)

## Important Notes

- Checkpoints are local to your machine
- They are separate from your project's git history
- Large files (>100MB by default) are excluded
- Binary files are included but may increase storage usage

## Disable Checkpointing

To temporarily disable:
```json
{
  "checkpointing": {
    "enabled": false
  }
}
```

Or remove the PreToolUse hook from `settings.json`.

## Support

For issues or questions about the checkpointing system, check:
- The hook logs in `~/.claude/logs/` (if debug enabled)
- Run commands with `--dry-run` to test
- Use `/checkpoint-status` to verify system state