import asyncio
import json

import pytest

from inspect_agents.exceptions import ToolException
from inspect_agents.tools_files import (
    EditParams,
    FilesParams,
    MkdirParams,
    MoveParams,
    WriteParams,
    files_tool,
)
from tests.fixtures.editor_stubs import install_bash_stub, install_editor_stub


def _find_policy_log(caplog_records, tool_name: str):
    for rec in caplog_records:
        msg = rec.getMessage()
        if not isinstance(msg, str) or not msg.startswith("tool_event "):
            continue
        try:
            payload = json.loads(msg[len("tool_event ") :])
        except Exception:
            continue
        if payload.get("tool") == tool_name and payload.get("phase") == "error":
            if payload.get("error") == "PolicyDenied":
                return payload
    return None


def test_sandbox_write_policy_denial_post_normalization(monkeypatch, caplog):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    # Deny docs/private/**; ensure normalization collapses ./../
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/private/**")

    fs: dict[str, str] = {}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level("INFO", logger="inspect_agents.tools")

    async def _run():
        params = FilesParams(
            root=WriteParams(
                command="write",
                file_path="/repo/docs/./../docs/private/secret.txt",
                content="x",
            )
        )
        with pytest.raises(ToolException):
            await tool(params=params)

    asyncio.run(_run())
    payload = _find_policy_log(caplog.records, "files:write")
    assert payload is not None and payload.get("policy_rule") == "docs/private/**"


def test_sandbox_edit_policy_denial_post_normalization(monkeypatch, caplog):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/private/**")

    fs: dict[str, str] = {}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level("INFO", logger="inspect_agents.tools")

    async def _run():
        params = FilesParams(
            root=EditParams(
                command="edit",
                file_path="/repo/docs/../docs/private/conf.txt",
                old_string="a",
                new_string="b",
            )
        )
        with pytest.raises(ToolException):
            await tool(params=params)

    asyncio.run(_run())
    payload = _find_policy_log(caplog.records, "files:edit")
    assert payload is not None and payload.get("policy_rule") == "docs/private/**"


def test_sandbox_mkdir_policy_denial_post_normalization(monkeypatch, caplog):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/private/**")

    fs: dict[str, str] = {}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level("INFO", logger="inspect_agents.tools")

    async def _run():
        params = FilesParams(root=MkdirParams(command="mkdir", dir_path="/repo/docs/./private/sub"))
        with pytest.raises(ToolException):
            await tool(params=params)

    asyncio.run(_run())
    payload = _find_policy_log(caplog.records, "files:mkdir")
    assert payload is not None and payload.get("policy_rule") == "docs/private/**"


def test_sandbox_move_policy_denial_post_normalization(monkeypatch, caplog):
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    monkeypatch.setenv("INSPECT_FS_DENY", "docs/private/**")

    fs: dict[str, str] = {}
    install_editor_stub(monkeypatch, fs)
    install_bash_stub(monkeypatch, fs)

    tool = files_tool()
    caplog.set_level("INFO", logger="inspect_agents.tools")

    async def _run():
        params = FilesParams(
            root=MoveParams(
                command="move",
                src_path="/repo/docs/a.txt",
                dst_path="/repo/docs/./../docs/private/secret.txt",
            )
        )
        with pytest.raises(ToolException):
            await tool(params=params)

    asyncio.run(_run())
    payload = _find_policy_log(caplog.records, "files:move")
    assert payload is not None and payload.get("policy_rule") == "docs/private/**"
