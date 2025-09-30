"""Filesystem Access Façade.

This module provides a unified façade for filesystem operations that encapsulates
sandbox vs. store selection, policy enforcement, and instrumentation. It isolates
these responsibilities from the tools_files module to enable:

- Cleaner separation of concerns
- Easier testing of filesystem logic
- Simpler addition of new storage backends
- Reduced change amplification across modules

The façade accepts dependencies (sandbox adapter, store context factory,
instrumentation) via constructor and exposes async methods for all file operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from .files_instrumentation import LogToolEvent
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
    from .files_ops_store import StoreOpsContext
    from .fs_adapter import SandboxFsAdapter

__all__ = ["FilesystemAccess", "create_default_filesystem_access"]


class FilesystemAccess:
    """Façade for filesystem operations with sandbox/store abstraction.

    This class encapsulates:
    - Sandbox vs. store mode selection (_use_sandbox_fs)
    - Policy enforcement (_check_policy)
    - Instrumentation/logging (_log_tool_event)
    - Delegation to appropriate backend (sandbox adapter or store operations)

    All file operations (ls, read, write, edit, delete, trash, mkdir, move, stat)
    go through this façade, which handles mode selection and delegates to the
    appropriate implementation.
    """

    def __init__(
        self,
        *,
        sandbox_adapter: SandboxFsAdapter,
        store_context_factory: Callable[[], StoreOpsContext],
        use_sandbox_fs: Callable[[], bool],
        log_tool_event: LogToolEvent,
    ) -> None:
        """Initialize the filesystem access façade.

        Args:
            sandbox_adapter: Adapter for sandbox filesystem operations
            store_context_factory: Factory function to create StoreOpsContext
            use_sandbox_fs: Function that returns True if sandbox mode is active
            log_tool_event: Instrumentation function for logging tool events
        """
        self._sandbox_adapter = sandbox_adapter
        self._store_context_factory = store_context_factory
        self._use_sandbox_fs = use_sandbox_fs
        self._log_tool_event = log_tool_event

    async def ls(self, params: LsParams) -> list[str] | FileListResult:
        """List files in directory.

        Delegates to sandbox adapter or store operations based on mode.
        """
        from .files_ops_sandbox import ls_sandbox
        from .files_ops_store import ls_store

        self._log_tool_event(
            name="files:ls",
            phase="start",
            args={"instance": params.instance},
        )

        if self._use_sandbox_fs():
            try:
                return await ls_sandbox(params, log_tool_event=self._log_tool_event)
            except Exception:
                # Graceful fallback to store
                pass

        return await ls_store(params, ctx=self._store_context_factory())

    async def read(self, params: ReadParams) -> str | FileReadResult:
        """Read file content.

        Delegates to sandbox adapter or store operations based on mode.
        Handles instrumentation, validation, and policy checks.
        """
        from .files_ops_store import read_store

        # Check mode first to avoid duplicate logging
        if not self._use_sandbox_fs():
            return await read_store(params, ctx=self._store_context_factory())

        # Sandbox mode: handle logging here

        _t0 = self._log_tool_event(
            name="files:read",
            phase="start",
            args={
                "file_path": params.file_path,
                "offset": params.offset,
                "limit": params.limit,
                "instance": params.instance,
            },
        )

        # Import the execute_read logic directly to avoid duplication
        # For now, we'll use a helper method to encapsulate this
        return await self._read_sandbox(params, _t0)

    async def write(self, params: WriteParams) -> str | FileWriteResult:
        """Write file content.

        Delegates to sandbox adapter or store operations based on mode.
        Handles instrumentation, validation, and policy checks.
        """
        from .files_ops_store import write_store

        # Check mode first to avoid duplicate logging
        if not self._use_sandbox_fs():
            return await write_store(params, ctx=self._store_context_factory())

        # Sandbox mode: handle via helper
        _t0 = self._log_tool_event(
            name="files:write",
            phase="start",
            args={"file_path": params.file_path, "content_len": len(params.content), "instance": params.instance},
        )

        return await self._write_sandbox(params, _t0)

    async def edit(self, params: EditParams) -> str | FileEditResult:
        """Edit file content with string replacement.

        Delegates to sandbox adapter or store operations based on mode.
        Handles instrumentation, validation, and policy checks.
        """
        from .files_ops_store import edit_store

        # Check mode first to avoid duplicate logging
        if not self._use_sandbox_fs():
            return await edit_store(params, ctx=self._store_context_factory())

        # Sandbox mode: handle via helper
        _t0 = self._log_tool_event(
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

        return await self._edit_sandbox(params, _t0)

    async def delete(self, params: DeleteParams) -> str | FileDeleteResult:
        """Delete a file.

        Note: Delete is disabled in sandbox mode for safety.
        """
        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import delete_store

        _t0 = self._log_tool_event(
            name="files:delete",
            phase="start",
            args={"file_path": params.file_path, "instance": params.instance},
        )

        # Sandbox mode: disabled for safety
        import os

        if self._use_sandbox_fs() and _fs.truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY")):
            self._log_tool_event(
                name="files:delete", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=_t0
            )
            raise ToolException("SandboxReadOnly")

        if self._use_sandbox_fs():
            self._log_tool_event(
                name="files:delete",
                phase="error",
                extra={"ok": False, "error": "SandboxUnsupported"},
                t0=_t0,
            )
            raise ToolException("SandboxUnsupported")

        return await delete_store(params, ctx=self._store_context_factory())

    async def trash(self, params: TrashParams) -> str | FileTrashResult:
        """Move file to trash (audited delete).

        Provides a reversible alternative to delete that keeps an audit trail.
        """
        import time as _time

        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import trash_store
        from .settings import typed_results_enabled as _use_typed_results

        _t0 = self._log_tool_event(
            name="files:trash",
            phase="start",
            args={"file_path": params.file_path, "instance": params.instance},
        )

        root = _fs.fs_root()
        ts = str(int(_time.time()))

        if self._use_sandbox_fs():
            try:
                if await self._sandbox_adapter.preflight("bash session"):
                    # Validate and guard source path
                    src_abs = self._sandbox_adapter.validate(params.file_path)
                    await self._sandbox_adapter.deny_symlink(src_abs)

                    # Policy check
                    try:
                        _fs.check_policy(src_abs, "trash")
                    except ToolException:
                        kind, rule = _fs.match_path_policy(src_abs)
                        self._log_tool_event(
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
                    import os as _os

                    try:
                        rel = _os.path.relpath(src_abs, root)
                    except Exception:
                        rel = params.file_path.lstrip("/")
                    dst_abs = _os.path.join(root, ".trash", ts, rel)

                    # Move to trash
                    await self._sandbox_adapter.trash(src_abs, dst_abs)

                    # Verify destination exists
                    existed, _, _ = await self._sandbox_adapter.stat(dst_abs)
                    if existed:
                        summary = f"Trashed {params.file_path} -> {dst_abs}"
                        self._log_tool_event(
                            name="files:trash",
                            phase="end",
                            extra={"ok": True, "action": "trash", "src": params.file_path, "dst": dst_abs},
                            t0=_t0,
                        )
                        if _use_typed_results():
                            from .files_models import FileTrashResult

                            return FileTrashResult(src=params.file_path, dst=dst_abs, summary=summary)
                        return summary
            except Exception:
                pass

        return await trash_store(params, ctx=self._store_context_factory(), timestamp=lambda: _time.time())

    async def mkdir(self, params: MkdirParams) -> str:
        """Create a directory.

        Delegates to sandbox adapter or store operations based on mode.
        """
        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import mkdir_store

        _t0 = self._log_tool_event(
            name="files:mkdir",
            phase="start",
            args={"dir_path": params.dir_path, "instance": params.instance},
        )

        if self._use_sandbox_fs():
            if await self._sandbox_adapter.preflight("bash session"):
                try:
                    validated = self._sandbox_adapter.validate(params.dir_path)
                    # Policy check
                    try:
                        _fs.check_policy(validated, "mkdir")
                    except ToolException:
                        kind, rule = _fs.match_path_policy(validated)
                        self._log_tool_event(
                            name="files:mkdir",
                            phase="error",
                            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dir_path},
                            t0=_t0,
                        )
                        raise
                    await self._sandbox_adapter.mkdir(validated)
                    self._log_tool_event(name="files:mkdir", phase="end", extra={"ok": True}, t0=_t0)
                    return f"Created directory {params.dir_path}"
                except Exception:
                    pass

        return await mkdir_store(params, ctx=self._store_context_factory())

    async def move(self, params: MoveParams) -> str | FileMoveResult:
        """Move or rename a file.

        Delegates to sandbox adapter or store operations based on mode.
        """
        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import move_store
        from .settings import typed_results_enabled as _use_typed_results

        _t0 = self._log_tool_event(
            name="files:move",
            phase="start",
            args={"src": params.src_path, "dst": params.dst_path, "instance": params.instance},
        )

        if self._use_sandbox_fs():
            if await self._sandbox_adapter.preflight("bash session"):
                try:
                    src = self._sandbox_adapter.validate(params.src_path)
                    dst = self._sandbox_adapter.validate(params.dst_path)
                    await self._sandbox_adapter.deny_symlink(src)

                    # Policy check for destination
                    try:
                        _fs.check_policy(dst, "move")
                    except ToolException:
                        kind, rule = _fs.match_path_policy(dst)
                        self._log_tool_event(
                            name="files:move",
                            phase="error",
                            extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.dst_path},
                            t0=_t0,
                        )
                        raise

                    await self._sandbox_adapter.move(src, dst)

                    # Verify destination exists
                    exists, _, _ = await self._sandbox_adapter.stat(dst)
                    if exists:
                        summary = f"Moved {params.src_path} -> {params.dst_path} (sandbox mode)"
                        if _use_typed_results():
                            from .files_models import FileMoveResult

                            self._log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
                            return FileMoveResult(src=params.src_path, dst=params.dst_path, summary=summary)
                        self._log_tool_event(name="files:move", phase="end", extra={"ok": True}, t0=_t0)
                        return summary
                except Exception:
                    pass

        return await move_store(params, ctx=self._store_context_factory())

    async def stat(self, params: StatParams) -> str | FileStatResult:
        """Get file metadata (existence, type, size).

        Delegates to sandbox adapter or store operations based on mode.
        """
        from .files_ops_store import stat_store
        from .settings import typed_results_enabled as _use_typed_results

        _t0 = self._log_tool_event(
            name="files:stat",
            phase="start",
            args={"path": params.path, "instance": params.instance},
        )

        if self._use_sandbox_fs():
            try:
                validated = self._sandbox_adapter.validate(params.path)
                exists, is_dir, size = await self._sandbox_adapter.stat(validated)
                if exists:
                    if _use_typed_results():
                        from .files_models import FileStatResult

                        self._log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
                        return FileStatResult(path=params.path, exists=exists, is_dir=is_dir, size=size)
                    self._log_tool_event(name="files:stat", phase="end", extra={"ok": True}, t0=_t0)
                    kind = "dir" if is_dir else ("file" if exists else "missing")
                    return f"{params.path}: {kind}{'' if size is None else f' ({size} bytes)'}"
            except Exception:
                pass

        return await stat_store(params, ctx=self._store_context_factory())

    # --- Private helper methods for sandbox operations ---

    async def _read_sandbox(self, params: ReadParams, t0: float) -> str | FileReadResult:
        """Sandbox-mode read implementation."""
        import os

        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import read_store
        from .settings import typed_results_enabled as _use_typed_results

        def _format_lines(
            content_lines: list[str], start_line_num: int = 1, *, pad: bool = True
        ) -> tuple[list[str], str]:
            """Format lines with numbering."""
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

        # Validate path
        validated_path = self._sandbox_adapter.validate(params.file_path)
        await self._sandbox_adapter.deny_symlink(validated_path)

        # Optional policy enforcement for reads
        if _fs.truthy(os.getenv("INSPECT_FS_POLICY_ENFORCE_READS")):
            try:
                _fs.check_policy(validated_path, "read")
            except ToolException:
                kind, rule = _fs.match_path_policy(validated_path)
                self._log_tool_event(
                    name="files:read",
                    phase="error",
                    extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                    t0=t0,
                )
                raise

        try:
            # Byte preflight
            file_bytes = await self._sandbox_adapter.wc_bytes(validated_path)
            if file_bytes is not None:
                max_bytes = _fs.max_bytes()
                if file_bytes > max_bytes:
                    self._log_tool_event(
                        name="files:read",
                        phase="error",
                        extra={
                            "ok": False,
                            "error": "FileSizeExceeded",
                            "actual_bytes": file_bytes,
                            "max_bytes": max_bytes,
                        },
                        t0=t0,
                    )
                    raise ToolException(
                        f"File exceeds maximum size limit: {file_bytes:,} bytes > {max_bytes:,} bytes. "
                        f"Use a smaller limit parameter or increase INSPECT_AGENTS_FS_MAX_BYTES."
                    )

            # Compute line range
            start_line = max(1, int(params.offset) + 1)
            max_lines = 0 if (params.limit is None or params.limit <= 0) else int(params.limit)

            # Try view_chunks first if available
            def _chunk_size_lines() -> int:
                try:
                    return int(os.getenv("INSPECT_AGENTS_FS_CHUNK_LINES", "512"))
                except (ValueError, TypeError):
                    return 512

            chunk_size = _chunk_size_lines()
            raw = ""

            if hasattr(self._sandbox_adapter, "view_chunks"):
                try:
                    chunks = []
                    async for chunk in self._sandbox_adapter.view_chunks(
                        validated_path, start_line, max_lines, chunk_size_lines=chunk_size
                    ):
                        chunks.append(chunk)
                    raw = "\n".join(chunks)
                    if not raw.strip():
                        raise Exception("Empty content from view_chunks")
                except Exception:
                    end_line = -1 if max_lines <= 0 else (start_line + max_lines - 1)
                    raw = await self._sandbox_adapter.view(validated_path, start_line, end_line)
            else:
                end_line = -1 if max_lines <= 0 else (start_line + max_lines - 1)
                raw = await self._sandbox_adapter.view(validated_path, start_line, end_line)

            if raw is None or str(raw).strip() == "":
                if _use_typed_results():
                    from .files_models import FileReadResult

                    self._log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=t0)
                    return FileReadResult(lines=[], summary=empty_message)
                self._log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": 0}, t0=t0)
                return empty_message

            # Format lines
            lines = str(raw).splitlines()
            if params.limit is not None and params.limit > 0:
                lines = lines[: int(params.limit)]
            padded_lines, joined_output = _format_lines(lines, start_line, pad=True)

            if _use_typed_results():
                from .files_models import FileReadResult

                nopad_lines, _ = _format_lines(lines, start_line, pad=False)
                self._log_tool_event(
                    name="files:read",
                    phase="end",
                    extra={"ok": True, "lines": len(nopad_lines)},
                    t0=t0,
                )
                return FileReadResult(
                    lines=nopad_lines,
                    summary=f"Read {len(nopad_lines)} lines from file_path={params.file_path} (sandbox mode)",
                )
            self._log_tool_event(name="files:read", phase="end", extra={"ok": True, "lines": len(padded_lines)}, t0=t0)
            return joined_output
        except ToolException:
            raise
        except Exception:
            # Fallback to store
            try:
                return await read_store(params, ctx=self._store_context_factory())
            except ToolException:
                raise

    async def _write_sandbox(self, params: WriteParams, t0: float) -> str | FileWriteResult:
        """Sandbox-mode write implementation."""
        import os
        import shlex as _shlex
        import uuid as _uuid

        import anyio

        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import write_store
        from .settings import typed_results_enabled as _use_typed_results

        # Read-only guard
        if (
            self._use_sandbox_fs()
            and _fs.truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY"))
            and (os.getenv("INSPECT_SANDBOX_PREFLIGHT", "auto").strip().lower() != "skip")
        ):
            self._log_tool_event(
                name="files:write", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=t0
            )
            raise ToolException("SandboxReadOnly")

        # Byte ceiling
        content_bytes = len(params.content.encode("utf-8"))
        max_bytes = _fs.max_bytes()
        if content_bytes > max_bytes:
            self._log_tool_event(
                name="files:write",
                phase="error",
                extra={"ok": False, "error": "FileSizeExceeded", "actual_bytes": content_bytes, "max_bytes": max_bytes},
                t0=t0,
            )
            raise ToolException(
                f"File content exceeds maximum size limit: {content_bytes:,} bytes > {max_bytes:,} bytes. "
                f"Consider breaking the content into smaller files or increase INSPECT_AGENTS_FS_MAX_BYTES."
            )

        summary = f"Updated file {params.file_path}"

        if self._use_sandbox_fs():
            if await self._sandbox_adapter.preflight("editor"):
                validated_path = self._sandbox_adapter.validate(params.file_path)
                await self._sandbox_adapter.deny_symlink(validated_path)

                # Policy check
                try:
                    _fs.check_policy(validated_path, "write")
                except ToolException:
                    kind, rule = _fs.match_path_policy(validated_path)
                    self._log_tool_event(
                        name="files:write",
                        phase="error",
                        extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                        t0=t0,
                    )
                    raise

                # Atomic write with temp file - use lazy import to avoid circular dependency
                def _get_lock_helper():
                    from . import tools_files as _tools_files

                    return _tools_files._get_lock(validated_path, params.instance)

                lock = _get_lock_helper()
                async with lock:
                    try:
                        try:
                            from inspect_ai.tool._tools._bash_session import bash_session as _bash_session
                        except Exception:
                            _bash_session = None  # type: ignore

                        tmp_path = f"{validated_path}.tmp-{_uuid.uuid4().hex}"
                        await self._sandbox_adapter.create(tmp_path, params.content)

                        # Atomic move if bash available
                        if _bash_session is not None and await self._sandbox_adapter.preflight("bash session"):
                            bash = _bash_session()
                            cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                            try:
                                with anyio.fail_after(_fs.default_tool_timeout()):
                                    await bash(action="run", command=cmd)  # type: ignore[misc]
                            except (TypeError, Exception):
                                await self._sandbox_adapter.create(validated_path, params.content)
                        else:
                            await self._sandbox_adapter.create(validated_path, params.content)

                        # Ensure content is present
                        try:
                            await self._sandbox_adapter.create(validated_path, params.content)
                        except Exception:
                            pass

                        if _use_typed_results():
                            from .files_models import FileWriteResult

                            self._log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=t0)
                            return FileWriteResult(path=params.file_path, summary=summary + " (sandbox mode)")
                        self._log_tool_event(name="files:write", phase="end", extra={"ok": True}, t0=t0)
                        return summary
                    except Exception:
                        pass

        # Fallback to store
        return await write_store(params, ctx=self._store_context_factory())

    async def _edit_sandbox(self, params: EditParams, t0: float) -> str | FileEditResult:
        """Sandbox-mode edit implementation."""
        import os
        import shlex as _shlex
        import uuid as _uuid

        import anyio

        from . import fs as _fs
        from .exceptions import ToolException
        from .files_ops_store import edit_store
        from .settings import typed_results_enabled as _use_typed_results

        # Read-only guard
        if (
            self._use_sandbox_fs()
            and _fs.truthy(os.getenv("INSPECT_AGENTS_FS_READ_ONLY"))
            and (os.getenv("INSPECT_SANDBOX_PREFLIGHT", "auto").strip().lower() != "skip")
        ):
            self._log_tool_event(
                name="files:edit", phase="error", extra={"ok": False, "error": "SandboxReadOnly"}, t0=t0
            )
            raise ToolException("SandboxReadOnly")

        if self._use_sandbox_fs():
            if await self._sandbox_adapter.preflight("editor"):
                validated_path = self._sandbox_adapter.validate(params.file_path)
                await self._sandbox_adapter.deny_symlink(validated_path)

                # Policy check
                try:
                    _fs.check_policy(validated_path, "edit")
                except ToolException:
                    kind, rule = _fs.match_path_policy(validated_path)
                    self._log_tool_event(
                        name="files:edit",
                        phase="error",
                        extra={"ok": False, "error": "PolicyDenied", "policy_rule": rule, "path": params.file_path},
                        t0=t0,
                    )
                    raise

                # Use lazy import to avoid circular dependency
                def _get_lock_helper():
                    from . import tools_files as _tools_files

                    return _tools_files._get_lock(validated_path, params.instance)

                lock = _get_lock_helper()
                try:
                    async with lock:
                        # Byte preflight
                        current_bytes = await self._sandbox_adapter.wc_bytes(validated_path)
                        max_bytes = _fs.max_bytes()
                        if current_bytes is not None and current_bytes > max_bytes:
                            self._log_tool_event(
                                name="files:edit",
                                phase="error",
                                extra={
                                    "ok": False,
                                    "error": "FileSizeExceeded",
                                    "actual_bytes": current_bytes,
                                    "max_bytes": max_bytes,
                                },
                                t0=t0,
                            )
                            raise ToolException(
                                f"File exceeds maximum size limit: {current_bytes:,} bytes > {max_bytes:,} bytes. "
                                f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
                            )

                        # Pre-read for validation
                        counted_occurrences: int | None = None
                        if params.expected_count is not None or params.dry_run:
                            try:
                                raw = await self._sandbox_adapter.view(validated_path, 1, -1)
                                text = "" if raw is None else str(raw)
                            except Exception:
                                text = ""
                            if params.old_string not in text:
                                self._log_tool_event(
                                    name="files:edit",
                                    phase="error",
                                    extra={"ok": False, "error": "StringNotFound"},
                                    t0=t0,
                                )
                                raise ToolException(
                                    f"String '{params.old_string}' not found in file '{params.file_path}'. "
                                    f"Please check the exact text to replace."
                                )
                            counted_occurrences = text.count(params.old_string)

                            if params.expected_count is not None:
                                would_replace = counted_occurrences if params.replace_all else 1
                                if int(params.expected_count) != int(would_replace):
                                    self._log_tool_event(
                                        name="files:edit",
                                        phase="error",
                                        extra={
                                            "ok": False,
                                            "error": "ExpectedCountMismatch",
                                            "expected": params.expected_count,
                                            "actual": would_replace,
                                        },
                                        t0=t0,
                                    )
                                    raise ToolException(
                                        f"ExpectedCountMismatch: expected {params.expected_count}, got {would_replace}"
                                    )

                        # Dry run
                        if params.dry_run:
                            replaced = (
                                (counted_occurrences if params.replace_all else 1)
                                if counted_occurrences is not None
                                else 1
                            )
                            summary = (
                                f"(dry_run) Would update file {params.file_path} replacing {replaced} occurrence(s)"
                            )
                            if _use_typed_results():
                                from .files_models import FileEditResult

                                self._log_tool_event(
                                    name="files:edit",
                                    phase="end",
                                    extra={"ok": True, "replaced": replaced, "dry_run": True},
                                    t0=t0,
                                )
                                return FileEditResult(path=params.file_path, replaced=replaced, summary=summary)
                            self._log_tool_event(
                                name="files:edit",
                                phase="end",
                                extra={"ok": True, "replaced": replaced, "dry_run": True},
                                t0=t0,
                            )
                            return summary

                        # Compute updated content
                        try:
                            raw_all = await self._sandbox_adapter.view(validated_path, 1, -1)
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
                            self._log_tool_event(
                                name="files:edit",
                                phase="error",
                                extra={
                                    "ok": False,
                                    "error": "FileSizeExceeded",
                                    "actual_bytes": updated_bytes,
                                    "max_bytes": max_bytes,
                                },
                                t0=t0,
                            )
                            raise ToolException(
                                f"Edit would result in file exceeding maximum size limit: {updated_bytes:,} bytes > {max_bytes:,} bytes. "
                                f"Consider smaller edits or increase INSPECT_AGENTS_FS_MAX_BYTES."
                            )

                        # Atomic write
                        try:
                            from inspect_ai.tool._tools._bash_session import bash_session as _bash_session
                        except Exception:
                            _bash_session = None  # type: ignore

                        tmp_path = f"{validated_path}.tmp-{_uuid.uuid4().hex}"

                        try:
                            await self._sandbox_adapter.create(tmp_path, updated_text)
                            if _bash_session is not None and await self._sandbox_adapter.preflight("bash session"):
                                bash = _bash_session()
                                cmd = f"mv {_shlex.quote(tmp_path)} {_shlex.quote(validated_path)}"
                                try:
                                    with anyio.fail_after(_fs.default_tool_timeout()):
                                        await bash(action="run", command=cmd)  # type: ignore[misc]
                                except (TypeError, Exception):
                                    await self._sandbox_adapter.create(validated_path, updated_text)
                            else:
                                await self._sandbox_adapter.create(validated_path, updated_text)

                            # Verify destination
                            try:
                                exists, _, size = await self._sandbox_adapter.stat(validated_path)
                                needs_write = (not exists) or (size == 0 and len(updated_text or "") > 0)
                                if not needs_write:
                                    try:
                                        cur = await self._sandbox_adapter.view(validated_path, 1, -1)
                                        cur_text = "" if cur is None else str(cur)
                                        if cur_text != updated_text:
                                            needs_write = True
                                    except Exception:
                                        needs_write = True
                                if needs_write:
                                    await self._sandbox_adapter.create(validated_path, updated_text)
                            except Exception:
                                pass
                        except TimeoutError:
                            raise
                        except AttributeError:
                            try:
                                _ = await self._sandbox_adapter.str_replace(
                                    validated_path, params.old_string, params.new_string
                                )  # type: ignore[attr-defined]
                            except Exception:
                                raise

                        replaced = replacement_count if params.replace_all else (1 if replacement_count > 0 else 0)
                        summary = f"Updated file {params.file_path} (sandbox mode)"
                        if _use_typed_results():
                            from .files_models import FileEditResult

                            self._log_tool_event(
                                name="files:edit",
                                phase="end",
                                extra={"ok": True, "replaced": replaced},
                                t0=t0,
                            )
                            return FileEditResult(path=params.file_path, replaced=replaced, summary=summary)
                        self._log_tool_event(
                            name="files:edit",
                            phase="end",
                            extra={"ok": True, "replaced": replaced},
                            t0=t0,
                        )
                        return summary
                except TimeoutError:
                    pass

        # Fallback to store
        return await edit_store(params, ctx=self._store_context_factory())


def create_default_filesystem_access() -> FilesystemAccess:
    """Create a FilesystemAccess instance with default dependencies.

    This factory function wires up the default implementations:
    - Sandbox adapter from fs_adapter.get_default_adapter()
    - Store context from tools_files._create_store_context()
    - Mode selection from fs.use_sandbox_fs()
    - Logging from files_instrumentation.log_tool_event()
    """
    from . import fs as _fs
    from .files_instrumentation import log_tool_event as _log_tool_event
    from .fs_adapter import get_default_adapter as _get_sandbox_adapter

    # Import the store context factory
    def _create_store_context():
        """Create StoreOpsContext with required dependencies."""
        import anyio
        from inspect_ai.util._store_model import store_as

        from .files_ops_store import StoreOpsContext
        from .state import Files

        def wrapped_store_as(files_class: type[Files], instance: str | None) -> Files:
            return store_as(files_class, instance=instance)

        def _get_lock(path: str, instance: str | None) -> anyio.Lock:
            """Get or create a lock for the given path and instance."""
            # This mirrors the _get_lock logic from tools_files.py
            from . import tools_files as _tools_files

            return _tools_files._get_lock(path, instance)

        def _use_typed_results_wrapper() -> bool:
            """Wrapper that references tools_files._use_typed_results for test patching."""
            from . import tools_files as _tools_files

            return _tools_files._use_typed_results()

        return StoreOpsContext(
            log_tool_event=_log_tool_event,
            get_lock=_get_lock,
            default_tool_timeout=_fs.default_tool_timeout,
            store_as=wrapped_store_as,
            use_typed_results=_use_typed_results_wrapper,
            max_bytes=_fs.max_bytes,
            fs_root=_fs.fs_root,
            check_policy=_fs.check_policy,
            match_path_policy=_fs.match_path_policy,
        )

    return FilesystemAccess(
        sandbox_adapter=_get_sandbox_adapter(),
        store_context_factory=_create_store_context,
        use_sandbox_fs=_fs.use_sandbox_fs,
        log_tool_event=_log_tool_event,
    )
