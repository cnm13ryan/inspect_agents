import asyncio
import json

import pytest

from inspect_agents.exceptions import ToolException
from inspect_agents.tools_files import DeleteParams, execute_delete


def test_delete_sandbox_unsupported_raises_and_logs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Enable sandbox mode; ensure not in read-only variant for this test
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.delenv("INSPECT_AGENTS_FS_READ_ONLY", raising=False)

    # Capture tool_event logs emitted by observability wrapper
    caplog.set_level("INFO", logger="inspect_agents.tools")

    async def main() -> None:
        with pytest.raises(ToolException) as ei:
            await execute_delete(DeleteParams(file_path="tmp.txt"))
        # Canonical message must be exactly SandboxUnsupported
        msg = getattr(ei.value, "message", str(ei.value))
        assert msg == "SandboxUnsupported"

    asyncio.run(main())

    # Verify exactly one error log for files:delete with error=SandboxUnsupported
    error_events = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if "tool_event" not in msg:
            continue
        try:
            payload_str = msg.split("tool_event", 1)[1].strip()
            data = json.loads(payload_str)
        except Exception:
            continue
        if data.get("tool") == "files:delete" and data.get("phase") == "error":
            error_events.append(data)

    assert len(error_events) == 1
    assert error_events[0].get("error") == "SandboxUnsupported"
