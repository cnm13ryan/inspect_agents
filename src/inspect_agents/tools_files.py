"""Unified files tool with discriminated union pattern.

This module provides a single files_tool() that handles all file operations
using a discriminated union for commands: ls, read, write, edit.

The core filesystem orchestration logic has been moved to fs_access.py (FilesystemAccess façade)
to isolate sandbox/store selection, policy enforcement, and instrumentation concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:  # pragma: no cover
    from inspect_ai.tool._tool import Tool

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
    FilesParams,
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
from .fs_access import create_default_filesystem_access

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
# Adopt unified FS helpers from inspect_agents.fs (re-export for tests and compatibility)
reset_sandbox_preflight_cache = _fs.reset_sandbox_preflight_cache
_use_sandbox_fs = _fs.use_sandbox_fs
_ensure_sandbox_ready = _fs.ensure_sandbox_ready
_fs_root = _fs.fs_root
_validate_sandbox_path = _fs.validate_sandbox_path
_max_bytes = _fs.max_bytes
_default_tool_timeout = _fs.default_tool_timeout

# Import sandbox adapter for tests

# ---------------------------------------------------------------------------
# Per-path async locks to prevent torn writes and overlapping edits
# ---------------------------------------------------------------------------
_FILE_LOCKS: dict[str, anyio.Lock] = {}


def _lock_key(path: str, instance: str | None) -> str:
    mode = "sandbox" if _fs.use_sandbox_fs() else "store"
    ns = (instance or "default") if mode == "store" else "global"
    return f"{mode}:{ns}:{path}"


def _get_lock(path: str, instance: str | None) -> anyio.Lock:
    key = _lock_key(path, instance)
    lock = _FILE_LOCKS.get(key)
    if lock is None:
        lock = anyio.Lock()
        _FILE_LOCKS[key] = lock
    return lock


# ---------------------------------------------------------------------------
# Filesystem Access Façade
# ---------------------------------------------------------------------------
# Create a singleton instance of the filesystem access façade
_fs_access = create_default_filesystem_access()


# Execution functions (can be used by wrapper tools)
# These now delegate to the filesystem access façade
async def execute_ls(params: LsParams) -> list[str] | FileListResult:
    """Execute ls command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.ls(params)


async def execute_read(params: ReadParams) -> str | FileReadResult:
    """Execute read command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.read(params)


async def execute_write(params: WriteParams) -> str | FileWriteResult:
    """Execute write command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.write(params)


async def execute_edit(params: EditParams) -> str | FileEditResult:
    """Execute edit command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.edit(params)


async def execute_delete(params: DeleteParams) -> str | FileDeleteResult:
    """Execute delete command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.delete(params)


async def execute_trash(params: TrashParams) -> str | FileTrashResult:
    """Execute trash command (audited delete → move into .trash).

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.trash(params)


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
    """Execute mkdir command (create directory).

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.mkdir(params)


async def execute_move(params: MoveParams) -> str | FileMoveResult:
    """Execute move/rename command.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.move(params)


async def execute_stat(params: StatParams) -> str | FileStatResult:
    """Execute stat command to query existence/type/size.

    Delegates to FilesystemAccess façade which handles sandbox/store selection.
    """
    return await _fs_access.stat(params)
