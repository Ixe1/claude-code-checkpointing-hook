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

# Remove hook files
rm -rf ~/.claude/hooks/checkpoint*.py
rm -rf ~/.claude/hooks/checkpointing/
rm -f ~/.claude/hooks/checkpoint-aliases.sh

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
                        if 'checkpoint-manager.py' not in h.get('command', '')
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
                        if 'checkpoint-manager.py' not in h.get('command', '')
                    ]
            
            # Remove empty hook entries
            settings['hooks']['PostToolUse'] = [
                h for h in settings['hooks']['PostToolUse'] 
                if h.get('hooks')
            ]
    
    # Remove checkpointing config
    if 'checkpointing' in settings:
        del settings['checkpointing']
    
    # Write updated settings
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Removed checkpoint hooks from settings.json")

except Exception as e:
    print(f"⚠️  Could not update settings.json: {e}")
EOF
fi

echo
echo "Your checkpoints are preserved in: ~/.claude/checkpoints/"
echo "To remove them, run: rm -rf ~/.claude/checkpoints"
echo
echo "✅ Uninstall complete!"