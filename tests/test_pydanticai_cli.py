"""Tests for CLI argument parsing and invocation.

These tests focus on CLI interface behavior, not full worker execution.
Integration tests in test_pydanticai_integration.py cover end-to-end workflows.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from llm_do.pydanticai import WorkerDefinition, WorkerRegistry, WorkerRunResult
from llm_do.pydanticai.cli import main


def test_cli_parses_worker_file_path_and_infers_registry(tmp_path):
    """Test that CLI can take a worker file path and infer the registry."""
    # Create worker file
    worker_file = tmp_path / "test_worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="test_worker", instructions="demo"))

    # Mock run_worker to capture how it's called
    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="test output")

        # Run CLI with file path
        result = main([str(worker_file), "Hello"])

        assert result == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs

        # Verify registry was inferred from file path
        assert call_kwargs["registry"].root == tmp_path
        assert call_kwargs["worker"] == "test_worker"
        assert call_kwargs["input_data"] == "Hello"


def test_cli_accepts_plain_text_message(tmp_path):
    """Test that plain text message is passed as input_data."""
    worker_file = tmp_path / "greeter.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="greeter", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="Hi there!")

        main([str(worker_file), "Tell me a joke"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == "Tell me a joke"


def test_cli_accepts_json_input_instead_of_message(tmp_path):
    """Test that --input takes precedence over plain message."""
    worker_file = tmp_path / "worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([str(worker_file), "--input", '{"task": "analyze", "data": [1,2,3]}'])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == {"task": "analyze", "data": [1, 2, 3]}


def test_cli_accepts_worker_name_with_explicit_registry(tmp_path):
    """Test traditional usage with worker name and --registry flag."""
    registry_dir = tmp_path / "workers"
    registry = WorkerRegistry(registry_dir)
    registry.save_definition(WorkerDefinition(name="myworker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="result")

        main(["myworker", "input", "--registry", str(registry_dir)])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["registry"].root == registry_dir
        assert call_kwargs["worker"] == "myworker"


def test_cli_passes_model_override(tmp_path):
    """Test that --model is passed to run_worker."""
    worker_file = tmp_path / "worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([str(worker_file), "hi", "--model", "openai:gpt-4o"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cli_model"] == "openai:gpt-4o"


def test_cli_passes_attachments(tmp_path):
    """Test that --attachments are passed to run_worker."""
    worker_file = tmp_path / "worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    # Create attachment files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([
            str(worker_file),
            "process",
            "--attachments",
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["attachments"] == [
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
        ]


def test_cli_pretty_prints_by_default(tmp_path, capsys):
    """Test that output is pretty-printed by default."""
    worker_file = tmp_path / "worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output={"key": "value", "nested": {"a": 1}})

        main([str(worker_file), "test"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Verify it's valid JSON
        assert output["output"] == {"key": "value", "nested": {"a": 1}}

        # Verify it has indentation (pretty printed)
        assert "  " in captured.out  # Has indentation
        assert "\n" in captured.out  # Has newlines


def test_cli_respects_no_pretty_flag(tmp_path, capsys):
    """Test that --no-pretty disables pretty printing."""
    worker_file = tmp_path / "worker.yaml"
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output={"key": "value"})

        main([str(worker_file), "test", "--no-pretty"])

        captured = capsys.readouterr()
        # Should be compact JSON on one line
        assert captured.out.count("\n") == 1  # Only trailing newline
        assert "  " not in captured.out  # No indentation
