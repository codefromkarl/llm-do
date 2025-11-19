# TODO

## Upstream Discussion

- [ ] **Discuss CLI flag propagation with llm library maintainers**

  Currently, when `TemplateCall` invokes sub-templates via `model.prompt()`, it bypasses the CLI layer entirely. This means CLI flags like `--tools-debug` don't propagate to nested calls.

  We're using the `LLM_DO_DEBUG` environment variable as a workaround, but it would be good to understand:
  - Is there a recommended pattern for tools that need to make nested `model.prompt()` calls?
  - Should Response objects carry debug/display preferences?
  - Should there be a context manager or similar mechanism for propagating CLI options?

  Current workaround: `LLM_DO_DEBUG=1 llm -t template.yaml "task"`
