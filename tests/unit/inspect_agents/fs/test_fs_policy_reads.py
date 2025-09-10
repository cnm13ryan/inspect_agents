"""test(fs): optional policy on reads and ls (sandbox)

Covers the feature-flagged enforcement path for non-destructive operations:
- When INSPECT_FS_POLICY_ENFORCE_READS is truthy, sandbox `read` is denied
  by policy and emits a structured error tool_event with `policy_rule`.
- When the flag is enabled, sandbox `ls` filters out denied entries and logs
  a PolicyDenied event for each filtered path; ordering is deterministic.

We install in-process stubs for the Inspect tools to exercise sandbox paths
without network or host FS access.
"""

from __future__ import annotations

import json
import logging
import sys
import types

import pytest

from inspect_agents.tools_files import (
    FilesParams,
    LsParams,
    ReadParams,
    files_tool,
)


def _install_tool_decorator_stub(monkeypatch) -> None:
    mod_name = "inspect_ai.tool._tool"
    sys.modules.pop(mod_name, None)
    mod = types.ModuleType(mod_name)

    class Tool:  # minimal placeholder
        pass

    def tool(fn=None):  # supports @tool and @tool()
        if callable(fn):
            return fn

        def _wrap(f):
            return f

        return _wrap

    mod.Tool = Tool  # type: ignore[attr-defined]
    mod.tool = tool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, mod)


def _install_editor_bash_stubs(monkeypatch, fs: dict[str, str], *, ls_entries: list[str] | None = None) -> None:
    # Editor stub (create/view minimal)
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
            view_range: list[int] | None = None,
            **_: object,
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

    # Bash stub: support ls -1, sed -n, wc -c
    mod_name_bash = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name_bash, None)
    mod_bash = types.ModuleType(mod_name_bash)

    class MockResult:
        def __init__(self, stdout: str):
            self.stdout = stdout

    @tool()
    def bash_session() -> Tool:  # type: ignore[return-type]
        async def execute(action: str, command: str | None = None) -> MockResult:
            if action != "run" or not command:
                return MockResult("")
            if command.startswith("ls -1 "):
                # Return provided entries (one per line)
                items = ls_entries or []
                return MockResult("\n".join(items) + ("\n" if items else ""))
            if command.startswith("sed -n "):
                # Last token is the quoted path
                path = command.split()[-1].strip("'\"")
                return MockResult(fs.get(path, ""))
            if command.startswith("wc -c "):
                return MockResult("0\n")
            return MockResult("")

        return execute

    mod_bash.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name_bash, mod_bash)


@pytest.mark.asyncio
async def test_read_policy_denied_with_flag(monkeypatch, caplog):
    # Enable sandbox and policy enforcement
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    monkeypatch.setenv("INSPECT_FS_POLICY_ENFORCE_READS", "1")

    _install_tool_decorator_stub(monkeypatch)
    fs: dict[str, str] = {"/repo/docs/secret.txt": "top secret"}
    _install_editor_bash_stubs(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    params = FilesParams(root=ReadParams(command="read", file_path="docs/secret.txt"))
    # Deny docs/* for this test
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/*")

    with pytest.raises(Exception) as exc:
        await tool(params=params)
    assert "PolicyDenied" in str(exc.value)

    # Verify a structured error event was logged for files:read
    msgs = [r.getMessage() for r in caplog.records if isinstance(r.getMessage(), str)]
    joined = "\n".join(msgs)
    assert '"tool": "files:read"' in joined and '"PolicyDenied"' in joined


@pytest.mark.asyncio
async def test_ls_policy_filters_and_logs(monkeypatch, caplog):
    # Enable sandbox and policy enforcement
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    monkeypatch.setenv("INSPECT_FS_POLICY_ENFORCE_READS", "1")

    _install_tool_decorator_stub(monkeypatch)
    fs: dict[str, str] = {}
    # ls returns in non-deterministic order; we will ensure sorting in code path
    _install_editor_bash_stubs(monkeypatch, fs, ls_entries=["a.txt", "secret.txt", "b.txt"])

    # Deny secret*
    monkeypatch.setenv("INSPECT_FS_DENY", "secret*")

    tool = files_tool()
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    out = await tool(params=FilesParams(root=LsParams(command="ls")))
    assert out == ["a.txt", "b.txt"]

    # Verify a PolicyDenied error was logged for files:ls
    logged = False
    for rec in caplog.records:
        msg = rec.getMessage()
        if not (isinstance(msg, str) and msg.startswith("tool_event ")):
            continue
        try:
            payload = json.loads(msg.split("tool_event ", 1)[1])
        except Exception:
            continue
        if payload.get("tool") == "files:ls" and payload.get("error") == "PolicyDenied":
            logged = True
            # Ensure path and policy_rule present
            assert payload.get("path") in {"secret.txt"}
            assert payload.get("policy_rule")
    assert logged, "Expected PolicyDenied event for files:ls"
