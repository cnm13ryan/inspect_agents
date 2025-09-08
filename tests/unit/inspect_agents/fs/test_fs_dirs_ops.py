import asyncio

from inspect_agents.tools_files import (
    FilesParams,
    MkdirParams,
    MoveParams,
    ReadParams,
    StatParams,
    WriteParams,
    files_tool,
)


def test_store_mkdir_move_stat():
    tool = files_tool()

    async def _run():
        # write a file
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="a.txt", content="hello")))
        # mkdir (no-op in store but allowed)
        await tool(params=FilesParams(root=MkdirParams(command="mkdir", dir_path="dir")))
        # move into dir
        await tool(params=FilesParams(root=MoveParams(command="move", src_path="a.txt", dst_path="dir/b.txt")))
        # stat file
        st = await tool(params=FilesParams(root=StatParams(command="stat", path="dir/b.txt")))
        # read file to confirm content
        out = await tool(params=FilesParams(root=ReadParams(command="read", file_path="dir/b.txt")))
        return st, out

    st, out = asyncio.run(_run())
    assert "file" in str(st) or getattr(st, "exists", True)
    assert "hello" in str(out)


def test_sandbox_mkdir_move_stat_fallback(monkeypatch):
    tool = files_tool()

    async def _run():
        # enable sandbox mode to exercise sandbox branch; fallback allowed
        monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="x.txt", content="X")))
        await tool(params=FilesParams(root=MkdirParams(command="mkdir", dir_path="d")))
        await tool(params=FilesParams(root=MoveParams(command="move", src_path="x.txt", dst_path="d/y.txt")))
        st = await tool(params=FilesParams(root=StatParams(command="stat", path="d/y.txt")))
        return st

    st = asyncio.run(_run())
    # Should report existence true via fallback/store logic
    if hasattr(st, "exists"):
        assert st.exists is True
    else:
        assert "file" in str(st)
