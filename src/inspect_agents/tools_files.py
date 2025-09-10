"""Unified files tool with discriminated union pattern.

This module provides a single files_tool() that handles all file operations
using a discriminated union for commands: ls, read, write, edit.
"""

from __future__ import annotations

import os
import shlex as _shlex
import uuid as _uuid
from typing import TYPE_CHECKING, Annotated, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Discriminator, Field, RootModel

if TYPE_CHECKING:  # pragma: no cover
    from inspect_ai.tool._tool import Tool

from . import fs as _fs
from .exceptions import ToolException
from .fs_adapter import get_default_adapter as _get_sandbox_adapter
from .observability import log_tool_event as _base_log_tool_event
from .profiles import parse_profile as _parse_profile
from .settings import (
    typed_results_enabled as _use_typed_results,
)
from .state import Files

# Explicit module exports to clarify the public surface
__all__ = [
    # Tool factory
    "files_tool",
    # Result types
    "FileReadResult",
    "FileWriteResult",
    "FileEditResult",
    "FileDeleteResult",
    "FileTrashResult",
    "FileListResult",
    "FileMoveResult",
    "FileStatResult",
    # Parameter models
    "FilesParams",
    "LsParams",
    "ReadParams",
    "WriteParams",
    "EditParams",
    "MkdirParams",
    "MoveParams",
    "StatParams",
    "DeleteParams",
    "TrashParams",
]
# Adopt unified FS helpers from inspect_agents.fs (override local defs)
reset_sandbox_preflight_cache = _fs.reset_sandbox_preflight_cache
_ensure_sandbox_ready = _fs.ensure_sandbox_ready
_use_sandbox_fs = _fs.use_sandbox_fs
_default_tool_timeout = _fs.default_tool_timeout
_truthy = _fs.truthy
_fs_root = _fs.fs_root
_max_bytes = _fs.max_bytes
_deny_symlink = _fs.deny_symlink
_validate_sandbox_path = _fs.validate_sandbox_path


# ---------------------------------------------------------------------------
# Observability enrichment: include profile context in files:* tool events
# ---------------------------------------------------------------------------


def _obs_profile_extra() -> dict[str, object]:
    """Return optional profile/fs_root fields for observability logs.

    Controlled by env flags:
    - INSPECT_OBS_INCLUDE_PROFILE: when truthy, include t/h/n (if available)
      and fs_root in the tool_event payload.
    - INSPECT_OBS_REDACT_PATHS: when truthy, redact path-like values
      (fs_root) to avoid leaking host paths in logs.
    """
    try:
        if not _truthy(os.getenv("INSPECT_OBS_INCLUDE_PROFILE")):
            return {}

        # fs_root is always included when the flag is enabled
        root = _fs_root()
        if _truthy(os.getenv("INSPECT_OBS_REDACT_PATHS")):
            try:
                # Redact by keeping only the basename; if that fails, mask
                import os as _os

                redacted_root = _os.path.basename(root.rstrip(_os.sep)) or "[redacted]"
            except Exception:
                redacted_root = "[redacted]"
            fs_root_val: object = redacted_root
        else:
            fs_root_val = root

        # Parse INSPECT_PROFILE if present; ignore on parse errors
        t: str | None = None
        h: str | None = None
        n: str | None = None
        raw = (os.getenv("INSPECT_PROFILE") or "").strip()
        if raw:
            try:
                t, h, n = _parse_profile(raw)
            except Exception:
                # Do not raise; simply omit t/h/n when invalid
                t = h = n = None

        out: dict[str, object] = {"fs_root": fs_root_val}
        if t and h and n:
            out.update({"t": t, "h": h, "n": n})
        return out
    except Exception:
        # Never let observability impact control flow
        return {}


def _merge_obs_extra(extra: dict[str, object] | None) -> dict[str, object] | None:
    """Merge profile extra with provided extra without overwriting its keys.

    When disabled via env, returns the original extra unchanged.
    """
    try:
        base = _obs_profile_extra()
        if not base:
            return extra
        if extra is None:
            return base
        # Preserve existing keys by letting `extra` win on conflicts
        merged = dict(base)
        merged.update(extra)
        return merged
    except Exception:
        return extra


def _log_tool_event(
    *,
    name: str,
    phase: str,
    args: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
    t0: float | None = None,
) -> float:
    """Thin wrapper that augments files:* events with profile context.

    Mirrors the upstream signature and delegates to observability.log_tool_event.
    """
    # Only augment files:* events
    if isinstance(name, str) and name.startswith("files:"):
        extra = _merge_obs_extra(extra)
    return _base_log_tool_event(name=name, phase=phase, args=args, extra=extra, t0=t0)


def _chunk_size_lines() -> int:
    """Return chunk size for streaming reads from environment variable."""
    import os

    try:
        return int(os.getenv("INSPECT_AGENTS_FS_CHUNK_LINES", "512"))
    except (ValueError, TypeError):
        return 512


# Optional path policy checks (stubs by default)
def _check_policy(path: str, op: str) -> None:
    """Optional policy hook to validate path operations.

    By default, no policy is enforced. Repositories may monkeypatch this
    symbol to enforce allow/deny rules in CI or specific environments.
    """
    return


def _match_path_policy(path: str) -> tuple[str | None, str | None]:
    """Return a tuple of (kind, rule) describing the matching policy.

    This is used for logging when a policy denial occurs. Default stub returns
    (None, None).
    """
    return None, None


_check_policy = _fs.check_policy
_match_path_policy = _fs.match_path_policy


# Result types
class FileReadResult(BaseModel):
    """Typed result for read operations."""

    lines: list[str]
    summary: str


class FileWriteResult(BaseModel):
    """Typed result for write operations."""

    path: str
    summary: str


class FileEditResult(BaseModel):
    """Typed result for edit operations.

    When `dry_run=True`, no mutation is performed; `replaced` reflects the
    number of replacements that would have been applied given current file
    contents and the `replace_all` flag.
    """

    path: str
    replaced: int
    summary: str


class FileDeleteResult(BaseModel):
    """Typed result for delete operations."""

    path: str
    summary: str


class FileTrashResult(BaseModel):
    """Typed result for trash operations (audited delete)."""

    src: str
    dst: str
    summary: str


class FileListResult(BaseModel):
    """Typed result for ls operations."""

    files: list[str]


class FileMoveResult(BaseModel):
    """Typed result for move operations."""

    src: str
    dst: str
    summary: str


class FileStatResult(BaseModel):
    """Typed result for stat operations."""

    path: str
    exists: bool
    is_dir: bool
    size: int | None


# ---------------------------------------------------------------------------
# Per-path async locks to prevent torn writes and overlapping edits
# ---------------------------------------------------------------------------
_FILE_LOCKS: dict[str, anyio.Lock] = {}


def _lock_key(path: str, instance: str | None) -> str:
    mode = "sandbox" if _use_sandbox_fs() else "store"
    ns = (instance or "default") if mode == "store" else "global"
    return f"{mode}:{ns}:{path}"


def _get_lock(path: str, instance: str | None) -> anyio.Lock:
    key = _lock_key(path, instance)
    lock = _FILE_LOCKS.get(key)
    if lock is None:
        lock = anyio.Lock()
        _FILE_LOCKS[key] = lock
    return lock


# Parameter schemas for each command
class BaseFileParams(BaseModel):
    """Base parameters for all file operations."""

    instance: str | None = Field(None, description="Optional Files instance for isolation")

    # Pydantic v2 style config
    model_config = ConfigDict(extra="forbid")


class LsParams(BaseFileParams):
    """Parameters for ls command."""

    command: Literal["ls"] = "ls"


class ReadParams(BaseFileParams):
    """Parameters for read command."""

    command: Literal["read"] = "read"
    file_path: str = Field(description="Path to read")
    offset: int = Field(0, description="Line offset (0-based)")
    limit: int = Field(2000, description="Max lines to return")


class WriteParams(BaseFileParams):
    """Parameters for write command."""

    command: Literal["write"] = "write"
    file_path: str = Field(description="Path to write")
    content: str = Field(description="Content to write")


class EditParams(BaseFileParams):
    """Parameters for edit command."""

    command: Literal["edit"] = "edit"
    file_path: str = Field(description="Path to edit")
    old_string: str = Field(description="String to replace")
    new_string: str = Field(description="Replacement string")
    replace_all: bool = Field(False, description="Replace all occurrences if true")
    dry_run: bool = Field(False, description="When true, compute result without persisting changes")
    expected_count: int | None = Field(
        None,
        description=(
            "Optional expected number of replacements to perform. When set, the edit "
            "will validate that exactly this many replacements would occur and raise "
            "an error on mismatch."
        ),
    )


class MkdirParams(BaseFileParams):
    """Parameters for mkdir command."""

    command: Literal["mkdir"] = "mkdir"
    dir_path: str = Field(description="Directory path to create")


class MoveParams(BaseFileParams):
    """Parameters for move command."""

    command: Literal["move"] = "move"
    src_path: str = Field(description="Source path")
    dst_path: str = Field(description="Destination path")


class StatParams(BaseFileParams):
    """Parameters for stat command."""

    command: Literal["stat"] = "stat"
    path: str = Field(description="Path to stat")
    dry_run: bool = Field(
        False,
        description=("When true, compute counts and validate but do not modify the file."),
    )


class DeleteParams(BaseFileParams):
    """Parameters for delete command."""

    command: Literal["delete"] = "delete"
    file_path: str = Field(description="Path to delete")


class TrashParams(BaseFileParams):
    """Parameters for trash command (audited delete)."""

    command: Literal["trash"] = "trash"
    file_path: str = Field(description="Path to move into trash")


class FilesParams(RootModel):
    """Discriminated union of all file operation parameters."""

    root: Annotated[
        LsParams
        | ReadParams
        | WriteParams
        | EditParams
        | DeleteParams
        | TrashParams
        | MkdirParams
        | MoveParams
        | StatParams,
        Discriminator("command"),
    ]


# Execution functions (can be used by wrapper tools)
async def execute_ls(params: LsParams) -> list[str] | FileListResult:
    """Execute ls command.

    Sandbox vs store:
    - Sandbox: proxies via `bash_session` running `ls -1` inside the sandbox.
    - Store: lists files tracked by the in‑memory `Files` store for this instance.

    Notes: falls back from sandbox to store if sandbox is unavailable.
    """
    from inspect_ai.util._store_model import store_as

    # Import lazily to avoid circular import during module import
    # import provided at module level: from .observability import log_tool_event as _log_tool_event

    _t0 = _log_tool_event(
        name="files:ls",
        phase="start",
        args={"instance": params.instance},
    )

    # Sandbox FS mode: use adapter to run ls via bash session
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        if await adapter.preflight("bash session"):
            try:
                root = _fs_root()
                file_list = await adapter.ls(root)

                # Optional policy enforcement on ls results (feature-flagged)
                if _truthy(os.getenv("INSPECT_FS_POLICY_ENFORCE_READS")):
                    try:
                        # Filter out denied paths; emit a structured error for each denied entry
                        allowed: list[str] = []
                        for name in file_list:
                            abs_path = os.path.join(root, name)
                            kind, rule = _match_path_policy(abs_path)
                            if kind == "deny":
                                _log_tool_event(
                                    name="files:ls",
                                    phase="error",
                                    extra={
                                        "ok": False,
                                        "error": "PolicyDenied",
                                        "policy_rule": rule,
                                        "path": name,
                                    },
                                    t0=_t0,
                                )
                                continue
                            allowed.append(name)
                        # Ensure deterministic ordering when policy is enforced
                        file_list = sorted(allowed)
                    except Exception:
                        # Policy evaluation must not crash ls; fall back to original list
                        pass

                if _use_typed_results():
                    _log_tool_event(
                        name="files:ls",
                        phase="end",
                        extra={"ok": True, "count": len(file_list)},
                        t0=_t0,
                    )
                    return FileListResult(files=file_list)
                _log_tool_event(
                    name="files:ls",
                    phase="end",
                    extra={"ok": True, "count": len(file_list)},
                    t0=_t0,
                )
                return file_list
            except Exception:
                # Graceful fallback to store-backed mode
                pass

    # Store-backed mode (in-memory Files store) with timeout guard
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        file_list = files.list_files()

    if _use_typed_results():
        _log_tool_event(
            name="files:ls",
            phase="end",
            extra={"ok": True, "count": len(file_list) if isinstance(file_list, list) else len(file_list.files)},
            t0=_t0,
        )
        return FileListResult(files=file_list)
    _log_tool_event(
        name="files:ls",
        phase="end",
        extra={"ok": True, "count": len(file_list) if isinstance(file_list, list) else len(file_list.files)},
        t0=_t0,
    )
    return file_list


async def execute_read(params: ReadParams) -> str | FileReadResult:
    """Execute read command.

    Sandbox vs store:
    - Sandbox: routes through `text_editor('view')` with `view_range=[start,end]`.
    - Store: reads from the in‑memory `Files` store for this instance.

    Limits: returns at most `limit` lines (default 2000), truncates each line to 2000
    characters, and enforces byte ceiling from INSPECT_AGENTS_FS_MAX_BYTES to prevent OOM.
    In sandbox mode, the adapter validates paths against the configured root and
    denies symlinks before performing IO.
    """
    from inspect_ai.util._store_model import store_as

    # import provided at module level: from .observability import log_tool_event as _log_tool_event

    _t0 = _log_tool_event(
        name="files:read",
        phase="start",
        args={
            "file_path": params.file_path,
            "offset": params.offset,
            "limit": params.limit,
            "instance": params.instance,
        },
    )

    def _format_lines(content_lines: list[str], start_line_num: int = 1, *, pad: bool = True) -> tuple[list[str], str]:
        """Format lines with numbering and return both list and joined string.

        Args:
            content_lines: lines to format
            start_line_num: starting line number (1-based)
            pad: when True, left-pad line numbers (legacy store mode); when False, no padding
        """
        out_lines: list[str] = []
        ln = start_line_num
        for line_content in content_lines:
            if len(line_content) > 2000:
                line_content = line_content[:2000]
            if pad:
                formatted_line = f"{ln:6d}\t{line_content}"
            else:
                formatted_line = f"{ln}\t{line_content}"
            out_lines.append(formatted_line)
            ln += 1
        return out_lines, "\n".join(out_lines)

    empty_message = "System reminder: File exists but has empty contents"

    # Sandbox FS mode: delegate to adapter (sed via bash when possible, else editor)
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        # Validate path; propagate access errors (must not read outside root)
        validated_path = adapter.validate(params.file_path)
        # Symlink denial (adapter itself no-ops when sandbox is unavailable)
        await adapter.deny_symlink(validated_path)

        # Optional policy enforcement for reads (feature-flagged)
        if _truthy(os.getenv("INSPECT_FS_POLICY_ENFORCE_READS")):
            try:
                _check_policy(validated_path, "read")
            except ToolException:
                # Emit structured error with matching rule for observability
                kind, rule = _match_path_policy(validated_path)
                _log_tool_event(
                    name="files:read",
                    phase="error",
                    extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                    t0=_t0,
                )
                raise

        try:
            # Optional byte preflight via wc -c (no-op if bash is unavailable)
            file_bytes = await adapter.wc_bytes(validated_path)
            if file_bytes is not None:
                max_bytes = _max_bytes()
                if file_bytes > max_bytes:
                    _log_tool_event(
                        name="files:read",
                        phase="error",
                        extra={
                            "ok": False,
                            "error": "FileSizeExceeded",
                            "actual_bytes": file_bytes,
                            "max_bytes": max_bytes,
                        },
                        t0=_t0,
                    )
                    raise ToolException(
                        f"File exceeds maximum size limit: {file_bytes:,} bytes > {max_bytes:,} bytes. "
                        f"Use a smaller limit parameter or increase INSPECT_AGENTS_FS_MAX_BYTES."
                    )

            # Compute 1-based start and inclusive end; -1 means EOF
            start_line = max(1, int(params.offset) + 1)
            max_lines = 0 if (params.limit is None or params.limit <= 0) else int(params.limit)

            # Try view_chunks first if available, with fallback to view
            chunk_size = _chunk_size_lines()
            raw = ""

            if hasattr(adapter, "view_chunks"):
                try:
                    chunks = []
                    async for chunk in adapter.view_chunks(
                        validated_path, start_line, max_lines, chunk_size_lines=chunk_size
                    ):
                        chunks.append(chunk)
                    raw = "\n".join(chunks)
                    # If we got empty content, fall back to view method
                    if not raw.strip():
                        raise Exception("Empty content from view_chunks, trying view fallback")
                except Exception:
                    # Fall back to regular view
                    end_line = -1 if max_lines <= 0 else (start_line + max_lines - 1)
                    raw = await adapter.view(validated_path, start_line, end_line)
            else:
                # Regular behavior - use view with computed end_line
                end_line = -1 if max_lines <= 0 else (start_line + max_lines - 1)
                raw = await adapter.view(validated_path, start_line, end_line)

            if raw is None or str(raw).strip() == "":
                if _use_typed_results():
                    _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
                    return FileReadResult(lines=[], summary=empty_message)
                _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
                return empty_message

            # Format returned content with padded numbering (match store mode)
            lines = str(raw).splitlines()
            # Enforce requested limit defensively in case sed stub ignores the range
            if params.limit is not None and params.limit > 0:
                lines = lines[: int(params.limit)]
            # Legacy string output uses padded numbering; typed results do not
            padded_lines, joined_output = _format_lines(lines, start_line, pad=True)

            if _use_typed_results():
                nopad_lines, _ = _format_lines(lines, start_line, pad=False)
                _log_tool_event(
                    name="files:read",
                    phase="end",
                    extra={"ok": True, "lines": len(nopad_lines)},
                    t0=_t0,
                )
                return FileReadResult(
                    lines=nopad_lines,
                    summary=f"Read {len(nopad_lines)} lines from file_path={params.file_path} (sandbox mode)",
                )
            _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(padded_lines)}, t0=_t0)
            return joined_output
        except ToolException:
            # Re-raise ToolExceptions (like size limit exceeded) without fallback
            raise
        except Exception:
            # Secondary fallback: attempt a direct bash 'sed -n' read if available
            try:
                import shlex as _shlex

                from inspect_ai.tool._tools._bash_session import bash_session as _bash_session

                start_line = max(1, int(params.offset) + 1)
                end_line = -1 if (params.limit is None or params.limit <= 0) else (start_line + int(params.limit) - 1)
                sed_range = f"{start_line},{end_line}p" if end_line != -1 else f"{start_line},$p"
                bash = _bash_session()
                with anyio.fail_after(_default_tool_timeout()):
                    sed_result = await bash(
                        action="run", command=f"sed -n '{sed_range}' {_shlex.quote(validated_path)}"
                    )
                raw2 = getattr(sed_result, "stdout", None)
                if raw2 and str(raw2).strip() != "":
                    lines = str(raw2).splitlines()
                    if params.limit is not None and params.limit > 0:
                        lines = lines[: int(params.limit)]
                    if _use_typed_results():
                        nopad_lines, _ = _format_lines(lines, start_line, pad=False)
                        _log_tool_event(
                            name="files:read",
                            phase="end",
                            extra={"ok": True, "lines": len(nopad_lines)},
                            t0=_t0,
                        )
                        return FileReadResult(
                            lines=nopad_lines,
                            summary=f"Read {len(nopad_lines)} lines from file_path={params.file_path} (sandbox mode)",
                        )
                    _padded, joined_output = _format_lines(lines, start_line, pad=True)
                    _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(lines)}, t0=_t0)
                    return joined_output
            except Exception:
                # Graceful fallback to store-backed mode
                pass

    # Store-backed with timeout guard
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        content = files.get_file(params.file_path)
    if content is None:
        # As a last resort in sandbox mode, try a direct bash read before erroring
        if _use_sandbox_fs():
            try:
                import shlex as _shlex

                from inspect_ai.tool._tools._bash_session import bash_session as _bash_session

                start_line = max(1, int(params.offset) + 1)
                end_line = -1 if (params.limit is None or params.limit <= 0) else (start_line + int(params.limit) - 1)
                sed_range = f"{start_line},{end_line}p" if end_line != -1 else f"{start_line},$p"
                bash = _bash_session()
                with anyio.fail_after(_default_tool_timeout()):
                    sed_result = await bash(
                        action="run", command=f"sed -n '{sed_range}' {_shlex.quote(params.file_path)}"
                    )
                raw3 = getattr(sed_result, "stdout", None)
                if raw3 and str(raw3).strip() != "":
                    lines = str(raw3).splitlines()
                    if params.limit is not None and params.limit > 0:
                        lines = lines[: int(params.limit)]
                    if _use_typed_results():
                        nopad_lines, _ = _format_lines(lines, start_line, pad=False)
                        _log_tool_event(
                            name="files:read",
                            phase="end",
                            extra={"ok": True, "lines": len(nopad_lines)},
                            t0=_t0,
                        )
                        return FileReadResult(
                            lines=nopad_lines,
                            summary=f"Read {len(nopad_lines)} lines from file_path={params.file_path} (sandbox mode)",
                        )
                    _padded, joined_output = _format_lines(lines, start_line, pad=True)
                    _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(lines)}, t0=_t0)
                    return joined_output
            except Exception:
                pass
        _log_tool_event(
            name="files:read",
            phase="error",
            extra={"ok": False, "error": "FileNotFound"},
            t0=_t0,
        )
        raise ToolException(  # noqa: N806
            f"File '{params.file_path}' not found. Please check the file path and ensure the file exists."
        )

    if not content or content.strip() == "":
        if _use_typed_results():
            _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
            return FileReadResult(lines=[], summary=empty_message)
        _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
        return empty_message

    # Enforce byte ceiling to prevent OOM and long stalls
    content_bytes = len(content.encode("utf-8"))
    max_bytes = _max_bytes()
    if content_bytes > max_bytes:
        _log_tool_event(
            name="files:read",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": content_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        raise ToolException(
            f"File exceeds maximum size limit: {content_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Use a smaller limit parameter or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    lines = content.splitlines()
    start_idx = params.offset
    end_idx = min(start_idx + params.limit, len(lines))

    if start_idx >= len(lines):
        raise ToolException(  # noqa: N806
            f"Line offset {params.offset} exceeds file length ({len(lines)} lines). "
            f"Use an offset between 0 and {len(lines) - 1}."
        )

    selected_lines = lines[start_idx:end_idx]
    # Format with correct line numbers starting from offset + 1
    _padded, joined_output = _format_lines(selected_lines, start_idx + 1, pad=True)

    if _use_typed_results():
        nopad_lines, _ = _format_lines(selected_lines, start_idx + 1, pad=False)
        _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(nopad_lines)}, t0=_t0)
        return FileReadResult(
            lines=nopad_lines,
            summary=(
                f"Read {len(nopad_lines)} lines from {params.file_path} "
                f"(lines {start_idx + 1}-{start_idx + len(nopad_lines)})"
            ),
        )
    _log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(selected_lines)}, t0=_t0)
    return joined_output


async def execute_write(params: WriteParams) -> str | FileWriteResult:
    """Execute write command.

    Sandbox vs store:
    - Sandbox: routes through `text_editor('create')` to write a file.
    - Store: writes to the in‑memory `Files` store for this instance.

    Limits: enforces byte ceiling from INSPECT_AGENTS_FS_MAX_BYTES to prevent OOM.
    In sandbox mode, the adapter validates the path against the root and denies
    symlinks before writing. Content is not sanitized; ensure trusted input.
    """
    from inspect_ai.util._store_model import store_as

    # import provided at module level: from .observability import log_tool_event as _log_tool_event

    _t0 = _log_tool_event(
        name="files:write",
        phase="start",
        args={"file_path": params.file_path, "content_len": len(params.content), "instance": params.instance},
    )

    # Read-only guard in sandbox mode
    if (
        _use_sandbox_fs()
        and _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY"))
        and (os.getenv("INSPECT_SANDBOX_PREFLIGHT", "auto").strip().lower() != "skip")
    ):
        _log_tool_event(name="files:write", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=_t0)
        raise ToolException("SandboxReadOnly")

    # Enforce byte ceiling to prevent OOM and long stalls
    content_bytes = len(params.content.encode("utf-8"))
    max_bytes = _max_bytes()
    if content_bytes > max_bytes:
        _log_tool_event(
            name="files:write",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": content_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        raise ToolException(
            f"File content exceeds maximum size limit: {content_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Consider breaking the content into smaller files or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    summary = f"Updated file {params.file_path}"

    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        if await adapter.preflight("editor"):
            # Validate path is within configured root and deny symlinks
            validated_path = adapter.validate(params.file_path)
            await adapter.deny_symlink(validated_path)
            # Policy check (sandbox) — optional
            try:
                _policy = globals().get("_check_policy")
                if _policy is not None:
                    _policy(validated_path, "write")
            except ToolException:
                _match = globals().get("_match_path_policy")
                kind, rule = (None, None)
                if _match is not None:
                    kind, rule = _match(validated_path)
                _log_tool_event(
                    name="files:write",
                    phase="error",
                    extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                    t0=_t0,
                )
                raise

            # Serialize writes per-path and prefer atomic temp+rename when bash is available
            lock = _get_lock(validated_path, params.instance)
            async with lock:
                try:
                    try:
                        from inspect_ai.tool._tools._bash_session import bash_session as _bash_session
                    except Exception:
                        _bash_session = None  # type: ignore

                    tmp_path = f"{validated_path}.tmp-{_uuid.uuid4().hex}"
                    # Write temp file via editor (consistent code path)
                    await adapter.create(tmp_path, params.content)

                    # If bash session is available, try atomic move into place
                    if _bash_session is not None and await adapter.preflight("bash session"):
                        bash = _bash_session()
                        cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                        try:
                            with anyio.fail_after(_default_tool_timeout()):
                                await bash(action="run", command=cmd)  # type: ignore[misc]
                        except TypeError:
                            # Unsupported signature (no `run(command=...)`).
                            await adapter.create(validated_path, params.content)
                        except Exception:
                            # Any runtime failure → fallback to non-atomic write.
                            await adapter.create(validated_path, params.content)
                    else:
                        # Fallback: write directly (non-atomic)
                        await adapter.create(validated_path, params.content)

                    # Ensure destination content is present even if mv was a no-op in stub environments
                    try:
                        await adapter.create(validated_path, params.content)
                    except Exception:
                        # Best-effort only; verification/writes may fail silently in some stubs
                        pass

                    if _use_typed_results():
                        _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
                        return FileWriteResult(path=params.file_path, summary=summary + " (sandbox mode)")
                    _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
                    return summary
                except Exception:
                    pass

    # Store-backed with timeout guard
    # Keep store-mode simple: single put_file to the final key (no temp swap)
    # Policy check (store) — optional
    try:
        _policy = globals().get("_check_policy")
        if _policy is not None:
            _policy(os.path.join(_fs_root(), params.file_path), "write")
    except ToolException:
        _match = globals().get("_match_path_policy")
        kind, rule = (None, None)
        if _match is not None:
            kind, rule = _match(os.path.join(_fs_root(), params.file_path))
        _log_tool_event(
            name="files:write",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise
    lock = _get_lock(params.file_path, params.instance)
    async with lock:
        with anyio.fail_after(_default_tool_timeout()):
            files = store_as(Files, instance=params.instance)
            files.put_file(params.file_path, params.content)

    if _use_typed_results():
        _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
        return FileWriteResult(path=params.file_path, summary=summary)
    _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
    return summary


async def execute_edit(params: EditParams) -> str | FileEditResult:
    """Execute edit command.

    Sandbox vs store:
    - Sandbox: routes through `text_editor('str_replace')`; replacement count is
      not returned by the underlying tool.
    - Store: edits the in‑memory `Files` store and reports replacement count.

    Limits: enforces byte ceiling from INSPECT_AGENTS_FS_MAX_BYTES to prevent OOM.
    In sandbox mode, the adapter validates the path and denies symlinks before
    applying the edit. String replacement is not validated; ensure trusted input.
    """
    from inspect_ai.util._store_model import store_as

    # import provided at module level: from .observability import log_tool_event as _log_tool_event

    _t0 = _log_tool_event(
        name="files:edit",
        phase="start",
        args={
            "file_path": params.file_path,
            "old_len": len(params.old_string),
            "new_len": len(params.new_string),
            "replace_all": params.replace_all,
            "expected_count": params.expected_count,
            "instance": params.instance,
        },
    )
    # Read-only guard in sandbox mode
    if (
        _use_sandbox_fs()
        and _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY"))
        and (os.getenv("INSPECT_SANDBOX_PREFLIGHT", "auto").strip().lower() != "skip")
    ):
        _log_tool_event(name="files:edit", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=_t0)
        raise ToolException("SandboxReadOnly")
    # For sandbox mode, we need to preflight check file size before edit
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        if await adapter.preflight("editor"):
            # Validate path is within configured root first (before try block to prevent fallback)
            validated_path = adapter.validate(params.file_path)

            # Deny symlinks for security
            await adapter.deny_symlink(validated_path)
            # Policy check (sandbox) — optional
            try:
                _policy = globals().get("_check_policy")
                if _policy is not None:
                    _policy(validated_path, "edit")
            except ToolException:
                _match = globals().get("_match_path_policy")
                kind, rule = (None, None)
                if _match is not None:
                    kind, rule = _match(validated_path)
                _log_tool_event(
                    name="files:edit",
                    phase="error",
                    extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                    t0=_t0,
                )
                raise

            # Serialize edits per-path and prefer atomic temp+rename using bash when possible
            lock = _get_lock(validated_path, params.instance)
            try:
                async with lock:
                    # Preflight: actual byte size via wc -c when available
                    current_bytes = await adapter.wc_bytes(validated_path)
                    max_bytes = _max_bytes()
                    if current_bytes is not None and current_bytes > max_bytes:
                        _log_tool_event(
                            name="files:edit",
                            phase="error",
                            extra={
                                "ok": False,
                                "error": "FileSizeExceeded",
                                "actual_bytes": current_bytes,
                                "max_bytes": max_bytes,
                            },
                            t0=_t0,
                        )
                        raise ToolException(
                            f"File exceeds maximum size limit: {current_bytes:,} bytes > {max_bytes:,} bytes. "
                            f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
                        )

                    # Optional pre-read for counting/mismatch checks
                    counted_occurrences: int | None = None
                    if params.expected_count is not None or params.dry_run:
                        try:
                            raw = await adapter.view(validated_path, 1, -1)
                            text = "" if raw is None else str(raw)
                        except Exception:
                            text = ""
                        if params.old_string not in text:
                            _log_tool_event(
                                name="files:edit",
                                phase="error",
                                extra={"ok": False, "error": "StringNotFound"},
                                t0=_t0,
                            )
                            raise ToolException(
                                f"String '{params.old_string}' not found in file '{params.file_path}'. "
                                f"Please check the exact text to replace."
                            )
                        counted_occurrences = text.count(params.old_string)

                        if params.expected_count is not None:
                            would_replace = counted_occurrences if params.replace_all else 1
                            if int(params.expected_count) != int(would_replace):
                                _log_tool_event(
                                    name="files:edit",
                                    phase="error",
                                    extra={
                                        "ok": False,
                                        "error": "ExpectedCountMismatch",
                                        "expected": params.expected_count,
                                        "actual": would_replace,
                                    },
                                    t0=_t0,
                                )
                                raise ToolException(
                                    f"ExpectedCountMismatch: expected {params.expected_count}, got {would_replace}"
                                )

                    # Dry run: no write
                    if params.dry_run:
                        replaced = (
                            (counted_occurrences if params.replace_all else 1) if counted_occurrences is not None else 1
                        )
                        summary = f"(dry_run) Would update file {params.file_path} replacing {replaced} occurrence(s)"
                        if _use_typed_results():
                            _log_tool_event(
                                name="files:edit",
                                phase="end",
                                extra={"ok": True, "replaced": replaced, "dry_run": True},
                                t0=_t0,
                            )
                            return FileEditResult(path=params.file_path, replaced=replaced, summary=summary)
                        _log_tool_event(
                            name="files:edit",
                            phase="end",
                            extra={"ok": True, "replaced": replaced, "dry_run": True},
                            t0=_t0,
                        )
                        return summary

                    # Compute updated content for atomic swap
                    try:
                        raw_all = await adapter.view(validated_path, 1, -1)
                    except Exception:
                        raw_all = ""
                    text_all = "" if raw_all is None else str(raw_all)
                    if params.replace_all:
                        replacement_count = text_all.count(params.old_string)
                        updated_text = text_all.replace(params.old_string, params.new_string)
                    else:
                        replacement_count = 1 if params.old_string in text_all else 0
                        updated_text = text_all.replace(params.old_string, params.new_string, 1)

                    # Byte ceiling on updated text
                    updated_bytes = len(updated_text.encode("utf-8"))
                    if updated_bytes > max_bytes:
                        _log_tool_event(
                            name="files:edit",
                            phase="error",
                            extra={
                                "ok": False,
                                "error": "FileSizeExceeded",
                                "actual_bytes": updated_bytes,
                                "max_bytes": max_bytes,
                            },
                            t0=_t0,
                        )
                        raise ToolException(
                            f"Edit would result in file exceeding maximum size limit: {updated_bytes:,} bytes > {max_bytes:,} bytes. "
                            f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
                        )

                    # Atomic write: temp create then mv into place when bash is available
                    try:
                        from inspect_ai.tool._tools._bash_session import bash_session as _bash_session
                    except Exception:
                        _bash_session = None  # type: ignore

                    tmp_path = f"{validated_path}.tmp-{_uuid.uuid4().hex}"

                    try:
                        await adapter.create(tmp_path, updated_text)
                        if _bash_session is not None and await adapter.preflight("bash session"):
                            bash = _bash_session()
                            cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                            try:
                                with anyio.fail_after(_default_tool_timeout()):
                                    await bash(action="run", command=cmd)  # type: ignore[misc]
                            except TypeError:
                                await adapter.create(validated_path, updated_text)
                            except Exception:
                                await adapter.create(validated_path, updated_text)
                        else:
                            # Non-atomic editor replacement
                            await adapter.create(validated_path, updated_text)

                        # Verify destination exists; if move failed silently, write directly
                        try:
                            exists, _, size = await adapter.stat(validated_path)
                            needs_write = (not exists) or (size == 0 and len(updated_text or "") > 0)
                            if not needs_write:
                                try:
                                    cur = await adapter.view(validated_path, 1, -1)
                                    cur_text = "" if cur is None else str(cur)
                                    if cur_text != updated_text:
                                        needs_write = True
                                except Exception:
                                    # If verification fails, conservatively attempt write
                                    needs_write = True
                            if needs_write:
                                await adapter.create(validated_path, updated_text)
                        except Exception:
                            pass
                    except TimeoutError:
                        # Allow store-mode fallback on sandbox timeouts
                        raise
                    except AttributeError:
                        # Some adapters used in tests may not implement `create`; fall back to str_replace
                        try:
                            _ = await adapter.str_replace(validated_path, params.old_string, params.new_string)  # type: ignore[attr-defined]
                        except Exception:
                            raise

                    replaced = replacement_count if params.replace_all else (1 if replacement_count > 0 else 0)
                    summary = f"Updated file {params.file_path} (sandbox mode)"
                    if _use_typed_results():
                        _log_tool_event(
                            name="files:edit",
                            phase="end",
                            extra={"ok": True, "replaced": replaced},
                            t0=_t0,
                        )
                        return FileEditResult(path=params.file_path, replaced=replaced, summary=summary)
                    _log_tool_event(
                        name="files:edit",
                        phase="end",
                        extra={"ok": True, "replaced": replaced},
                        t0=_t0,
                    )
                    return summary
            except TimeoutError:
                # Let store-mode path handle the operation on timeouts
                pass

    # Store-backed: perform the full read-modify-write under a per-path lock
    lock = _get_lock(params.file_path, params.instance)
    async with lock:
        with anyio.fail_after(_default_tool_timeout()):
            files = store_as(Files, instance=params.instance)
            content = files.get_file(params.file_path)
        if content is None:
            _log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "FileNotFound"},
                t0=_t0,
            )
            raise ToolException(  # noqa: N806
                f"File '{params.file_path}' not found. Please check the file path and ensure the file exists."
            )

        if params.old_string not in content:
            _log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "StringNotFound"},
                t0=_t0,
            )
            raise ToolException(
                f"String '{params.old_string}' not found in file '{params.file_path}'. "
                f"Please check the exact text to replace."
            )

    # Policy check (store) — optional
    try:
        _policy = globals().get("_check_policy")
        if _policy is not None:
            _policy(os.path.join(_fs_root(), params.file_path), "edit")
    except ToolException:
        _match = globals().get("_match_path_policy")
        kind, rule = (None, None)
        if _match is not None:
            kind, rule = _match(os.path.join(_fs_root(), params.file_path))
        _log_tool_event(
            name="files:edit",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise

    # Count replacements for accurate reporting
    if params.replace_all:
        replacement_count = content.count(params.old_string)
        updated = content.replace(params.old_string, params.new_string)
    else:
        replacement_count = 1
        updated = content.replace(params.old_string, params.new_string, 1)

    # Validate expected_count when provided
    if params.expected_count is not None:
        expected = int(params.expected_count)
        actual = replacement_count if params.replace_all else 1
        if expected != actual:
            _log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "ExpectedCountMismatch", "expected": expected, "actual": actual},
                t0=_t0,
            )
            raise ToolException(f"ExpectedCountMismatch: expected {expected}, got {actual}")

    # Enforce byte ceiling on the updated content
    updated_bytes = len(updated.encode("utf-8"))
    max_bytes = _max_bytes()
    if updated_bytes > max_bytes:
        _log_tool_event(
            name="files:edit",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": updated_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        raise ToolException(
            f"Edit would result in file exceeding maximum size limit: {updated_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    # If dry_run, do not persist changes
    if params.dry_run:
        to_report = replacement_count if params.replace_all else 1
        summary = f"(dry_run) Would update file {params.file_path} replacing {to_report} occurrence(s)"
        if _use_typed_results():
            _log_tool_event(
                name="files:edit",
                phase="end",
                extra={"ok": True, "replaced": to_report, "dry_run": True},
                t0=_t0,
            )
            return FileEditResult(path=params.file_path, replaced=to_report, summary=summary)
        _log_tool_event(
            name="files:edit",
            phase="end",
            extra={"ok": True, "replaced": to_report, "dry_run": True},
            t0=_t0,
        )
        return summary

    # Single write in store mode
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        files.put_file(params.file_path, updated)

    summary = f"Updated file {params.file_path}"
    to_report = replacement_count if params.replace_all else 1
    if _use_typed_results():
        _log_tool_event(
            name="files:edit",
            phase="end",
            extra={"ok": True, "replaced": to_report},
            t0=_t0,
        )
        return FileEditResult(path=params.file_path, replaced=to_report, summary=summary)
    _log_tool_event(name="files:edit", phase="end", extra={"ok": True, "replaced": to_report}, t0=_t0)
    return summary


async def execute_delete(params: DeleteParams) -> str | FileDeleteResult:
    """Execute delete command.

    Sandbox vs store:
    - Sandbox: delete is disabled to avoid accidental host‑FS deletion.
    - Store: delete is supported against the in‑memory `Files` store.
    """
    from inspect_ai.util._store_model import store_as

    # import provided at module level: from .observability import log_tool_event as _log_tool_event

    _t0 = _log_tool_event(
        name="files:delete",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    # Sandbox mode: disabled for safety; if read-only flag is set, return specific error
    if _use_sandbox_fs() and _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
        _log_tool_event(name="files:delete", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=_t0)
        raise ToolException("SandboxReadOnly")

    # Sandbox mode: disabled for safety
    if _use_sandbox_fs():
        _log_tool_event(
            name="files:delete",
            phase="error",
            extra={"ok": False, "error": "SandboxUnsupported"},
            t0=_t0,
        )
        # Canonical short error code expected by tests/docs
        raise ToolException("SandboxUnsupported")

    # Store-backed with timeout guard
    # Policy check (store) — enforce before deletion
    try:
        _check_policy(os.path.join(_fs_root(), params.file_path), "delete")
    except ToolException:
        kind, rule = _match_path_policy(os.path.join(_fs_root(), params.file_path))
        _log_tool_event(
            name="files:delete",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        # Check if file exists before deletion for proper messaging
        file_exists = files.get_file(params.file_path) is not None
        files.delete_file(params.file_path)

    if file_exists:
        summary = f"Deleted file {params.file_path}"
    else:
        summary = f"File {params.file_path} did not exist (delete operation was idempotent)"

    if _use_typed_results():
        _log_tool_event(name="files:delete", phase="end", extra={"ok": True, "existed": file_exists}, t0=_t0)
        return FileDeleteResult(path=params.file_path, summary=summary)
    _log_tool_event(name="files:delete", phase="end", extra={"ok": True, "existed": file_exists}, t0=_t0)
    return summary


async def execute_trash(params: TrashParams) -> str | FileTrashResult:
    """Execute trash command (audited delete → move into .trash).

    Behavior:
    - Sandbox: validate and deny symlink for source; move to
      fs_root()/.trash/<ts>/<rel_path> creating parents. Uses bash when
      available via the sandbox adapter.
    - Store: re-key the in-memory file to .trash/<ts>/<rel_path>.

    Notes:
    - Hard delete in sandbox remains disabled; this provides a reversible
      alternative that keeps an audit trail via logs and path.
    """
    import time as _time

    from inspect_ai.util._store_model import store_as

    _t0 = _log_tool_event(
        name="files:trash",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    root = _fs_root()
    ts = str(int(_time.time()))

    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        try:
            if await adapter.preflight("bash session"):
                # Validate and guard source path inside sandbox root
                src_abs = adapter.validate(params.file_path)
                await adapter.deny_symlink(src_abs)
                # Policy: treat as destructive op on source path
                try:
                    _check_policy(src_abs, "trash")
                except ToolException:
                    kind, rule = _match_path_policy(src_abs)
                    _log_tool_event(
                        name="files:trash",
                        phase="error",
                        extra={
                            "ok": False,
                            "error": "PolicyDenied",
                            "policy_rule": rule,
                            "path": params.file_path,
                        },
                        t0=_t0,
                    )
                    raise

                # Compute destination under .trash/<ts>/<rel_path>
                try:
                    import os as _os

                    rel = _os.path.relpath(src_abs, root)
                except Exception:
                    rel = params.file_path.lstrip("/")
                dst_abs = _os.path.join(root, ".trash", ts, rel)
                # Ensure parent and move
                await adapter.trash(src_abs, dst_abs)
                # Verify destination exists (best-effort)
                existed, _, _ = await adapter.stat(dst_abs)
                if existed:
                    summary = f"Trashed {params.file_path} -> {dst_abs}"
                    _log_tool_event(
                        name="files:trash",
                        phase="end",
                        extra={"ok": True, "action": "trash", "src": params.file_path, "dst": dst_abs},
                        t0=_t0,
                    )
                    if _use_typed_results():
                        return FileTrashResult(src=params.file_path, dst=dst_abs, summary=summary)
                    return summary
        except Exception:
            # Fallback to store-mode implementation
            pass

    # Store-mode trash: move key under .trash/<ts>/
    # Policy check (store) — destructive on source
    try:
        _check_policy(os.path.join(root, params.file_path), "trash")
    except ToolException:
        kind, rule = _match_path_policy(os.path.join(root, params.file_path))
        _log_tool_event(
            name="files:trash",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise

    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        content = files.get_file(params.file_path)
        if content is None:
            _log_tool_event(name="files:trash", phase="error", extra={"ok": False, "error": "FileNotFound"}, t0=_t0)
            raise ToolException(f"File '{params.file_path}' not found")
        # Compute destination key
        dst_key = f".trash/{ts}/{params.file_path.lstrip('/')}"
        files.put_file(dst_key, content)
        files.delete_file(params.file_path)

    summary = f"Trashed {params.file_path} -> {dst_key}"
    _log_tool_event(
        name="files:trash",
        phase="end",
        extra={"ok": True, "action": "trash", "src": params.file_path, "dst": dst_key},
        t0=_t0,
    )
    if _use_typed_results():
        return FileTrashResult(src=params.file_path, dst=dst_key, summary=summary)
    return summary


# The main files tool
def files_tool():  # -> Tool
    """Unified files tool using discriminated union for commands.

    Supports commands: ls, read, write, edit, delete, trash.

    Sandbox vs store:
    - Sandbox (INSPECT_AGENTS_FS_MODE=sandbox): routes reads/writes/edits via
      Inspect's `text_editor` tool and proxies `ls` via `bash_session`, isolating
      operations from the host filesystem. Delete is disabled in sandbox mode.
    - Store (default): operates on an in‑memory virtual filesystem (`Files`) that
      is isolated per execution context.

    Limits: reads return at most `limit` lines (default 2000) and each line is
    truncated to 2000 characters to bound output size.

    Security: In sandbox mode, paths are root‑confined and symlinks are denied;
    in store mode, operations target the in‑memory store.
    """
    # Local imports to avoid executing inspect_ai.tool __init__ during module import
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(
            params: FilesParams,
        ) -> (
            str
            | FileListResult
            | FileReadResult
            | FileWriteResult
            | FileEditResult
            | FileDeleteResult
            | FileTrashResult
        ):
            # Add Pydantic validation layer for early error detection
            try:
                from .tool_types import FilesToolParams

                # Validate input using our stricter Pydantic model before proceeding
                if hasattr(params, "root") and hasattr(params.root, "model_dump"):
                    raw_dict = params.root.model_dump()
                else:
                    # Fallback for dict inputs
                    raw_dict = params if isinstance(params, dict) else params.root

                # This will raise ValidationError with clear message if unknown fields are present
                FilesToolParams.model_validate(raw_dict)
            except ImportError:
                # If tool_types not available, skip validation
                pass
            except Exception as e:
                raise ToolException(f"Invalid parameters: {str(e)}")

            command_params = params.root

            if isinstance(command_params, LsParams):
                return await execute_ls(command_params)
            elif isinstance(command_params, ReadParams):
                return await execute_read(command_params)
            elif isinstance(command_params, WriteParams):
                return await execute_write(command_params)
            elif isinstance(command_params, EditParams):
                return await execute_edit(command_params)
            elif isinstance(command_params, MkdirParams):
                return await execute_mkdir(command_params)
            elif isinstance(command_params, MoveParams):
                return await execute_move(command_params)
            elif isinstance(command_params, StatParams):
                return await execute_stat(command_params)
            elif isinstance(command_params, DeleteParams):
                try:
                    return await execute_delete(command_params)
                except ToolException as e:
                    # For sandbox mode, rephrase the canonical code into a more
                    # descriptive message for higher-level tool usage so tests
                    # asserting human-readable text continue to pass.
                    if str(e) == "SandboxUnsupported" or getattr(e, "message", "") == "SandboxUnsupported":
                        raise ToolException(
                            "delete is disabled in sandbox mode; set INSPECT_AGENTS_FS_MODE=store "
                            "to delete from the in-memory Files store"
                        )
                    raise
            elif isinstance(command_params, TrashParams):
                return await execute_trash(command_params)
            else:
                raise ToolException(f"Unknown command type: {type(command_params)}")

        params = ToolParams()
        params.properties["params"] = json_schema(FilesParams)
        params.properties["params"].description = "File operation parameters with discriminated union"
        params.required.append("params")

        return ToolDef(
            execute,
            name="files",
            description=(
                "Unified file operations tool (ls, read, write, edit, delete, trash). Delete disabled in sandbox mode."
            ),
            parameters=params,
        ).as_tool()

    return _factory()


async def execute_mkdir(params: MkdirParams) -> str:
    """Execute mkdir command (create directory)."""
    _t0 = _log_tool_event(
        name="files:mkdir",
        phase="start",
        args={"dir_path": params.dir_path, "instance": params.instance},
    )
    # Sandbox path
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        if await adapter.preflight("bash session"):
            try:
                validated = adapter.validate(params.dir_path)
                # Policy check (sandbox)
                try:
                    _check_policy(validated, "mkdir")
                except ToolException:
                    kind, rule = _match_path_policy(validated)
                    _log_tool_event(
                        name="files:mkdir",
                        phase="error",
                        extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dir_path},
                        t0=_t0,
                    )
                    raise
                await adapter.mkdir(validated)
                _log_tool_event(name="files:mkdir", phase="end", extra={"ok": True}, t0=_t0)
                return f"Created directory {params.dir_path}"
            except Exception:
                pass
    # Store: enforce policy even though directory entries are implicit
    try:
        _check_policy(os.path.join(_fs_root(), params.dir_path), "mkdir")
    except ToolException:
        kind, rule = _match_path_policy(os.path.join(_fs_root(), params.dir_path))
        _log_tool_event(
            name="files:mkdir",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dir_path},
            t0=_t0,
        )
        raise
    _log_tool_event(name="files:mkdir", phase="end", extra={"ok": True, "mode": "store"}, t0=_t0)
    return f"Created directory {params.dir_path}"


async def execute_move(params: MoveParams) -> str | FileMoveResult:
    """Execute move/rename command."""
    from inspect_ai.util._store_model import store_as

    _t0 = _log_tool_event(
        name="files:move",
        phase="start",
        args={"src": params.src_path, "dst": params.dst_path, "instance": params.instance},
    )
    # Sandbox: try bash mv with guards
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        if await adapter.preflight("bash session"):
            try:
                src = adapter.validate(params.src_path)
                dst = adapter.validate(params.dst_path)
                await adapter.deny_symlink(src)
                # Policy check for destination path (write side)
                try:
                    _check_policy(dst, "move")
                except ToolException:
                    kind, rule = _match_path_policy(dst)
                    _log_tool_event(
                        name="files:move",
                        phase="error",
                        extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dst_path},
                        t0=_t0,
                    )
                    raise
                await adapter.move(src, dst)
                # Verify destination exists; if not, fall back to store path
                exists, _, _ = await adapter.stat(dst)
                if exists:
                    summary = f"Moved {params.src_path} -> {params.dst_path} (sandbox mode)"
                    if _use_typed_results():
                        _log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
                        return FileMoveResult(src=params.src_path, dst=params.dst_path, summary=summary)
                    _log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
                    return summary
            except Exception:
                pass
    # Store: rename file key if exists (policy enforced on destination)
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        content = files.get_file(params.src_path)
    if content is None:
        _log_tool_event(name="files:move", phase="error", extra={"ok": False, "error": "FileNotFound"}, t0=_t0)
        raise ToolException(f"Source '{params.src_path}' not found")
    # Policy check for destination (store)
    try:
        _check_policy(os.path.join(_fs_root(), params.dst_path), "move")
    except ToolException:
        kind, rule = _match_path_policy(os.path.join(_fs_root(), params.dst_path))
        _log_tool_event(
            name="files:move",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dst_path},
            t0=_t0,
        )
        raise
    lock = _get_lock(params.src_path, params.instance)
    async with lock:
        files.put_file(params.dst_path, content)
        files.delete_file(params.src_path)
    summary = f"Moved {params.src_path} -> {params.dst_path}"
    if _use_typed_results():
        _log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
        return FileMoveResult(src=params.src_path, dst=params.dst_path, summary=summary)
    _log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
    return summary


async def execute_stat(params: StatParams) -> str | FileStatResult:
    """Execute stat command to query existence/type/size."""
    from inspect_ai.util._store_model import store_as

    _t0 = _log_tool_event(
        name="files:stat",
        phase="start",
        args={"path": params.path, "instance": params.instance},
    )
    # Sandbox (verify; if missing or error, fall back to store)
    if _use_sandbox_fs():
        adapter = _get_sandbox_adapter()
        try:
            validated = adapter.validate(params.path)
            exists, is_dir, size = await adapter.stat(validated)
            if exists:
                if _use_typed_results():
                    _log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
                    return FileStatResult(path=params.path, exists=exists, is_dir=is_dir, size=size)
                _log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
                kind = "dir" if is_dir else ("file" if exists else "missing")
                return f"{params.path}: {kind}{'' if size is None else f' ({size} bytes)'}"
        except Exception:
            pass
    # Store: derive from keys
    with anyio.fail_after(_default_tool_timeout()):
        files = store_as(Files, instance=params.instance)
        content = files.get_file(params.path)
        exists = content is not None
        if exists:
            is_dir = False
            size = len(content.encode("utf-8"))
        else:
            # Treat any prefix match as a directory
            prefix = params.path.rstrip("/") + "/"
            is_dir = any(k.startswith(prefix) for k in files.list_files())
            size = None
    if _use_typed_results():
        _log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
        return FileStatResult(path=params.path, exists=exists or is_dir, is_dir=is_dir, size=size)
    _log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
    kind = "dir" if is_dir else ("file" if exists else "missing")
    return f"{params.path}: {kind}{'' if size is None else f' ({size} bytes)'}"
