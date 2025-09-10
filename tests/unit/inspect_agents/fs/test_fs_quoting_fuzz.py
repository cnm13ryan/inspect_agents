import asyncio
import os
import shlex
import sys
import types

import pytest

from inspect_agents.fs_adapter import SandboxFsAdapter


def _install_bash_capture_stub(monkeypatch: pytest.MonkeyPatch, sink: list[str]) -> None:
    """Install a minimal `bash_session` stub that records commands.

    Avoids importing upstream Inspect modules; provides just enough shape
    for `SandboxFsAdapter` to call `bash(action="run", command=...)`.
    """

    mod_name = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name, None)
    mod = types.ModuleType(mod_name)

    class MockResult:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    async def _execute(action: str, command: str | None = None) -> MockResult:
        # Only record when executing a concrete command
        if action == "run" and command is not None:
            sink.append(command)
        return MockResult("")

    def bash_session():  # type: ignore[override]
        return _execute

    mod.bash_session = bash_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, mod)


def test_trash_commands_use_shlex_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force sandbox mode (for clarity; adapter prefers bash path first)
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")

    commands: list[str] = []
    _install_bash_capture_stub(monkeypatch, commands)

    adapter = SandboxFsAdapter()

    tricky_names = [
        "a space.txt",
        "qu\"o'te.txt",
        "uni🚀code.txt",
        "semi;colon.txt",
        "$crazy$(rm -rf).txt",
        "square[brackets]{curly}.txt",
        "pipe|and&redir>.txt",
        "back\\slash.txt",
    ]

    def run_once(src: str, dst: str) -> None:
        asyncio.run(adapter.trash(src, dst))

    for name in tricky_names:
        src = f"/repo/docs/{name}"
        dst = f"/repo/.trash/2025-09-10/{name}"
        before = len(commands)
        run_once(src, dst)
        after = len(commands)
        # Expect exactly two commands per trash(): mkdir -p <dir> and mv <src> <dst>
        assert after - before == 2
        mkdir_cmd, mv_cmd = commands[before:after]

        expected_mkdir = f"mkdir -p {shlex.quote(os.path.dirname(dst))}"
        expected_mv = f"mv {shlex.quote(src)} {shlex.quote(dst)}"

        assert mkdir_cmd == expected_mkdir
        assert mv_cmd == expected_mv
