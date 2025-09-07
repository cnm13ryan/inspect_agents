import json
import logging

import pytest

from inspect_agents.tools import read_file, write_file
from inspect_agents.tools_files import FilesParams, ReadParams, files_tool


def _parse_tool_events(records):
    events = []
    for rec in records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
                events.append(payload)
            except Exception:
                pass
    return events


@pytest.mark.asyncio
async def test_read_wrapper_parity_with_files_tool(caplog):
    """Wrapper read_file() should route through unified files tool and match behavior."""
    caplog.set_level(logging.INFO, logger="inspect_agents")

    # Create content to read
    write = write_file()
    await write(file_path="parity.txt", content="hello\nworld\n")

    # 1) Call wrapper and capture its logs
    before = len(caplog.records)
    read = read_file()
    out_wrapper = await read(file_path="parity.txt", offset=1, limit=1)
    wrapper_events = _parse_tool_events(caplog.records[before:])
    wrapper_read_phases = [e["phase"] for e in wrapper_events if e.get("tool") == "files:read"]

    # 2) Call unified files tool with equivalent params
    files = files_tool()
    before2 = len(caplog.records)
    out_files = await files(
        params=FilesParams(root=ReadParams(command="read", file_path="parity.txt", offset=1, limit=1))
    )
    files_events = _parse_tool_events(caplog.records[before2:])
    files_read_phases = [e["phase"] for e in files_events if e.get("tool") == "files:read"]

    # Assert result equality and identical phase sequence for the read operation
    assert out_wrapper == out_files
    assert files_read_phases == wrapper_read_phases == ["start", "end"]
