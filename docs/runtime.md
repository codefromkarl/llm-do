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

# Async version
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

Enforces `allow_workers` allowlist from the caller's definition.

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

Workers are saved to `workers/generated/{name}.yaml`.

---

## Protocol Implementations

Used internally for dependency injection. See [dependency_injection.md](dependency_injection.md).

### RuntimeDelegator

Implements `WorkerDelegator` protocol. Handles worker delegation with approval enforcement.

```python
class RuntimeDelegator:
    def __init__(self, context: WorkerContext): ...
    async def call_async(self, worker: str, input_data: Any, attachments: list[str]) -> Any: ...
```

### RuntimeCreator

Implements `WorkerCreator` protocol. Handles worker creation with approval enforcement.

```python
class RuntimeCreator:
    def __init__(self, context: WorkerContext): ...
    def create(self, name: str, instructions: str, ...) -> dict: ...
```

---

## WorkerContext

Runtime context passed to tools via PydanticAI's dependency injection.

```python
@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    sandbox_manager: SandboxManager
    sandbox_toolset: SandboxToolset
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    attachments: List[AttachmentPayload]
    message_callback: Optional[MessageCallback]
    custom_tools_path: Optional[Path]
```

Tools access context via `RunContext[WorkerContext]`:

```python
@agent.tool
def my_tool(ctx: RunContext[WorkerContext], arg: str) -> str:
    return ctx.deps.sandbox_toolset.read_text("sandbox", "file.txt")
```

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

Session approvals are cached to avoid repeated prompts for the same operation.

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
    )
```

---

## Module Structure

```
llm_do/
├── runtime.py      # run_worker, call_worker, create_worker
├── execution.py    # Agent runners (default_agent_runner, etc.)
├── approval.py     # ApprovalController
├── tools.py        # Tool registration
└── protocols.py    # WorkerDelegator, WorkerCreator protocols
```
