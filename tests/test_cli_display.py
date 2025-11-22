"""Tests for cli_display module."""
import json
from pathlib import Path

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from rich.console import Console
from rich.json import JSON
from rich.text import Text

from llm_do.cli_display import (
    display_messages,
    render_json_or_text,
    stringify_user_input,
)


def test_render_json_or_text_with_string():
    """Plain strings should render as Text."""
    result = render_json_or_text("hello world")
    assert isinstance(result, Text)
    assert "hello world" in str(result)


def test_render_json_or_text_with_dict():
    """Dicts should render as JSON."""
    result = render_json_or_text({"foo": "bar", "baz": 123})
    assert isinstance(result, JSON)


def test_render_json_or_text_with_list():
    """Lists should render as JSON."""
    result = render_json_or_text([1, 2, 3])
    assert isinstance(result, JSON)


def test_render_json_or_text_with_non_serializable():
    """Non-serializable objects should fall back to repr Text."""
    result = render_json_or_text(Path("/test"))
    assert isinstance(result, Text)
    # Should contain the repr output
    assert "test" in str(result).lower()


def test_stringify_user_input_with_string():
    """Plain strings should be returned as-is."""
    assert stringify_user_input("hello") == "hello"


def test_stringify_user_input_with_dict():
    """Dicts should be JSON-serialized."""
    result = stringify_user_input({"task": "test", "count": 42})
    parsed = json.loads(result)
    assert parsed == {"task": "test", "count": 42}
    # Should be pretty-printed
    assert "\n" in result


def test_stringify_user_input_with_list():
    """Lists should be JSON-serialized."""
    result = stringify_user_input([1, 2, 3])
    parsed = json.loads(result)
    assert parsed == [1, 2, 3]


def test_display_messages_with_model_request():
    """ModelRequest should display user input and instructions."""
    console = Console(record=True)
    request = ModelRequest(
        parts=[UserPromptPart(content="Hello world")],
        instructions="Be helpful and friendly"
    )

    display_messages([request], console)

    output = console.export_text()
    assert "Hello world" in output
    assert "User Input" in output
    assert "Be helpful and friendly" in output
    assert "System Instructions" in output


def test_display_messages_with_model_response():
    """ModelResponse should display text parts."""
    console = Console(record=True)
    response = ModelResponse(
        parts=[TextPart(content="Hi there! How can I help?")],
        model_name="test-model"
    )

    display_messages([response], console)

    output = console.export_text()
    assert "Hi there! How can I help?" in output
    assert "Model Response" in output


def test_display_messages_with_tool_call():
    """ToolCallPart should display tool name and args."""
    console = Console(record=True)
    response = ModelResponse(
        parts=[ToolCallPart(
            tool_name="read_file",
            args={"path": "/test.txt", "max_chars": 1000}
        )],
        model_name="test-model"
    )

    display_messages([response], console)

    output = console.export_text()
    assert "Tool Call" in output
    assert "read_file" in output
    assert "/test.txt" in output


def test_display_messages_with_tool_result():
    """ToolReturnPart should display result content."""
    console = Console(record=True)
    request = ModelRequest(
        parts=[ToolReturnPart(
            tool_name="read_file",
            content={"status": "success", "data": "file contents"},
            tool_call_id="call_123"
        )],
        instructions="Process the file"
    )

    display_messages([request], console)

    output = console.export_text()
    assert "Tool Result" in output
    assert "read_file" in output
    assert "success" in output


def test_display_messages_with_attachments():
    """UserPromptPart with attachments should show count."""
    console = Console(record=True)
    from pydantic_ai.messages import BinaryContent

    request = ModelRequest(
        parts=[UserPromptPart(content=[
            "Check this file",
            BinaryContent(data=b"test", media_type="text/plain", identifier="test.txt"),
            BinaryContent(data=b"test2", media_type="text/plain", identifier="test2.txt"),
        ])],
        instructions="Review files"
    )

    display_messages([request], console)

    output = console.export_text()
    assert "Check this file" in output
    assert "2 attachment(s)" in output
