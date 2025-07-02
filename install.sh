#!/bin/bash
# Claude Code Checkpointing Hook - Installer
# This script sets up the checkpointing system automatically

set -e  # Exit on error

echo "=== Claude Code Checkpointing Hook Installer ==="
echo

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ Error: Git is required but not found"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo "✅ Git found: $(git --version)"
echo

# Create directories
echo "Creating directories..."
mkdir -p ~/.claude/hooks/ixe1/claude-code-checkpointing-hook
mkdir -p ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints

# Copy files
echo "Installing checkpointing system..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.claude/hooks/ixe1/claude-code-checkpointing-hook"

# Copy all Python files and modules
cp -r "$SCRIPT_DIR"/*.py "$TARGET_DIR"/
cp -r "$SCRIPT_DIR"/checkpointing "$TARGET_DIR"/
cp "$SCRIPT_DIR"/checkpoint-aliases.sh "$TARGET_DIR"/
cp "$SCRIPT_DIR"/config.json "$TARGET_DIR"/

# Make scripts executable
chmod +x "$TARGET_DIR"/*.py

echo "✅ Files copied to $TARGET_DIR"
echo

# Set up ckpt command
echo "Setting up 'ckpt' command..."

# Determine user bin directory
if [ -d "$HOME/.local/bin" ]; then
    BIN_DIR="$HOME/.local/bin"
elif [ -d "$HOME/bin" ]; then
    BIN_DIR="$HOME/bin"
else
    # Create .local/bin if neither exists
    mkdir -p "$HOME/.local/bin"
    BIN_DIR="$HOME/.local/bin"
fi

# Create the ckpt executable
cat > "$BIN_DIR/ckpt" << 'EOF'
#!/bin/bash
# Claude Code checkpoint system - standalone executable
source ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-aliases.sh
ckpt "$@"
EOF

chmod +x "$BIN_DIR/ckpt"
echo "✅ Created $BIN_DIR/ckpt"

# Check if bin directory is in PATH
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo
    echo "⚠️  $BIN_DIR is not in your PATH"
    
    # Detect shell
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
        SHELL_NAME="zsh"
    else
        SHELL_RC="$HOME/.bashrc"
        SHELL_NAME="bash"
    fi
    
    echo "Adding to $SHELL_RC..."
    echo "" >> "$SHELL_RC"
    echo "# Claude Code checkpoint system" >> "$SHELL_RC"
    echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
    echo "✅ Added to PATH in $SHELL_RC"
    echo
    echo "🔄 Please run: source $SHELL_RC"
    echo "   Or start a new terminal session"
fi

# Test installation
echo
echo "Testing installation..."
if python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py --help &> /dev/null; then
    echo "✅ Checkpoint manager is working"
else
    echo "❌ Error: Checkpoint manager test failed"
    exit 1
fi

# Update or create settings.json
echo
echo "Configuring Claude Code hooks..."

if [ -f ~/.claude/settings.json ]; then
    # Backup existing settings
    cp ~/.claude/settings.json ~/.claude/settings.json.backup
    
    # Use Python to update the JSON properly
    python3 << 'EOF'
import json
import sys
import os

settings_path = os.path.expanduser('~/.claude/settings.json')

try:
    with open(settings_path, 'r') as f:
        settings = json.load(f)
except:
    settings = {}

# Note: Checkpointing config is now stored in the hook's own config.json file

# Add hooks config
if 'hooks' not in settings:
    settings['hooks'] = {}

if 'PreToolUse' not in settings['hooks']:
    settings['hooks']['PreToolUse'] = []

if 'PostToolUse' not in settings['hooks']:
    settings['hooks']['PostToolUse'] = []

# Check if checkpoint hooks already exist
pre_exists = False
for hook in settings['hooks']['PreToolUse']:
    if hook.get('matcher') == 'Write|Edit|MultiEdit':
        for h in hook.get('hooks', []):
            if 'ixe1/claude-code-checkpointing-hook/checkpoint-manager.py' in h.get('command', ''):
                pre_exists = True
                break

post_exists = False
for hook in settings['hooks']['PostToolUse']:
    if hook.get('matcher') == 'Write|Edit|MultiEdit':
        for h in hook.get('hooks', []):
            if 'ixe1/claude-code-checkpointing-hook/checkpoint-manager.py --update-status' in h.get('command', ''):
                post_exists = True
                break

# Add PreToolUse hook if not exists
if not pre_exists:
    # Find existing Write|Edit|MultiEdit matcher
    found = False
    for hook in settings['hooks']['PreToolUse']:
        if hook.get('matcher') == 'Write|Edit|MultiEdit':
            if 'hooks' not in hook:
                hook['hooks'] = []
            # Check if the specific hook doesn't already exist before appending
            hook_command = "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py"
            already_has_hook = any(
                h.get('command') == hook_command 
                for h in hook['hooks']
            )
            if not already_has_hook:
                hook['hooks'].append({
                    "type": "command",
                    "command": hook_command
                })
            found = True
            break
    
    if not found:
        settings['hooks']['PreToolUse'].append({
            "matcher": "Write|Edit|MultiEdit",
            "hooks": [{
                "type": "command",
                "command": "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py"
            }]
        })

# Add PostToolUse hook if not exists
if not post_exists:
    # Find existing Write|Edit|MultiEdit matcher
    found = False
    for hook in settings['hooks']['PostToolUse']:
        if hook.get('matcher') == 'Write|Edit|MultiEdit':
            if 'hooks' not in hook:
                hook['hooks'] = []
            # Check if the specific hook doesn't already exist before appending
            hook_command = "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py --update-status"
            already_has_hook = any(
                h.get('command') == hook_command 
                for h in hook['hooks']
            )
            if not already_has_hook:
                hook['hooks'].append({
                    "type": "command",
                    "command": hook_command
                })
            found = True
            break
    
    if not found:
        settings['hooks']['PostToolUse'].append({
            "matcher": "Write|Edit|MultiEdit",
            "hooks": [{
                "type": "command",
                "command": "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py --update-status"
            }]
        })

# Write updated settings
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print("✅ Updated settings.json with checkpoint hooks")
EOF
else
    # Create new settings file
    cat > ~/.claude/settings.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoint-manager.py --update-status"
          }
        ]
      }
    ]
  }
}
EOF
    echo "✅ Created ~/.claude/settings.json with checkpoint hooks"
fi

# Success message
echo
echo "========================================="
echo "✅ Installation complete!"
echo "========================================="
echo
echo "Quick start:"
echo "  ckpt help     - Show available commands"
echo "  ckpt list     - List checkpoints"
echo "  ckpt restore  - Restore from checkpoint"
echo
echo "Claude Code commands:"
echo "  /checkpoints  - List checkpoints"
echo "  /restore      - Restore files"
echo
echo "For more information, see the README.md"

# Check if we need to reload shell
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo
    echo "⚠️  Remember to reload your shell:"
    echo "    source $SHELL_RC"
fi