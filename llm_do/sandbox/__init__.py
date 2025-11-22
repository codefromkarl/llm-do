"""Sandbox-aware filesystem helpers reused across the runtime."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ApprovalRunner",
    "AttachmentPolicy",
    "SandboxConfig",
    "SandboxManager",
    "SandboxRoot",
    "SandboxToolset",
]


class AttachmentPolicy(BaseModel):
    """Constraints for inbound attachments."""

    max_attachments: int = 4
    max_total_bytes: int = 10_000_000
    allowed_suffixes: List[str] = Field(default_factory=list)
    denied_suffixes: List[str] = Field(default_factory=list)

    @field_validator("max_attachments")
    @classmethod
    def _positive_max_attachments(cls, value: int) -> int:
        if value < 0:
            raise ValueError("max_attachments must be non-negative")
        return value

    @field_validator("max_total_bytes")
    @classmethod
    def _positive_max_total_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_total_bytes must be positive")
        return value

    @field_validator("allowed_suffixes", "denied_suffixes")
    @classmethod
    def _lower_suffixes(cls, value: List[str]) -> List[str]:
        return [suffix.lower() for suffix in value]

    def validate_paths(self, attachments: Sequence[Path]) -> None:
        if len(attachments) > self.max_attachments:
            raise ValueError("Too many attachments provided")
        total = 0
        for path in attachments:
            suffix = path.suffix.lower()
            if self.allowed_suffixes and suffix not in self.allowed_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' not allowed")
            if self.denied_suffixes and suffix in self.denied_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' is denied")
            size = path.stat().st_size
            total += size
            if total > self.max_total_bytes:
                raise ValueError("Attachments exceed max_total_bytes")


class SandboxConfig(BaseModel):
    """Configuration for a sandbox root."""

    name: str
    path: Path
    mode: str = Field(default="ro", description="ro or rw")
    allowed_suffixes: List[str] = Field(default_factory=list)
    text_suffixes: List[str] = Field(
        default_factory=list, description="Suffixes allowed for sandbox_read_text"
    )
    attachment_suffixes: List[str] = Field(
        default_factory=list, description="Suffixes allowed when attaching files"
    )
    max_bytes: int = 2_000_000

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("mode")
    @classmethod
    def _normalize_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"ro", "rw"}:
            raise ValueError("Sandbox mode must be 'ro' or 'rw'")
        return normalized

    @field_validator("allowed_suffixes", "text_suffixes", "attachment_suffixes")
    @classmethod
    def _lower_suffixes(cls, value: List[str]) -> List[str]:
        return [suffix.lower() for suffix in value]


@dataclass
class SandboxRoot:
    name: str
    path: Path
    read_only: bool
    allowed_suffixes: List[str]
    text_suffixes: List[str]
    attachment_suffixes: List[str]
    max_bytes: int

    def resolve(self, relative: str) -> Path:
        relative = relative.lstrip("/")
        candidate = (self.path / relative).resolve()
        try:
            candidate.relative_to(self.path)
        except ValueError as exc:
            raise PermissionError("Path escapes sandbox root") from exc
        return candidate


class SandboxManager:
    """Manage sandboxed filesystem access for a worker."""

    def __init__(self, sandboxes: Mapping[str, SandboxConfig]):
        self.sandboxes: dict[str, SandboxRoot] = {}
        for name, cfg in sandboxes.items():
            root = Path(cfg.path).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.sandboxes[name] = SandboxRoot(
                name=name,
                path=root,
                read_only=cfg.mode == "ro",
                allowed_suffixes=list(cfg.allowed_suffixes),
                text_suffixes=list(cfg.text_suffixes),
                attachment_suffixes=list(cfg.attachment_suffixes),
                max_bytes=cfg.max_bytes,
            )

    def _sandbox_for(self, sandbox: str) -> SandboxRoot:
        if sandbox not in self.sandboxes:
            raise KeyError(f"Unknown sandbox '{sandbox}'")
        return self.sandboxes[sandbox]

    def list_files(self, sandbox: str, pattern: str = "**/*") -> List[str]:
        root = self._sandbox_for(sandbox)
        matches: List[str] = []
        for path in root.path.glob(pattern):
            try:
                rel = path.relative_to(root.path)
            except ValueError:
                continue
            matches.append(str(rel))
        return sorted(matches)

    def read_text(self, sandbox: str, path: str, *, max_chars: int = 200_000) -> str:
        root = self._sandbox_for(sandbox)
        target = root.resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        suffix = target.suffix.lower()
        if root.text_suffixes and suffix not in root.text_suffixes:
            raise PermissionError(
                f"Suffix '{suffix}' not allowed for sandbox_read_text in '{sandbox}'"
            )
        text = target.read_text(encoding="utf-8")
        if len(text) > max_chars:
            raise ValueError("File exceeds max_chars")
        return text

    def write_text(self, sandbox: str, path: str, content: str) -> str:
        root = self._sandbox_for(sandbox)
        if root.read_only:
            raise PermissionError("Sandbox is read-only")
        target = root.resolve(path)
        suffix = target.suffix.lower()
        if root.allowed_suffixes and suffix not in root.allowed_suffixes:
            raise PermissionError(f"Suffix '{suffix}' not allowed in sandbox '{sandbox}'")
        if len(content.encode("utf-8")) > root.max_bytes:
            raise ValueError("Content exceeds sandbox max_bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(root.path)
        return f"wrote {len(content)} chars to {sandbox}:{rel}"


class ApprovalRunner(Protocol):
    """Minimal approval controller interface used by sandbox tools."""

    def maybe_run(
        self,
        tool_name: str,
        payload: Mapping[str, Any],
        func: Callable[[], Any],
    ) -> Any:  # pragma: no cover - protocol only
        ...


class SandboxToolset:
    """Filesystem helpers exposed to agents."""

    def __init__(self, manager: SandboxManager, approvals: ApprovalRunner):
        self.manager = manager
        self.approvals = approvals

    def list(self, sandbox: str, pattern: str = "**/*") -> List[str]:
        return self.manager.list_files(sandbox, pattern)

    def read_text(self, sandbox: str, path: str, *, max_chars: int = 200_000) -> str:
        return self.manager.read_text(sandbox, path, max_chars=max_chars)

    def write_text(self, sandbox: str, path: str, content: str) -> Optional[str]:
        return self.approvals.maybe_run(
            "sandbox.write",
            {"sandbox": sandbox, "path": path},
            lambda: self.manager.write_text(sandbox, path, content),
        )
