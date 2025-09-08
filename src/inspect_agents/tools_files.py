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
from .observability import log_tool_event as _log_tool_event
from .settings import (
    typed_results_enabled as _use_typed_results,
)
from .state import Files

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


class FileListResult(BaseModel):
    """Typed result for ls operations."""

    files: list[str]


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
    expected_count: int | None = Field(
        None,
        description=(
            "Optional expected number of replacements to perform. When set, the edit "
            "will validate that exactly this many replacements would occur and raise "
            "an error on mismatch."
        ),
    )
    dry_run: bool = Field(
        False,
        description=("When true, compute counts and validate but do not modify the file."),
    )


class DeleteParams(BaseFileParams):
    """Parameters for delete command."""

    command: Literal["delete"] = "delete"
    file_path: str = Field(description="Path to delete")


class FilesParams(RootModel):
    """Discriminated union of all file operation parameters."""

    root: Annotated[
        LsParams | ReadParams | WriteParams | EditParams | DeleteParams,
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
            end_line = -1 if (params.limit is None or params.limit <= 0) else (start_line + int(params.limit) - 1)

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
    if _use_sandbox_fs() and _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
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

                    # If bash session is available, atomically move into place
                    if _bash_session is not None and await adapter.preflight("bash session"):
                        bash = _bash_session()
                        cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                        with anyio.fail_after(_default_tool_timeout()):
                            await bash(action="run", command=cmd)
                    else:
                        # Fallback: write directly (non-atomic)
                        await adapter.create(validated_path, params.content)

                    if _use_typed_results():
                        _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
                        return FileWriteResult(path=params.file_path, summary=summary + " (sandbox mode)")
                    _log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
                    return summary
                except Exception:
                    pass

    # Store-backed with timeout guard
    # Store-backed with timeout + per-path lock; simulate atomic swap via temp key
    lock = _get_lock(params.file_path, params.instance)
    async with lock:
        with anyio.fail_after(_default_tool_timeout()):
            files = store_as(Files, instance=params.instance)
            tmp_key = f"{params.file_path}.tmp-{_uuid.uuid4().hex}"
            files.put_file(tmp_key, params.content)
            files.put_file(params.file_path, params.content)
            files.delete_file(tmp_key)

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
            "dry_run": params.dry_run,
            "instance": params.instance,
        },
    )
    # Read-only guard in sandbox mode
    if _use_sandbox_fs() and _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
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

            # Serialize edits per-path and prefer atomic temp+rename using bash when possible
            lock = _get_lock(validated_path, params.instance)
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
                await adapter.create(tmp_path, updated_text)

                if _bash_session is not None and await adapter.preflight("bash session"):
                    bash = _bash_session()
                    cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                    with anyio.fail_after(_default_tool_timeout()):
                        await bash(action="run", command=cmd)
                else:
                    # Fallback: non-atomic editor replacement
                    await adapter.create(validated_path, updated_text)

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

    # Store-backed with timeout guard
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

    # Store-backed atomic swap under per-path lock
    lock = _get_lock(params.file_path, params.instance)
    async with lock:
        tmp_key = f"{params.file_path}.tmp-{_uuid.uuid4().hex}"
        files.put_file(tmp_key, updated)
        files.put_file(params.file_path, updated)
        files.delete_file(tmp_key)

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
    _log_tool_event(
        name="files:edit",
        phase="end",
        extra={"ok": True, "replaced": to_report},
        t0=_t0,
    )
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


# The main files tool
def files_tool():  # -> Tool
    """Unified files tool using discriminated union for commands.

    Supports commands: ls, read, write, edit, delete.

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
        ) -> str | FileListResult | FileReadResult | FileWriteResult | FileEditResult | FileDeleteResult:
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
                "Unified file operations tool (ls, read, write, edit, delete). Delete disabled in sandbox mode."
            ),
            parameters=params,
        ).as_tool()

    return _factory()
