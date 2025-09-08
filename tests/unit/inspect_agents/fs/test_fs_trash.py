import asyncio
import json

from inspect_agents.tools_files import (
    FilesParams,
    StatParams,
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


def test_trash_store_moves_and_logs(monkeypatch, caplog):
    # Force store mode for deterministic, offline behavior
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "store")

    tool = files_tool()

    async def _roundtrip():
        # Write a file
        await tool(params=FilesParams(root=WriteParams(command="write", file_path="docs/a.txt", content="hello")))
        # Trash it
        return await tool(params=FilesParams(root=TrashParams(command="trash", file_path="docs/a.txt")))

    caplog.set_level("INFO", logger="inspect_agents.tools")
    asyncio.run(_roundtrip())

    # Original path should be missing; inspect via stat
    async def _stat_missing():
        return await tool(params=FilesParams(root=StatParams(command="stat", path="docs/a.txt")))

    res = asyncio.run(_stat_missing())
    text = str(res)
    assert "missing" in text or (hasattr(res, "exists") and not res.exists)

    # Logs should include destination path under .trash/<ts>/docs/a.txt
    dst = _extract_trash_dst(caplog.records)
    assert dst is not None
    assert ("/.trash/" in dst) or (dst.startswith(".trash/"))
    assert dst.endswith("/docs/a.txt")

    # Optionally, verify we can read content at dst when running in store mode
    # (stat on dst should report file)
    async def _stat_dst():
        return await tool(
            params=FilesParams(root=StatParams(command="stat", path=dst if isinstance(dst, str) else str(dst)))
        )

    res2 = asyncio.run(_stat_dst())
    txt2 = str(res2)
    assert "file" in txt2 or (hasattr(res2, "exists") and res2.exists)
