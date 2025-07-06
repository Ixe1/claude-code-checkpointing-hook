#!/usr/bin/env python3
"""Common test utilities for the checkpointing test suite."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock


def create_test_project(base_dir: Path, files: Optional[Dict[str, str]] = None) -> Path:
    """Create a test project with sample files.
    
    Args:
        base_dir: Base directory for the test project
        files: Dictionary of file paths (relative) to content
        
    Returns:
        Path to the created project directory
    """
    project_dir = base_dir / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Default files if none provided
    if files is None:
        files = {
            "main.py": "def main():\n    print('Hello, world!')\n\nif __name__ == '__main__':\n    main()\n",
            "utils.py": "def helper(x):\n    return x * 2\n",
            "README.md": "# Test Project\n\nThis is a test project for checkpointing.",
            "src/module.py": "class TestClass:\n    def __init__(self):\n        self.value = 42\n",
            "tests/test_main.py": "import unittest\n\nclass TestMain(unittest.TestCase):\n    pass\n"
        }
    
    # Create files
    for file_path, content in files.items():
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    return project_dir


def simulate_hook_input(tool_name: str, tool_input: Dict, 
                       session_id: str = "test-session",
                       tool_response: Optional[Dict] = None) -> Dict:
    """Create a simulated Claude Code hook input.
    
    Args:
        tool_name: Name of the tool (Write, Edit, MultiEdit, etc.)
        tool_input: Tool-specific input parameters
        session_id: Session identifier
        tool_response: Optional tool response for PostToolUse
        
    Returns:
        Dictionary formatted as Claude Code hook input
    """
    input_data = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": session_id
    }
    
    if tool_response is not None:
        input_data["tool_response"] = tool_response
    
    return input_data


def run_checkpoint_manager(input_data: Dict, args: Optional[List[str]] = None, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run checkpoint-manager.py with given input.
    
    Args:
        input_data: Hook input data to pass via stdin
        args: Additional command line arguments
        cwd: Working directory for the command
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    script_path = Path(__file__).parent.parent / "checkpoint-manager.py"
    cmd = ["python3", str(script_path)]
    if args is not None:
        cmd.extend(args)
    
    result = subprocess.run(
        cmd,
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None
    )
    
    return result.returncode, result.stdout, result.stderr


def create_git_failure_mock(command_pattern: str, error_message: str = "Git command failed"):
    """Create a mock that simulates git command failures.
    
    Args:
        command_pattern: Git command pattern to fail on (e.g., "checkout")
        error_message: Error message to return
        
    Returns:
        Mock object for GitCheckpointManager._run_git
    """
    def mock_run_git(cmd, cwd=None):
        if any(command_pattern in arg for arg in cmd):
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = error_message
            return result
        # Default success
        result = MagicMock()
        result.returncode = 0
        result.stdout = "Success"
        result.stderr = ""
        return result
    
    return mock_run_git


def create_large_file_set(project_dir: Path, num_files: int = 1000, 
                         file_size: int = 1024) -> List[Path]:
    """Create a large set of files for performance testing.
    
    Args:
        project_dir: Directory to create files in
        num_files: Number of files to create
        file_size: Size of each file in bytes
        
    Returns:
        List of created file paths
    """
    files = []
    content = "x" * file_size
    
    for i in range(num_files):
        # Create files in subdirectories to test directory handling
        subdir = f"dir_{i // 100}"
        file_path = project_dir / subdir / f"file_{i}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        files.append(file_path)
    
    return files


def corrupt_json_file(file_path: Path):
    """Corrupt a JSON file for error testing.
    
    Args:
        file_path: Path to the JSON file to corrupt
    """
    if file_path.exists():
        content = file_path.read_text()
        # Truncate the file in the middle
        corrupted = content[:len(content)//2]
        file_path.write_text(corrupted)


def create_readonly_file(file_path: Path) -> Path:
    """Create a read-only file for permission testing.
    
    Args:
        file_path: Path where to create the file
        
    Returns:
        Path to the created file
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("Read-only content")
    file_path.chmod(0o444)  # Read-only
    return file_path


def measure_operation_time(func):
    """Decorator to measure operation time.
    
    Usage:
        @measure_operation_time
        def test_performance():
            # test code
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"\n{func.__name__} took {duration:.2f} seconds")
        return result
    return wrapper


def init_git_repo(path: Path, initial_commit: bool = True) -> None:
    """Initialize a git repository for testing.
    
    Args:
        path: Directory to initialize as git repo
        initial_commit: Whether to create an initial commit
    """
    subprocess.run(['git', 'init'], cwd=str(path), capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], 
                   cwd=str(path), capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], 
                   cwd=str(path), capture_output=True)
    
    if initial_commit:
        # Create initial commit
        readme = path / "README.md"
        readme.write_text("Initial commit")
        subprocess.run(['git', 'add', '.'], cwd=str(path), capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], 
                       cwd=str(path), capture_output=True)


def wait_for_file_operation(file_path: Path, timeout: float = 1.0) -> bool:
    """Wait for a file operation to complete (useful for concurrent tests).
    
    Args:
        file_path: Path to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if file exists within timeout, False otherwise
    """
    start = time.time()
    while time.time() - start < timeout:
        if file_path.exists():
            return True
        time.sleep(0.05)
    return False


class TempProjectContext:
    """Context manager for creating temporary test projects.
    
    Usage:
        with TempProjectContext() as project_dir:
            # Use project_dir for testing
            # Automatically cleaned up on exit
    """
    
    def __init__(self, files: Optional[Dict[str, str]] = None):
        self.files = files
        self.temp_dir = None
        self.project_dir = None
    
    def __enter__(self) -> Path:
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = create_test_project(Path(self.temp_dir), self.files)
        return self.project_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir)