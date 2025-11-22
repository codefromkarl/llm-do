# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, toolboxes, examples
- `docs/templatecall.md` — TemplateCall design
- `examples/pitchdeck_eval/` — working example

---

## Development

- Run full test suite before committing: `pytest`
- Tests use mock models, no real API calls
- After changing templates, test with `llm -t <template>`
- **Testing with real models**: Use `anthropic:claude-haiku-4-5` for fast, cost-effective testing
- Style: black, 4 spaces, snake_case/PascalCase
- **No backwards compatibility** — new project, no external users yet; breaking changes are fine if they improve design
- **Balance simplicity with good design** — aim for clean architecture, but don't over-engineer; delete complexity when possible

---

## Template Design

- Start simple, trust the LLM
- List available tools in system prompt
- Give goals, not step-by-step instructions
- Use `TemplateHelpers_make_template()` for template generation

---

## Git Discipline

- **Never** `git add -A` — review `git status` and stage specific files
- Check `git diff` before committing
- Write clear commit messages (why, not just what)

---

## Common Pitfalls

- Only `Files_workspace_out_write_text` exists for writing (not `_ro_write_text`)
- Template files must end in `.yaml`
- Use `LLM_DO_DEBUG=1` for debugging TemplateCall

---

Stay small, stay testable, trust the LLM.
