"""Store-mode file operation helpers.

This module centralizes logic that previously lived in the store branches of
``tools_files`` so that sandbox and store concerns are decoupled. Each helper
mirrors the behavior of its counterpart in ``execute_*`` while relying on an
explicit context object for shared dependencies (locks, timeouts, telemetry,
policy hooks, etc.).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import anyio

from .files_models import (
    DeleteParams,
    EditParams,
    FileDeleteResult,
    FileEditResult,
    FileListResult,
    FileMoveResult,
    FileReadResult,
    FileStatResult,
    FileTrashResult,
    FileWriteResult,
    LsParams,
    MkdirParams,
    MoveParams,
    ReadParams,
    StatParams,
    TrashParams,
    WriteParams,
)
from .state import Files

__all__ = [
    "StoreOpsContext",
    "ls_store",
    "read_store",
    "write_store",
    "edit_store",
    "delete_store",
    "trash_store",
    "mkdir_store",
    "move_store",
    "stat_store",
]


class LogToolEvent(Protocol):
    """Protocol matching the observability log_tool_event helper."""

    def __call__(
        self,
        *,
        name: str,
        phase: str,
        args: dict[str, object] | None = None,
        extra: dict[str, object] | None = None,
        t0: float | None = None,
    ) -> float: ...


@dataclass(slots=True)
class StoreOpsContext:
    """Dependencies required by store-mode file operations."""

    log_tool_event: LogToolEvent
    get_lock: Callable[[str, str | None], anyio.Lock]
    default_tool_timeout: Callable[[], float]
    store_as: Callable[[type[Files], str | None], Files]
    use_typed_results: Callable[[], bool]
    max_bytes: Callable[[], int]
    fs_root: Callable[[], str]
    check_policy: Callable[[str, str], None]
    match_path_policy: Callable[[str], tuple[str | None, str | None]]


async def ls_store(
    params: LsParams,
    *,
    ctx: StoreOpsContext,
) -> list[str] | FileListResult:
    """Store-backed implementation for ``files:ls``.

    Mirrors the previous ``execute_ls`` store branch including timeout guards,
    typed-result toggling, and observability fields. Sandbox fallbacks should be
    handled by the caller before invoking this helper.
    """
    _t0 = ctx.log_tool_event(
        name="files:ls",
        phase="start",
        args={"instance": params.instance},
    )

    # Store-backed mode (in-memory Files store) with timeout guard
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        file_list = files.list_files()

    if ctx.use_typed_results():
        ctx.log_tool_event(
            name="files:ls",
            phase="end",
            extra={"ok": True, "count": len(file_list) if isinstance(file_list, list) else len(file_list.files)},
            t0=_t0,
        )
        return FileListResult(files=file_list)
    ctx.log_tool_event(
        name="files:ls",
        phase="end",
        extra={"ok": True, "count": len(file_list) if isinstance(file_list, list) else len(file_list.files)},
        t0=_t0,
    )
    return file_list


async def read_store(
    params: ReadParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileReadResult:
    """Store-backed implementation for ``files:read``.

    Responsible for enforcing byte ceilings, handling offset/limit slicing, and
    preserving legacy padded output vs typed results.
    """
    _t0 = ctx.log_tool_event(
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

    # Store-backed with timeout guard
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        content = files.get_file(params.file_path)
    if content is None:
        ctx.log_tool_event(
            name="files:read",
            phase="error",
            extra={"ok": False, "error": "FileNotFound"},
            t0=_t0,
        )
        from .exceptions import ToolException

        raise ToolException(  # noqa: N806
            f"File '{params.file_path}' not found. Please check the file path and ensure the file exists."
        )

    if not content or content.strip() == "":
        if ctx.use_typed_results():
            ctx.log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
            return FileReadResult(lines=[], summary=empty_message)
        ctx.log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=_t0)
        return empty_message

    # Enforce byte ceiling to prevent OOM and long stalls
    content_bytes = len(content.encode("utf-8"))
    max_bytes = ctx.max_bytes()
    if content_bytes > max_bytes:
        ctx.log_tool_event(
            name="files:read",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": content_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        from .exceptions import ToolException

        raise ToolException(
            f"File exceeds maximum size limit: {content_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Use a smaller limit parameter or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    lines = content.splitlines()
    start_idx = params.offset
    end_idx = min(start_idx + params.limit, len(lines))

    if start_idx >= len(lines):
        from .exceptions import ToolException

        raise ToolException(  # noqa: N806
            f"Line offset {params.offset} exceeds file length ({len(lines)} lines). "
            f"Use an offset between 0 and {len(lines) - 1}."
        )

    selected_lines = lines[start_idx:end_idx]
    # Format with correct line numbers starting from offset + 1
    _padded, joined_output = _format_lines(selected_lines, start_idx + 1, pad=True)

    if ctx.use_typed_results():
        nopad_lines, _ = _format_lines(selected_lines, start_idx + 1, pad=False)
        ctx.log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(nopad_lines)}, t0=_t0)
        return FileReadResult(
            lines=nopad_lines,
            summary=(
                f"Read {len(nopad_lines)} lines from {params.file_path} "
                f"(lines {start_idx + 1}-{start_idx + len(nopad_lines)})"
            ),
        )
    ctx.log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(selected_lines)}, t0=_t0)
    return joined_output


async def write_store(
    params: WriteParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileWriteResult:
    """Store-backed implementation for ``files:write``.

    Performs policy enforcement, per-path locking, timeout-wrapped ``put_file``
    writes, and emits the legacy string or typed result as previously done in
    ``execute_write``.
    """
    _t0 = ctx.log_tool_event(
        name="files:write",
        phase="start",
        args={"file_path": params.file_path, "content_len": len(params.content), "instance": params.instance},
    )

    # Enforce byte ceiling to prevent OOM and long stalls
    content_bytes = len(params.content.encode("utf-8"))
    max_bytes = ctx.max_bytes()
    if content_bytes > max_bytes:
        ctx.log_tool_event(
            name="files:write",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": content_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        from .exceptions import ToolException

        raise ToolException(
            f"File content exceeds maximum size limit: {content_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Consider breaking the content into smaller files or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    summary = f"Updated file {params.file_path}"

    # Store-backed with timeout guard
    # Keep store-mode simple: single put_file to the final key (no temp swap)
    # Policy check (store) — optional
    try:
        import os

        ctx.check_policy(os.path.join(ctx.fs_root(), params.file_path), "write")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(ctx.fs_root(), params.file_path))
        ctx.log_tool_event(
            name="files:write",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise
    lock = ctx.get_lock(params.file_path, params.instance)
    async with lock:
        with anyio.fail_after(ctx.default_tool_timeout()):
            files = ctx.store_as(Files, params.instance)
            files.put_file(params.file_path, params.content)

    if ctx.use_typed_results():
        ctx.log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
        return FileWriteResult(path=params.file_path, summary=summary)
    ctx.log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=_t0)
    return summary


async def edit_store(
    params: EditParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileEditResult:
    """Store-backed implementation for ``files:edit``.

    Must support dry-run semantics, expected-count validation, byte ceilings,
    and typed result toggling while using the shared lock/timeout utilities.
    """
    _t0 = ctx.log_tool_event(
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

    # Store-backed: perform the full read-modify-write under a per-path lock
    lock = ctx.get_lock(params.file_path, params.instance)
    async with lock:
        with anyio.fail_after(ctx.default_tool_timeout()):
            files = ctx.store_as(Files, params.instance)
            content = files.get_file(params.file_path)
        if content is None:
            ctx.log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "FileNotFound"},
                t0=_t0,
            )
            from .exceptions import ToolException

            raise ToolException(  # noqa: N806
                f"File '{params.file_path}' not found. Please check the file path and ensure the file exists."
            )

        if params.old_string not in content:
            ctx.log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "StringNotFound"},
                t0=_t0,
            )
            from .exceptions import ToolException

            raise ToolException(
                f"String '{params.old_string}' not found in file '{params.file_path}'. "
                f"Please check the exact text to replace."
            )

    # Policy check (store) — optional
    try:
        import os

        ctx.check_policy(os.path.join(ctx.fs_root(), params.file_path), "edit")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(ctx.fs_root(), params.file_path))
        ctx.log_tool_event(
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
            ctx.log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": "ExpectedCountMismatch", "expected": expected, "actual": actual},
                t0=_t0,
            )
            from .exceptions import ToolException

            raise ToolException(f"ExpectedCountMismatch: expected {expected}, got {actual}")

    # Enforce byte ceiling on the updated content
    updated_bytes = len(updated.encode("utf-8"))
    max_bytes = ctx.max_bytes()
    if updated_bytes > max_bytes:
        ctx.log_tool_event(
            name="files:edit",
            phase="error",
            extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": updated_bytes, "max_bytes": max_bytes},
            t0=_t0,
        )
        from .exceptions import ToolException

        raise ToolException(
            f"Edit would result in file exceeding maximum size limit: {updated_bytes:,} bytes > {max_bytes:,} bytes. "
            f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
        )

    # If dry_run, do not persist changes
    if params.dry_run:
        to_report = replacement_count if params.replace_all else 1
        summary = f"(dry_run) Would update file {params.file_path} replacing {to_report} occurrence(s)"
        if ctx.use_typed_results():
            ctx.log_tool_event(
                name="files:edit",
                phase="end",
                extra={"ok": True, "replaced": to_report, "dry_run": True},
                t0=_t0,
            )
            return FileEditResult(path=params.file_path, replaced=to_report, summary=summary)
        ctx.log_tool_event(
            name="files:edit",
            phase="end",
            extra={"ok": True, "replaced": to_report, "dry_run": True},
            t0=_t0,
        )
        return summary

    # Single write in store mode
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        files.put_file(params.file_path, updated)

    summary = f"Updated file {params.file_path}"
    to_report = replacement_count if params.replace_all else 1
    if ctx.use_typed_results():
        ctx.log_tool_event(
            name="files:edit",
            phase="end",
            extra={"ok": True, "replaced": to_report},
            t0=_t0,
        )
        return FileEditResult(path=params.file_path, replaced=to_report, summary=summary)
    ctx.log_tool_event(name="files:edit", phase="end", extra={"ok": True, "replaced": to_report}, t0=_t0)
    return summary


async def delete_store(
    params: DeleteParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileDeleteResult:
    """Store-backed implementation for ``files:delete``.

    Enforces policy checks, performs idempotent deletion messaging, and emits
    the canonical observability payloads.
    """
    _t0 = ctx.log_tool_event(
        name="files:delete",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    # Store-backed with timeout guard
    # Policy check (store) — enforce before deletion
    try:
        import os

        ctx.check_policy(os.path.join(ctx.fs_root(), params.file_path), "delete")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(ctx.fs_root(), params.file_path))
        ctx.log_tool_event(
            name="files:delete",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        # Check if file exists before deletion for proper messaging
        file_exists = files.get_file(params.file_path) is not None
        files.delete_file(params.file_path)

    if file_exists:
        summary = f"Deleted file {params.file_path}"
    else:
        summary = f"File {params.file_path} did not exist (delete operation was idempotent)"

    if ctx.use_typed_results():
        ctx.log_tool_event(name="files:delete", phase="end", extra={"ok": True, "existed": file_exists}, t0=_t0)
        return FileDeleteResult(path=params.file_path, summary=summary)
    ctx.log_tool_event(name="files:delete", phase="end", extra={"ok": True, "existed": file_exists}, t0=_t0)
    return summary


async def trash_store(
    params: TrashParams,
    *,
    ctx: StoreOpsContext,
    timestamp: Callable[[], float],
) -> str | FileTrashResult:
    """Store-backed implementation for ``files:trash``.

    Moves the in-memory file to ``.trash/<ts>/...`` and removes the original
    key. ``timestamp`` is injected to keep clock management outside helpers.
    """
    _t0 = ctx.log_tool_event(
        name="files:trash",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    root = ctx.fs_root()
    ts = str(int(timestamp()))

    # Store-mode trash: move key under .trash/<ts>/
    # Policy check (store) — destructive on source
    try:
        import os

        ctx.check_policy(os.path.join(root, params.file_path), "trash")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(root, params.file_path))
        ctx.log_tool_event(
            name="files:trash",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
            t0=_t0,
        )
        raise

    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        content = files.get_file(params.file_path)
        if content is None:
            ctx.log_tool_event(name="files:trash", phase="error", extra={"ok": False, "error": "FileNotFound"}, t0=_t0)
            from .exceptions import ToolException

            raise ToolException(f"File '{params.file_path}' not found")
        # Compute destination key
        dst_key = f".trash/{ts}/{params.file_path.lstrip('/')}"
        files.put_file(dst_key, content)
        files.delete_file(params.file_path)

    summary = f"Trashed {params.file_path} -> {dst_key}"
    ctx.log_tool_event(
        name="files:trash",
        phase="end",
        extra={"ok": True, "action": "trash", "src": params.file_path, "dst": dst_key},
        t0=_t0,
    )
    if ctx.use_typed_results():
        return FileTrashResult(src=params.file_path, dst=dst_key, summary=summary)
    return summary


async def mkdir_store(
    params: MkdirParams,
    *,
    ctx: StoreOpsContext,
) -> str:
    """Store-backed implementation for ``files:mkdir``.

    Store mode treats directories implicitly but still enforces policy and logs
    success. Caller is responsible for sandbox behavior.
    """
    _t0 = ctx.log_tool_event(
        name="files:mkdir",
        phase="start",
        args={"dir_path": params.dir_path, "instance": params.instance},
    )

    # Store: enforce policy even though directory entries are implicit
    try:
        import os

        ctx.check_policy(os.path.join(ctx.fs_root(), params.dir_path), "mkdir")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(ctx.fs_root(), params.dir_path))
        ctx.log_tool_event(
            name="files:mkdir",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dir_path},
            t0=_t0,
        )
        raise
    ctx.log_tool_event(name="files:mkdir", phase="end", extra={"ok": True, "mode": "store"}, t0=_t0)
    return f"Created directory {params.dir_path}"


async def move_store(
    params: MoveParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileMoveResult:
    """Store-backed implementation for ``files:move``.

    Reads the source key, enforces destination policy, writes the destination,
    deletes the source, and returns the expected summary/result.
    """
    _t0 = ctx.log_tool_event(
        name="files:move",
        phase="start",
        args={"src": params.src_path, "dst": params.dst_path, "instance": params.instance},
    )

    # Store: rename file key if exists (policy enforced on destination)
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
        content = files.get_file(params.src_path)
    if content is None:
        ctx.log_tool_event(name="files:move", phase="error", extra={"ok": False, "error": "FileNotFound"}, t0=_t0)
        from .exceptions import ToolException

        raise ToolException(f"Source '{params.src_path}' not found")
    # Policy check for destination (store)
    try:
        import os

        ctx.check_policy(os.path.join(ctx.fs_root(), params.dst_path), "move")
    except Exception:
        kind, rule = ctx.match_path_policy(os.path.join(ctx.fs_root(), params.dst_path))
        ctx.log_tool_event(
            name="files:move",
            phase="error",
            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dst_path},
            t0=_t0,
        )
        raise
    lock = ctx.get_lock(params.src_path, params.instance)
    async with lock:
        files.put_file(params.dst_path, content)
        files.delete_file(params.src_path)
    summary = f"Moved {params.src_path} -> {params.dst_path}"
    if ctx.use_typed_results():
        ctx.log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
        return FileMoveResult(src=params.src_path, dst=params.dst_path, summary=summary)
    ctx.log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
    return summary


async def stat_store(
    params: StatParams,
    *,
    ctx: StoreOpsContext,
) -> str | FileStatResult:
    """Store-backed implementation for ``files:stat``.

    Determines existence, directory inference, and byte size (for files) while
    keeping typed vs legacy outputs aligned with ``execute_stat``.
    """
    _t0 = ctx.log_tool_event(
        name="files:stat",
        phase="start",
        args={"path": params.path, "instance": params.instance},
    )

    # Store: derive from keys
    with anyio.fail_after(ctx.default_tool_timeout()):
        files = ctx.store_as(Files, params.instance)
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
    if ctx.use_typed_results():
        ctx.log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
        return FileStatResult(path=params.path, exists=exists or is_dir, is_dir=is_dir, size=size)
    ctx.log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
    kind = "dir" if is_dir else ("file" if exists else "missing")
    return f"{params.path}: {kind}{'' if size is None else f' ({size} bytes)'}"
