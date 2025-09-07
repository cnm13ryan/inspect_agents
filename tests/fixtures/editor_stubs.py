"""Editor and bash tool stubs for sandbox tests.

These utilities install lightweight, in-process implementations of the
`text_editor` and `bash_session` tools from Inspect-AI that operate over
an in-memory dict to keep tests deterministic and offline.
"""

from __future__ import annotations

import sys
import types


def install_editor_stub(monkeypatch, fs: dict[str, str]) -> None:
    """Install a dict-backed `text_editor` tool stub."""

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
            insert_line: int | None = None,
            new_str: str | None = None,
            old_str: str | None = None,
            view_range: list[int] | None = None,
        ) -> str:
            if command == "create":
                fs[path] = file_text or ""
                return "OK"
            elif command == "view":
                content = fs.get(path, "")
                if view_range is None:
                    return content
                start, end = view_range
                lines = content.splitlines()
                s = max(1, start) - 1
                e = len(lines) if end == -1 else min(len(lines), end)
                return "\n".join(lines[s:e])
            elif command == "str_replace":
                content = fs.get(path, None)
                if content is None:
                    return "ERR"
                fs[path] = content.replace(old_str or "", new_str or "")
                return "OK"
            else:
                return "UNSUPPORTED"

        return execute

    mod.text_editor = text_editor
    monkeypatch.setitem(sys.modules, mod_name, mod)


def install_bash_stub(monkeypatch, fs: dict[str, str]) -> None:
    """Install a dict-backed `bash_session` tool stub that supports `ls -1`.

    The stub returns a minimal object with a `stdout` attribute matching the
    behavior expected by the repo tools.
    """

    mod_name = "inspect_ai.tool._tools._bash_session"
    sys.modules.pop(mod_name, None)

    mod = types.ModuleType(mod_name)

    from inspect_ai.tool._tool import Tool, tool

    class MockResult:
        def __init__(self, stdout: str):
            self.stdout = stdout

    @tool()
    def bash_session() -> Tool:  # type: ignore[return-type]
        async def execute(action: str, command: str | None = None) -> MockResult:
            if action == "run" and command and command.startswith("ls -1"):
                # Accept bare `ls -1` and `ls -1 /repo` variants (quoted/unquoted)
                if command == "ls -1" or command.endswith(" /repo") or "'/repo'" in command or '"/repo"' in command:
                    file_list = list(fs.keys())
                    return MockResult("\n".join(file_list))
                return MockResult("")
            return MockResult("")

        return execute

    mod.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name, mod)


def install_slow_text_editor(monkeypatch) -> None:
    """Install a `text_editor` stub that intentionally sleeps before returning.

    If a pytest ``monkeypatch`` fixture is provided, the stub is registered
    via ``monkeypatch.setitem(sys.modules, ...)`` so it is automatically
    cleaned up after the test. Otherwise, falls back to assigning directly
    into ``sys.modules``.
    """

    mod_name = "inspect_ai.tool._tools._text_editor"
    sys.modules.pop(mod_name, None)

    mod = types.ModuleType(mod_name)

    import anyio
    from inspect_ai.tool._tool import Tool, tool

    @tool()
    def text_editor() -> Tool:  # type: ignore[return-type]
        async def execute(
            command: str,
            path: str,
            file_text: str | None = None,
            view_range: list[int] | None = None,
            old_str: str | None = None,
            new_str: str | None = None,
        ) -> str:
            # Delay long enough to exceed typical per-test timeouts
            await anyio.sleep(1.0)
            return "SLOW"

        return execute

    mod.text_editor = text_editor
    # Always managed via pytest monkeypatch for auto-teardown
    monkeypatch.setitem(sys.modules, mod_name, mod)
