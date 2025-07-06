# Test Suite for Claude Code Checkpointing Hook

This directory contains the comprehensive test suite for the checkpointing system.

## Running Tests

From the project root directory:

```bash
# Run all tests
python3 -m unittest discover tests -v

# Run all tests with the test runner
./run_tests.py

# Run specific test file
python3 -m unittest tests.test_config
python3 -m unittest tests.test_git_ops
python3 -m unittest tests.test_metadata
python3 -m unittest tests.test_checkpoint_manager
python3 -m unittest tests.test_integration
python3 -m unittest tests.test_restore_script
python3 -m unittest tests.test_cleanup_script

# Run with pytest (if installed)
python3 -m pytest tests/ -v
```

## Test Coverage

The test suite provides comprehensive coverage with both unit and integration tests:

### Unit Tests

- **Configuration Management** (`test_config.py`)
  - Default configuration loading
  - Custom configuration validation
  - File exclusion patterns and complex glob matching
  - Size limits and edge case values
  - Error handling: missing files, invalid JSON, permission errors
  - Type validation and normalization

- **Git Operations** (`test_git_ops.py`)
  - Project hash generation
  - Input validation (checkpoint hashes, paths, metadata)
  - Repository initialization
  - Checkpoint creation and restoration
  - File synchronization and batch operations
  - Diff generation
  - Error handling: invalid hashes, permission errors
  - Edge cases: binary files, symlinks, empty repos
  - Concurrent checkpoint creation

- **Metadata Management** (`test_metadata.py`)
  - Checkpoint metadata storage and retrieval
  - Project statistics and checkpoint listing
  - File search and cleanup operations
  - Error handling: corrupted JSON, file permissions
  - Concurrent access and race conditions
  - Large metadata files and performance
  - Unicode handling
  - Extract files for Edit/MultiEdit tools

- **Checkpoint Manager** (`test_checkpoint_manager.py`)
  - Real integration tests (no mocking)
  - PreToolUse and PostToolUse hook handling
  - Tool-specific message generation
  - Configuration integration
  - File exclusion logic
  - Status tracking and reporting

### Integration Tests

- **End-to-End Scenarios** (`test_integration.py`)
  - Complete checkpoint → modify → restore cycles
  - Multiple checkpoints with different tools
  - File deletion and restoration
  - Nested directory structures
  - Large project performance (100+ files)
  - Concurrent operations
  - Gitignore integration
  - Error recovery

### Script Tests

- **Restore Script** (`test_restore_script.py`)
  - Command-line interface testing
  - Interactive restore flow
  - Search and list functionality
  - Dry-run mode
  - Input validation and error handling
  - Output formatting

- **Cleanup Script** (`test_cleanup_script.py`)
  - Age-based cleanup operations
  - Dry-run mode
  - All-projects cleanup
  - Orphaned repository detection
  - Configuration integration
  - Output formatting

### Test Utilities

- **Shared Utilities** (`test_utils.py`)
  - Test project creation
  - Hook input simulation
  - Performance measurement
  - File operation helpers
  - Mock utilities for error injection

## Adding New Tests

1. Create a new test file: `test_<module>.py`
2. Import the module to test with the sys.path setup:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
   ```
3. Import test utilities if needed:
   ```python
   from test_utils import create_test_project, simulate_hook_input, TempProjectContext
   ```
4. Create test classes inheriting from `unittest.TestCase`
5. Use setUp() and tearDown() for test fixtures
6. Follow the pattern of using real operations instead of mocks where possible

## Best Practices

- **Prefer Real Operations**: Use actual file operations and git commands instead of mocking
- **Isolate Tests**: Use temporary directories to avoid interference
- **Test Error Cases**: Include tests for permission errors, corrupted data, etc.
- **Clean Up**: Always clean up temporary files and restore system state
- **Type Guards**: Use `assert x is not None` for type checking when needed
- **Platform Awareness**: Skip platform-specific tests appropriately

## Performance Testing

For performance-sensitive operations, use the `@measure_operation_time` decorator:
```python
from test_utils import measure_operation_time

@measure_operation_time
def test_large_project_performance(self):
    # Test code here
```

## Note on Import Errors

Static type checkers may show import errors for the local modules. These can be safely ignored as the imports work correctly at runtime due to the sys.path modifications.

## Test Dependencies

The test suite requires:
- Python 3.6+
- Git installed and configured
- Unix-like system for some tests (Windows users may see some tests skipped)
- Sufficient disk space for large file tests

## Continuous Integration

When running in CI environments:
- Ensure git user.email and user.name are configured
- Some file permission tests may behave differently
- Concurrent tests may need adjustment based on available resources