"""Test for nested worker call hanging issue.

This test reproduces the bug where calling a worker that uses attachments
from within another worker's tool call causes the system to hang.
"""
import shutil
from pathlib import Path

import pytest

from llm_do import (
    WorkerRegistry,
    approve_all_callback,
    run_worker,
)
from tests.test_examples import ToolCallingModel


pytestmark = pytest.mark.examples


@pytest.fixture
def whiteboard_registry(tmp_path, monkeypatch):
    """Registry for the whiteboard_planner example."""
    source = Path(__file__).parent.parent / "examples" / "whiteboard_planner"
    dest = tmp_path / "whiteboard_planner"
    shutil.copytree(source, dest)

    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(dest)
    return WorkerRegistry(dest)


def test_nested_worker_with_attachments_hang_reproduction(whiteboard_registry):
    """Reproduce the hang when orchestrator calls whiteboard_planner with attachment.

    This test simulates the exact sequence from the live session:
    1. Orchestrator lists files (tries pattern first, then broader search)
    2. Finds white_board_plan.png
    3. Calls whiteboard_planner worker with attachment
    4. Whiteboard_planner should process the image (THIS IS WHERE IT HANGS)

    The hang occurs because:
    - The orchestrator's agent.run_sync creates an event loop
    - worker_call tool runs in an AnyIO worker thread
    - The nested whiteboard_planner agent.run_sync tries to create another event loop
    - Event loop conflict/deadlock occurs
    """
    # Setup input file (whiteboard_registry fixture already changed to example dir)
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    (input_dir / "white_board_plan.png").write_bytes(b"fake whiteboard image data")

    # Setup plans directory
    plans_dir = Path("plans")
    plans_dir.mkdir(exist_ok=True)

    # Mock the whiteboard_planner's response
    # In reality, this would analyze the image and return markdown
    whiteboard_plan_markdown = """# Project: Whiteboard Planning System

## High-level Summary
This project aims to create an automated system for converting whiteboard photos into structured project plans.

## Epics / Workstreams
- **Epic 1**: Image Processing Pipeline
  - Goal: Build a robust pipeline for ingesting and processing whiteboard images
  - Tasks:
    - [P0] Set up image storage and retrieval system
    - [P1] Implement OCR for text extraction
    - [P1] Add image preprocessing (rotation, contrast enhancement)

- **Epic 2**: AI-Powered Plan Generation
  - Goal: Use LLMs to interpret whiteboard content and generate structured plans
  - Tasks:
    - [P0] Integrate with Claude API for image analysis
    - [P0] Design prompt templates for plan generation
    - [P1] Implement validation and formatting

## Timeline
- Week 1-2: Image Processing Pipeline (Epic 1)
- Week 3-4: AI Integration (Epic 2)
- Week 5: Testing and refinement

## Open Questions / Risks
- Image quality requirements - what's the minimum resolution?
- Handling of handwriting vs. printed text
- Cost of API calls at scale
"""

    # Create a ToolCallingModel that simulates the orchestrator's behavior
    # Based on the actual transcript from the live session
    orchestrator_model = ToolCallingModel([
        # First attempt: list with pattern (returns empty)
        {
            "name": "sandbox_list",
            "args": {"sandbox": "input", "pattern": "**/*.{jpg,jpeg,png}"}
        },
        # Second attempt: list without pattern (finds the file)
        {
            "name": "sandbox_list",
            "args": {"sandbox": "input"}
        },
        # Call the whiteboard_planner worker with attachment
        # In the real scenario with live models, THIS IS WHERE THE HANG OCCURS
        # For this test, we'll mock call_worker to avoid the hang
        {
            "name": "worker_call",
            "args": {
                "worker": "whiteboard_planner",
                "input_data": {"original_filename": "white_board_plan.png"},
                "attachments": ["input/white_board_plan.png"]
            }
        },
        # After getting the plan, write it to the plans sandbox
        {
            "name": "sandbox_write_text",
            "args": {
                "sandbox": "plans",
                "path": "white_board_plan.md",
                "content": whiteboard_plan_markdown
            }
        }
    ])

    # Mock call_worker_async to return the expected plan without actually running the nested worker
    # Now that async is working, we mock the async version instead of the sync version
    from llm_do.base import WorkerRunResult

    async def mock_call_worker_async(**kwargs):
        # Verify the worker_call was made with correct parameters
        assert kwargs["worker"] == "whiteboard_planner"
        assert kwargs["input_data"] == {"original_filename": "white_board_plan.png"}
        assert len(kwargs["attachments"]) == 1
        assert "white_board_plan.png" in str(kwargs["attachments"][0].path)

        # Return the mocked plan
        return WorkerRunResult(output=whiteboard_plan_markdown, messages=[])

    import llm_do.base
    original_call_worker_async = llm_do.base.call_worker_async
    llm_do.base.call_worker_async = mock_call_worker_async

    try:
        # Run the orchestrator
        result = run_worker(
            registry=whiteboard_registry,
            worker="whiteboard_orchestrator",
            input_data={},
            cli_model=orchestrator_model,
            approval_callback=approve_all_callback,
        )

        assert result is not None

        # Verify the plan was written
        plans_dir = Path("plans")
        assert (plans_dir / "white_board_plan.md").exists()
        plan_content = (plans_dir / "white_board_plan.md").read_text()
        assert "Project: Whiteboard Planning System" in plan_content
    finally:
        # Restore original call_worker_async
        llm_do.base.call_worker_async = original_call_worker_async


@pytest.mark.skip(reason="TestModel makes default tool calls that fail without sandboxes")
def test_direct_whiteboard_planner_works(whiteboard_registry):
    """Verify that whiteboard_planner works when called directly (not nested).

    This test confirms that the issue is specific to nested worker calls,
    not a problem with the whiteboard_planner worker itself.
    """
    # Setup input file
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    test_image = input_dir / "test_board.png"
    test_image.write_bytes(b"fake whiteboard image data")

    # Mock the LLM response for whiteboard_planner
    # The whiteboard_planner worker just returns text (markdown), no tools
    from pydantic_ai.models.test import TestModel

    plan_text = """# Project: Test Board

## High-level Summary
A simple test project.

## Epics / Workstreams
- **Epic 1**: Setup
  - Goal: Initialize the project
  - Tasks:
    - [P0] Create repository

## Timeline
- Week 1: Setup

## Open Questions / Risks
- None identified
"""

    planner_model = TestModel()

    # Call whiteboard_planner directly (not through orchestrator)
    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_planner",
        input_data={"original_filename": "test_board.png"},
        attachments=[str(test_image.absolute())],
        cli_model=planner_model,
        approval_callback=approve_all_callback,
    )

    assert result is not None
    # TestModel returns a default response, so we just verify it didn't hang
    assert result.output is not None


@pytest.mark.slow
def test_nested_worker_with_real_api(whiteboard_registry):
    """Integration test: nested worker calls with real API now work!

    This test was previously marked as hanging, but the async refactor fixed it.
    It validates that nested worker calls with attachments work end-to-end with
    real API calls.

    Requirements:
    1. Set ANTHROPIC_API_KEY environment variable
    2. Run: pytest -k test_nested_worker_with_real_api -v

    What it tests:
    - Orchestrator calls Claude API
    - Orchestrator uses worker_call tool to delegate to whiteboard_planner
    - Nested worker receives attachment and calls Claude API again
    - No hang occurs due to async implementation
    - Result is properly returned and written
    """
    # Setup input file with real image data
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    # Create a minimal valid PNG (1x1 pixel red image)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf'
        b'\xc0\x00\x00\x00\x03\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    (input_dir / "white_board_plan.png").write_bytes(png_data)

    # Setup plans directory
    plans_dir = Path("plans")
    plans_dir.mkdir(exist_ok=True)

    # This will now complete successfully (no hang!)
    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_orchestrator",
        input_data={},
        cli_model="anthropic:claude-haiku-4-5",
        approval_callback=approve_all_callback,
    )

    # Verify it completed
    assert result is not None

    # Verify a plan was written (orchestrator's job is to process images and create plans)
    written_files = list(plans_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one plan file"
