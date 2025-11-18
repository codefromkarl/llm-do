"""
LLM plugin registration for llm-do

Registers the 'llm do' command with the llm CLI tool.
"""

import click
import llm
from pathlib import Path
from .executor import execute_spec
from .toolbox import BaseToolbox
from .config import LlmDoConfig, load_config


@llm.hookimpl
def register_commands(cli):
    """Register the 'do' command with llm CLI"""

    @cli.command()
    @click.argument("task")
    @click.option(
        "--spec",
        "-s",
        type=click.Path(exists=True),
        help="Path to specification file (otherwise resolved via llm-do config)",
    )
    @click.option(
        "--working-dir",
        "-d",
        type=click.Path(exists=True, file_okay=False),
        help="Working directory for file operations (default: current directory)",
    )
    @click.option(
        "--model",
        "-m",
        default=None,
        help="Model to use (default: llm\'s configured default)",
    )
    @click.option(
        "--quiet",
        "-q",
        is_flag=True,
        help="Suppress verbose output",
    )
    @click.option(
        "--toolbox",
        "-t",
        help="Python path to custom toolbox class (e.g., mymodule.MyToolbox)",
    )
    @click.option(
        "tools_approve",
        "--ta",
        "--tools-approve",
        is_flag=True,
        help="Manually approve every tool execution",
    )
    def do(task, spec, working_dir, model, quiet, toolbox, tools_approve):
        """
        Execute a task according to a specification.

        The task should be a natural language description of what you want to do.
        The spec file defines the workflow and how to interpret tasks.

        Examples:

            llm do "process all PDFs in pipeline/"

            llm do "generate questions for CompanyX" --spec ./SPEC.md

            llm do "re-evaluate all" -d /path/to/project
        """
        # Set working directory
        if not working_dir:
            working_dir = Path.cwd()
        else:
            working_dir = Path(working_dir)

        # Load optional config from working directory
        config = load_config(working_dir)

        # Resolve spec if the flag was not provided
        if not spec:
            spec = _discover_spec_path(working_dir, config)

        # Get toolbox
        if toolbox:
            # Import custom toolbox
            try:
                module_path, class_name = toolbox.rsplit(".", 1)
                import importlib
                module = importlib.import_module(module_path)
                toolbox_class = getattr(module, class_name)
                toolbox_instance = toolbox_class(working_dir=working_dir)
            except Exception as e:
                raise click.ClickException(f"Error loading toolbox {toolbox}: {e}")
        else:
            # Use base toolbox
            toolbox_instance = BaseToolbox(working_dir=working_dir)

        # Execute
        try:
            execute_spec(
                task=task,
                spec_path=spec,
                toolbox=toolbox_instance,
                model_name=model,
                verbose=not quiet,
                config=config,
                working_dir=working_dir,
                tools_approve=tools_approve,
            )
        except KeyboardInterrupt:
            click.echo("\nInterrupted", err=True)
            raise SystemExit(1)
        except Exception as e:
            raise click.ClickException(str(e))


def _discover_spec_path(working_dir: Path, config: LlmDoConfig) -> str:
    """Resolve the spec path based on workflow config."""

    if not config.path:
        raise click.ClickException(
            "No llm-do config found in {}. Provide --spec or create llm-do.toml with workflow.spec.".format(
                working_dir
            )
        )

    if config.workflow.spec_file:
        spec_path = working_dir / config.workflow.spec_file
        if spec_path.exists():
            return str(spec_path)
        raise click.ClickException(
            f"Configured spec file '{config.workflow.spec_file}' not found in {working_dir}"
        )

    raise click.ClickException(
        f"Config {config.path} is missing [workflow].spec. Provide --spec or set it there."
    )
