"""Rich console display utilities for llm-do CLI.

Provides rendering functions for LLM messages, user input, and structured data.
All functions use Rich for terminal formatting.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.text import Text


def render_json_or_text(value: Any) -> JSON | Text:
    """Render value as Rich JSON or Text with fallback for edge cases."""
    if isinstance(value, str):
        return Text(value)

    try:
        return JSON.from_data(value)
    except (TypeError, ValueError):
        # Fallback for non-serializable objects (should rarely happen)
        return Text(repr(value), style="dim")


def display_messages(messages: list[ModelMessage], console: Console) -> None:
    """Display LLM messages with rich formatting."""
    for msg in messages:
        if isinstance(msg, ModelRequest):
            # User/system input to the model
            console.print()

            if msg.instructions:
                console.print(Panel(
                    msg.instructions,
                    title="[bold cyan]System Instructions[/bold cyan]",
                    border_style="cyan",
                ))

            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    # Handle both string and list content (with attachments)
                    if isinstance(part.content, str):
                        display_content = part.content
                    else:
                        # part.content is a Sequence[UserContent] with text + attachments
                        text_parts = []
                        attachment_count = 0
                        for item in part.content:
                            if isinstance(item, str):
                                text_parts.append(item)
                            else:
                                # BinaryContent, ImageUrl, etc.
                                attachment_count += 1

                        display_content = "\n".join(text_parts)
                        if attachment_count:
                            display_content += f"\n\n[dim]+ {attachment_count} attachment(s)[/dim]"

                    console.print(Panel(
                        display_content,
                        title="[bold green]User Input[/bold green]",
                        border_style="green",
                    ))
                elif isinstance(part, SystemPromptPart):
                    console.print(Panel(
                        part.content,
                        title="[bold cyan]System Prompt[/bold cyan]",
                        border_style="cyan",
                    ))
                elif isinstance(part, ToolReturnPart):
                    # Tool result being sent back to model
                    console.print(Panel(
                        render_json_or_text(part.content),
                        title=f"[bold yellow]Tool Result: {part.tool_name}[/bold yellow]",
                        border_style="yellow",
                    ))

        elif isinstance(msg, ModelResponse):
            # Model's response
            for part in msg.parts:
                if isinstance(part, TextPart):
                    console.print(Panel(
                        part.content,
                        title="[bold magenta]Model Response[/bold magenta]",
                        border_style="magenta",
                    ))
                elif isinstance(part, ToolCallPart):
                    # Model is calling a tool
                    console.print(Panel(
                        render_json_or_text(part.args),
                        title=f"[bold blue]Tool Call: {part.tool_name}[/bold blue]",
                        border_style="blue",
                    ))


def stringify_user_input(user_input: Any) -> str:
    """Convert arbitrary input data to displayable text."""
    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


def display_initial_request(
    *,
    definition: Any,  # WorkerDefinition - avoiding circular import
    user_input: Any,
    attachments: Optional[list[str]],
    console: Console,
) -> None:
    """Render the outgoing message sent to the LLM before streaming starts."""
    prompt_text = stringify_user_input(user_input)
    user_content: Any
    if attachments:
        user_content = [prompt_text]
        for attachment in attachments:
            placeholder = BinaryContent(
                data=b"",
                media_type="application/octet-stream",
                identifier=Path(attachment).name,
            )
            user_content.append(placeholder)
    else:
        user_content = prompt_text

    request = ModelRequest(
        parts=[UserPromptPart(content=user_content)],
        instructions=definition.instructions,
    )
    display_messages([request], console)
