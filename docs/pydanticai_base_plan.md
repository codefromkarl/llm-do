# PydanticAI base implementation plan

This plan outlines the first-pass implementation of a PydanticAI-based architecture for `llm-do`, based on the proposal in `docs/pydanticai_architecture.md`. The goal is to land a minimal but end-to-end runnable slice that exercises registry-driven workers, sandboxed tools, delegation, and approval workflows.

## Objectives for the base version
- Provide an executable `run_worker` pipeline that loads worker definitions, resolves schemas, builds agents, executes with context, and returns structured results.
- Ship foundational worker artifacts (`WorkerDefinition`, `WorkerSpec`, `WorkerCreationProfile`) with YAML/JSON persistence and profile expansion.
- Implement core toolsets (sandboxed filesystem, worker delegation, worker creation) with policy-aware approval wrappers.
- Enforce attachment and locking policies sufficiently to run safely in iterative environments.
- Support progressive hardening by keeping schema resolution and approval hooks extensible.

## Delivery slices and milestones
1. **Artifact and registry groundwork**
   - Define Pydantic models for `WorkerDefinition`, `WorkerSpec`, `WorkerCreationProfile`, `AttachmentPolicy`, `ToolRule`, and `WorkerRunResult`.
   - Implement `WorkerRegistry` to resolve paths, load/save definitions, and look up output schemas via a pluggable resolver.
   - Add YAML/JSON read/write helpers and minimal validation (e.g., locked workers cannot be overwritten without force).

2. **Runtime context and agent assembly**
   - Create `WorkerContext` carrying registry handle, active profiles, sandbox manager, effective model, attachments, and run metadata.
   - Implement `run_worker` that selects the effective model (worker → caller → CLI), resolves the output schema, and instantiates an Agent with worker instructions and toolsets.
   - Return `WorkerRunResult` including output, deferred tool requests, and usage accounting scaffold.

3. **Sandboxed filesystem toolset**
   - Integrate a `SandboxManager` enforcing root scoping, RO/RW modes, suffix and size limits, and total-size accounting.
   - Wrap PydanticAI filesystem helpers (read/write/list) with sandbox path resolution and approval gating for writes.
   - Provide configuration hooks so per-worker rules (from `ToolRule`/profiles) can mark writes as approval-required or disallowed.

4. **Worker delegation toolset**
   - Implement `call_worker(worker, input)` that checks allowlists, inherits the caller’s effective model when the callee is unset, and forwards context history/attachments as allowed.
   - Ensure delegated runs contribute to aggregated usage accounting and return typed results aligned with the callee’s schema.

5. **Worker creation and approval flow**
   - Build `create_worker(spec)` that expands a `WorkerSpec` using the active `WorkerCreationProfile`, defaults model to inherit unless pinned, and persists via the registry.
   - Mark creation and high-risk tools as approval-required by default; implement `ApprovalRequiredToolset` wrapping to produce deferred tool requests.
   - Add resume hooks so hosts can approve and re-run deferred calls with preserved history.

6. **Attachments and locking enforcement**
   - Validate inbound attachments against `AttachmentPolicy` (count, total size, suffix allow/deny) before execution; share validated attachments with delegated workers when permitted.
   - Enforce `locked` semantics: block edits unless explicitly forced and optionally restrict creation/write tools even when approvals exist.

7. **CLI/host integration and examples**
   - Provide a thin CLI entry point around `run_worker`, supporting model selection, history/deferred input, and attachment injection.
   - Add or adapt an example (e.g., pitch deck evaluation) to exercise sandboxed IO, delegation, approvals, and schema validation end-to-end.

## Risk and sequencing notes
- Start with in-memory schema resolution (registry of dotted paths) to avoid import complexity; expand to module discovery once the core pipeline is stable.
- Keep approval/deferred plumbing minimal but compatible with host-provided review UIs; persist deferred requests in `WorkerRunResult`.
- Prioritize deterministic enforcement (sandbox, attachments, locking) before optimizing for ergonomics to avoid rework.
- Use progressive hardening: land the runnable slice first, then add stricter policies and richer validation.
