# Message Display and Logging

## Overview

The CLI provides rich, colored output of all messages exchanged between the user, LLM, and tools during worker execution. This transparency helps users understand what the LLM is doing and debug workflow issues.

## Design Choices

### 1. Rich Library for Terminal Formatting

We use the [`rich`](https://rich.readthedocs.io/) library for terminal output because:

- **Built-in color support**: Handles terminal color codes automatically across platforms
- **Structured formatting**: Panels, syntax highlighting, and tables out of the box
- **Console abstraction**: Clean API that separates content from presentation
- **Wide adoption**: Well-maintained, popular library in the Python ecosystem

Alternative considered: Manual ANSI codes would be brittle and harder to maintain.

### 2. Rich Output by Default

Message display is **enabled by default** to provide transparency and debugging insight.

**Default behavior** (rich formatted output):
```bash
llm-do pitch_evaluator --model claude-3-5-haiku-20241022
# Shows: System Instructions → User Input → Tool Calls → Tool Results → Model Response → Final Output
```

**JSON mode** (for scripting/automation):
```bash
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --json
# Outputs: {"output": "...", "messages": [...]}
```

**Why default to rich output:**

- **Transparency**: Users can see what the LLM is doing (tool calls, reasoning)
- **Debugging**: Immediately visible when something goes wrong
- **Learning**: New users understand how workers and tools interact
- **Opt-out available**: Production scripts can use `--json` for clean output

### 3. Message Capture Architecture

Messages are captured at the **agent runner level** in `_default_agent_runner()`:

```python
def _default_agent_runner(...) -> tuple[Any, List[Any]]:
    # ... setup agent ...
    run_result = agent.run_sync(prompt, deps=context)

    # Extract messages from PydanticAI result
    messages = run_result.all_messages()

    return (run_result.output, messages)
```

**Why this approach:**

- **Non-invasive**: Doesn't modify PydanticAI's Agent internals
- **Uses public API**: `run_result.all_messages()` is the official way to get message history
- **Backward compatible**: Custom agent runners can still return just output
- **Centralized**: All worker executions (CLI, delegation, tests) benefit

### 4. WorkerRunResult Enhancement

Added `messages` field to `WorkerRunResult`:

```python
class WorkerRunResult(BaseModel):
    output: Any
    messages: List[Any] = Field(default_factory=list)
```

**Why this design:**

- **Preserves existing behavior**: `output` field remains primary
- **Optional data**: Empty list when messages not captured
- **Serializable**: Can be included in JSON output or excluded
- **Future extensibility**: Could add timing, token counts, etc.

The `run_worker()` function handles both old and new agent runner signatures:

```python
result = agent_runner(definition, input_data, context, output_model)

# Handle both old-style (output only) and new-style (output, messages) returns
if isinstance(result, tuple) and len(result) == 2:
    raw_output, messages = result
else:
    raw_output = result
    messages = []
```

### 5. Color Coding by Message Type

Each message type has distinct formatting:

| Message Type | Color | Purpose |
|--------------|-------|---------|
| System Instructions | Cyan | Worker's system prompt (loaded from prompts/) |
| User Input | Green | User's input message or JSON payload |
| Tool Call | Blue | LLM calling a tool (e.g., `sandbox_read_text()`) |
| Tool Result | Yellow | Tool output being sent back to LLM |
| Model Response | Magenta | LLM's text response |

**Why these colors:**

- **High contrast**: Easy to scan visually
- **Semantic grouping**:
  - Green (user) vs. Magenta (model) = conversation flow
  - Blue (tool call) vs. Yellow (tool result) = action/reaction
  - Cyan (system) = metadata/configuration
- **Accessible**: Works on both light and dark terminal backgrounds
- **Standard conventions**: Aligns with common CLI color usage

### 6. Structured Display Format

Messages are displayed in **panels with borders**:

```
╭─ System Instructions ───────────────────────────────────╮
│ Evaluate the attached document using the provided      │
│ rubric. Return structured scores and analysis.         │
╰─────────────────────────────────────────────────────────╯
```

**Why panels over plain text:**

- **Visual separation**: Easy to distinguish message boundaries
- **Metadata in title**: Tool names, message types visible at a glance
- **Professional appearance**: Matches modern CLI tool aesthetics
- **Syntax highlighting**: JSON/code in tool calls/results gets proper formatting

### 7. JSON Syntax Highlighting

Tool arguments and results use **syntax highlighting**:

```python
Syntax(args_json, "json", theme="monokai", line_numbers=False)
```

**Design rationale:**

- **Readability**: Easier to spot keys, values, nesting
- **Error detection**: Malformed JSON stands out visually
- **Consistency**: Matches developer experience in editors
- **No line numbers**: Keeps output concise (line numbers not useful for short snippets)

### 8. Message Flow Presentation

Messages are displayed in **chronological order** as they occurred:

1. System Instructions (once, at start)
2. User Input
3. Model Response (may contain tool calls)
4. Tool Results (sent back to model)
5. Model Response (continues after tool execution)
6. ... (repeat until final output)

**Why chronological order:**

- **Debugging**: Trace exact sequence of events
- **Understanding**: See how LLM reasons through multi-step tasks
- **Transparency**: Nothing hidden; full conversation visible

### 9. Output Display

Final output is displayed in a green panel after the message exchange:

```
═══ Message Exchange ═══
[... all messages ...]

╭─ Final Output ──────────────────────────────────╮
│ {                                               │
│   "deck_id": "Aurora Solar",                    │
│   "verdict": "go",                              │
│   ...                                           │
│ }                                               │
╰─────────────────────────────────────────────────╯
```

**Why panel format:**

- **Visual clarity**: Easy to distinguish final result from message trace
- **Consistent styling**: Matches the rest of the rich output
- **Readable**: JSON is pretty-printed automatically

## Future Enhancements

Potential improvements for future versions:

1. **Filtering**: `--verbose=tool_calls` to show only specific message types
2. **Logging to file**: `--log-file=messages.jsonl` for post-mortem analysis
3. **Token counts**: Show token usage per message (requires model API support)
4. **Timing**: Display duration for each LLM call and tool execution
5. **Streaming**: Show messages as they arrive (requires async support)
6. **Diff mode**: Highlight changes in multi-turn conversations

## Example Usage

```bash
# Default: Rich formatted output with full message trace
llm-do pitch_evaluator --model claude-3-5-haiku-20241022

# JSON mode for scripting/automation
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --json

# Auto-approve all tool calls (no interactive prompts)
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --approve-all

# Strict mode (reject all non-pre-approved tools)
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --strict

# With debugging (includes stack traces on errors)
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --debug

# JSON mode with auto-approval and debugging
llm-do pitch_evaluator --model claude-3-5-haiku-20241022 --json --approve-all --debug
```

## Approval System

The CLI supports sophisticated approval controls for tool execution:

- **Default mode**: Interactive approval (currently defaults to auto-approve)
- **`--approve-all`**: Auto-approve all tool calls without prompting (use with caution)
- **`--strict`**: Deny-by-default mode - rejects all non-pre-approved tools

Workers can define `tool_rules` in their YAML to mark specific tools as pre-approved
or require approval. The approval system prevents unauthorized file writes, worker
creation, and other sensitive operations.

## Implementation Files

- **Message capture**: `llm_do/pydanticai/base.py` (`_default_agent_runner`, `WorkerRunResult`)
- **Display logic**: `llm_do/pydanticai/cli.py` (`_display_messages`, `main`)
- **Dependencies**: `pyproject.toml` (added `rich>=13.0`)
