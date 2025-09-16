import json
import logging

import pytest

from inspect_agents.tools_files import WriteParams, execute_write


def _cap_tool_events(caplog):
    events = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
                events.append(payload)
            except Exception:
                pass
    return events


@pytest.mark.asyncio
async def test_files_events_include_profile_context_when_enabled(caplog, monkeypatch):
    # Enable enrichment and set a valid INSPECT_PROFILE
    monkeypatch.setenv("INSPECT_OBS_INCLUDE_PROFILE", "1")
    monkeypatch.setenv("INSPECT_PROFILE", "T1.H2.N0")
    monkeypatch.delenv("INSPECT_OBS_REDACT_PATHS", raising=False)

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    params = WriteParams(command="write", file_path="obs.txt", content="hello")
    await execute_write(params)

    events = _cap_tool_events(caplog)
    # Look for an end event from files:write
    ev = next((e for e in events if e.get("tool") == "files:write" and e.get("phase") == "end"), None)
    assert ev is not None, f"files:write end event not found in {events}"

    # Enrichment fields included
    assert ev.get("t") == "T1"
    assert ev.get("h") == "H2"
    assert ev.get("n") == "N0"
    assert "fs_root" in ev


@pytest.mark.asyncio
async def test_files_events_skip_profile_context_when_disabled(caplog, monkeypatch):
    # Ensure enrichment is disabled; profile may be set but should not be logged
    monkeypatch.delenv("INSPECT_OBS_INCLUDE_PROFILE", raising=False)
    monkeypatch.setenv("INSPECT_PROFILE", "T0.H1.N2")

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    params = WriteParams(command="write", file_path="obs2.txt", content="world")
    await execute_write(params)

    events = _cap_tool_events(caplog)
    ev = next((e for e in events if e.get("tool") == "files:write" and e.get("phase") == "end"), None)
    assert ev is not None

    # No enrichment fields when the flag is off
    for k in ("t", "h", "n", "fs_root"):
        assert k not in ev


@pytest.mark.asyncio
async def test_files_events_redact_fs_root_when_enabled(caplog, monkeypatch):
    # Enable enrichment and redaction; set an explicit fs root to verify basename redaction
    monkeypatch.setenv("INSPECT_OBS_INCLUDE_PROFILE", "1")
    monkeypatch.setenv("INSPECT_OBS_REDACT_PATHS", "1")
    monkeypatch.setenv("INSPECT_PROFILE", "T0.H1.N2")
    monkeypatch.setenv("INSPECT_AGENTS_FS_ROOT", "/very/secret/project-root")

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    params = WriteParams(command="write", file_path="obs3.txt", content="ok")
    await execute_write(params)

    events = _cap_tool_events(caplog)
    ev = next((e for e in events if e.get("tool") == "files:write" and e.get("phase") == "end"), None)
    assert ev is not None

    # fs_root should be redacted to the basename only
    fs_root = ev.get("fs_root")
    assert fs_root == "project-root"
    # Ensure path separators do not appear
    assert "/" not in str(fs_root)
