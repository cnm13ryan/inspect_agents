import asyncio

import pytest

from inspect_agents.tools import ToolException
from inspect_agents.tools_files import (
    DeleteParams,
    FilesParams,
    MkdirParams,
    MoveParams,
    WriteParams,
    files_tool,
)


def test_policy_allow_and_deny(monkeypatch, caplog):
    tool = files_tool()
    # Allow only docs/**, deny docs/private/**
    monkeypatch.setenv("INSPECT_FS_ALLOW", "docs/**")
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/private/**")

    async def _run_ok():
        # Write allowed
        return await tool(params=FilesParams(root=WriteParams(command="write", file_path="docs/pub.txt", content="ok")))

    asyncio.run(_run_ok())

    # Move into denied subtree
    async def _run_move_denied():
        await tool(
            params=FilesParams(
                root=MoveParams(command="move", src_path="docs/pub.txt", dst_path="docs/private/secret.txt")
            )
        )

    caplog.set_level("INFO", logger="inspect_agents.tools")
    with pytest.raises(ToolException):
        asyncio.run(_run_move_denied())
    # Error log should include PolicyDenied and the deny rule
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "PolicyDenied" in logs
    assert "docs/private/**" in logs


def test_policy_denied_mkdir(monkeypatch):
    tool = files_tool()
    monkeypatch.setenv("INSPECT_FS_DENY", "disallowed/**")

    async def _run_mkdir():
        await tool(params=FilesParams(root=MkdirParams(command="mkdir", dir_path="disallowed/new")))

    with pytest.raises(ToolException):
        asyncio.run(_run_mkdir())


def test_policy_denied_delete(monkeypatch, caplog):
    tool = files_tool()
    # Force store mode to avoid sandbox delete shortcut
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "store")
    # Deny deleting anything under tmp/**
    monkeypatch.setenv("INSPECT_FS_DENY", "tmp/**")

    async def _setup_and_delete():
        # Create then attempt to delete a denied path
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="tmp/a.txt", content="x")))
        await tool(params=FilesParams(root=DeleteParams(command="delete", file_path="tmp/a.txt")))

    caplog.set_level("INFO", logger="inspect_agents.tools")
    with pytest.raises(ToolException):
        asyncio.run(_setup_and_delete())
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "PolicyDenied" in logs and "tmp/**" in logs
