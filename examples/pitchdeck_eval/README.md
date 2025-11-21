# Pitch deck evaluation (PydanticAI workers)

This example shows how to build a multi-worker workflow with the new `llm-do`
architecture:

- `workers/pitch_orchestrator.yaml` — lists decks, delegates to the evaluator,
  and writes Markdown reports.
- `workers/pitch_evaluator.yaml` — scores a single deck and returns JSON.
- `pipeline/` — drop Markdown (`.md`/`.txt`) versions of pitch decks here. The
  provided `aurora_solar.md` file acts as a sample input, and `PROCEDURE.md`
  contains the rubric shared with every run.
- `evaluations/` — destination for generated reports.

## Prerequisites

```bash
pip install -e .            # from the repo root
export ANTHROPIC_API_KEY=...  # or another model provider supported by PydanticAI
```

Both workers leave the `model` field unset so you can choose one at runtime.
Any Claude, OpenAI, or Gemini model exposed through PydanticAI will work.

## Run the workflow

From the example directory:

```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator \
  --registry workers \
  --model anthropic:claude-sonnet-4-20250514 \
  --pretty
```

What happens:

1. The orchestrator lists `*.md` and `*.txt` files in the `pipeline` sandbox.
2. The rubric in `pipeline/PROCEDURE.md` is read (if present) and sent to every
   evaluator call.
3. Each deck triggers `worker_call(worker="pitch_evaluator", input_data={...})`.
4. The evaluator reads the deck file via `sandbox_read_text`, produces JSON, and
   returns it to the orchestrator.
5. The orchestrator converts the JSON to Markdown and saves it with
   `sandbox_write_text("evaluations", "<slug>.md", content)`.
6. CLI output contains a summary plus the path to the generated reports.

Open `evaluations/` afterwards to inspect the Markdown summaries.

## Customizing

- Add or edit files in `pipeline/` to evaluate different companies. A deck can be
  any Markdown or text file that roughly describes the problem, solution, team,
  traction, and financial model. (Convert PDFs to text before running.)
- Modify `pipeline/PROCEDURE.md` to change the rubric. The orchestrator sends the
  entire file to the evaluator as part of `input_data` so you can adapt the
  schema without touching Python.
- Update the worker YAML definitions to tweak tool policies, change sandboxes, or
  pin specific models.

## Anatomy of the workers

`pitch_orchestrator` demonstrates several primitives from the new runtime:

- Multiple sandboxes (`pipeline` read-only, `evaluations` read/write)
- `worker_call` to delegate to a locked evaluator worker
- `sandbox_write_text` for report generation
- Tight `allow_workers` list so only `pitch_evaluator` can run from this worker

`pitch_evaluator` stays focused on deterministic output formatting: it only reads
from the pipeline sandbox and emits structured JSON. Because both workers inherit
whatever `--model` you pass on the CLI, delegation feels like a normal function
call with shared settings.

## Resetting the example

```bash
rm -f evaluations/*.md
```

Leave `aurora_solar.md` (or add your own decks) in `pipeline/` and rerun the
command above to regenerate reports.
