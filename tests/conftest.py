"""Shared pytest fixtures for llm-do tests"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock


@pytest.fixture
def temp_workspace():
    """Provide temporary workspace directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        yield workspace


@pytest.fixture
def sample_spec(temp_workspace):
    """Provide sample specification file"""
    spec_path = temp_workspace / "SPEC.md"
    spec_path.write_text("""# Sample Specification

You are a helpful assistant that can execute bash commands.

When the user asks you to do something, use the available tools to accomplish the task.
""")
    return spec_path


@pytest.fixture
def mock_toolbox(temp_workspace):
    """Provide mock toolbox for testing"""
    from llm_do.toolbox import BaseToolbox
    return BaseToolbox(working_dir=temp_workspace)


@pytest.fixture
def mock_tool():
    """Provide mock tool object"""
    tool = Mock()
    tool.name = "test_tool"
    return tool


@pytest.fixture
def mock_tool_call():
    """Provide mock tool call object"""
    tool_call = Mock()
    tool_call.name = "run_bash"
    tool_call.arguments = {"command": "echo 'test'"}
    return tool_call
