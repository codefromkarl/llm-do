# Future Work

Consolidated list of future enhancements. These are optional improvements that can be tackled when needed.

---

## OS-Level Sandbox Enforcement

**Source:** sandbox_implementation_plan.md (Phase 7)

Wrap shell commands in OS-level sandbox (Seatbelt on macOS, bubblewrap on Linux).

### Tasks

1. **Create os_sandbox.py module**
   ```python
   def os_sandbox_available() -> bool:
       """Check if OS sandbox is available on this platform."""

   def run_sandboxed(
       args: list[str],
       config: SandboxConfig,
       **kwargs
   ) -> subprocess.CompletedProcess:
       """Run command with OS-level sandbox."""
   ```

2. **Implement macOS Seatbelt**
   - Generate Seatbelt policy string from SandboxConfig
   - Run commands with `sandbox-exec`

3. **Implement Linux bubblewrap**
   - Generate bwrap command prefix from SandboxConfig
   - Run commands with bwrap

4. **Update shell tool to use OS sandbox**
   - If available, wrap commands
   - If unavailable and `require_os_sandbox=True`, raise error
   - If unavailable and `require_os_sandbox=False`, warn and continue

### Notes
- OS sandbox only covers subprocesses, not Python I/O
- Network blocking only works for shell commands
- Each worker uses its own Sandbox instance for application-level validation

---

## Runtime Refactor Continuation (Optional)

**Source:** runtime_refactor_with_di.md

Further reduce `runtime.py` size (currently 540 lines).

### Potential extractions
- Worker lifecycle logic to `lifecycle.py` (~150 lines)
- Context preparation helpers to `context.py` (~80 lines)
- Could reduce `runtime.py` to ~300 lines (70% total reduction)

### Status
The core refactor is complete and architecture is clean. These are nice-to-have.

---

## Per-Worker Tool Interface

**Source:** worker_tool_interface.md

Expose registered workers as first-class tools so the LLM can call them directly without using `worker_call`.

### Benefits
- Tool schema is self-descriptive ("call `pitch_evaluator`" looks like any other tool)
- Worker description becomes the tool docstring

### Implementation Steps
1. During agent setup, register tools for each allowed worker
2. Each tool wraps `call_worker` with attachment resolution
3. Keep `worker_call` for backward compat and dynamic workers

### Limitations
- Workers created mid-run via `worker_create` still need `worker_call`
- Tool names must be valid Python identifiers

---

## Attachment Policy Enforcement for Delegation

**Source:** attachment_policy_plan.md

Propagate attachment policies when a worker calls another worker.

### Requirements
- Resolve attachment paths relative to caller's sandbox
- Reject paths that escape or exceed caller's AttachmentPolicy limits
- Surface attachment metadata in approval prompts
- Allow worker definitions to specify stricter attachment policy for delegated runs

### Implementation
1. Extend `WorkerContext.validate_attachments(paths)`
2. Update `worker_call` to use validation instead of raw `Path.resolve()`
3. Update CLI approval callback to show attachment info

---

## Other Ideas (From worker.md)

- First-class Python object with methods like `.run()` or `.delegate_to()`
- Schema repository for output schema resolution
- Structured policies instead of string-based tool rule naming
- State diagram for worker creation → locking → promotion
