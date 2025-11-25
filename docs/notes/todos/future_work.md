# Future Work

Consolidated list of future enhancements. These are optional improvements that can be tackled when needed.

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

## CLI Configuration Overrides - Phase 2 & 3

**Source:** cli_overrides_design.md

Phase 1 (MVP) is complete with `--set KEY=VALUE` support. Future enhancements:

### Phase 2: Enhanced Overrides

1. **`--override JSON` support** for bulk/complex overrides:
   ```bash
   llm-do worker --override production.json
   llm-do worker --override '{"model": "gpt-4", "sandbox": {...}}'
   ```

2. **List operators** (`+=`, `-=`) for appending/removing from lists:
   ```bash
   llm-do worker --set allow_workers+=new_worker
   llm-do worker --set allow_workers-=old_worker
   ```

3. **Improved error messages** with detailed type mismatch explanations

### Phase 3: Advanced Features

1. **Override profiles** - predefined override sets:
   ```bash
   llm-do worker --profile production
   # Loads ~/.llm-do/profiles/production.json
   ```

2. **Environment variable expansion**:
   ```bash
   --set sandbox.paths.output.root=$OUTPUT_DIR
   ```

3. **Validation mode** - check overrides without running:
   ```bash
   llm-do worker --validate-overrides overrides.json
   ```

4. **Diff/preview mode** - show what changed:
   ```bash
   llm-do worker --show-overrides --set model=gpt-4
   ```

See `docs/design/cli_overrides_design.md` for full design details.

---

## Other Ideas (From worker.md)

- First-class Python object with methods like `.run()` or `.delegate_to()`
- Schema repository for output schema resolution
- Structured policies instead of string-based tool rule naming
- State diagram for worker creation → locking → promotion
