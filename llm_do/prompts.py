"""Prompt file loading and Jinja2 template rendering for llm-do workers.

This module handles:
- Convention-based prompt file discovery (.jinja2, .j2, .txt, .md)
- Jinja2 template rendering with custom file() function and security checks
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError


def load_prompt_file(worker_name: str, prompts_dir: Path) -> tuple[str, bool]:
    """Load prompt by convention from prompts/ directory.

    Looks for prompts/{worker_name}.{txt,jinja2,j2,md} in order.

    Args:
        worker_name: Name of the worker
        prompts_dir: Path to prompts directory

    Returns:
        Tuple of (prompt_content, is_jinja_template)

    Raises:
        FileNotFoundError: If no prompt file found for worker
    """
    # Try extensions in order - Jinja2 templates first, then plain text
    for ext, is_jinja in [
        (".jinja2", True),
        (".j2", True),
        (".txt", False),
        (".md", False),
    ]:
        prompt_file = prompts_dir / f"{worker_name}{ext}"
        if prompt_file.exists():
            content = prompt_file.read_text(encoding="utf-8")
            return (content, is_jinja)

    raise FileNotFoundError(
        f"No prompt file found for worker '{worker_name}' in {prompts_dir}. "
        f"Expected: {worker_name}.{{txt,jinja2,j2,md}}"
    )


def render_jinja_template(template_str: str, template_root: Path) -> str:
    """Render a Jinja2 template with prompts/ directory as the base.

    Provides a `file(path)` function that loads files relative to template_root.
    Also supports standard {% include %} directive.

    Args:
        template_str: Jinja2 template string
        template_root: Root directory for template file loading (prompts/ directory)

    Returns:
        Rendered template string

    Raises:
        FileNotFoundError: If a referenced file doesn't exist
        PermissionError: If a file path escapes template root directory
        jinja2.TemplateError: If template syntax is invalid
    """

    # Set up Jinja2 environment with prompts/ as base
    env = Environment(
        loader=FileSystemLoader(template_root),
        autoescape=False,  # Don't escape - we want raw text
        keep_trailing_newline=True,
    )

    # Add custom file() function
    def load_file(path_str: str) -> str:
        """Load a file relative to template root."""
        file_path = (template_root / path_str).resolve()

        # Security: ensure resolved path doesn't escape template root
        try:
            file_path.relative_to(template_root)
        except ValueError:
            raise PermissionError(
                f"File path escapes allowed directory: {path_str}"
            )

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path_str}"
            )

        return file_path.read_text(encoding="utf-8")

    # Make file() available in templates
    env.globals["file"] = load_file

    # Render the template
    try:
        template = env.from_string(template_str)
        return template.render()
    except (TemplateNotFound, UndefinedError) as exc:
        raise ValueError(f"Template error: {exc}") from exc
