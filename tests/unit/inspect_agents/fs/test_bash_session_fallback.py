"""Ensure files.edit falls back when bash_session lacks run/command.

This test installs a bash_session stub that does not accept a generic
`run(command=...)` interface (mirrors the vendored Inspect API that uses
`input` instead). The edit flow should gracefully fall back to the editor
create path rather than raising a TypeError.
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from inspect_agents.tools_files import EditParams, FilesParams, files_tool


def _install_editor_stub(monkeypatch: pytest.MonkeyPatch, fs: dict[str, str]) -> None:
    mod_name = "inspect_ai.tool._tools._text_editor"
    sys.modules.pop(mod_name, None)

    mod = types.ModuleType(mod_name)

    from inspect_ai.tool._tool import Tool, tool

    @tool()
    def text_editor() -> Tool:  # type: ignore[return-type]
        async def execute(
            command: str,
            path: str,
            file_text: str | None = None,
            insert_line: int | None = None,  # unused
            new_str: str | None = None,
            old_str: str | None = None,
            view_range: list[int] | None = None,
        ) -> str:
            if command == "create":
                fs[path] = file_text or ""
                return "OK"
            if command == "view":
                content = fs.get(path, "")
                if view_range is None:
                    return content
                start, end = view_range
                lines = content.splitlines()
                s = max(1, start) - 1
                e = len(lines) if end == -1 else min(len(lines), end)
                return "\n".join(lines[s:e])
            if command == "str_replace":
                content = fs.get(path, None)
                if content is None:
                    return "ERR"
                fs[path] = content.replace(old_str or "", new_str or "")
                return "OK"
            return "UNSUPPORTED"

        return execute

    mod.text_editor = text_editor
    monkeypatch.setitem(sys.modules, mod_name, mod)


def _install_bash_without_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install bash_session stub that lacks a run/command interface."""
    mod_name = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name, None)

    mod = types.ModuleType(mod_name)

    from inspect_ai.tool._tool import Tool, tool

    class MockResult:
        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    @tool()
    def bash_session() -> Tool:  # type: ignore[return-type]
        async def execute(action: str, input: str | None = None) -> MockResult:  # noqa: A002
            # Deliberately no support for action="run" with command=...
            if action in {"type", "read"}:
                return MockResult("")
            return MockResult("")

        return execute

    mod.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name, mod)


class TestBashSessionFallback:
    def test_edit_falls_back_when_run_unsupported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
        monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")

        fs: dict[str, str] = {"/repo/f.txt": "hello world"}
        _install_editor_stub(monkeypatch, fs)
        _install_bash_without_run(monkeypatch)

        tool = files_tool()

        async def run_case() -> str:
            params = FilesParams(
                root=EditParams(
                    command="edit",
                    file_path="/repo/f.txt",
                    old_string="hello",
                    new_string="hi",
                )
            )
            return await tool(params)

        result = asyncio.run(run_case())
        assert "Updated file" in result
        # Ensure content was updated via fallback path
        assert fs["/repo/f.txt"].startswith("hi ")
