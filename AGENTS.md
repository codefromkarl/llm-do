# AGENTS.md — Simplicity-First Field Guide

This document complements the top-level `README.md`. Treat the README as the source for setup, installation, and usage details; the guidance below captures the expectations that frequently trip up automation agents.

---

## 1. Key References

- `README.md` — project overview, installation, toolbox descriptions, example workflows
- `docs/templatecall.md` — TemplateCall design, motivation, and patterns
- `TODO.md` — upstream discussion topics for the llm library
- `llm_do/templates/` — template files (generic-orchestrator.yaml, etc.)
- `examples/pitchdeck_eval/` — working example of the two-step orchestration pattern

Keep these open when working; this file intentionally avoids duplicating the same information.

---

## 2. Daily Development Loop

- Practice TDD: update or add tests first, then code. Run the narrowest test you can (`pytest -k test_specific_feature`).
- Before committing, run the full suite once via `pytest`. The full run completes quickly and catches integration issues.
- Always invoke the test runner via the project environment: use `.venv/bin/pytest` or just `pytest` if the venv is active.
- Tests live under `tests/` and use fixtures from `tests/conftest.py`. They should use mock models (see `DummyModel` in conftest) and avoid real LLM API calls.
- When modifying toolboxes (Files, TemplateCall, TemplateHelpers), add corresponding tests in `tests/test_*_tool.py`.
- After changing templates, manually test them with `llm -t <template>` to ensure they work end-to-end.

---

## 3. Coding Standards & Error Handling

- Style: black (default), 4 spaces, UTF-8. Keep changes minimal—avoid drive-by formatting in logic commits.
- Use descriptive snake_case names for functions/modules and PascalCase for classes.
- Error handling: raise specific exceptions (`ValueError`, `FileNotFoundError`, etc.) with clear messages. Tests should assert exception types and key message content.
- Toolbox methods should fail fast when given invalid inputs (bad paths, missing templates, oversized attachments).
- Maintain test determinism: use mock models with predictable outputs, avoid relying on external state.

---

## 4. Refactoring & Simplification

When refactoring, prioritize simplicity:
- **Start with working tests:** Ensure existing tests pass before refactoring.
- **Keep the contract:** Public toolbox APIs (method names, required parameters) should remain stable unless there's a strong reason to break them.
- **Delete over preserve:** If code isn't used or tested, remove it rather than maintaining it "just in case."
- **Simplify prompts:** Template prompts should be concise and trust the LLM to figure out details. Remove prescriptive step-by-step instructions when possible.
- **Extract complexity:** When templates accumulate inline functions, consider moving them to proper toolboxes (like we did with `make_template` → `TemplateHelpers`).

---

## 5. Template Design Principles

- **Start simple:** New templates should have minimal system prompts and trust the LLM's capabilities.
- **Use toolboxes:** Prefer calling toolbox methods over inline functions. Inline functions should only be used for truly template-specific logic.
- **Clear tool descriptions:** List available tools in the system prompt with brief descriptions of what they do.
- **Avoid over-specification:** Don't tell the LLM exactly what function to call in what order unless necessary. Give it goals and let it figure out the implementation.
- **Test with real models:** Mock tests are great for unit testing, but manually run templates with real models (haiku is cheap) to verify end-to-end behavior.

---

## 6. Operational Guardrails

- **Commits:** Do not mix logic with formatting. Stage intentional files only—never use `git add -A` without reviewing first.
- **Security & data:** Never commit API keys or secrets. Use environment variables (`ANTHROPIC_API_KEY`, etc.). Example outputs under `examples/` can be committed if they're useful for documentation.
- **Git discipline:**
  - Review `git status` and `git diff` before staging
  - Write clear commit messages explaining "why" not just "what"
  - Use the Co-Authored-By trailer when AI assists with commits
- **Debug mode:** Use `LLM_DO_DEBUG=1` environment variable to enable debug output for TemplateCall when troubleshooting.
- **TODO tracking:** Use `TODO.md` for cross-project issues (like upstream discussions). Use inline `# TODO:` comments for code-level issues.

---

## 7. Common Pitfalls for AI Agents

**File operations:**
- Never use `git add -A` or `git add .` — always review and stage specific files
- Check `git status` and `git diff` before committing
- Don't commit generated test outputs unless they're intentional examples

**Template editing:**
- When the LLM suggests calling `Files_workspace_ro_write_text`, remind it that only `Files_workspace_out_write_text` exists for writing
- Template files must end in `.yaml` to pass TemplateCall's allowlist
- Use `TemplateHelpers_make_template()` rather than having the LLM generate full YAML templates

**Testing:**
- Don't skip test runs when changing toolbox code
- Use mock models in tests, not real API calls
- Ensure tests check behavior, not just that code runs without errors

**Documentation:**
- Keep README.md and docs/ in sync with code changes
- When toolbox APIs change, update the README examples
- Add docstrings to new toolbox methods

---

Stay small, stay testable, and trust the LLM to figure out reasonable implementations when given clear goals.
