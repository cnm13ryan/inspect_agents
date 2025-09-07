import asyncio
import sys

from inspect_agents.tools import edit_file, ls, read_file, write_file
from tests.fixtures.editor_stubs import install_bash_stub, install_editor_stub


def test_sandbox_mode_uses_editor_stub(monkeypatch):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    fs: dict[str, str] = {}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    r = read_file()
    w = write_file()
    e = edit_file()

    async def run_all():
        await w(file_path="/repo/a.txt", content="hello")
        pre = await r(file_path="/repo/a.txt", offset=0, limit=5)
        await e(file_path="/repo/a.txt", old_string="hello", new_string="hi")
        post = await r(file_path="/repo/a.txt", offset=0, limit=5)
        return pre, post

    pre, post = asyncio.run(run_all())
    assert pre.endswith("hello")
    assert post.endswith("hi")


def test_sandbox_mode_graceful_fallback_without_editor(monkeypatch):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    # Ensure no editor stub present so code falls back to store mode
    sys.modules.pop("inspect_ai.tool._tools._text_editor", None)

    r = read_file()
    w = write_file()
    e = edit_file()

    async def roundtrip():
        await w(file_path="b.txt", content="alpha\nbeta\n")
        out1 = await r(file_path="b.txt", offset=1, limit=1)
        await e(file_path="b.txt", old_string="beta", new_string="BETA")
        out2 = await r(file_path="b.txt", offset=1, limit=1)
        return out1, out2

    out1, out2 = asyncio.run(roundtrip())
    assert out1.strip().endswith("beta")
    assert out2.strip().endswith("BETA")


def test_sandbox_ls_command(monkeypatch):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    fs: dict[str, str] = {"file1.txt": "content1", "file2.py": "print('hello')", "README.md": "# Project"}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    ls_tool = ls()

    async def test_ls():
        result = await ls_tool()
        return result

    file_list = asyncio.run(test_ls())
    assert isinstance(file_list, list)
    assert set(file_list) == {"file1.txt", "file2.py", "README.md"}
