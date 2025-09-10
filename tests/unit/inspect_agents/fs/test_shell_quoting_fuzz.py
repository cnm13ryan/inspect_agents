"""test(fs): shell quoting fuzz for sandbox adapter

Exercises SandboxFsAdapter operations with "funky" paths to ensure commands
are safely quoted via `shlex.quote` (spaces, quotes, backticks, unicode).

The test installs an in-process `bash_session` stub that records command
strings and returns minimal results so we can assert the exact quoting used.
"""

from __future__ import annotations

import shlex
import sys
import types
from typing import Any

import pytest

from inspect_agents.fs_adapter import SandboxFsAdapter
from tests.fixtures.editor_stubs import install_editor_stub


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fname",
    [
        "a b.txt",
        "quote'file.txt",
        'double"quote.txt',
        "back`tick`.txt",
        "üni code.txt",
        "semi;colon.txt",
    ],
)
async def test_shell_quoting_across_ops(monkeypatch, fname):
    # Enable sandbox mode and root confinement
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    # Ensure preflight runs (auto) and sees our in-process stub as available
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")

    # Install a minimal stub for `inspect_ai.tool._tool` to satisfy fixtures
    mod_name = "inspect_ai.tool._tool"
    sys.modules.pop(mod_name, None)
    tool_mod = types.ModuleType(mod_name)

    class Tool:  # noqa: D401 - simple type marker
        pass

    def tool(fn=None):
        # Support both decorator styles: @tool and @tool()
        if callable(fn):
            return fn

        def _wrap(f):
            return f

        return _wrap

    tool_mod.Tool = Tool  # type: ignore[attr-defined]
    tool_mod.tool = tool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, tool_mod)

    # Backing in-memory FS and command recorder
    fs: dict[str, str] = {}
    commands: list[str] = []

    # Editor stub for create/view used by adapter fallbacks
    install_editor_stub(monkeypatch, fs)

    # Advanced bash stub that records commands and simulates minimal outputs
    mod_name = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name, None)
    mod = types.ModuleType(mod_name)

    class MockResult:
        def __init__(self, stdout: str):
            self.stdout = stdout

    # Use the stubbed decorator and Tool type from our module
    from inspect_ai.tool._tool import Tool, tool  # type: ignore  # noqa: E402

    @tool()
    def bash_session() -> Tool:  # type: ignore[return-type]
        async def execute(action: str, command: str | None = None) -> Any:
            if action != "run" or command is None:
                return MockResult("")
            commands.append(command)
            # Minimal behavior for operations under test
            if command.startswith("wc -c "):
                # Return byte length for the target path if present
                # Not parsing the path; a non-empty number is sufficient for the adapter path
                return MockResult("0\n")
            if command.startswith("sed -n "):
                return MockResult("hello\nworld\n")
            if command.startswith("mkdir -p "):
                return MockResult("")
            if command.startswith("mv "):
                return MockResult("")
            if command.startswith("ls -1"):
                return MockResult("\n".join(sorted({p.split("/repo/")[-1] for p in fs.keys()})))
            if command.startswith("bash -lc "):
                # stat helper; pretend files exist
                if "-d" in command:
                    return MockResult("MISSING\n")
                return MockResult("FILE\n")
            return MockResult("")

        return execute

    mod.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name, mod)

    adapter = SandboxFsAdapter()
    path = f"/repo/{fname}"

    # Create the file via editor
    await adapter.create(path, "alpha\nβeta\n")

    # wc_bytes should quote path
    await adapter.wc_bytes(path)
    assert commands and commands[-1] == f"wc -c {shlex.quote(path)}"

    # view with a range uses sed -n '<start>,<end>p' and quoted path
    await adapter.view(path, 1, 2)
    assert "sed -n '1,2p' " in commands[-1]
    assert commands[-1].endswith(shlex.quote(path))

    # mkdir parents for a directory with funky name
    dir_path = f"/repo/{fname}.d"
    await adapter.mkdir(dir_path)
    assert commands[-1] == f"mkdir -p {shlex.quote(dir_path)}"

    # move quotes both src and dst
    dst_path = f"/repo/{fname}.moved"
    await adapter.move(path, dst_path)
    assert commands[-1] == f"mv {shlex.quote(path)} {shlex.quote(dst_path)}"

    # trash should mkdir -p trash dir and then mv with quoted paths
    trash_dst = f"/repo/.trash/123/{fname}"
    await adapter.trash(dst_path, trash_dst)
    # Expect the last two commands to be mkdir then mv
    assert commands[-2] == f"mkdir -p {shlex.quote('/repo/.trash/123')}"
    assert commands[-1] == f"mv {shlex.quote(dst_path)} {shlex.quote(trash_dst)}"

    # stat issues a bash -lc script; ensure our quoted path appears in command
    await adapter.stat(trash_dst)
    assert shlex.quote(trash_dst) in commands[-1]
