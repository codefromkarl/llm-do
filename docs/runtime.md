# Runtime API

The runtime module provides the core worker execution API.

## Entry Points

### run_worker / run_worker_async

Primary entry points for executing workers.

```python
from llm_do import run_worker, run_worker_async

# Sync version
result = run_worker(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    attachments=None,              # Optional files to expose
    cli_model="openai:gpt-4",      # Fallback model
    approval_callback=callback,    # For tool approvals
    message_callback=on_message,   # For streaming events
)

# Async version (recommended for nested worker calls)
result = await run_worker_async(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    # ... same parameters
)
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `registry` | `WorkerRegistry` | Source for worker definitions |
| `worker` | `str` | Name of the worker to run |
| `input_data` | `Any` | Input payload (string or dict) |
| `attachments` | `Sequence[AttachmentInput]` | Optional files to expose |
| `cli_model` | `ModelLike` | Fallback model if worker has none |
| `approval_callback` | `ApprovalCallback` | Callback for tool approvals |
| `message_callback` | `MessageCallback` | Callback for streaming events |

**Returns:** `WorkerRunResult` with `output` and `messages`.

**Implementation Note:** Both functions share preparation logic through internal helpers (`_prepare_worker_context`, `_handle_result`) to avoid duplication while maintaining separate sync/async execution paths.

---

### call_worker / call_worker_async

Delegate to another worker (used internally by `worker_call` tool).

```python
result = await call_worker_async(
    registry=registry,
    worker="target-worker",
    input_data=payload,
    caller_context=context,    # Required: parent worker's context
    attachments=files,
)
```

**Enforces:**
- `allow_workers` allowlist from the caller's definition
- Attachment approval via `sandbox.read` with full metadata (path, size, target worker)
- Attachment policy limits (max count, total size, allowed suffixes)

**Note:** When delegating with attachments, each attachment triggers a `sandbox.read` approval check before being passed to the child worker. This ensures the user is aware of what files are being shared between workers.

---

### create_worker

Create and persist a new worker definition.

```python
from llm_do import create_worker, WorkerSpec, WorkerCreationDefaults

spec = WorkerSpec(
    name="new-worker",
    instructions="You are a helpful assistant.",
    description="A simple worker",
)

definition = create_worker(
    registry=registry,
    spec=spec,
    defaults=WorkerCreationDefaults(default_model="openai:gpt-4"),
    force=False,  # Set True to overwrite existing
)
```

Workers are saved to `workers/generated/{name}.worker`.

---

## Protocol Implementations

Used internally for dependency injection. See [dependency_injection.md](dependency_injection.md).

### RuntimeDelegator

Implements `WorkerDelegator` protocol. Handles worker delegation with approval enforcement.

```python
class RuntimeDelegator:
    def __init__(self, context: WorkerContext): ...
    async def call_async(self, worker: str, input_data: Any, attachments: list[str]) -> Any: ...
    def call_sync(self, worker: str, input_data: Any, attachments: list[str]) -> Any: ...
```

**Attachment approval enforcement:** When attachments are provided, `RuntimeDelegator` validates them through `AttachmentValidator`, then checks `sandbox.read` approval for each attachment before passing them to the child worker.

### RuntimeCreator

Implements `WorkerCreator` protocol. Handles worker creation with approval enforcement.

```python
class RuntimeCreator:
    def __init__(self, context: WorkerContext): ...
    def create(self, name: str, instructions: str, ...) -> dict: ...
```

---

## WorkerContext

Runtime context passed to worker execution and available to tools via PydanticAI's dependency injection.

```python
@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    attachment_validator: AttachmentValidator
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    attachments: List[AttachmentPayload]
    message_callback: Optional[MessageCallback]
    custom_tools_path: Optional[Path]

    def validate_attachments(
        self, attachment_specs: Sequence[AttachmentInput]
    ) -> tuple[List[Path], List[Dict[str, Any]]]:
        """Resolve attachment specs to sandboxed files and enforce policy limits."""
```

**Key components:**

- **`attachment_validator`**: Validates and resolves attachments for worker delegation
- **`approval_controller`**: Enforces tool rules and prompts for user approval
- **`attachments`**: Files passed to this worker from parent (if delegated)
- **`custom_tools_path`**: Path to `tools.py` if worker has custom tools

Tools access context via `RunContext[WorkerContext]`:

```python
from pydantic_ai import RunContext
from llm_do import WorkerContext

@agent.tool
def my_tool(ctx: RunContext[WorkerContext], arg: str) -> str:
    # Access worker definition
    worker_name = ctx.deps.worker.name

    # Access approval controller
    result = ctx.deps.approval_controller.maybe_run(
        "my_tool",
        {"arg": arg},
        lambda: perform_operation(arg),
    )
    return result
```

**Note:** File operations are handled through the `Sandbox` toolset registered automatically. Tools like `read_file`, `write_file`, and `list_files` are available based on the worker's sandbox configuration.

---

## ApprovalController

Enforces tool rules and prompts for user approval when required.

```python
from llm_do import ApprovalController

controller = ApprovalController(
    tool_rules=definition.tool_rules,
    approval_callback=my_callback,
)

# Used internally by tools
result = controller.maybe_run(
    tool_name="sandbox.write",
    payload={"path": "output/file.txt"},
    func=lambda: do_write(),
)
```

**Features:**
- Session approval caching to avoid repeated prompts for identical operations
- Configurable `approval_callback` for custom approval logic
- Integration with `ToolRule` for per-tool configuration

**Tool Rules:**
```python
from llm_do import ToolRule

rule = ToolRule(
    name="sandbox.write",
    allowed=True,
    approval_required=True,
    description="Write files to output sandbox"
)
```

---

## Approval Callbacks

```python
from llm_do import ApprovalDecision, approve_all_callback, strict_mode_callback

# Auto-approve everything (for tests)
result = run_worker(..., approval_callback=approve_all_callback)

# Reject all approval-required tools (strict mode)
result = run_worker(..., approval_callback=strict_mode_callback)

# Custom callback
def my_callback(tool_name: str, payload: dict, reason: str) -> ApprovalDecision:
    # Show prompt to user, get decision
    return ApprovalDecision(
        approved=True,
        approve_for_session=True,  # Don't ask again for same operation
        note="User approved via CLI",
    )
```

**Built-in callbacks:**
- `approve_all_callback`: Auto-approves all requests (testing, non-interactive)
- `strict_mode_callback`: Rejects all approval-required tools (production, CI)

---

## Module Structure

The runtime is organized into focused modules with clear responsibilities:

```
llm_do/
├── runtime.py           # Worker execution and delegation
│                        # - run_worker / run_worker_async
│                        # - call_worker / call_worker_async
│                        # - create_worker
│                        # - RuntimeDelegator / RuntimeCreator
│                        # - Internal helpers: _prepare_worker_context, _handle_result
│
├── execution.py         # Agent execution strategies
│                        # - default_agent_runner (sync wrapper)
│                        # - default_agent_runner_async (PydanticAI integration)
│                        # - prepare_agent_execution (context prep)
│
├── types.py             # Type definitions and data models
│                        # - WorkerDefinition, WorkerSpec, WorkerContext
│                        # - AgentRunner, ApprovalCallback, MessageCallback
│
├── approval.py          # Approval enforcement
│                        # - ApprovalController
│
├── tools.py             # Tool registration
│                        # - register_worker_tools
│                        # - File tools (read_file, write_file, list_files)
│                        # - Shell tool (shell)
│                        # - Delegation tools (worker_call, worker_create)
│
├── protocols.py         # Dependency injection protocols
│                        # - WorkerDelegator, WorkerCreator, FileSandbox
│
├── worker_sandbox.py    # Sandbox for worker execution
│                        # - Sandbox (unified sandbox implementation)
│                        # - SandboxConfig (paths configuration)
│                        # - AttachmentValidator (attachment validation)
│
└── filesystem_sandbox.py # Reusable filesystem sandbox
                         # - FileSandboxImpl (core I/O operations)
                         # - PathConfig (path-level configuration)
```

**Architecture highlights:**

- **Separation of concerns**: Runtime orchestration separated from agent execution
- **Dependency injection**: Protocols enable testability and flexibility
- **Shared helpers**: `_prepare_worker_context` eliminates ~110 lines of duplication
- **Async-first**: `run_worker` wraps async implementation for backward compatibility
