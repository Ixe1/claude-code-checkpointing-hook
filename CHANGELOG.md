# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-07-06

### Added
- Comprehensive test suite with 94 tests (increased from 29)
- New test files for cleanup script, restore script, and integration testing
- Test utilities module for shared test functionality
- Improved pattern matching for file exclusions with proper glob support
- Enhanced error handling and robustness throughout the codebase
- Better support for complex file patterns in configuration
- Thread synchronization for concurrent checkpoint operations

### Changed
- Significantly improved test coverage across all modules
- Enhanced configuration validation and edge case handling
- Improved metadata operations with better error recovery
- Refined git operations for better reliability
- Updated cleanup script with more robust handling

### Fixed
- Concurrent checkpoint creation race conditions
- Pattern matching for directory exclusions (e.g., `node_modules/`)
- Various edge cases discovered through comprehensive testing

## [1.1.2] - 2025-07-02

### Fixed
- Fixed failing tests to work with standalone config.json structure
- Fixed directory pattern matching for file exclusions (e.g., `node_modules/` now properly excludes all files within)
- Fixed search command path in checkpoint-aliases.sh to use correct installation directory
- Fixed install.sh to prevent duplicate hook entries when run multiple times
- Added proper type guards in tests for static analyzer compatibility

### Added
- Comprehensive test coverage for metadata operations (test_metadata.py)
- Comprehensive test coverage for checkpoint manager hooks (test_checkpoint_manager.py)
- Tests increased from 10 to 29 total tests

### Changed
- Improved duplicate detection logic in install.sh to check within existing hook arrays

## [1.1.1] - 2025-07-02

### Fixed
- Uninstall script now correctly preserves checkpoint data instead of deleting it
- Updated all documentation to reference the correct checkpoint path (`~/.claude/hooks/ixe1/claude-code-checkpointing-hook/checkpoints/`)

### Removed
- CHECKPOINT_README.md duplicate documentation file

## [1.1.0] - 2025-07-02

### Added
- Manual checkpoint creation support via `ckpt now` command
- Full restoration mode that removes files not present in checkpoint
- Support for custom messages in manual checkpoints
- Isolated hook directory structure under `~/.claude/hooks/ixe1/claude-code-checkpointing-hook/`

### Changed
- Moved all hook files to author-namespaced directory for better organization
- Separated configuration into dedicated `config.json` file within hook directory
- Updated all paths to use the new directory structure
- Improved restoration to handle file deletions properly
- Enhanced checkpoint creation to support manual triggers

### Fixed
- Restoration now properly removes files that were deleted between checkpoints
- Empty directories are cleaned up during restoration

## [1.0.1] - 2025-07-01

### Added
- Input validation for checkpoint hashes and file paths to prevent invalid operations
- Configuration validation with sensible limits (1-365 days retention, 0.1-1000 MB file size)
- Logging system with debug mode support (set `CHECKPOINT_DEBUG=1` environment variable)
- Log rotation to prevent disk space issues (10MB per file, 3 backups)
- Batch file operations for better performance with large repositories
- Progress indicators for operations involving many files
- Comprehensive test suite with unit tests
- Test runner script (`run_tests.py`)

### Changed
- Replaced hardcoded home directory paths with dynamic detection for better portability
- Improved error handling with timeouts (30s default) for git operations
- Enhanced error messages to be more descriptive
- Dual output approach: stderr for Claude visibility, detailed logging for debugging

### Fixed
- Installation failures on systems where home directory is not `/home/developer`
- Potential security issues with unvalidated user input
- Missing error handling for git command failures
- Configuration values not being properly validated

### Security
- Added validation to prevent directory traversal attacks
- Limited metadata size to prevent memory exhaustion (1MB limit)
- Improved input sanitization for all user-provided data

## [1.0.0] - 2025-07-01

### Added
- Initial release of Claude Code Checkpointing Hook
- Automatic git-based checkpointing before file modifications
- Shadow repository system to avoid cluttering main project
- Interactive checkpoint restoration with diff preview
- Shell command interface with git-style subcommands
- Configuration via `~/.claude/settings.json`
- Automatic cleanup of old checkpoints
- Session tracking for checkpoints
- File exclusion patterns and size limits
- Installation and uninstallation scripts