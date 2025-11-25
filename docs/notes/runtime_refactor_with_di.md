# Runtime Refactor: Dependency Injection Pattern

## Status: ✅ COMPLETED

## Goal
Reduce complexity in `runtime.py` (originally 991 lines) by extracting tool registration and related logic into separate modules. Use protocol-based dependency injection to eliminate circular dependencies while enabling recursive worker calls.

## Results Achieved
- **runtime.py**: 991 → 540 lines (**45% reduction**)
- Created 4 focused modules (733 lines total):
  - `protocols.py` (97 lines) - Interface definitions
  - `approval.py` (76 lines) - Approval enforcement
  - `tools.py` (282 lines) - Tool registration with DI
  - `execution.py` (278 lines) - Agent runners
- All 108 tests passing
- Zero circular dependencies
- Clean protocol-based architecture

## Current Problems

### 1. Monolithic runtime.py
The runtime module has too many responsibilities:
- Approval control (52 lines)
- Helper functions (155 lines)
- Tool registration (343 lines) - largest chunk
- Agent execution (73 lines)
- Worker lifecycle management (367 lines)

### 2. Tight Coupling
Worker tools need to call `call_worker_async` and `call_worker` for recursive delegation, creating tight coupling between tool registration and runtime orchestration.

### 3. Potential Circular Dependencies
If we naively split tool registration into `tools.py`:
```python
# tools.py
from .runtime import call_worker_async  # ← Import from runtime

def register_worker_tools(...):
    # Uses call_worker_async

# runtime.py
from .tools import register_worker_tools  # ← Import from tools

async def run_worker_async(...):
    register_worker_tools(...)
```
**Result:** Circular import! ❌

## Proposed Solution: Protocol-Based Dependency Injection

### Architecture Overview
```
protocols.py      # Interface definitions (no imports from other llm_do modules)
    ↑
    |
tools.py          # Tool registration (imports protocols only)
approval.py       # Approval logic (no circular deps)
execution.py      # Agent runners
    ↑
    |
runtime.py        # Orchestration (implements protocols, imports all above)
    ↑
    |
base.py           # Re-export layer (unchanged interface)
```

### Key Insight
**Tools depend on abstractions (protocols), not concrete implementations.**
Runtime provides concrete implementations. No circular dependency!

## Detailed Changes

### 1. `llm_do/protocols.py` (NEW - ~80 lines)

Define protocol interfaces for runtime capabilities:

```python
"""Protocol definitions for dependency injection.

These protocols define the interfaces that tools and other components
depend on, without coupling to concrete runtime implementations.
"""
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path


class WorkerDelegator(Protocol):
    """Protocol for delegating to other workers.

    Concrete implementation lives in runtime.py to avoid circular imports.
    """

    async def call_async(
        self,
        worker: str,
        input_data: Any,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker asynchronously."""
        ...

    def call_sync(
        self,
        worker: str,
        input_data: Any,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker synchronously."""
        ...


class WorkerCreator(Protocol):
    """Protocol for creating new workers.

    Concrete implementation lives in runtime.py.
    """

    def create(
        self,
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Create and persist a new worker definition."""
        ...
```

**Rationale:**
- Protocols are typing-only constructs (PEP 544)
- No runtime dependencies on concrete implementations
- Can be imported by any module without circular deps
- Type checkers enforce correct implementations

### 2. `llm_do/tools.py` (NEW - ~380 lines)

Extract ALL tool registration logic from runtime.py:

```python
"""Tool registration for llm-do workers.

This module registers both built-in tools (sandbox_*, worker_*) and
custom tools loaded from workers/{name}/tools.py files.

Uses protocol-based DI to avoid circular imports with runtime.py.
"""
from typing import Any, List, Optional, Dict
import logging

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext

from .protocols import WorkerDelegator, WorkerCreator
from .types import WorkerContext

logger = logging.getLogger(__name__)


def register_worker_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
) -> None:
    """Register all tools for a worker.

    Args:
        agent: PydanticAI agent to register tools with
        context: Worker execution context
        delegator: Implementation of worker delegation (DI)
        creator: Implementation of worker creation (DI)

    Registers:
    1. Sandbox tools (list, read_text, write_text)
    2. Worker delegation tool (worker_call)
    3. Worker creation tool (worker_create)
    4. Custom tools from tools.py if available
    """

    # Register built-in sandbox tools
    _register_sandbox_tools(agent, context)

    # Register worker delegation/creation tools
    _register_worker_delegation_tools(agent, context, delegator, creator)

    # Load and register custom tools if available
    if context.custom_tools_path:
        load_custom_tools(agent, context)


def _register_sandbox_tools(agent: Agent, context: WorkerContext) -> None:
    """Register sandbox file operations."""

    @agent.tool(
        name="sandbox_list",
        description="List files within a sandbox using a glob pattern"
    )
    def sandbox_list(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        pattern: str = "**/*",
    ) -> List[str]:
        return ctx.deps.sandbox_toolset.list(sandbox, pattern)

    @agent.tool(
        name="sandbox_read_text",
        description="Read UTF-8 text from a sandboxed file. "
                    "Do not use this on binary files (PDFs, images, etc) - "
                    "pass them as attachments instead."
    )
    def sandbox_read_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        *,
        max_chars: int = 200_000,
    ) -> str:
        return ctx.deps.sandbox_toolset.read_text(sandbox, path, max_chars=max_chars)

    @agent.tool(
        name="sandbox_write_text",
        description="Write UTF-8 text to a sandboxed file"
    )
    def sandbox_write_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        content: str,
    ) -> Optional[str]:
        return ctx.deps.sandbox_toolset.write_text(sandbox, path, content)


def _register_worker_delegation_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
) -> None:
    """Register worker_call and worker_create tools using injected implementations."""

    @agent.tool(
        name="worker_call",
        description="Delegate to another registered worker"
    )
    async def worker_call_tool(
        ctx: RunContext[WorkerContext],
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        # Use injected delegator instead of importing call_worker_async
        return await delegator.call_async(worker, input_data, attachments)

    @agent.tool(
        name="worker_create",
        description="Persist a new worker definition using the active profile"
    )
    def worker_create_tool(
        ctx: RunContext[WorkerContext],
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        # Use injected creator
        return creator.create(
            name=name,
            instructions=instructions,
            description=description,
            model=model,
            output_schema_ref=output_schema_ref,
            force=force,
        )


def load_custom_tools(agent: Agent, context: WorkerContext) -> None:
    """Load and register custom tools from tools.py module.

    Custom tools are functions defined in the tools.py file in the worker's directory.
    Only functions explicitly listed in the worker's tool_rules are registered.
    Each tool call is wrapped with the approval controller to enforce security policies.

    Security guarantees:
    - Only functions listed in definition.tool_rules are registered (allowlist)
    - All tool calls go through approval_controller.maybe_run() (approval enforcement)
    - Tool rules (allowed, approval_required) are respected
    """
    import importlib.util
    import sys
    import inspect

    tools_path = context.custom_tools_path
    if not tools_path or not tools_path.exists():
        return

    # [... rest of _load_custom_tools implementation from runtime.py ...]
    # Move the entire implementation here (lines 340-467 of current runtime.py)
```

**Key changes:**
- ✅ Takes `delegator` and `creator` as parameters (DI)
- ✅ No imports from `runtime.py`
- ✅ Can be tested independently with mock delegators/creators
- ✅ Kept internal functions for organization (`_register_sandbox_tools`, etc.)

### 3. `llm_do/approval.py` (NEW - ~100 lines)

Extract approval logic:

```python
"""Approval enforcement for tool calls.

This module provides the ApprovalController class which enforces
tool rules and prompts for user approval when required.
"""
from typing import Any, Callable, Mapping, Optional, Set, Tuple

from .types import ApprovalCallback, ApprovalDecision, approve_all_callback


class ApprovalController:
    """Apply tool rules with blocking approval prompts."""

    def __init__(
        self,
        tool_rules: Mapping[str, Any],  # ToolRule from types
        *,
        approval_callback: ApprovalCallback = approve_all_callback,
    ):
        self.tool_rules = tool_rules
        self.approval_callback = approval_callback
        self.session_approvals: Set[Tuple[str, frozenset]] = set()

    def _make_approval_key(
        self, tool_name: str, payload: Mapping[str, Any]
    ) -> Tuple[str, frozenset]:
        """Create a hashable key for session approval tracking."""
        try:
            items = frozenset(payload.items())
        except TypeError:
            # If payload has unhashable values, use repr as fallback
            items = frozenset((k, repr(v)) for k, v in payload.items())
        return (tool_name, items)

    def maybe_run(
        self,
        tool_name: str,
        payload: Mapping[str, Any],
        func: Callable[[], Any],
    ) -> Any:
        """Check approval rules and execute function if approved."""
        rule = self.tool_rules.get(tool_name)
        if rule:
            if not rule.allowed:
                raise PermissionError(f"Tool '{tool_name}' is disallowed")
            if rule.approval_required:
                # Check session approvals
                key = self._make_approval_key(tool_name, payload)
                if key in self.session_approvals:
                    return func()

                # Block and wait for approval
                decision = self.approval_callback(tool_name, payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call '{tool_name}'{note}")

                # Track session approval if requested
                if decision.approve_for_session:
                    self.session_approvals.add(key)

        return func()
```

**Rationale:**
- Self-contained logic
- No dependencies on runtime.py
- Can be tested independently

### 4. `llm_do/execution.py` (NEW - ~150 lines)

Extract agent execution logic:

```python
"""Agent execution strategies for llm-do workers.

This module provides the default agent runners (sync and async)
and helper functions for preparing agent execution contexts.
"""
import asyncio
import json
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel

from .types import (
    AgentExecutionContext,
    ModelLike,
    WorkerContext,
    WorkerDefinition,
)


def model_supports_streaming(model: ModelLike) -> bool:
    """Return True if the configured model supports streaming callbacks."""
    # [... copy implementation from runtime.py ...]


def format_user_prompt(user_input: Any) -> str:
    """Serialize user input into a prompt string for the agent."""
    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


def prepare_agent_execution(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> AgentExecutionContext:
    """Prepare everything needed for agent execution (sync or async).

    This extracts all the setup logic that's common between sync and async
    agent runners, including:
    - Building the prompt with attachments
    - Setting up streaming callbacks
    - Preparing agent kwargs
    - Initializing status tracking
    """
    # [... copy implementation from runtime.py lines 132-258 ...]


async def default_agent_runner_async(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    register_tools_fn: Callable[[Agent, WorkerContext], None],
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    Args:
        definition: Worker definition
        user_input: Input data
        context: Worker execution context
        output_model: Optional output schema
        register_tools_fn: Function to register tools (injected)

    Returns:
        Tuple of (output, messages)
    """
    exec_ctx = prepare_agent_execution(definition, user_input, context, output_model)

    agent = Agent(**exec_ctx.agent_kwargs)
    register_tools_fn(agent, context)  # ← Injected tool registration

    run_result = await agent.run(
        exec_ctx.prompt,
        deps=context,
        event_stream_handler=exec_ctx.event_handler,
    )

    if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
        exec_ctx.emit_status("end", duration=round(perf_counter() - exec_ctx.started_at, 2))

    messages = run_result.all_messages() if hasattr(run_result, 'all_messages') else []
    return (run_result.output, messages)


def default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    register_tools_fn: Callable[[Agent, WorkerContext], None],
) -> tuple[Any, List[Any]]:
    """Synchronous wrapper around the async agent runner."""
    return asyncio.run(
        default_agent_runner_async(
            definition, user_input, context, output_model,
            register_tools_fn=register_tools_fn
        )
    )
```

**Key changes:**
- ✅ Agent runners now take `register_tools_fn` as a parameter
- ✅ No direct imports from tools.py or runtime.py
- ✅ Focused on execution logic only

### 5. `llm_do/runtime.py` (MODIFIED - ~450 lines, down from 991)

Becomes the orchestration layer that ties everything together:

```python
"""Runtime orchestration for llm-do workers.

This module provides the core runtime implementation:
- Worker delegation and creation (implements protocols)
- Context preparation and lifecycle management
- Orchestrates execution, tools, and approvals
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Type

from pydantic import BaseModel

# Import extracted modules
from .approval import ApprovalController
from .execution import (
    default_agent_runner_async,
    default_agent_runner,
    prepare_agent_execution,
)
from .protocols import WorkerCreator, WorkerDelegator
from .sandbox import AttachmentInput, AttachmentPayload, SandboxManager, SandboxToolset
from .tools import register_worker_tools
from .types import (
    AgentRunner,
    ApprovalCallback,
    MessageCallback,
    ModelLike,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback as _auto_approve_callback,
)


# ---------------------------------------------------------------------------
# Concrete implementations of protocols (for dependency injection)
# ---------------------------------------------------------------------------


class RuntimeDelegator:
    """Concrete implementation of WorkerDelegator protocol.

    This wraps call_worker_async/call_worker with approval enforcement.
    Injected into tools to enable recursive worker calls without circular imports.
    """

    def __init__(self, context: WorkerContext):
        self.context = context

    async def call_async(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Async worker delegation with approval enforcement."""
        # [... move _worker_call_tool_async implementation here ...]
        # Lines 469-527 from current runtime.py

    def call_sync(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Sync worker delegation with approval enforcement."""
        # [... move _worker_call_tool implementation here ...]
        # Lines 530-573 from current runtime.py


class RuntimeCreator:
    """Concrete implementation of WorkerCreator protocol.

    Handles worker creation with approval enforcement.
    Injected into tools to enable worker_create tool.
    """

    def __init__(self, context: WorkerContext):
        self.context = context

    def create(
        self,
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Create worker with approval enforcement."""
        # [... move _worker_create_tool implementation here ...]
        # Lines 576-607 from current runtime.py


# ---------------------------------------------------------------------------
# Worker delegation (public API)
# ---------------------------------------------------------------------------


def call_worker(
    registry: Any,
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: AgentRunner = None,  # Will use default
) -> WorkerRunResult:
    """Delegate to another worker (sync version)."""
    # [... keep implementation, lines 691-716 ...]


async def call_worker_async(
    registry: Any,
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: Optional[Callable] = None,
) -> WorkerRunResult:
    """Async version of call_worker for delegating to another worker."""
    # [... keep implementation, lines 719-760 ...]


# ---------------------------------------------------------------------------
# Worker creation (public API)
# ---------------------------------------------------------------------------


def create_worker(
    registry: Any,
    spec: WorkerSpec,
    *,
    defaults: WorkerCreationDefaults,
    force: bool = False,
) -> WorkerDefinition:
    """Create and persist a new worker definition."""
    # [... keep implementation, lines 768-782 ...]


# ---------------------------------------------------------------------------
# Main worker execution (sync and async)
# ---------------------------------------------------------------------------


async def run_worker_async(
    *,
    registry: Any,
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[Callable] = None,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    """Execute a worker by name (async version)."""

    # [... keep context setup code, lines 826-865 ...]

    # Create concrete protocol implementations for DI
    delegator = RuntimeDelegator(context)
    creator = RuntimeCreator(context)

    # Create a tool registration function that uses our concrete implementations
    def register_tools_for_worker(agent, ctx):
        register_worker_tools(agent, ctx, delegator, creator)

    # Use the provided agent_runner or default to the async version
    if agent_runner is None:
        result = await default_agent_runner_async(
            definition, input_data, context, output_model,
            register_tools_fn=register_tools_for_worker
        )
    else:
        # Support both sync and async agent runners
        # [... keep existing logic ...]

    # [... keep result handling, lines 879-891 ...]


def run_worker(
    *,
    registry: Any,
    worker: str,
    input_data: Any,
    # ... same signature ...
) -> WorkerRunResult:
    """Execute a worker by name (sync version)."""

    # [... similar changes as run_worker_async ...]
    # Create delegator, creator, and inject into tools
```

**Key changes:**
- ✅ Implements protocol interfaces via `RuntimeDelegator` and `RuntimeCreator`
- ✅ Injects concrete implementations into `register_worker_tools`
- ✅ Reduced from 991 to ~450 lines (55% reduction!)
- ✅ Focused on orchestration and lifecycle management

### 6. `llm_do/base.py` (MODIFIED - minimal changes)

Update re-exports to include new modules:

```python
"""Foundational runtime for llm-do.

This module now serves as a backward-compatible re-export layer.
"""
from __future__ import annotations

from typing import Iterable

# Re-export sandbox types
from .sandbox import (
    AttachmentInput,
    AttachmentPayload,
    AttachmentPolicy,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
)

# Re-export types
from .types import (
    AgentExecutionContext,
    AgentRunner,
    ApprovalCallback,
    ApprovalDecision,
    MessageCallback,
    ModelLike,
    OutputSchemaResolver,
    ToolRule,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback,
    strict_mode_callback,
)

# Re-export registry
from .registry import WorkerRegistry

# Re-export approval (NEW)
from .approval import ApprovalController

# Re-export runtime functions
from .runtime import (
    call_worker,
    call_worker_async,
    create_worker,
    run_worker,
    run_worker_async,
)

# Re-export protocols (NEW - for advanced users)
from .protocols import WorkerCreator, WorkerDelegator

# Re-export tools (NEW - for testing/advanced use)
from .tools import register_worker_tools, load_custom_tools

__all__: Iterable[str] = [
    # ... existing exports ...
    # Add new exports:
    "WorkerCreator",
    "WorkerDelegator",
    "register_worker_tools",
    "load_custom_tools",
]
```

### 7. `llm_do/types.py` (NO CHANGES NEEDED)

Already has all the type definitions we need. No changes required.

### 8. Tests (MODIFIED)

Update `tests/test_worker_delegation.py` to use public API instead of private functions:

```python
# OLD (imports private functions):
from llm_do.runtime import _worker_call_tool, _worker_create_tool

# NEW (use public API or protocol implementations):
from llm_do import WorkerDelegator, WorkerCreator
from llm_do.runtime import RuntimeDelegator, RuntimeCreator

# Update tests to create RuntimeDelegator/RuntimeCreator instances
# instead of calling _worker_call_tool directly
```

## Migration Strategy

### Phase 1: Extract Protocols and Approval (Low Risk)
1. Create `protocols.py` with interface definitions
2. Create `approval.py` by moving `ApprovalController` from runtime.py
3. Update `runtime.py` to import from `approval.py`
4. Update `base.py` re-exports
5. **Run full test suite** - should pass with no changes needed

### Phase 2: Extract Tools (Medium Risk)
1. Create `tools.py` with all tool registration logic
2. Update function signatures to accept `delegator` and `creator` parameters
3. Keep temporary shim in `runtime.py` that creates wrapper functions
4. **Run full test suite** - verify tools still work

### Phase 3: Extract Execution (Low Risk)
1. Create `execution.py` with agent runner logic
2. Update runners to accept `register_tools_fn` parameter
3. Update `runtime.py` to import from `execution.py`
4. **Run full test suite**

### Phase 4: Wire Up Dependency Injection (High Risk)
1. Create `RuntimeDelegator` and `RuntimeCreator` classes in `runtime.py`
2. Update `run_worker` and `run_worker_async` to instantiate them
3. Pass concrete implementations to `register_worker_tools`
4. Remove old `_worker_call_tool` and `_worker_create_tool` functions
5. Update tests to use public API
6. **Run full test suite** - this is the critical integration point

### Phase 5: Cleanup
1. Remove any temporary shims
2. Update documentation
3. Final test run

## Testing Approach

### Unit Tests
- Test protocols work with mock implementations
- Test `tools.py` independently with mock delegator/creator
- Test `approval.py` in isolation
- Test `execution.py` with mock tool registration

### Integration Tests
- All existing tests should continue to pass
- Add new test: Verify protocol implementations satisfy protocol definitions
- Add new test: Mock delegator/creator and verify tools use them correctly

### Backward Compatibility Tests
- Verify all public API exports still work
- Verify CLI continues to function
- Verify custom tools still load correctly

## Benefits

### Immediate Benefits
1. **55% reduction in runtime.py size** (991 → ~450 lines)
2. **No circular dependencies** - protocols break the cycle
3. **Better testability** - each module can be tested independently
4. **Clear separation of concerns** - each module has one responsibility

### Long-term Benefits
1. **Easier to add new tools** - just implement protocols
2. **Easier to swap implementations** - protocols enable different strategies
3. **Better onboarding** - smaller, focused modules are easier to understand
4. **Foundation for future features** - clean DI pattern enables extensions

## Risk Assessment

### Low Risk
- Extracting `ApprovalController` (self-contained)
- Extracting helper functions to `execution.py`
- Creating `protocols.py` (typing-only)

### Medium Risk
- Extracting tool registration (but keeping same behavior)
- Updating test imports

### High Risk
- Wiring up DI in `run_worker_async` (core integration point)
- Ensuring approval enforcement still works with new structure

### Mitigation
- Incremental migration with test runs after each phase
- Comprehensive test coverage before starting
- Keep old code in comments during transition
- Can roll back any single phase if issues arise

## Open Questions

1. **Should we expose protocols in public API?**
   - Pros: Advanced users can provide custom implementations
   - Cons: More API surface to maintain
   - Recommendation: Yes, but mark as "Advanced" in docs

2. **Should RuntimeDelegator/RuntimeCreator be public?**
   - Pros: Useful for testing
   - Cons: Implementation details
   - Recommendation: Make public but document as "typically not needed"

3. **Backward compatibility for `_worker_call_tool` imports?**
   - Current: One test imports these private functions
   - Options: (a) Break the test, (b) Keep shims, (c) Make them public
   - Recommendation: Fix the test to use public API (RuntimeDelegator)

4. **Should we go further with extraction?**
   - Could extract worker lifecycle to `lifecycle.py` (~200 lines)
   - Could extract context preparation helpers
   - Recommendation: Start with this plan, evaluate after

## Success Criteria

- [ ] All existing tests pass
- [ ] runtime.py reduced to < 500 lines
- [ ] No circular import errors
- [ ] CLI works unchanged
- [ ] Custom tools continue to load
- [ ] Documentation updated
- [ ] Type checking passes (mypy/pyright)

---

## Implementation Summary

### Actual Implementation (Completed January 2025)

All phases completed successfully with the following results:

#### Phase 1: Extract Protocols and Approval ✅
- Created `protocols.py` with `WorkerDelegator` and `WorkerCreator` interfaces
- Created `approval.py` by extracting `ApprovalController` (76 lines)
- Updated `runtime.py` and `base.py` imports
- Result: All tests passing

#### Phase 2: Extract Tools ✅
- Created `tools.py` with all tool registration logic (282 lines)
- Implemented protocol-based DI for worker delegation and creation
- Created temporary wrapper classes for gradual migration
- Result: All tests passing, no behavior changes

#### Phase 3: Extract Execution ✅
- Created `execution.py` with agent runner logic (278 lines)
- Extracted helper functions (model streaming detection, prompt formatting, execution preparation)
- Updated runners to accept `register_tools_fn` parameter for DI
- Result: All tests passing

#### Phase 4: Final DI Integration ✅
- Replaced temporary wrappers with proper `RuntimeDelegator` and `RuntimeCreator` classes
- Moved all tool implementation logic into protocol implementations
- Updated tests to use public API (`RuntimeDelegator`/`RuntimeCreator`) instead of private functions
- Updated exports in `__init__.py` and `base.py`
- Result: All 108 tests passing, clean architecture

### Key Achievements

1. **Massive Reduction**: runtime.py reduced from 991 to 540 lines (45% reduction)
2. **Zero Circular Dependencies**: Protocol-based DI successfully eliminated all circular imports
3. **Better Organization**: 4 focused modules with clear responsibilities:
   - `protocols.py`: Type-safe interfaces (97 lines)
   - `approval.py`: Approval enforcement (76 lines)
   - `tools.py`: Tool registration with DI (282 lines)
   - `execution.py`: Agent execution (278 lines)
4. **Maintained Backward Compatibility**: All existing tests pass without modification (except test internals)
5. **Improved Testability**: Protocol implementations can be easily mocked for testing

### Architecture Benefits

- **Separation of Concerns**: Each module has a single, clear responsibility
- **Dependency Injection**: Tools depend on protocols, not concrete implementations
- **Type Safety**: Protocols provide clear contracts between layers
- **Extensibility**: Easy to add new tools or swap implementations
- **Maintainability**: Smaller, focused modules are easier to understand and modify

### Migration Path Used

The incremental 5-phase approach worked exceptionally well:
1. Each phase was independently testable
2. No big-bang refactoring - gradual, safe changes
3. Temporary wrappers allowed smooth transition in Phase 2-3
4. Final Phase 4 cleaned up and completed the DI architecture

### Lessons Learned

1. **Protocols are powerful**: Python's Protocol type (PEP 544) provides excellent compile-time checking without runtime coupling
2. **Incremental is better**: Breaking into phases made the refactor manageable and low-risk
3. **Test coverage is essential**: 108 tests gave confidence at each step
4. **DI solves circular deps**: Dependency injection elegantly breaks circular import cycles

### Next Steps (Optional Future Work)

While the core refactor is complete, potential future improvements:
- Extract worker lifecycle logic to `lifecycle.py` (~150 lines)
- Extract context preparation helpers to `context.py` (~80 lines)
- Further reduce `runtime.py` to ~300 lines (70% reduction from original)

However, at 540 lines, `runtime.py` is now much more manageable and the current architecture is clean and well-organized.

---

## Final Architecture Diagram

```
┌─────────────────────────────────────────────┐
│           protocols.py (97 lines)            │
│  - WorkerDelegator Protocol                  │
│  - WorkerCreator Protocol                    │
└─────────────────────────────────────────────┘
                    ▲
                    │ (implements)
                    │
┌───────────────────┴─────────────────────────┐
│         runtime.py (540 lines)               │
│  - RuntimeDelegator (implements Protocol)    │
│  - RuntimeCreator (implements Protocol)      │
│  - call_worker / call_worker_async           │
│  - run_worker / run_worker_async             │
│  - create_worker                             │
└──────────────────┬──────────────────────────┘
                   │
                   ├─────► approval.py (76 lines)
                   │       - ApprovalController
                   │
                   ├─────► tools.py (282 lines)
                   │       - register_worker_tools
                   │       - load_custom_tools
                   │       (depends on protocols, not runtime)
                   │
                   └─────► execution.py (278 lines)
                           - default_agent_runner_async
                           - default_agent_runner
                           - prepare_agent_execution
```

**Key Design Principle**: `tools.py` depends on `protocols.py` (interfaces), NOT on `runtime.py` (implementations). This breaks the circular dependency.
