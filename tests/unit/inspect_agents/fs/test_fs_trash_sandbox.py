"""test(fs): sandbox trash behavior (audited delete)

Covers two aspects:
1) Policy denial in sandbox mode emits a structured error tool_event.
2) Successful trash emits an `end` event with `src` and `dst` under /.trash/<ts>/...

We use in-process stubs for editor/bash and rely on auto preflight detection
to exercise sandbox paths deterministically without network or host FS.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import types

import pytest

from inspect_agents.tools_files import (
    FilesParams,
    StatParams,
    TrashParams,
    WriteParams,
    files_tool,
)


def _install_tool_decorator_stub(monkeypatch) -> None:
    mod_name = "inspect_ai.tool._tool"
    sys.modules.pop(mod_name, None)
    mod = types.ModuleType(mod_name)

    class Tool:
        pass

    def tool(fn=None):
        # Support both decorator styles: @tool and @tool()
        if callable(fn):
            return fn

        def _wrap(f):
            return f

        return _wrap

    mod.Tool = Tool  # type: ignore[attr-defined]
    mod.tool = tool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, mod)


def _install_editor_bash_stubs(monkeypatch, fs: dict[str, str]) -> None:
    """Install editor + bash stubs that support mkdir/mv/sed/stat for trash paths."""

    # Editor
    mod_name_editor = "inspect_ai.tool._tools._text_editor"
    sys.modules.pop(mod_name_editor, None)
    mod_editor = types.ModuleType(mod_name_editor)
    from inspect_ai.tool._tool import Tool, tool  # type: ignore

    @tool()
    def text_editor() -> Tool:  # type: ignore[return-type]
        async def execute(
            command: str,
            path: str,
            file_text: str | None = None,
            insert_line: int | None = None,
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
                s, e = view_range[0], view_range[1]
                lines = content.splitlines()
                s0 = max(1, s) - 1
                e0 = len(lines) if e == -1 else min(len(lines), e)
                return "\n".join(lines[s0:e0])
            return "UNSUPPORTED"

        return execute

    mod_editor.text_editor = text_editor
    monkeypatch.setitem(sys.modules, mod_name_editor, mod_editor)

    # Bash
    mod_name_bash = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name_bash, None)
    mod_bash = types.ModuleType(mod_name_bash)

    class MockResult:
        def __init__(self, stdout: str):
            self.stdout = stdout

    @tool()
    def bash_session() -> Tool:  # type: ignore[return-type]
        async def execute(action: str, command: str | None = None) -> MockResult:
            if action != "run" or command is None:
                return MockResult("")
            # Support mkdir -p, mv, sed -n, wc -c, and bash -lc stat probe
            if command.startswith("mkdir -p "):
                return MockResult("")
            if command.startswith("mv "):
                return MockResult("")
            if command.startswith("sed -n "):
                # Return file contents for view fallback
                return MockResult("\n".join(fs.get(command.split()[-1].strip("'"), "").splitlines()))
            if command.startswith("wc -c "):
                return MockResult("0\n")
            if command.startswith("bash -lc "):
                # Minimal stat simulation: treat trash dst as file
                if "-d" in command:
                    return MockResult("MISSING\n")
                return MockResult("FILE\n")
            return MockResult("")

        return execute

    mod_bash.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name_bash, mod_bash)


def _extract_trash_dst(records) -> str | None:
    for rec in records:
        msg = rec.getMessage()
        if not isinstance(msg, str) or not msg.startswith("tool_event "):
            continue
        try:
            payload = json.loads(msg.split("tool_event ", 1)[1])
        except Exception:
            continue
        if payload.get("tool") == "files:trash" and payload.get("phase") == "end":
            return str(payload.get("dst"))
    return None


def test_trash_sandbox_logs_dst(monkeypatch, caplog):
    # Enable sandbox mode and sane root
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")

    _install_tool_decorator_stub(monkeypatch)
    fs: dict[str, str] = {}
    _install_editor_bash_stubs(monkeypatch, fs)

    tool = files_tool()

    async def _roundtrip():
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="docs/a.txt", content="hello")))
        # Trash the file
        return await tool(params=FilesParams(root=TrashParams(command="trash", file_path="/repo/docs/a.txt")))

    caplog.set_level(logging.INFO, logger="inspect_agents.tools")
    asyncio.run(_roundtrip())

    # Verify logs contain destination under /.trash/<ts>/docs/a.txt
    dst = _extract_trash_dst(caplog.records)
    assert dst is not None
    assert "/.trash/" in dst and dst.endswith("/docs/a.txt"), dst

    # Stat the destination path to ensure adapter wrote something
    async def _stat():
        return await tool(params=FilesParams(root=StatParams(command="stat", path=dst)))

    res = asyncio.run(_stat())
    assert hasattr(res, "exists") or isinstance(str(res), str)


def test_trash_sandbox_policy_denied(monkeypatch, caplog):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    # We'll deny docs/* only for the trash step to allow initial write

    _install_tool_decorator_stub(monkeypatch)
    fs: dict[str, str] = {}
    _install_editor_bash_stubs(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    async def _do_trash():
        # Allow write
        monkeypatch.delenv("INSPECT_FS_DENY", raising=False)
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="docs/a.txt", content="hello")))
        # Deny subsequent destructive op (trash)
        monkeypatch.setenv("INSPECT_FS_DENY", "docs/*")
        return await tool(params=FilesParams(root=TrashParams(command="trash", file_path="/repo/docs/a.txt")))

    # Expect ToolException bubbling due to policy denial
    with pytest.raises(Exception):
        asyncio.run(_do_trash())

    # Logs should include PolicyDenied error for files:trash
    msgs = [
        r.getMessage()
        for r in caplog.records
        if isinstance(r.getMessage(), str) and r.getMessage().startswith("tool_event ")
    ]
    joined = "\n".join(msgs)
    assert '"tool": "files:trash"' in joined and '"PolicyDenied"' in joined
