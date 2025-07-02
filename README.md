# Claude Code Checkpointing Hook

> ⚠️ **BETA SOFTWARE DISCLAIMER**
> 
> This tool is currently in beta and has undergone limited testing. It is under active development and may contain bugs or unexpected behavior. 
> 
> **USE AT YOUR OWN RISK**: The author takes no responsibility for any data loss, corruption, or other issues that may arise from using this software. Always maintain proper backups of your important work.
> 
> Please report issues and contribute to development at the project repository.

Automatic git-based checkpointing system for Claude Code that creates snapshots before file modifications.

## Quick Start

```bash
# Install
./install.sh

# Use
ckpt help     # Show commands
ckpt list     # List checkpoints  
ckpt restore  # Restore files
```

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

### Quick Install (Recommended)

```bash
# Clone or download this repository, then:
cd claude-code-checkpointing-hook
./install.sh
```

That's it! The installer will:
- Check for Python 3 and Git
- Copy all files to `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/`
- Set up the `ckpt` command in your PATH
- Create default settings
- Verify the installation

### System Requirements
- Linux or macOS
- Python 3.6+
- Git
- Bash or Zsh shell

### Manual Installation

If you prefer to install manually:

1. Copy this entire directory to `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/`
2. Ensure the main scripts are at:
   - `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py`
   - `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/restore-checkpoint.py`
   - `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/cleanup-checkpoints.py`
3. The `checkpointing/` module should be at `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpointing/`
4. Create a `ckpt` command by running:
```bash
# Create user bin directory if needed
mkdir -p ~/.local/bin

# Create the executable
cat > ~/.local/bin/ckpt << 'EOF'
#!/bin/bash
source ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-aliases.sh
ckpt "$@"
EOF

# Make it executable
chmod +x ~/.local/bin/ckpt

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Quick Start

### Using Shell Commands

```bash
# First, ensure ckpt is available (see Installation section above)
# Then use the ckpt command:
ckpt restore       # Interactive restoration (or: ckpt r)
ckpt list          # List all checkpoints (or: ckpt l)
ckpt status        # Show statistics (or: ckpt st)
ckpt diff          # Show recent changes (or: ckpt d)
ckpt clean         # Clean old checkpoints (or: ckpt c)
ckpt search <term> # Search checkpoints (or: ckpt s <term>)
ckpt now           # Create manual checkpoint (or: ckpt n)
ckpt help          # Show all commands (or: ckpt h)
```

## Configuration

The checkpointing hook stores its configuration in `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/config.json`:

```json
{
  "enabled": true,              // Enable/disable checkpointing
  "retention_days": 7,          // Keep checkpoints for N days
  "exclude_patterns": [         // Files to exclude
    "*.log",
    "node_modules/",
    ".env",
    "__pycache__/",
    "*.tmp",
    ".git/"
  ],
  "max_file_size_mb": 100,     // Skip large files
  "checkpoint_on_stop": false,  // Create checkpoint on Stop hook
  "auto_cleanup": true          // Automatically clean old checkpoints
}
```

This configuration is separate from Claude's main `settings.json`, which now only contains the hook registration.

## How It Works

1. **PreToolUse Hook**: Before file modifications, creates a git commit in a shadow repository
2. **Shadow Repository**: Stored within the hook at `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/{project_hash}/`
3. **Metadata Tracking**: JSON file stores tool info, session ID, and affected files
4. **PostToolUse Hook**: Updates checkpoint status based on operation success
5. **Restoration**: Copies files from shadow repo back to your project

## File Structure

After installation, the hook files are organized as:

```
~/.claude/hooks/ixe1/claude-code-checkpointing-hook/
├── checkpointing/
│   ├── __init__.py      # Package initialization
│   ├── config.py        # Configuration management
│   ├── git_ops.py       # Git operations wrapper
│   └── metadata.py      # Checkpoint metadata handling
├── checkpoint-manager.py     # Main hook script
├── restore-checkpoint.py    # Interactive restoration tool
├── cleanup-checkpoints.py   # Maintenance utility
├── checkpoint-aliases.sh    # Convenient shell aliases
└── config.json             # Hook configuration
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
- Located in `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/{project_hash}/`
- Contains full git history of all checkpoints
- Separate from your main project's git repo
- Stored within the hook's directory for better isolation

### Metadata Storage
- JSON file in `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/metadata.json`
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
ckpt clean

# Preview what would be cleaned
ckpt clean --dry-run

# Remove orphaned repos
ckpt clean --orphaned
```

### Uninstalling
To remove the checkpointing system:
```bash
./uninstall.sh
```
This preserves your existing checkpoints. To remove everything including checkpoints:
```bash
./uninstall.sh
rm -rf ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/
```

## Troubleshooting

### No checkpoints found
- Check if checkpointing is enabled in settings
- Verify the project directory is correct
- Ensure git is installed: `which git`

### Checkpoint creation failed
- Check disk space: `df -h ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints`
- Verify permissions: `ls -la ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints`
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
ls ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/

# Examine checkpoint history
cd ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/{project_hash}
git log --oneline
```

## Security Considerations

- Checkpoints may contain sensitive data (API keys, passwords)
- Shadow repos have same permissions as your user account
- Consider encrypting `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/` if needed
- Add sensitive files to exclude patterns

## Testing

Run the test suite:
```bash
# From project root
./run_tests.py

# Or using unittest directly
python3 -m unittest discover tests -v
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes between versions.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.