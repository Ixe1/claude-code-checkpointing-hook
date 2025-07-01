#!/bin/bash
# Shell aliases for Claude Code checkpoint system
# Add this to your ~/.bashrc or ~/.zshrc:
# source ~/.claude/hooks/checkpoint-aliases.sh

# Checkpoint restoration
alias restore-checkpoint='python3 ~/.claude/hooks/restore-checkpoint.py'
alias list-checkpoints='python3 ~/.claude/hooks/restore-checkpoint.py --list'
alias search-checkpoints='python3 ~/.claude/hooks/restore-checkpoint.py --search'

# Checkpoint status
alias checkpoint-status='python3 ~/.claude/hooks/checkpoint-manager.py --status'

# Checkpoint cleanup
alias cleanup-checkpoints='python3 ~/.claude/hooks/cleanup-checkpoints.py'
alias cleanup-checkpoints-dry='python3 ~/.claude/hooks/cleanup-checkpoints.py --dry-run'

# Quick checkpoint creation (manual)
checkpoint-now() {
    local message="${1:-Manual checkpoint}"
    echo '{"tool_name":"Manual","tool_input":{"action":"checkpoint"},"session_id":"manual"}' | \
    python3 ~/.claude/hooks/checkpoint-manager.py
}

# Show checkpoint diff
checkpoint-diff() {
    python3 -c "
import sys
sys.path.insert(0, '/home/developer/.claude/hooks')
from pathlib import Path
from checkpointing import GitCheckpointManager

mgr = GitCheckpointManager(Path.cwd())
diff = mgr.get_checkpoint_diff('$1' if '$1' else None)
if diff:
    print('Changes since checkpoint:')
    print('=' * 80)
    print(diff)
else:
    print('No changes found.')
"
}

echo "Claude Code checkpoint aliases loaded. Available commands:"
echo "  restore-checkpoint    - Interactive checkpoint restoration"
echo "  list-checkpoints      - List all checkpoints"
echo "  checkpoint-status     - Show checkpoint statistics"
echo "  checkpoint-diff       - Show changes since last checkpoint"
echo "  cleanup-checkpoints   - Clean up old checkpoints"