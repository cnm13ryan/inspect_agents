"""Sandbox-mode file operations extracted from tools_files.py.

This module extracts sandbox behavior using fs_adapter to improve testability
and maintainability. These functions handle the sandbox-specific logic for
file operations, including validation, policy checks, and adapter calls.

All functions preserve existing logs, error messages, policy checks and
read-only rules from the original tools_files.py implementation.
"""

from __future__ import annotations

import os
import time as _time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass

from . import fs as _fs
from .exceptions import ToolException
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
from .fs_adapter import get_default_adapter as _get_sandbox_adapter
from .settings import typed_results_enabled as _use_typed_results

# Adopt unified FS helpers from inspect_agents.fs
_truthy = _fs.truthy
_fs_root = _fs.fs_root
_max_bytes = _fs.max_bytes
_default_tool_timeout = _fs.default_tool_timeout
_check_policy = _fs.check_policy
_match_path_policy = _fs.match_path_policy


def _chunk_size_lines() -> int:
    """Return chunk size for streaming reads from environment variable."""
    try:
        return int(os.getenv("INSPECT_AGENTS_FS_CHUNK_LINES", "512"))
    except (ValueError, TypeError):
        return 512


async def ls_sandbox(params: LsParams, *, log_tool_event) -> list[str] | FileListResult:
    """Execute ls command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:ls",
        phase="start",
        args={"instance": params.instance},
    )

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("bash session"):
        raise ToolException("SandboxUnsupported")

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
                    try:
                        _check_policy(abs_path, "read")
                        allowed.append(name)
                    except ToolException:
                        kind, rule = _match_path_policy(abs_path)
                        log_tool_event(
                            name="files:ls",
                            phase="policy_deny",
                            extra={
                                "ok": False,
                                "error": "PolicyDenied",
                                "policy_rule": rule,
                                "path": name,
                            },
                            t0=_t0,
                        )
                file_list = allowed
            except Exception:
                # Silent fallback; policy is best-effort
                pass

        log_tool_event(
            name="files:ls",
            phase="end",
            extra={"ok": True, "count": len(file_list)},
            t0=_t0,
        )

        if _use_typed_results():
            return FileListResult(files=file_list)
        return file_list

    except Exception as e:
        log_tool_event(
            name="files:ls",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise


async def read_sandbox(params: ReadParams, *, log_tool_event) -> str | FileReadResult:
    """Execute read command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:read",
        phase="start",
        args={
            "file_path": params.file_path,
            "offset": params.offset,
            "limit": params.limit,
            "instance": params.instance,
        },
    )

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("text_editor"):
        raise ToolException("SandboxUnsupported")

    try:
        # Validate and guard the path
        abs_path = adapter.validate(params.file_path)
        await adapter.deny_symlink(abs_path)

        # Policy check
        try:
            _check_policy(abs_path, "read")
        except ToolException:
            kind, rule = _match_path_policy(abs_path)
            log_tool_event(
                name="files:read",
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

        # Optional byte count preflight
        wc_result = await adapter.wc_bytes(abs_path)
        if wc_result is not None:
            max_b = _max_bytes()
            if max_b > 0 and wc_result > max_b:
                log_tool_event(
                    name="files:read",
                    phase="error",
                    extra={
                        "ok": False,
                        "error": "FileTooLarge",
                        "bytes": wc_result,
                        "max_bytes": max_b,
                    },
                    t0=_t0,
                )
                raise ToolException("FileTooLarge")

        # Determine line range for reading
        start_line = max(1, (params.offset or 0) + 1)
        limit = params.limit or 2000
        end_line = start_line + limit - 1 if limit > 0 else -1

        # Read content using adapter (streaming if available)
        content_lines = []
        total_lines = 0

        if hasattr(adapter, "view_chunks"):
            # Use streaming read if available
            async for chunk in adapter.view_chunks(abs_path, start_line, limit, chunk_size_lines=_chunk_size_lines()):
                lines = chunk.splitlines()
                content_lines.extend(lines)
                total_lines += len(lines)
                if limit > 0 and total_lines >= limit:
                    content_lines = content_lines[:limit]
                    break
        else:
            # Fallback to regular view
            content = await adapter.view(abs_path, start_line, end_line)
            if content:
                content_lines = content.splitlines()
                if limit > 0:
                    content_lines = content_lines[:limit]

        # Truncate each line to 2000 characters
        truncated_lines = []
        for line in content_lines:
            if len(line) > 2000:
                truncated_lines.append(line[:2000] + "...")
            else:
                truncated_lines.append(line)

        # Format output with line numbers
        output_lines = []
        for i, line in enumerate(truncated_lines):
            line_num = start_line + i
            output_lines.append(f"{line_num:>6}→{line}")

        result_content = "\n".join(output_lines)

        log_tool_event(
            name="files:read",
            phase="end",
            extra={"ok": True, "lines": len(truncated_lines)},
            t0=_t0,
        )

        if _use_typed_results():
            return FileReadResult(
                content=result_content,
                start_line=start_line,
                lines_read=len(truncated_lines),
                file_path=params.file_path,
            )
        return result_content

    except Exception as e:
        log_tool_event(
            name="files:read",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise


async def write_sandbox(params: WriteParams, *, log_tool_event, get_lock) -> str | FileWriteResult:
    """Execute write command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:write",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    # Read-only check
    if _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
        log_tool_event(
            name="files:write",
            phase="error",
            extra={"ok": False, "error": "SandboxReadOnly"},
            t0=_t0,
        )
        raise ToolException("SandboxReadOnly")

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("text_editor"):
        raise ToolException("SandboxUnsupported")

    # Use per-path lock to prevent torn writes
    lock = get_lock(params.file_path, params.instance)
    async with lock:
        try:
            # Validate and guard the path
            abs_path = adapter.validate(params.file_path)
            await adapter.deny_symlink(abs_path)

            # Policy check
            try:
                _check_policy(abs_path, "write")
            except ToolException:
                kind, rule = _match_path_policy(abs_path)
                log_tool_event(
                    name="files:write",
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

            # Write content using adapter
            await adapter.create(abs_path, params.content)

            # Count written lines for logging
            lines_written = len(params.content.splitlines()) if params.content else 0

            log_tool_event(
                name="files:write",
                phase="end",
                extra={"ok": True, "lines": lines_written},
                t0=_t0,
            )

            summary = f"Wrote {lines_written} lines to {params.file_path}"
            if _use_typed_results():
                return FileWriteResult(
                    file_path=params.file_path,
                    lines_written=lines_written,
                    summary=summary,
                )
            return summary

        except Exception as e:
            log_tool_event(
                name="files:write",
                phase="error",
                extra={"ok": False, "error": str(e)},
                t0=_t0,
            )
            raise


async def edit_sandbox(params: EditParams, *, log_tool_event, get_lock) -> str | FileEditResult:
    """Execute edit command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:edit",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    # Read-only check
    if _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
        log_tool_event(
            name="files:edit",
            phase="error",
            extra={"ok": False, "error": "SandboxReadOnly"},
            t0=_t0,
        )
        raise ToolException("SandboxReadOnly")

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("text_editor"):
        raise ToolException("SandboxUnsupported")

    # Use per-path lock to prevent overlapping edits
    lock = get_lock(params.file_path, params.instance)
    async with lock:
        try:
            # Validate and guard the path
            abs_path = adapter.validate(params.file_path)
            await adapter.deny_symlink(abs_path)

            # Policy check
            try:
                _check_policy(abs_path, "edit")
            except ToolException:
                kind, rule = _match_path_policy(abs_path)
                log_tool_event(
                    name="files:edit",
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

            # Perform string replacement using adapter
            result = await adapter.str_replace(abs_path, params.old_str, params.new_str)

            log_tool_event(
                name="files:edit",
                phase="end",
                extra={"ok": True, "action": "str_replace"},
                t0=_t0,
            )

            summary = f"Edited {params.file_path}: replaced text"
            if _use_typed_results():
                return FileEditResult(
                    file_path=params.file_path,
                    summary=summary,
                    edit_result=result if result else "Edit completed",
                )
            return result if result else summary

        except Exception as e:
            log_tool_event(
                name="files:edit",
                phase="error",
                extra={"ok": False, "error": str(e)},
                t0=_t0,
            )
            raise


async def delete_sandbox(params: DeleteParams, *, log_tool_event) -> str | FileDeleteResult:
    """Execute delete command in sandbox mode (disabled for safety)."""
    _t0 = log_tool_event(
        name="files:delete",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    # Read-only check
    if _truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
        log_tool_event(
            name="files:delete",
            phase="error",
            extra={"ok": False, "error": "SandboxReadOnly"},
            t0=_t0,
        )
        raise ToolException("SandboxReadOnly")

    # Sandbox mode: disabled for safety
    log_tool_event(
        name="files:delete",
        phase="error",
        extra={"ok": False, "error": "SandboxUnsupported"},
        t0=_t0,
    )
    # Canonical short error code expected by tests/docs
    raise ToolException("SandboxUnsupported")


async def trash_sandbox(params: TrashParams, *, log_tool_event) -> str | FileTrashResult:
    """Execute trash command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:trash",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    root = _fs_root()
    ts = str(int(_time.time()))

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("bash session"):
        raise ToolException("SandboxUnsupported")

    try:
        # Validate and guard source path inside sandbox root
        src_abs = adapter.validate(params.file_path)
        await adapter.deny_symlink(src_abs)

        # Policy: treat as destructive op on source path
        try:
            _check_policy(src_abs, "trash")
        except ToolException:
            kind, rule = _match_path_policy(src_abs)
            log_tool_event(
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
            rel = os.path.relpath(src_abs, root)
        except Exception:
            rel = params.file_path.lstrip("/")
        dst_abs = os.path.join(root, ".trash", ts, rel)

        # Ensure parent and move
        await adapter.trash(src_abs, dst_abs)

        # Verify destination exists (best-effort)
        existed, _, _ = await adapter.stat(dst_abs)
        if existed:
            summary = f"Trashed {params.file_path} -> {dst_abs}"
            log_tool_event(
                name="files:trash",
                phase="end",
                extra={"ok": True, "action": "trash", "src": params.file_path, "dst": dst_abs},
                t0=_t0,
            )
            if _use_typed_results():
                return FileTrashResult(src=params.file_path, dst=dst_abs, summary=summary)
            return summary
        else:
            # Fallback error if verification failed
            raise ToolException("TrashFailed: destination not found after move")

    except Exception as e:
        log_tool_event(
            name="files:trash",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise


async def mkdir_sandbox(params: MkdirParams, *, log_tool_event) -> str:
    """Execute mkdir command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:mkdir",
        phase="start",
        args={"dir_path": params.dir_path, "instance": params.instance},
    )

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("bash session"):
        raise ToolException("SandboxUnsupported")

    try:
        validated = adapter.validate(params.dir_path)

        # Policy check (sandbox)
        try:
            _check_policy(validated, "mkdir")
        except ToolException:
            kind, rule = _match_path_policy(validated)
            log_tool_event(
                name="files:mkdir",
                phase="error",
                extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dir_path},
                t0=_t0,
            )
            raise

        await adapter.mkdir(validated)
        log_tool_event(name="files:mkdir", phase="end", extra={"ok": True}, t0=_t0)
        return f"Created directory {params.dir_path}"

    except Exception as e:
        log_tool_event(
            name="files:mkdir",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise


async def move_sandbox(params: MoveParams, *, log_tool_event) -> str | FileMoveResult:
    """Execute move/rename command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:move",
        phase="start",
        args={"src": params.src_path, "dst": params.dst_path, "instance": params.instance},
    )

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("bash session"):
        raise ToolException("SandboxUnsupported")

    try:
        src = adapter.validate(params.src_path)
        dst = adapter.validate(params.dst_path)
        await adapter.deny_symlink(src)

        # Policy checks for both source and destination
        try:
            _check_policy(src, "move")
            _check_policy(dst, "write")
        except ToolException:
            kind, rule = _match_path_policy(src)
            if kind is None:
                kind, rule = _match_path_policy(dst)
            log_tool_event(
                name="files:move",
                phase="error",
                extra={
                    "ok": False,
                    "error": "PolicyDenied",
                    "policy_rule": rule,
                    "src": params.src_path,
                    "dst": params.dst_path,
                },
                t0=_t0,
            )
            raise

        await adapter.move(src, dst)

        # Verify move was successful (best-effort)
        dst_exists, _, _ = await adapter.stat(dst)
        if dst_exists:
            summary = f"Moved {params.src_path} -> {params.dst_path}"
            log_tool_event(
                name="files:move",
                phase="end",
                extra={"ok": True, "action": "move", "src": params.src_path, "dst": params.dst_path},
                t0=_t0,
            )
            if _use_typed_results():
                return FileMoveResult(src=params.src_path, dst=params.dst_path, summary=summary)
            return summary
        else:
            raise ToolException("MoveFailed: destination not found after move")

    except Exception as e:
        log_tool_event(
            name="files:move",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise


async def stat_sandbox(params: StatParams, *, log_tool_event) -> str | FileStatResult:
    """Execute stat command in sandbox mode using adapter."""
    _t0 = log_tool_event(
        name="files:stat",
        phase="start",
        args={"file_path": params.file_path, "instance": params.instance},
    )

    adapter = _get_sandbox_adapter()
    if not await adapter.preflight("bash session"):
        raise ToolException("SandboxUnsupported")

    try:
        # Validate path
        abs_path = adapter.validate(params.file_path)

        # Policy check
        try:
            _check_policy(abs_path, "read")
        except ToolException:
            kind, rule = _match_path_policy(abs_path)
            log_tool_event(
                name="files:stat",
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

        # Get file stats using adapter
        exists, is_dir, size_bytes = await adapter.stat(abs_path)

        if not exists:
            summary = f"Path does not exist: {params.file_path}"
            log_tool_event(
                name="files:stat",
                phase="end",
                extra={"ok": True, "exists": False},
                t0=_t0,
            )
            if _use_typed_results():
                return FileStatResult(
                    file_path=params.file_path,
                    exists=False,
                    is_directory=False,
                    size_bytes=None,
                    summary=summary,
                )
            return summary

        # Format summary
        if is_dir:
            summary = f"Directory: {params.file_path}"
        else:
            size_str = f" ({size_bytes} bytes)" if size_bytes is not None else ""
            summary = f"File: {params.file_path}{size_str}"

        log_tool_event(
            name="files:stat",
            phase="end",
            extra={"ok": True, "exists": True, "is_dir": is_dir, "size": size_bytes},
            t0=_t0,
        )

        if _use_typed_results():
            return FileStatResult(
                file_path=params.file_path,
                exists=True,
                is_directory=is_dir,
                size_bytes=size_bytes,
                summary=summary,
            )
        return summary

    except Exception as e:
        log_tool_event(
            name="files:stat",
            phase="error",
            extra={"ok": False, "error": str(e)},
            t0=_t0,
        )
        raise
