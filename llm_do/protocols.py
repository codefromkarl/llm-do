"""Protocol definitions for dependency injection.

These protocols define the interfaces that tools and other components
depend on, without coupling to concrete runtime implementations.

This enables clean separation between tool registration (tools.py) and
runtime orchestration (runtime.py) without circular dependencies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class WorkerDelegator(Protocol):
    """Protocol for delegating to other workers.

    Concrete implementation lives in runtime.py to avoid circular imports.
    Tools depend on this protocol rather than importing call_worker directly.
    """

    async def call_async(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker asynchronously.

        Args:
            worker: Name of the worker to delegate to
            input_data: Input payload for the worker
            attachments: Optional list of attachment paths (sandbox-relative)

        Returns:
            Output from the delegated worker

        Raises:
            PermissionError: If delegation is not allowed or user rejects
        """
        ...

    def call_sync(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker synchronously.

        Args:
            worker: Name of the worker to delegate to
            input_data: Input payload for the worker
            attachments: Optional list of attachment paths (sandbox-relative)

        Returns:
            Output from the delegated worker

        Raises:
            PermissionError: If delegation is not allowed or user rejects
        """
        ...


class WorkerCreator(Protocol):
    """Protocol for creating new workers.

    Concrete implementation lives in runtime.py.
    Tools depend on this protocol for the worker_create tool.
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
        """Create and persist a new worker definition.

        Args:
            name: Worker name (used for file path and identification)
            instructions: System prompt for the worker
            description: Optional human-readable description
            model: Optional model override (defaults to profile default)
            output_schema_ref: Optional reference to output schema
            force: If True, overwrite existing worker definition

        Returns:
            Dictionary representation of the created WorkerDefinition

        Raises:
            PermissionError: If creation is not allowed or user rejects
            FileExistsError: If worker exists and force=False
        """
        ...
