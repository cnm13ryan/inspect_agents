import asyncio
import sys
import types

from inspect_agents.tools import read_file, write_file


def _install_editor_stub(monkeypatch, fs: dict[str, str]):
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
            return "UNSUPPORTED"

        return execute

    mod.text_editor = text_editor
    monkeypatch.setitem(sys.modules, mod_name, mod)


def _install_bash_stub(monkeypatch):
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
            # Minimal stub: return empty for unknown commands; ensures preflight passes
            return MockResult("")

        return execute

    mod.bash_session = bash_session
    monkeypatch.setitem(sys.modules, mod_name, mod)


def test_store_numbering_padded(monkeypatch):
    # Ensure legacy string output
    monkeypatch.delenv("INSPECT_AGENTS_TYPED_RESULTS", raising=False)
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "store")

    r = read_file()
    w = write_file()

    async def run():
        await w(file_path="pad.txt", content="alpha\nbeta\n")
        out = await r(file_path="pad.txt", offset=0, limit=2)
        return out

    out = asyncio.run(run())
    lines = str(out).splitlines()
    assert lines[0].startswith("     1\t") and lines[0].endswith("alpha")
    assert lines[1].startswith("     2\t") and lines[1].endswith("beta")


def test_sandbox_numbering_padded(monkeypatch):
    # Ensure legacy string output
    monkeypatch.delenv("INSPECT_AGENTS_TYPED_RESULTS", raising=False)
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")

    # In-memory FS and stubs so sandbox path is exercised without external deps
    fs: dict[str, str] = {}
    _install_editor_stub(monkeypatch, fs)
    _install_bash_stub(monkeypatch)

    r = read_file()
    w = write_file()

    async def run():
        await w(file_path="/repo/pad.txt", content="alpha\nbeta\n")
        out = await r(file_path="/repo/pad.txt", offset=0, limit=2)
        return out

    out = asyncio.run(run())
    lines = str(out).splitlines()
    assert lines[0].startswith("     1\t") and lines[0].endswith("alpha")
    assert lines[1].startswith("     2\t") and lines[1].endswith("beta")
