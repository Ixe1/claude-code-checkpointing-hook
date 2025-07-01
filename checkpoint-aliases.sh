#!/bin/bash
# Claude Code checkpoint system - ckpt command
# Add this to your ~/.bashrc or ~/.zshrc:
# source ~/.claude/hooks/checkpoint-aliases.sh

# Main ckpt command with git-style subcommands
ckpt() {
    case "$1" in
        restore|r)
            shift
            python3 ~/.claude/hooks/restore-checkpoint.py "$@"
            ;;
        list|l)
            shift
            python3 ~/.claude/hooks/restore-checkpoint.py --list "$@"
            ;;
        search|s)
            shift
            if [ -z "$1" ]; then
                echo "Error: search requires a search term"
                echo "Usage: ckpt search <term>"
                return 1
            fi
            python3 ~/.claude/hooks/restore-checkpoint.py --search "$@"
            ;;
        status|st)
            shift
            python3 ~/.claude/hooks/checkpoint-manager.py --status "$@"
            ;;
        clean|c)
            shift
            python3 ~/.claude/hooks/cleanup-checkpoints.py "$@"
            ;;
        diff|d)
            shift
            local checkpoint_id="$1"
            python3 -c "
import sys
sys.path.insert(0, '/home/developer/.claude/hooks')
from pathlib import Path
from checkpointing import GitCheckpointManager

mgr = GitCheckpointManager(Path.cwd())
diff = mgr.get_checkpoint_diff('$checkpoint_id' if '$checkpoint_id' else None)
if diff:
    print('Changes since checkpoint:')
    print('=' * 80)
    print(diff)
else:
    print('No changes found.')
"
            ;;
        now|n)
            shift
            local message="${1:-Manual checkpoint}"
            echo '{"tool_name":"Manual","tool_input":{"action":"checkpoint"},"session_id":"manual"}' | \
            python3 ~/.claude/hooks/checkpoint-manager.py
            ;;
        help|h|"")
            echo "Usage: ckpt <command> [args]"
            echo ""
            echo "Commands:"
            echo "  restore, r [id]      Restore from checkpoint (interactive if no id)"
            echo "  list, l              List all checkpoints"
            echo "  search, s <term>     Search checkpoints by term"
            echo "  status, st           Show checkpoint statistics"
            echo "  clean, c [opts]      Clean up old checkpoints (--dry-run available)"
            echo "  diff, d [id]         Show changes since checkpoint"
            echo "  now, n [msg]         Create manual checkpoint with optional message"
            echo "  help, h              Show this help message"
            echo ""
            echo "Examples:"
            echo "  ckpt list            # List all checkpoints"
            echo "  ckpt r               # Interactive restore"
            echo "  ckpt r abc123        # Restore specific checkpoint"
            echo "  ckpt s feature       # Search for 'feature' in checkpoints"
            echo "  ckpt clean --dry-run # Preview what would be cleaned"
            echo "  ckpt now 'pre-refactor' # Create checkpoint with message"
            ;;
        *)
            echo "Unknown command: $1"
            echo "Use 'ckpt help' for usage information"
            return 1
            ;;
    esac
}

# Bash completion for ckpt command
_ckpt_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Main command options
    if [ $COMP_CWORD -eq 1 ]; then
        opts="restore r list l search s status st clean c diff d now n help h"
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        return 0
    fi
    
    # Subcommand-specific completions
    case "${COMP_WORDS[1]}" in
        clean|c)
            if [ $COMP_CWORD -eq 2 ]; then
                opts="--dry-run --force"
                COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            fi
            ;;
        restore|r|diff|d)
            # Could potentially complete with checkpoint IDs here
            # For now, just return nothing to allow default completion
            ;;
    esac
}

# Register bash completion
complete -F _ckpt_completion ckpt

echo "Claude Code checkpoint system loaded. Type 'ckpt help' for usage."