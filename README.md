# llm-do

**Treat prompts as executables.** Package prompts with configuration (model, tools, schemas, security constraints) to create workers that LLMs interpret.

## Status

🚧 **Active development** — Currently porting to PydanticAI. The architecture described here is being implemented. The old `llm` plugin-based design is being replaced.

## Core Concept

Workers are self-contained executable units: **prompt + config + tools**. Just like source code is packaged with build configs and dependencies to become executable programs, prompts need packaging to become executable workers.

```yaml
# workers/evaluator.yaml
name: evaluator
instructions: |
  Evaluate the attached document using the provided rubric.
  Return structured scores and analysis.
model: gpt-4
output_schema_ref: EvaluationResult
sandboxes:
  input:
    path: ./documents
    mode: ro
  output:
    path: ./evaluations
    mode: rw
```

Run from CLI:
```bash
cd /path/to/project  # Registry defaults to current working directory
llm-do evaluator \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf

# Or specify registry explicitly:
llm-do evaluator \
  --registry ./workers \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf
```

Or call from another worker (recursive delegation):
```python
# Inside a worker's agent runtime
result = call_worker("evaluator", input_data={"rubric": "..."}, attachments=["doc.pdf"])
```

## Why This Matters

### 1. Context Bloat
Large workflows with bloated prompts drift and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**Solution**: Decompose into focused sub-calls. Each worker handles a single unit of work ("evaluate exactly this PDF with this procedure") instead of processing everything at once.

### 2. Recursive Calls Are Hard
Making workers call other workers should feel natural, like function calls. But in most frameworks, templates and tools live in separate worlds.

**Solution**: Workers are first-class executables. Delegation is a core primitive with built-in sandboxing, allowlists, and validation.

### 3. Progressive Hardening
Start with flexible prompts that solve problems. Over time, extract deterministic operations (math, formatting, parsing) from prompts into tested Python code. The prompt stays as orchestration; deterministic operations move to functions.

## Key Capabilities

### Sandboxed File Access
Workers read/write files through configured sandboxes:
- Each sandbox has a root directory and access mode (read-only or writable)
- Path escapes blocked by design
- File size limits prevent resource exhaustion

```python
# In a worker's tools
files = sandbox_list("input", "*.pdf")
content = sandbox_read_text("input", files[0])
sandbox_write_text("output", "result.md", report)
```

### Worker-to-Worker Delegation
Workers invoke other workers with controlled inputs:
- Allowlists restrict which workers can be called
- Attachment validation (count, size, extensions) enforced
- Model inheritance: worker definition → caller → CLI → error
- Results can be structured (validated JSON) or freeform text

See [Worker Delegation](docs/worker_delegation.md) for detailed design and examples.

### Tool Approval System
Control which tools execute automatically vs. require human approval:
- Pre-approved tools (read files, call specific workers) execute automatically
- Approval-required tools (write files, create workers) prompt user
- Configurable per-worker and per-tool

### Autonomous Worker Creation
Workers can create specialized sub-workers when they identify the need:
- Subject to approval controls
- User reviews proposed definition before saving
- Created workers start with minimal permissions
- Saved definitions are immediately executable

## Example: Pitch Deck Evaluation

**Scenario**: Evaluate multiple pitch decks using a shared rubric.

**Orchestrator worker**:
1. Lists PDFs in sandbox
2. For each PDF, calls locked evaluator worker
3. Passes PDF + rubric
4. Gets back structured JSON
5. Writes formatted report

Each PDF gets isolated worker invocation = reproducible results, testable components.

## Progressive Hardening Workflow

1. **Autonomous creation**: Worker creates specialized sub-worker, user approves
2. **Testing**: Run tasks, observe behavior
3. **Iteration**: Edit saved definition—refine prompts, add schemas
4. **Locking**: Pin orchestrators to vetted worker definitions via allowlists
5. **Migration**: Extract deterministic operations to tested Python functions

Workers stay as orchestration layer; Python handles deterministic operations.

## Architecture

```
llm_do/
  pydanticai/
    __init__.py
    base.py              # Core runtime: registry, sandboxes, delegation
    cli.py               # CLI entry point with mock runner support

tests/
  test_pydanticai_base.py
  test_pydanticai_cli.py

docs/
  concept_spec.md           # Detailed design philosophy
  worker_delegation.md      # Worker-to-worker delegation design
  pydanticai_architecture.md
  pydanticai_base_plan.md
```

## Installation

Not yet published to PyPI. Install in development mode:

```bash
pip install -e .
```

Dependencies:
- `pydantic-ai>=0.0.13`
- `pydantic>=2.7`
- `PyYAML`

## Current Status

✅ Implemented:
- Worker artifacts (definition/spec/defaults) with YAML persistence
- WorkerRegistry with file-backed storage
- Sandboxed file access with escape prevention
- Tool approval system with deferred requests
- Model inheritance (definition → caller → CLI)
- Mock runner for deterministic testing
- CLI with mock reply support

🚧 In progress:
- Worker-to-worker delegation tools (call_worker, create_worker not exposed to agents yet)
- Output schema resolution
- Real PydanticAI integration (currently uses mock runners for tests)

## Design Principles

1. **Prompts as executables**: Workers are self-contained units you can run from CLI or invoke from other workers
2. **Workers as artifacts**: Definitions saved to disk, version controlled, auditable, refinable
3. **Security by construction**: Sandbox escapes and resource bombs prevented by design, not instructions
4. **Explicit configuration**: Tool access and allowlists declared in definitions, not inherited
5. **Recursive composability**: Worker calls feel like function calls
6. **Sophisticated approval controls**: Balance autonomy with safety

## Contributing

PRs welcome. See `AGENTS.md` for development guidance.

Key points:
- Run `pytest` before committing
- No backwards compatibility constraints (new project)
- Balance simplicity with good design

## Acknowledgements

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.

Inspired by [Simon Willison's llm library](https://llm.datasette.io/) for the concept of templates as executable units.
