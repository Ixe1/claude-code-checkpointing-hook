# Test Suite for Claude Code Checkpointing Hook

This directory contains the test suite for the checkpointing system.

## Running Tests

From the project root directory:

```bash
# Run all tests
python3 -m unittest discover tests

# Run specific test file
python3 -m unittest tests.test_config
python3 -m unittest tests.test_git_ops

# Run with verbose output
python3 -m unittest discover tests -v
```

## Test Coverage

The test suite covers:

- **Configuration Management** (`test_config.py`)
  - Default configuration loading
  - Custom configuration validation
  - File exclusion patterns
  - Size limits

- **Git Operations** (`test_git_ops.py`)
  - Project hash generation
  - Input validation (checkpoint hashes, paths, metadata)
  - Repository initialization
  - Checkpoint creation

## Adding New Tests

1. Create a new test file: `test_<module>.py`
2. Import the module to test with the sys.path setup:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
   ```
3. Create test classes inheriting from `unittest.TestCase`
4. Use setUp() and tearDown() for test fixtures

## Note on Import Errors

Static type checkers may show import errors for the local modules. These can be safely ignored as the imports work correctly at runtime due to the sys.path modifications.