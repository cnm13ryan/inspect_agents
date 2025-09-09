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
from collections.abc import AsyncIterator

import anyio

from . import fs as _fs


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
    async def wc_bytes(self, path: str) -> int | None:
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
    async def view_chunks(
        self, path: str, start_line: int, max_lines: int, *, chunk_size_lines: int = 512
    ) -> AsyncIterator[str]:
        """Return content from file in chunks for streaming reads.

        Args:
            path: file path
            start_line: 1-based starting line
            max_lines: maximum lines to read (0 means unbounded)
            chunk_size_lines: lines per chunk for streaming

        Yields:
            String chunks containing lines from the file
        """

        # Use sed to read file in chunks
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            escaped_path = shlex.quote(path)

            current_line = start_line
            remaining_lines = None if max_lines <= 0 else max_lines

            while remaining_lines is None or remaining_lines > 0:
                # Calculate chunk size for this iteration
                lines_to_read = chunk_size_lines
                if remaining_lines is not None:
                    lines_to_read = min(chunk_size_lines, remaining_lines)

                # Calculate end line for sed command
                end_line = current_line + lines_to_read - 1
                sed_range = f"{current_line},{end_line}p"

                with anyio.fail_after(_fs.default_tool_timeout()):
                    result = await bash(action="run", command=f"sed -n '{sed_range}' {escaped_path}")

                if result and hasattr(result, "stdout") and result.stdout:
                    chunk_content = str(result.stdout).rstrip("\n")
                    if not chunk_content:
                        # No more content
                        break

                    # Count actual lines returned to track progress
                    actual_lines = len(chunk_content.splitlines())
                    if actual_lines == 0:
                        break

                    yield chunk_content
                    current_line += actual_lines

                    if remaining_lines is not None:
                        remaining_lines -= actual_lines

                    # If we got fewer lines than requested, we've reached EOF
                    if actual_lines < lines_to_read:
                        break
                else:
                    break

        except Exception:
            # Fallback: use view method and split into chunks
            try:
                full_content = await self.view(path, start_line, -1 if max_lines <= 0 else start_line + max_lines - 1)
                if full_content:
                    lines = full_content.splitlines()
                    if max_lines > 0:
                        lines = lines[:max_lines]

                    # Yield in chunks
                    for i in range(0, len(lines), chunk_size_lines):
                        chunk_lines = lines[i : i + chunk_size_lines]
                        yield "\n".join(chunk_lines)
            except Exception:
                return

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

    # --- New directory/metadata helpers ------------------------------------
    async def mkdir(self, path: str) -> None:
        """Create a directory (parents as needed) via bash when available.

        Falls back to a no-op if neither bash nor editor can approximate it.
        """
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            escaped = shlex.quote(path)
            with anyio.fail_after(_fs.default_tool_timeout()):
                await bash(action="run", command=f"mkdir -p {escaped}")
        except Exception:
            # No-op fallback; directory presence is inferred by file paths
            return

    async def move(self, src: str, dst: str) -> None:
        """Move/rename a file or directory using bash when available.

        Falls back to read+create for files when editor is available.
        """
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            s = shlex.quote(src)
            d = shlex.quote(dst)
            with anyio.fail_after(_fs.default_tool_timeout()):
                await bash(action="run", command=f"mv {s} {d}")
            return
        except Exception:
            pass

        # Fallback: file-only best-effort move via editor (copy semantics)
        try:
            text = await self.view(src, 1, -1)
            await self.create(dst, text)
        except Exception:
            return

    async def trash(self, src: str, dst: str) -> None:
        """Move a path into a trash location, creating parents as needed.

        This is a convenience that ensures the destination directory exists
        before delegating to a regular move operation. Prefer bash when
        available; otherwise fall back to create+copy semantics as in move().
        """
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            import os as _os

            trash_dir = _os.path.dirname(dst)
            with anyio.fail_after(_fs.default_tool_timeout()):
                await bash(action="run", command=f"mkdir -p {shlex.quote(trash_dir)}")
                await bash(action="run", command=f"mv {shlex.quote(src)} {shlex.quote(dst)}")
            return
        except Exception:
            pass

        # Fallback behavior mirrors move(): copy via editor then rely on best-effort
        try:
            text = await self.view(src, 1, -1)
            # Ensure parent via mkdir (best-effort)
            try:
                await self.mkdir(dst.rsplit("/", 1)[0])
            except Exception:
                pass
            await self.create(dst, text)
        except Exception:
            return

    async def stat(self, path: str) -> tuple[bool, bool, int | None]:
        """Return (exists, is_dir, size_bytes|None) using bash or editor fallback."""
        # Prefer bash test + wc -c
        try:
            from inspect_ai.tool._tools._bash_session import bash_session

            bash = bash_session()
            p = shlex.quote(path)
            with anyio.fail_after(_fs.default_tool_timeout()):
                kind = await bash(
                    action="run",
                    command=f"bash -lc 'if [ -d {p} ]; then echo DIR; elif [ -f {p} ]; then echo FILE; else echo MISSING; fi'",
                )
            label = str(getattr(kind, "stdout", "")).strip()
            if label == "DIR":
                return True, True, None
            if label == "FILE":
                size = await self.wc_bytes(path)
                return True, False, size
        except Exception:
            pass

        # Fallback via editor view: file existence only
        try:
            raw = await self.view(path, 1, -1)
            if raw is not None:
                size = len(str(raw).encode("utf-8"))
                return True, False, size
        except Exception:
            pass
        return False, False, None


def get_default_adapter() -> SandboxFsAdapter:
    """Return the default adapter instance.

    Provided as a function to enable monkeypatching in tests.
    """

    return SandboxFsAdapter()
