# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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