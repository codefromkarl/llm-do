"""CLI entry point for running PydanticAI-style workers.

The CLI is intentionally lightweight and focused on production use cases.
It provides a simple interface for running workers with live LLM models.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .base import WorkerCreationProfile, WorkerRegistry, run_worker


def _load_jsonish(value: str) -> Any:
    """Load JSON from an inline string or filesystem path.

    The helper mirrors the permissive behavior of many CLIs: if the argument
    points to an existing file, the file is read as JSON. Otherwise the value
    itself is parsed as JSON. This keeps the interface small while supporting
    both ad-hoc invocations and scripted runs.
    """

    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def _load_profile(path: Optional[str]) -> WorkerCreationProfile:
    if not path:
        return WorkerCreationProfile()
    data = _load_jsonish(path)
    return WorkerCreationProfile.model_validate(data)




def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PydanticAI worker")
    parser.add_argument(
        "worker",
        help="Worker name or path to .yaml file (e.g., 'greeter' or 'examples/greeter.yaml')",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Input message (plain text). Use --input for JSON instead.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to the worker registry root (inferred from worker path if not provided)",
    )
    parser.add_argument(
        "--input",
        dest="input_json",
        default=None,
        help="JSON payload or path to JSON file for worker input (alternative to plain message)",
    )
    parser.add_argument(
        "--model",
        dest="cli_model",
        default=None,
        help="Override the effective model for this run",
    )
    parser.add_argument(
        "--profile",
        dest="profile_path",
        default=None,
        help="Optional JSON profile file for creation defaults",
    )
    parser.add_argument(
        "--attachments",
        nargs="*",
        default=None,
        help="Attachment file paths passed to the worker",
    )
    parser.add_argument(
        "--no-pretty",
        dest="pretty",
        action="store_false",
        default=True,
        help="Disable pretty-printing of JSON output",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    # Determine worker name and registry
    worker_path = Path(args.worker)
    if worker_path.exists() and worker_path.suffix in {".yaml", ".yml"}:
        # Worker is a file path
        if args.registry is None:
            # Infer registry from worker path directory
            registry_root = worker_path.parent
        else:
            registry_root = args.registry
        worker_name = worker_path.stem
    else:
        # Worker is a name, registry must be provided or use current directory
        if args.registry is None:
            registry_root = Path(".")
        else:
            registry_root = args.registry
        worker_name = args.worker

    registry = WorkerRegistry(registry_root)

    # Determine input data
    if args.input_json is not None:
        # Use JSON input if provided
        input_data = _load_jsonish(args.input_json)
    elif args.message is not None:
        # Use plain text message
        input_data = args.message
    else:
        # Default to empty input
        input_data = {}

    profile = _load_profile(args.profile_path)

    result = run_worker(
        registry=registry,
        worker=worker_name,
        input_data=input_data,
        attachments=args.attachments,
        cli_model=args.cli_model,
        creation_profile=profile,
    )

    serialized = result.model_dump(mode="json")
    indent = 2 if args.pretty else None
    json.dump(serialized, sys.stdout, indent=indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

