#!/bin/bash
# Claude Code Checkpointing Hook - Uninstaller

echo "=== Claude Code Checkpointing Hook Uninstaller ==="
echo
echo "This will remove the checkpointing system but preserve your checkpoints."
echo
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Removing checkpointing system..."

# Remove hook files but preserve checkpoints
HOOK_DIR="$HOME/.claude/hooks/ixe1/claude-code-checkpointing-hook"

# Remove all files in the hook directory
find "$HOOK_DIR" -maxdepth 1 -type f -exec rm -f {} \;

# Remove all directories except checkpoints
for dir in "$HOOK_DIR"/*; do
    if [ -d "$dir" ] && [ "$(basename "$dir")" != "checkpoints" ]; then
        rm -rf "$dir"
    fi
done

# Remove empty author directory if no other hooks exist
if [ -d ~/.claude/hooks/ixe1 ] && [ -z "$(ls -A ~/.claude/hooks/ixe1)" ]; then
    rmdir ~/.claude/hooks/ixe1
fi

# Remove ckpt command
for dir in "$HOME/.local/bin" "$HOME/bin"; do
    if [ -f "$dir/ckpt" ]; then
        rm -f "$dir/ckpt"
        echo "✅ Removed $dir/ckpt"
    fi
done

# Remove checkpoint hooks from settings.json
if [ -f ~/.claude/settings.json ]; then
    echo "Updating settings.json..."
    python3 << 'EOF'
import json
import sys
import os

settings_path = os.path.expanduser('~/.claude/settings.json')

try:
    with open(settings_path, 'r') as f:
        settings = json.load(f)
    
    # Remove checkpoint-manager.py hooks
    if 'hooks' in settings:
        # Clean PreToolUse hooks
        if 'PreToolUse' in settings['hooks']:
            for hook in settings['hooks']['PreToolUse']:
                if hook.get('matcher') == 'Write|Edit|MultiEdit' and 'hooks' in hook:
                    # Remove checkpoint-manager.py entries
                    hook['hooks'] = [
                        h for h in hook['hooks'] 
                        if 'ixe1/claude-code-checkpointing-hook/checkpoint-manager.py' not in h.get('command', '')
                    ]
            
            # Remove empty hook entries
            settings['hooks']['PreToolUse'] = [
                h for h in settings['hooks']['PreToolUse'] 
                if h.get('hooks')
            ]
        
        # Clean PostToolUse hooks
        if 'PostToolUse' in settings['hooks']:
            for hook in settings['hooks']['PostToolUse']:
                if hook.get('matcher') == 'Write|Edit|MultiEdit' and 'hooks' in hook:
                    # Remove checkpoint-manager.py entries
                    hook['hooks'] = [
                        h for h in hook['hooks'] 
                        if 'ixe1/claude-code-checkpointing-hook/checkpoint-manager.py' not in h.get('command', '')
                    ]
            
            # Remove empty hook entries
            settings['hooks']['PostToolUse'] = [
                h for h in settings['hooks']['PostToolUse'] 
                if h.get('hooks')
            ]
    
    # Note: Checkpointing config is now stored separately in the hook's config.json
    
    # Write updated settings
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Removed checkpoint hooks from settings.json")

except Exception as e:
    print(f"⚠️  Could not update settings.json: {e}")
EOF
fi

echo
echo "✅ Uninstall complete!"
echo
echo "Your checkpoints are preserved in: ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/"
echo "To remove them, run: rm -rf ~/.claude/hooks/ixe1/claude-code-checkpointing-hook/"