"""
Core execution logic for llm-do

Executes spec-driven workflows by providing tools to LLM and letting it
interpret natural language commands according to a specification.
"""

import llm
from llm.models import CancelToolCall
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import click

from .config import LlmDoConfig


class ToolApprovalCallback:
    """
    Stateful callback for approving tool executions.

    Allows user to approve each tool call individually, or approve all
    tool calls for the duration of the session.
    """

    def __init__(self):
        self.approve_all = False

    def __call__(self, tool, tool_call):
        """Called before each tool execution."""
        # If user previously approved all, skip prompting
        if self.approve_all:
            return

        # Display the tool call
        click.echo(
            click.style(
                f"\nTool call: {tool_call.name}({tool_call.arguments})",
                fg="yellow",
                bold=True,
            ),
            err=True,
        )

        # Prompt for approval
        while True:
            response = click.prompt(
                "Approve? [y]es, [n]o, [a]lways, [q]uit",
                type=str,
                default="y",
                err=True,
            ).lower().strip()

            if response in ("y", "yes", ""):
                return  # Approve this tool call
            elif response in ("n", "no"):
                raise CancelToolCall("User declined tool call")
            elif response in ("a", "always"):
                self.approve_all = True
                click.echo(
                    click.style("✓ All tool calls approved for this session", fg="green"),
                    err=True,
                )
                return
            elif response in ("q", "quit"):
                raise CancelToolCall("User quit")
            else:
                click.echo("Invalid response. Please enter y, n, a, or q.", err=True)


def execute_spec(
    task: str,
    spec_path: str,
    toolbox,
    model_name: Optional[str] = None,
    verbose: bool = True,
    config: Optional[LlmDoConfig] = None,
    working_dir: Optional[Path] = None,
    tools_approve: bool = False,
):
    """
    Execute a task according to a specification using LLM + tools.

    Args:
        task: Natural language task description
        spec_path: Path to specification file (markdown)
        toolbox: Toolbox instance with tools for LLM to use
        model_name: LLM model to use (defaults to llm's configured default)
        verbose: Print execution details
        config: Workflow configuration loaded from working directory
        working_dir: Base directory for resolving relative paths
        tools_approve: Manually approve every tool execution

    Returns:
        Response text from LLM

    Raises:
        FileNotFoundError: If spec file doesn't exist
        Exception: If model or execution fails
    """

    config = config or LlmDoConfig()

    # Load specification
    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    spec_content = spec_file.read_text()

    prompt_text, system_text = _build_prompt_and_system(
        task=task,
        spec_content=spec_content,
        spec_file=spec_file,
        config=config,
        working_dir=working_dir,
    )

    # Resolve model (falls back to llm's default)
    resolved_model_name = model_name or llm.get_default_model()

    if verbose:
        print(f"Task: {task}")
        print(f"Spec: {spec_path}")
        if config.prompt.template:
            print(f"Template: {config.prompt.template}")
        print(f"Model: {resolved_model_name}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("=" * 60)
        print()

    try:
        model = llm.get_model(resolved_model_name)
    except Exception as e:
        raise Exception(f"Error loading model {resolved_model_name}: {e}")

    _enforce_model_constraints(model, resolved_model_name, config)

    if verbose:
        print(f"Executing with {resolved_model_name}...")
        print()

    # Execute with tool chain
    try:
        # Set up approval callback if requested
        before_call = None
        if tools_approve:
            before_call = ToolApprovalCallback()

        chain_response = model.chain(
            prompt_text,
            system=system_text,
            tools=[toolbox],  # Toolbox must be in a list
            before_call=before_call,
        )

        # Collect response text
        response_text = []
        for chunk in chain_response:
            if verbose:
                print(chunk, end="", flush=True)
            response_text.append(chunk)

        if verbose:
            print()  # Final newline
            print()
            print("=" * 60)
            print()
            print("Complete!")

        return "".join(response_text)

    except KeyboardInterrupt:
        if verbose:
            print("\n\nInterrupted by user")
        raise
    except Exception as e:
        if verbose:
            print(f"\n\nError during execution: {e}")
        raise


def _enforce_model_constraints(model, resolved_name: str, config: LlmDoConfig) -> None:
    """Validate model against any configured allow-lists or attachment needs."""

    allowed = set(config.model.allowed_models)
    if allowed:
        candidate_names = {resolved_name, getattr(model, "model_id", resolved_name)}
        model_name = getattr(model, "model_name", None)
        if model_name:
            candidate_names.add(model_name)
        if candidate_names.isdisjoint(allowed):
            raise Exception(
                "Model '{}' is not permitted for this workflow. Allowed models: {}".format(
                    resolved_name,
                    ", ".join(sorted(allowed)),
                )
            )

    required_types = set(config.requires_attachment_types)
    if required_types:
        supported = set(getattr(model, "attachment_types", set()))
        missing = sorted(required_types - supported)
        if missing:
            raise Exception(
                "Model '{}' is missing required attachment support: {}".format(
                    resolved_name, ", ".join(missing)
                )
            )


def _build_prompt_and_system(
    task: str,
    spec_content: str,
    spec_file: Path,
    config: LlmDoConfig,
    working_dir: Optional[Path],
) -> Tuple[str, str]:
    """Return the prompt/system strings, possibly via a configured template."""

    prompt_text = task
    system_text = spec_content
    template_name = config.prompt.template
    if not template_name:
        return prompt_text, system_text

    # Lazy import to avoid circular dependency
    from llm.cli import LoadTemplateError, load_template
    from llm.templates import Template

    try:
        template = load_template(template_name)
    except LoadTemplateError as exc:
        raise Exception(f"Unable to load template '{template_name}': {exc}")

    params = dict(config.prompt.params)
    params.setdefault("spec", spec_content)
    params.setdefault("spec_path", str(spec_file))
    params.setdefault("task", task)
    if working_dir:
        params.setdefault("working_dir", str(working_dir))

    try:
        template_prompt, template_system = template.evaluate(task, params)
    except Template.MissingVariables as exc:
        raise Exception(
            f"Template '{template_name}' is missing variables: {exc}"
        )

    if template_prompt:
        prompt_text = template_prompt
    if template_system:
        system_text = template_system

    return prompt_text, system_text
