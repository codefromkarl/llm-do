# llm-do Rewrite Specification

## Purpose
This document captures the behavior of the current `llm-do` plugin (built on the `llm` library) and defines the minimum feature set we need to preserve when rebuilding the idea on a different base library (e.g., PydanticAI). It focuses on orchestration, sandboxed file access, and guarded template-to-template calls, with a bias toward simple, inspectable security defaults.

## Current Architecture (llm-based)
- **Plugin registration**: `llm_do.plugin.register_tools` exposes three toolboxes to the `llm` runtime: `Files`, `TemplateCall`, and `TemplateHelpers`. Templates reference them by class name in YAML `tools:` entries and llm instantiates them per run.
- **Templates as the primary interface**: YAML templates provide `system`/`prompt` strings, `schema_object` for structured outputs, and optional `tools` lists. Templates can also embed fragments and system fragments. Template evaluation renders prompt/system text and binds params before execution.
- **Model resolution**: Sub-calls use the target template’s `model` if present; otherwise they fall back to `llm.get_default_model()`. Parent `-m` flags do not propagate into sub-calls.
- **Tool surface seen by LLMs**: Only the functions returned by each toolbox’s `tools()` method are visible to the model. Inline `functions:` blocks inside YAML are intentionally ignored for safety.

## Files Toolbox Behavior
- **Sandbox construction**: `Files(config)` accepts `"<mode>:<path>"` or a dict. Mode is `ro` (read-only) or `out` (writable). Paths are expanded, created when writable, and must be directories.
- **Path enforcement**: All file paths are resolved against the sandbox root; attempts to escape (`..` or absolute paths) raise immediately. Read-only sandboxes reject writes.
- **Operations**:
  - `Files_<alias>_list(pattern="**/*")` lists files relative to the sandbox.
  - `Files_<alias>_read_text(path, max_chars=200_000)` reads UTF-8 text with a size cap.
  - `Files_<alias>_write_text(path, content)` writes text (writable sandboxes only).
- **Instance-specific naming**: Each instance prefixes its tools with a slugified alias to avoid collisions when multiple sandboxes are exposed.

## TemplateCall / llm_worker_call Behavior
- **Purpose**: Allow one template to call another with controlled inputs and strict validation of attachments and template paths.
- **Configuration (per toolbox instance)**:
  - `allow_templates`: glob allowlist (supports `pkg:` package templates and absolute paths)
  - `lock_template`: optional forced template path that overrides the caller’s argument
  - `allowed_suffixes`: lowercased file suffix allowlist for attachments
  - `max_attachments`: count cap
  - `max_bytes`: total attachment size cap
  - `debug`: can be set explicitly or via `LLM_DO_DEBUG=1` for verbose stderr logging
- **Call flow (`run`)**:
  1. Resolve the template name (respecting `lock_template`) and check it against the allowlist; error otherwise.
  2. Load the template from disk or package resources; fail if missing. Inline `functions:` are ignored; tools listed in YAML are resolved from registered toolboxes.
  3. Evaluate the template with provided `input` and `params`; fail fast on missing variables.
  4. Build fragment lists (template fragments + caller-supplied `fragments`).
  5. Validate attachments: must exist, obey suffix allowlist, not exceed `max_attachments` or `max_bytes`; converted to `llm.Attachment` objects.
  6. Resolve the model (template’s `model` or global default) and execute `model.prompt` with prompt/system text, fragments, system fragments, schema, attachments, and tools. Streaming is off.
  7. If `expect_json=True`, require the template to define `schema_object` and JSON-decode the response; otherwise return raw text. Debug mode echoes call/response metadata and tool traces.
- **LLM-facing alias**: `llm_worker_call` maps `worker_name` → `template`, `extra_context` → `fragments`, and passes through `attachments`, `params`, and `expect_json`, exposing a single tool entry to prompts.

## Example Workflow (Pitch Deck Evaluation)
- **Orchestrator template** (`examples/pitchdeck_eval/templates/pitchdeck-orchestrator.yaml`):
  - Exposes two sandboxes: `pipeline` (read-only PDFs and procedure) and `evaluations` (writable outputs).
  - Enumerates PDFs via `Files_pipeline_ro_list`, reads `PROCEDURE.md` if present, then calls the locked single-deck worker once per PDF via `llm_worker_call` with the PDF attached and procedure as extra context.
  - Converts the worker’s JSON into Markdown and writes `<slug>.md` reports into `evaluations/`.
- **Worker template** (`examples/pitchdeck_eval/templates/pitchdeck-single.yaml`):
  - Evaluates one pitch deck. Requires an attached PDF and optional procedure fragment. Emits JSON with `deck_id`, `file_slug`, `summary`, scored dimensions, verdict, and optional red flags (max 3), validated by `schema_object`.

## Requirements for a Rewrite on PydanticAI (or similar)
- **Template/story layer**:
  - Replace `llm` templates with an equivalent prompt/schema mechanism (system + user text, parameter substitution, optional fragments/system fragments).
  - Support per-template model selection with fallback to a global default; avoid implicit inheritance from callers.
- **Toolbox abstraction**:
  - Provide sandboxed file operations with alias-based namespacing, path escape prevention, read-only/write modes, and read size caps.
  - Expose a single public tool for delegated calls (analogous to `llm_worker_call`) that enforces template allowlists/locks, attachment validation, and optional JSON parsing against declared schemas.
  - Ignore or disallow inline code inside template definitions; only registered tool classes/functions should be invokable.
- **Attachment and fragment handling**:
  - Enforce suffix allowlist, attachment count, and cumulative size limits before dispatching to the model.
  - Allow caller-provided fragments/extra context plus template-defined fragments; include them separately from the main prompt text.
- **Execution semantics**:
  - Non-streaming call by default; return text or validated JSON. Provide debug logging toggled by config/env for visibility into model name, attachments, fragments, and tool calls.
  - Ensure deterministic resolution of allowed templates whether loaded from package resources or filesystem paths.
- **Basic security posture (minimum viable)**:
  - Sandbox all file IO with mandatory root directories and escape checks.
  - Attachment validation caps (count/size/suffix) plus explicit template allowlists/locks.
  - Reject JSON mode unless a schema is present; validate/parse responses.
  - Avoid executing arbitrary inline code; only pre-registered tools should run.

## Non-goals for the first rewrite iteration
- Streaming responses, retries/backoff, cost tracking, or advanced template composition are nice-to-haves but not required for parity with the current minimal feature set.
