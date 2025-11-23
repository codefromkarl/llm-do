# Worker Tool Interface Plan

## Goal
Expose registered workers as first-class tools so the LLM can call them directly without relying on the generic `worker_call` instruction. This keeps the tool schema self-descriptive—"call `pitch_evaluator`" looks like any other tool call, and the worker description becomes the tool docstring.

## Proposed Flow
1. **Discovery.** When a worker starts, inspect its `allow_workers` list. For each allowed worker, load its definition (or a stub) from the registry.
2. **Tool registration.** Dynamically register a tool named after the worker (e.g., `pitch_evaluator`). The tool metadata pulls from the worker description/instructions summary so the LLM sees the intent directly.
3. **Invocation.** The tool implementation simply wraps today’s `call_worker`, but hides `worker_call` from the LLM. It should accept:
   - `input_data`: structured payload (defaulting to `{}` if omitted)
   - `attachments`: list of `sandbox/path` strings. The runtime resolves these relative to the caller’s sandboxes, re-validates with the caller’s attachment policy, and attaches files to the child worker request.
4. **Execution & logging.** The wrapper forwards CLI approval metadata so the logs still show the callee worker name (now identical to the tool name). Streaming callbacks remain unchanged.

## Attachment Handling
- Keep attachments as strings in the tool schema (e.g., `attachments: list[str]`).
- At call time, convert each entry to `sandbox/relative` format, resolve into `AttachmentPayload`, enforce the caller policy, and send along to the child worker just like today’s `worker_call`.
- Report validation errors via the tool result so the LLM sees “attachment not allowed”.

## Dynamic Tool Lifecycle
- Tools must be registered per run because `allow_workers` differs by worker.
- When a worker is locked down (`allow_workers=[]`), no additional tools are added—the schema stays minimal.
- We should surface the allowed worker list somewhere in the CLI output (e.g., “exposed tools: pitch_evaluator”) so operators see what the agent can call.

## Interaction with `create_worker`
Dynamic workers created via `worker_create` won’t automatically appear in the tool schema because:
1. They are unknown at session start, so they can’t be part of the static tool list presented to the LLM.
2. Without schema updates, the LLM can’t call them via the new mechanism even if creation succeeds.

Options to address this:
- **Hybrid approach (recommended):** keep the existing `worker_call` tool as a fallback. When the LLM creates a worker mid-run, it can still call it via `worker_call("new_worker", ...)` even though it lacks a dedicated tool. For pre-defined workers the nicer per-worker tool is available.
- **Dynamic schema updates:** in theory we could re-register tools mid-run after `create_worker`, but PydanticAI tooling would have to support live tool injection and communicate schema updates back to the model. That’s more complex and may confuse current LLM APIs.

Document this limitation so prompt authors know: *pre-existing workers get first-class tools; ad-hoc workers still require `worker_call`.*

## Implementation Steps
1. Extend `WorkerContext` to track allowed workers + their definitions.
2. During agent setup (`_default_agent_runner`), register extra tools for each allowed worker. Each tool wraps `call_worker` with attachment resolution.
3. Update approval logging so calls show up as `pitch_evaluator` instead of the generic `worker.call` when they go through the new wrapper.
4. Keep `worker_call` tool available for backward compatibility and for dynamic workers.
5. Update docs/examples to remove explicit `worker_call` instructions where not needed.
6. Add regression tests that: 
   - confirm tools are registered for allowed workers,
   - exercise attachment resolution via the new tool,
   - ensure dynamic workers still work through `worker_call`.

## Open Questions
- Should the per-worker tool accept arbitrary keyword args to support future structured inputs? (Probably start with `input_data: dict | str` and `attachments: list[str]`.)
- How to summarize worker instructions concisely for tool docs without exceeding token limits? Maybe reuse `description` or add a short `tool_summary` field.
- Need to ensure tool names remain valid Python identifiers for PydanticAI; consider auto-normalizing (e.g., replace `-` with `_`).

## Risks
- **Instruction drift:** newly registered tools might give the model too many options and dilute focus. Mitigation: only register workers explicitly listed in `allow_workers`.
- **Attachment confusion:** LLM must remember to pass `attachments=["input/file"]`. Provide clear docstrings + example usage in worker instructions.
- **Backward compatibility:** ensure existing workflows using `worker_call` keep working until prompts are updated.

## Next Steps
1. Prototype per-worker tool registration in a feature branch.
2. Verify `pitch_orchestrator` can delegate without mentioning `worker_call`.
3. Update docs to teach authors how to rely on the new tooling and when to fall back to `worker_call` for dynamically created workers.
