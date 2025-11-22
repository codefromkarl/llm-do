# Worker Delegation: Design and Motivation

This document explains how workers call other workers in `llm-do`, why this matters, and how the `worker_call` and `worker_create` tools enable recursive, composable workflows.

## Programmer vs LLM Perspective

- **Programmers** work with `WorkerDefinition` YAML files and the Python runtime. Their mental model is "workers are executable units that can safely call other workers" with:
  - Worker allowlists to restrict which workers can be called
  - Attachment validation (count, size, suffix) enforced before execution
  - Sandboxed file access for security
  - Structured outputs via `output_schema_ref`
  - Model inheritance chain: worker definition → caller → CLI
  - Tool approval system for gated operations

- **LLMs** see tools like `worker_call` and `worker_create` that mean "delegate to another worker" and "create a new specialized worker." The model chooses which worker to call, provides input data and attachments, and receives structured or freeform results. The callee's instructions, model, and tools are defined in its worker definition; the caller only passes arguments.

## What Worker Delegation Does

Worker delegation lets one worker invoke another worker with controlled inputs. It provides:

- **Worker allowlisting:** Only approved workers can be called (via `allow_workers` list in the worker definition)
- **Attachment validation:** File count, size, and suffix restrictions enforced before passing to the worker
- **Sandboxed file access:** Workers read/write files only within configured sandboxes, with path escape prevention
- **Structured outputs:** Workers can declare `output_schema_ref` for validated JSON responses
- **Model inheritance:** Callee inherits caller's effective model if it doesn't declare its own
- **Tool approval system:** Pre-approved tools execute automatically; approval-required tools (writes, worker creation) gate through user approval
- **Autonomous worker creation:** Workers can create specialized sub-workers subject to approval controls

Example worker definition:

```yaml
# workers/orchestrator.yaml
name: orchestrator
description: Orchestrates multi-step pitch deck evaluation
instructions: |
  You coordinate pitch deck evaluations. First list PDFs in the input sandbox,
  then process each one using the locked evaluator worker.
  Write results to the output sandbox.

model: claude-sonnet-4
allow_workers:
  - evaluator  # Only allow calling the evaluator worker

sandboxes:
  input:
    path: ./pipeline
    mode: ro
    allowed_suffixes: [".pdf", ".txt"]
    max_bytes: 15000000
  output:
    path: ./evaluations
    mode: rw

tool_rules:
  - name: sandbox.write
    allowed: true
    approval_required: true  # Writes require approval
  - name: worker.call
    allowed: true
    approval_required: false  # Pre-approved for allowed workers
```

Programmer-facing API (in Python code or toolboxes):

```python
from llm_do.pydanticai import call_worker

result = call_worker(
    worker_name="evaluator",
    input_data={"rubric": "Evaluate this pitch deck thoroughly"},
    attachments=["input/deck.pdf"],
    model="claude-sonnet-4",  # Optional override
    registry=worker_registry,
    approval_callback=approve_all_callback,
)
```

LLM-facing tool surface (exposed to agents):

```python
# Conceptual view of the tool the LLM sees
@agent.tool
def worker_call(
    worker_name: str,
    input_data: dict | str,
    attachments: list[str] | None = None,
) -> WorkerRunResult:
    """
    Call another registered worker to delegate a subtask.

    The worker will process the input with its own instructions and tools.
    Results may be structured JSON or freeform text depending on the worker's
    output_schema_ref configuration.
    """
```

This enforces allowlists, file validation, sandbox security, and approval rules. Workers can be locked (prevent overwrites) to ensure orchestrators always use vetted definitions.

**Attachment resolution.** When a worker passes `attachments` to `worker_call`, each entry must reference one of the caller's sandboxes (for example `attachments=["input/deck.pdf"]`). The runtime resolves the path inside that sandbox, blocks escape attempts, and re-applies the caller's `attachment_policy` (count, total bytes, suffix allow/deny) before forwarding the files to the callee. This keeps delegated attachments confined to data the caller already has permission to touch.

### Model Selection

Worker delegation resolves the model using this chain:

1. The callee's `model` field in its worker definition
2. The caller's effective model (inherited from its caller or CLI)
3. The CLI `--model` flag
4. Error if none specified

**Important:** This creates a natural inheritance chain. If you run `llm-do orchestrator --model claude-sonnet-4`, the orchestrator uses `claude-sonnet-4`. Any workers it calls without their own `model` field will also use `claude-sonnet-4` (inherited from the orchestrator).

### Tool Approval System

Each worker configures which tools require approval via `tool_rules`:

```yaml
tool_rules:
  - name: sandbox.read
    allowed: true
    approval_required: false  # Reads are pre-approved

  - name: sandbox.write
    allowed: true
    approval_required: true  # Writes require user approval

  - name: worker.call
    allowed: true
    approval_required: false  # Delegation pre-approved (if in allowlist)

  - name: worker.create
    allowed: true
    approval_required: true  # Creating workers requires approval
```

When a tool with `approval_required: true` is called, the runtime gates it through an approval callback. The user sees:
- Which tool is being invoked
- The full arguments
- Context about why

They can then approve, reject, or modify before execution. Session approvals remember approvals for identical calls during the same run.

When `worker_call` sends attachments, the approval payload includes each sandbox-relative path and file size so the operator understands exactly which files will be shared with the delegated worker.

## Why Recursion Matters

When workers can call other workers naturally, the system becomes recursively composable. This is useful because:

1. **Composability:** Common patterns like "choose files → process files" or "triage → escalate" become reusable building blocks instead of bespoke scripts.
2. **Uniformity:** Sub-calls inherit the same auditing, logging, and security guarantees as top-level invocations.
3. **Programmer ergonomics:** Clean recursion is easier to reason about than ad-hoc orchestration glue. You can build workflows that feel like composing functions.
4. **Autonomous decomposition:** Workers can identify when they need specialized sub-workers and create them via `worker_create`, subject to approval.

This isn't just theoretical—it matters in practice. When your orchestrator needs to handle edge cases (retry logic, partial failures, dynamic worker selection), having a consistent primitive for "call another worker" makes those extensions straightforward.

## The Two-Step Pattern in Practice

Here's how worker delegation fits into a pitch deck evaluation workflow:

```yaml
# workers/orchestrator.yaml
name: orchestrator
instructions: |
  You orchestrate pitch deck evaluations. Follow these steps:

  1. Use sandbox_list("input", "*.pdf") to find all PDFs
  2. For each PDF (up to max_decks):
     - Call worker_call("evaluator", input with rubric context, [pdf_path])
     - The evaluator returns structured JSON with scores and analysis
  3. Use sandbox_write_text("output", filename, formatted_report) to save results

allow_workers:
  - evaluator  # Lock to vetted evaluator only

sandboxes:
  input:
    path: ./pipeline
    mode: ro
    allowed_suffixes: [".pdf"]
    max_bytes: 15000000
  output:
    path: ./evaluations
    mode: rw

tool_rules:
  - name: sandbox.read
    allowed: true
    approval_required: false
  - name: sandbox.write
    allowed: true
    approval_required: true
  - name: worker.call
    allowed: true
    approval_required: false
```

The locked `evaluator` worker:

```yaml
# workers/evaluator.yaml
name: evaluator
description: Evaluates a single pitch deck against a rubric
instructions: |
  Evaluate the attached pitch deck PDF thoroughly.
  Return structured scores for: team, market, product, traction, financials.
  Include overall summary and any red flags.

model: claude-opus-4
output_schema_ref: EvaluationResult  # Enforces structured JSON output

attachment_policy:
  max_count: 1
  max_bytes: 15000000
  allowed_suffixes: [".pdf"]

tool_rules:
  - name: sandbox.read
    allowed: false  # Evaluator only works with attachments
  - name: sandbox.write
    allowed: false  # Evaluator doesn't write files
  - name: worker.call
    allowed: false  # Evaluator doesn't delegate further
```

The evaluator expects exactly one PDF, returns structured JSON, and doesn't need to know about directory traversal or file selection. The orchestrator handles selection; the evaluator handles analysis. Clean separation.

## Benefits

- **Tight context:** Each sub-call is scoped to a single unit of work (one file, one task) rather than batching everything into a bloated prompt.
- **Guardrails by construction:** File size caps, suffix restrictions, path escapes, and worker locks are enforced in code, not by hoping the LLM respects instructions.
- **Reproducibility:** Sub-calls are explicit, loggable, and re-runnable. You can audit exactly which worker processed which files with which parameters.
- **Iteration speed:** Refining the evaluator worker doesn't require touching the orchestrator. They evolve independently.
- **Security by default:** Sandboxes prevent path traversal, attachment policies prevent resource exhaustion, tool approval prevents unintended side effects.

## When to Use Worker Delegation

Reach for worker delegation when:

- You need LLM-mediated selection followed by guarded execution
- You want to decompose complex workflows into focused subtasks
- You're hardening a workflow: keep orchestration in workers, migrate deterministic logic to Python tools, lock sub-workers as they stabilize
- You want workers to autonomously create specialized sub-workers when they identify the need

For simpler tasks (single-file operations, no selection step, no multi-stage processing), you probably don't need delegation. Just use a single worker.

## Comparison to Other Approaches

**Hard-coding in Python:**
Fine for production workflows with stable requirements, but slow to iterate. Every change requires editing code, running tests, redeploying.

**Single mega-worker:**
Works for simple cases but doesn't scale. Context bloats, instructions drift, guardrails become suggestions rather than enforced constraints.

**Shell scripts calling `llm-do` CLI:**
Closer to what worker delegation does, but harder to audit, no built-in attachment validation, and mixing shell logic with worker logic gets messy fast.

**Worker delegation** sits in between: flexible enough for iteration, structured enough for safety, and composable enough to build complex workflows without custom code.

## Autonomous Worker Creation

Workers can create specialized sub-workers when they identify the need:

```python
# Conceptual view of the tool the LLM sees
@agent.tool
def worker_create(
    name: str,
    instructions: str,
    description: str,
    output_schema_ref: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Create a new worker definition with specialized instructions.

    The worker will be saved to the registry with safe defaults (minimal
    permissions, no sandboxes, no tool access). Subject to user approval.
    """
```

This enables autonomous task decomposition:

1. Orchestrator identifies need for specialized subtask
2. Calls `worker_create(...)` with appropriate instructions
3. User reviews proposed definition (sees full YAML)
4. User can approve, edit, or reject
5. If approved, worker is immediately available for use

The created worker inherits `WorkerCreationDefaults` from the runtime:
- Default sandboxes (if any)
- Default tool rules (safe defaults: reads pre-approved, writes approval-required)
- Default attachment policy
- Always starts with `locked: false`

This supports the **progressive hardening workflow**:
1. Worker autonomously creates sub-worker
2. User reviews and approves
3. Run tasks, observe behavior
4. Edit saved definition to refine
5. Lock when stable
6. Extract deterministic logic to Python tools

## Example Workflow: Pitch Deck Evaluation

The `examples/pitchdeck_eval` directory demonstrates this pattern. The orchestrator:

1. Lists PDFs in `pipeline/` sandbox using `sandbox_list("input", "*.pdf")`
2. Chooses which ones to evaluate (based on the task input)
3. Calls the `evaluator` worker once per PDF via `worker_call`, passing:
   - The rubric as input data
   - The PDF path as an attachment
4. Receives structured JSON back (scores, summary, red flags)
5. Formats the results as Markdown
6. Writes to `evaluations/` sandbox using `sandbox_write_text("output", ...)`

Each PDF gets its own isolated worker invocation with tightly scoped inputs. If the evaluator needs refinement, you edit its definition once and all subsequent runs use the updated version. The orchestrator doesn't change.

Run it like this:

```bash
cd examples/pitchdeck_eval
llm-do workers/orchestrator.yaml \
  --input '{"instruction": "evaluate every deck using the standard rubric"}' \
  --model claude-sonnet-4

# Worker file path is used, registry defaults to CWD (examples/pitchdeck_eval)
# Workers will be loaded from ./workers/ relative to CWD
```

## Implementation Notes

Worker delegation is implemented in `llm_do/pydanticai/base.py`. Key details:

- **WorkerRegistry** manages loading/saving worker definitions from filesystem
- **SandboxManager** handles path resolution, escape prevention, and file validation
- **ApprovalController** manages tool approval rules and user callbacks
- **call_worker()** orchestrates the full delegation lifecycle:
  1. Load callee definition from registry
  2. Validate attachments against policy
  3. Compute effective model (callee → caller → CLI)
  4. Create WorkerContext with sandboxes and approval controller
  5. Build PydanticAI agent with tools
  6. Execute and return WorkerRunResult

- **create_worker()** handles autonomous worker creation:
  1. Takes minimal WorkerSpec (name, instructions, description, schema, model)
  2. Applies WorkerCreationDefaults to expand to full WorkerDefinition
  3. Saves to registry (respects locked flag)
  4. Subject to approval via "worker.create" tool rule

From the LLM's point of view, all of this is exposed as `worker_call` and `worker_create` tools. The model only decides which worker to invoke, what input to send, which files to attach, and (for creation) what instructions the new worker should have.

## Future Directions

Possible enhancements:

- **Streaming support:** For long-running sub-calls, stream intermediate results
- **Retry logic:** Built-in retry with exponential backoff for transient failures
- **Cost tracking:** Log token usage per sub-call for budget analysis
- **Worker composition:** Allow workers to import/extend other workers (beyond just calling them)
- **Template support:** Jinja2 templates for dynamic worker instructions

These aren't priorities yet—better to keep the initial design simple and see what usage patterns emerge.

## Summary

Worker delegation solves a specific problem: you need recursive LLM calls, but you want to keep orchestration logic in worker definitions rather than hard-coding it in Python. It provides a clean, recursive primitive that makes multi-step workflows composable, auditable, and safe.

For the two-step "choose → then act" pattern, it's a natural fit. For more complex workflows (multi-stage pipelines, conditional branching, parallel execution, autonomous decomposition), worker delegation with creation capabilities provides the foundation.

The key insight: **workers calling workers should feel like function calls, not template loading gymnastics.** By making workers first-class executables with built-in delegation and creation primitives, complex workflows become composable building blocks.
