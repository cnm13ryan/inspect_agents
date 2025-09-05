"""Sandbox filesystem adapter (DI) for tools_files.

This module extracts sandbox-related operations (preflight, validation,
symlink checks, and editor/bash invocations) behind a minimal adapter
interface so execute_* flows in tools_files.py can delegate without
duplicating control flow.

The default adapter preserves current behavior, messages, and timeouts by
reusing helpers from inspect_agents.fs and upstream Inspect tools.
"""

from __future__ import annotations

import shlex
from typing import Optional

import anyio

from . import fs as _fs
from .exceptions import ToolException


class SandboxFsAdapter:
    """Default sandbox FS adapter that proxies to Inspect tools.

    Methods mirror the operations currently embedded in execute_*:
    - preflight(tool): availability check (with TTL+env semantics)
    - validate(path): root confinement normalization/validation
    - deny_symlink(path): security check via bash `test -L`
    - wc_bytes(path): optional preflight byte size via bash `wc -c`
    - view(path,start,end): read range via `sed -n` with editor fallback
    - create(path,content): write via text_editor('create')
    - str_replace(path, old, new): edit via text_editor('str_replace')
    - ls(root): list via bash `ls -1`
    """

    # --- Capability checks -------------------------------------------------
    async def preflight(self, tool_name: str) -> bool:
        return await _fs.ensure_sandbox_ready(tool_name)

    # --- Path guards -------------------------------------------------------
    def validate(self, path: str) -> str:
        return _fs.validate_sandbox_path(path)

    async def deny_symlink(self, path: str) -> None:
        await _fs.deny_symlink(path)

    # --- Bash helpers ------------------------------------------------------
    async def wc_bytes(self, path: str) -> Optional[int]:
        """Return file byte count via `wc -c` or None on any failure."""
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            escaped_path = shlex.quote(path)
            with anyio.fail_after(_fs.default_tool_timeout()):
                result = await bash(action="run", command=f"wc -c {escaped_path}")
            if result and hasattr(result, "stdout") and result.stdout:
                try:
                    return int(str(result.stdout).strip().split()[0])
                except (ValueError, IndexError):
                    return None
            return None
        except Exception:
            return None

    # --- Core operations ---------------------------------------------------
    async def view(self, path: str, start_line: int, end_line: int) -> str:
        """Return a line-range from file using sed when available, else editor.

        - `start_line` is 1-based; `end_line=-1` means EOF.
        - Returns raw content without numbering (caller formats).
        """
        # Prefer `sed -n` for performance when bash is usable
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            escaped_path = shlex.quote(path)
            sed_range = f"{start_line},{end_line}p" if end_line != -1 else f"{start_line},$p"
            with anyio.fail_after(_fs.default_tool_timeout()):
                sed_result = await bash(action="run", command=f"sed -n '{sed_range}' {escaped_path}")
            raw = getattr(sed_result, "stdout", None)
            if raw and str(raw).strip() != "":
                return str(raw)
        except Exception:
            # Fall through to editor
            pass

        # Fallback: text_editor('view')
        from inspect_ai.tool._tools._text_editor import text_editor

        editor = text_editor()
        view_range = [start_line, end_line if end_line != -1 else -1]
        with anyio.fail_after(_fs.default_tool_timeout()):
            return await editor(command="view", path=path, view_range=view_range)

    async def create(self, path: str, content: str) -> None:
        from inspect_ai.tool._tools._text_editor import text_editor

        editor = text_editor()
        with anyio.fail_after(_fs.default_tool_timeout()):
            await editor(command="create", path=path, file_text=content)

    async def str_replace(self, path: str, old: str, new: str) -> str:
        from inspect_ai.tool._tools._text_editor import text_editor

        editor = text_editor()
        with anyio.fail_after(_fs.default_tool_timeout()):
            return await editor(command="str_replace", path=path, old_str=old, new_str=new)

    async def ls(self, root: str) -> list[str]:
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            escaped_root = shlex.quote(root)
            with anyio.fail_after(_fs.default_tool_timeout()):
                result = await bash(action="run", command=f"ls -1 {escaped_root}")
            if result and hasattr(result, "stdout") and result.stdout:
                return [line.strip() for line in str(result.stdout).strip().splitlines() if line.strip()]
            return []
        except Exception:
            return []


def get_default_adapter() -> SandboxFsAdapter:
    """Return the default adapter instance.

    Provided as a function to enable monkeypatching in tests.
    """

    return SandboxFsAdapter()

