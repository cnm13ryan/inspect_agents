import asyncio
import json

from inspect_agents.tools_files import (
    FilesParams,
    MoveParams,
    ReadParams,
    TrashParams,
    WriteParams,
    files_tool,
)


def _extract_trash_dst(caplog_records) -> str | None:
    for rec in caplog_records:
        msg = rec.getMessage()
        if not isinstance(msg, str):
            continue
        if "tool_event" not in msg:
            continue
        try:
            payload = json.loads(msg.split("tool_event ", 1)[1])
        except Exception:
            continue
        if payload.get("tool") == "files:trash" and payload.get("phase") == "end":
            return str(payload.get("dst"))
    return None


def test_trash_then_restore_store_mode(monkeypatch, caplog):
    # Store mode ensures offline, deterministic behavior
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "store")

    tool = files_tool()

    async def _trash_roundtrip():
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="docs/a.txt", content="hello")))
        await tool(params=FilesParams(root=TrashParams(command="trash", file_path="docs/a.txt")))

    caplog.set_level("INFO", logger="inspect_agents.tools")
    asyncio.run(_trash_roundtrip())

    # Locate trash destination from logs
    dst = _extract_trash_dst(caplog.records)
    assert dst is not None

    async def _restore_and_read():
        # Restore file by moving from trash dst back to original path
        await tool(params=FilesParams(root=MoveParams(command="move", src_path=dst, dst_path="docs/a.txt")))
        return await tool(
            params=FilesParams(root=ReadParams(command="read", file_path="docs/a.txt", offset=0, limit=1))
        )

    result = asyncio.run(_restore_and_read())
    text = str(result)
    assert "hello" in text.lower()
