"""
Base toolbox class for llm-do

Provides common tools that are useful across different spec-driven workflows.
Users can extend this to create domain-specific toolboxes.
"""

import llm
import subprocess
from pathlib import Path


class BaseToolbox(llm.Toolbox):
    """
    Base toolbox with common tools for file and shell operations.

    Extend this class to add domain-specific tools.
    """

    def __init__(self, working_dir=None):
        """
        Initialize toolbox with optional working directory.

        Args:
            working_dir: Base directory for file operations (default: cwd)
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()

    def run_bash(self, command: str) -> str:
        """
        Execute a bash command and return output.
        Use this for git operations, finding files, getting file metadata, etc.

        Examples:
            run_bash("git pull")
            run_bash("find pipeline/ -name '*.pdf'")
            run_bash("stat -c '%y' file.pdf")
            run_bash("ls -la directory/")

        Args:
            command: Shell command to execute

        Returns:
            Command output or error message
        """
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(self.working_dir)
        )

        if result.returncode != 0:
            return f"Error (exit {result.returncode}): {result.stderr}"

        output = result.stdout.strip()
        return output if output else "(command succeeded, no output)"

    def read_file(self, path: str) -> str:
        """
        Read a text file and return its contents.
        Use for reading specs, documents, existing outputs, etc.

        Path is relative to working directory.

        Examples:
            read_file("SPEC.md")
            read_file("output/evaluation.md")
            read_file("framework/criteria.md")

        Args:
            path: File path relative to working directory

        Returns:
            File contents or error message
        """
        try:
            file_path = self.working_dir / path
            return file_path.read_text()
        except Exception as e:
            return f"Error reading {path}: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        """
        Write content to a file (creates parent directories if needed).
        Use for saving outputs, results, logs, etc.

        Path is relative to working directory.

        Examples:
            write_file("output/result.md", result_text)
            write_file("logs/task.log", log_entry)

        Args:
            path: File path relative to working directory
            content: Content to write

        Returns:
            Success message or error
        """
        try:
            file_path = self.working_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return f"Written {len(content)} characters to {path}"
        except Exception as e:
            return f"Error writing {path}: {str(e)}"
