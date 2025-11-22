# Architecture Review (LLM-DO)

This document captures a high-level architectural map and design improvement proposals based on the current PydanticAI-based runtime.

## Conceptual Overview
- Workers are YAML-defined artifacts (prompt + config + sandboxes + tool rules) executed via a registry-backed runtime.
- `run_worker` builds a `WorkerContext` (registry, sandboxes, approvals, callbacks) and delegates execution to an `AgentRunner` (default: PydanticAI `Agent`).
- Tools exposed to the model include sandbox file helpers, `worker_call`, and `worker_create`, all gated by `ApprovalController`.
- The CLI layers input parsing, approval-mode selection, and rich streaming display over the runtime; callbacks feed streaming events back to the CLI renderer.
- Sandboxes and attachment policies enforce filesystem safety for both user-provided attachments and model-initiated writes.

## Module Map
- `llm_do/pydanticai/base.py`: worker artifacts, registry, approval controller, worker context, tool registration, delegation/creation, and the default agent runner.
- `llm_do/pydanticai/sandbox/`: sandbox configs, enforcement, and approval-aware file helpers.
- `llm_do/pydanticai/cli.py`: CLI front-end, approval prompt UI, streaming event display, and argument parsing.
- `docs/worker_delegation.md` and `docs/design/cli_approval_user_stories.md`: describe delegation rules and desired approval UX.

## Execution Flow (CLI → Worker → Callbacks)
1. CLI parses args, loads the worker definition from the registry root (default CWD), and resolves input data/attachments.
2. CLI chooses approval behavior (`--approve-all`, `--strict`, or interactive) and builds a streaming callback (rich panels) unless JSON mode is requested.
3. `run_worker` constructs sandboxes, approval controller, and a `WorkerContext` with the chosen callbacks; `AgentRunner` receives the context.
4. The default runner builds a PydanticAI `Agent`, registers tools, formats attachments as `BinaryContent`, and (optionally) wires `event_stream_handler` that forwards raw events to the message callback.
5. As the agent streams events (tool calls/results, text parts), the callback prints them; approval-gated tools invoke `ApprovalController.maybe_run`, which routes through the selected approval callback before executing underlying operations.
6. Worker-to-worker delegation (`worker_call`) re-enters `run_worker` with inherited model/defaults and passes along the message callback, preserving streaming display.

## Key Design Issues (SOLID + smells)
1. **Mixed concerns in `base.py`** – Worker models, registry I/O, approval logic, sandbox tool registration, and default agent runner live in one module, reducing cohesion (SRP) and making substitutions harder. (S)【F:llm_do/pydanticai/base.py†L40-L155】【F:llm_do/pydanticai/base.py†L427-L520】
2. **Implicit callback contracts** – `ApprovalCallback` and `MessageCallback` are bare callables with positional parameters; workers assume CLI-style side effects (printing/input), hindering alternative UIs or automated runners (D/I).【F:llm_do/pydanticai/base.py†L113-L148】【F:llm_do/pydanticai/base.py†L427-L440】
3. **Approval gating limited to tool rules** – `ApprovalController` only wraps tool invocations; sandbox writes and worker creation share the same controller but lack structured context (request IDs, worker stack), constraining richer policies or auditing (O/D).【F:llm_do/pydanticai/base.py†L400-L419】【F:llm_do/pydanticai/base.py†L519-L566】
4. **Streaming callback payloads are loosely typed** – CLI expects a list of `dict` or events; delegation reuses the same callback without metadata about call depth or lifecycle, making nested runs hard to render or test (L/I).【F:llm_do/pydanticai/base.py†L618-L652】【F:llm_do/pydanticai/cli.py†L260-L322】
5. **Tight CLI coupling for approvals** – Non-interactive mode is enforced in the CLI; the runtime defaults to auto-approve and doesn’t expose a headless approval policy or context object, so non-CLI hosts must reimplement approval selection (D/S).【F:llm_do/pydanticai/cli.py†L443-L473】【F:llm_do/pydanticai/base.py†L705-L752】
6. **Registry mixes discovery and template rendering** – Loading renders Jinja and mutates the definition dict before validation; prompt discovery logic is embedded in registry load, complicating alternate storage backends or caching (S/O).【F:llm_do/pydanticai/base.py†L172-L241】
7. **Agent runner signature is monolithic** – `AgentRunner` accepts the whole `WorkerContext` and raw definitions; swapping model backends or injecting tracing requires touching core runtime rather than small interfaces (O/D).【F:llm_do/pydanticai/base.py†L443-L520】【F:llm_do/pydanticai/base.py†L705-L752】
8. **Limited test seams for callbacks** – Approval and streaming callbacks aren’t protocolized, and `run_worker` wires them directly, making unit tests rely on side-effect functions rather than fakes (Testability).【F:llm_do/pydanticai/base.py†L705-L752】

## Ranked Improvement Proposals
1. **Introduce typed callback protocols and context objects** (Impact 5 / Effort 3 — Quick win)
   - Define `ApprovalHandler` and `EventSink` protocols carrying worker name, call_id, and payloads; pass a `RunCallbacks` object through `WorkerContext`.
   - Adapt CLI to implement these protocols; keep backwards-compatible adapters for existing callables.
   - Benefits: dependency inversion, better test seams, easier alternative UIs.

2. **Separate runtime layers into focused modules** (Impact 4 / Effort 3 — High-leverage refactor)
   - Split `base.py` into `artifacts.py` (models/registry), `runtime.py` (run_worker/AgentRunner), and `tools.py` (tool registration + approval wiring).
   - Improves SRP and future extension (e.g., alternate registries or agent runners) without touching unrelated code.

3. **Make approvals policy-driven and contextual** (Impact 4 / Effort 3 — High-leverage refactor)
   - Extend `ApprovalController.maybe_run` to accept `RequestContext` (worker stack, tool type, attachments summary) and return structured decisions including audit IDs.
   - Implement reusable policies: auto, strict, interactive CLI, and “deny writes on non-TTY,” selectable in `run_worker` arguments (not only CLI flags).

4. **Structure streaming events with envelopes** (Impact 3 / Effort 2 — Quick win)
   - Emit `WorkerEvent` dataclass `{worker, call_id, kind, payload}` instead of raw dicts; propagate through delegation so nesting is visible.
   - CLI renderer maps event kinds to panels; tests can assert on event sequences without Rich.

5. **Decouple prompt discovery/rendering from registry** (Impact 3 / Effort 3 — Medium refactor)
   - Move prompt loading/rendering behind a `PromptLoader` injected into `WorkerRegistry`; support cached/remote stores and explicit inline vs. file-based prompts.
   - Keeps registry persistence focused on YAML I/O and validation.

6. **Refine AgentRunner boundary** (Impact 2 / Effort 2 — Cleanup)
   - Wrap PydanticAI agent creation in an adapter implementing a small `ModelRunner` protocol; allow swapping in mock/test runners or future backends without editing `run_worker`.

## Testing & Documentation Suggestions
- Add unit tests with fake `ApprovalHandler` and `EventSink` to verify tool gating, session approvals, and nested `worker_call` streaming without Rich/TTY dependencies.
- Provide integration tests for CLI interactive mode using injected input streams and capturing rendered events.
- Expand docs with a “Callback and Approval Layer” page explaining: callback protocols, how approvals are selected (CLI vs. headless), event shapes, and how to plug in alternate UIs.
- Document worker lifecycle separation: artifact loading, runtime execution, and CLI-only behavior (flags, display), highlighting where to extend each layer.
