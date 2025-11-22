"""Tests for cli_display module."""
from pathlib import Path

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
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
    display_streaming_model_response,
    display_streaming_tool_call,
    display_streaming_tool_result,
    display_worker_request,
    render_json_or_text,
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


def test_display_worker_request_shows_details():
    """Request preview should include worker name, instructions, and attachments."""
    console = Console(record=True)
    preview = {
        "instructions": "Follow the rubric",
        "user_input": "Evaluate decks",
        "attachments": ["input/deck.pdf", "input/brief.pdf"],
    }

    display_worker_request(console, "pitch_orchestrator", preview)

    output = console.export_text()
    assert "pitch_orchestrator" in output
    assert "System Instructions" in output
    assert "Evaluate decks" in output
    assert "Attachments" in output
    assert "input/deck.pdf" in output


def test_display_worker_request_handles_empty_input():
    """Request preview should show placeholder for empty input."""
    console = Console(record=True)
    preview = {
        "instructions": None,
        "user_input": "",
        "attachments": [],
    }

    display_worker_request(console, "child_worker", preview)

    output = console.export_text()
    assert "child_worker" in output
    assert "(no user input)" in output


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


def test_display_streaming_tool_call():
    """Streaming tool call should display worker, tool name, and args."""
    console = Console(record=True)
    part = ToolCallPart(
        tool_name="read_file",
        args={"path": "/test.txt", "max_chars": 1000}
    )

    display_streaming_tool_call(console, "my_worker", part)

    output = console.export_text()
    assert "Tool Call" in output
    assert "my_worker" in output
    assert "read_file" in output
    assert "/test.txt" in output


def test_display_streaming_tool_result():
    """Streaming tool result should display worker and result content."""
    console = Console(record=True)
    result = ToolReturnPart(
        tool_name="read_file",
        content={"status": "success", "lines": 42},
        tool_call_id="call_123"
    )

    display_streaming_tool_result(console, "my_worker", result)

    output = console.export_text()
    assert "Tool Result" in output
    assert "my_worker" in output
    assert "read_file" in output
    assert "success" in output


def test_display_streaming_tool_result_with_retry():
    """Streaming retry should display retry message."""
    console = Console(record=True)
    result = RetryPromptPart(
        content="Please try again with different parameters"
    )

    display_streaming_tool_result(console, "my_worker", result)

    output = console.export_text()
    assert "Tool Retry" in output
    assert "my_worker" in output
    assert "Please try again" in output


def test_display_streaming_model_response():
    """Streaming model response should display worker and text."""
    console = Console(record=True)

    display_streaming_model_response(console, "my_worker", "Hello from the model!")

    output = console.export_text()
    assert "Model Response" in output
    assert "my_worker" in output
    assert "Hello from the model!" in output


def test_display_streaming_model_response_empty():
    """Streaming model response with empty text should not print anything."""
    console = Console(record=True)

    display_streaming_model_response(console, "my_worker", "   ")

    output = console.export_text()
    # Should be empty since whitespace-only text is skipped
    assert output.strip() == ""
