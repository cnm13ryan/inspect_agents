import asyncio
import logging
import os

import pytest

from inspect_agents.profiles import resolve_profile_from_env
from inspect_agents.tools import ToolException, write_file


def test_prod_profile_applies_readonly_and_blocks_writes(monkeypatch, caplog):
    # Prepare a clean env and select a prod-like profile (H>=H1)
    monkeypatch.setenv("INSPECT_PROFILE", "T1.H2.N2")
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.delenv("INSPECT_AGENTS_FS_READ_ONLY", raising=False)
    monkeypatch.delenv("INSPECT_SANDBOX_PREFLIGHT", raising=False)

    # Apply profile defaults to the process environment
    resolve_profile_from_env()

    # Defaults should now be present
    assert os.getenv("INSPECT_AGENTS_FS_READ_ONLY") == "1"
    assert os.getenv("INSPECT_SANDBOX_PREFLIGHT") == "force"

    # Write attempts in sandbox must raise SandboxReadOnly
    caplog.set_level(logging.INFO, logger="inspect_agents")
    wf = write_file()

    async def _attempt_write():
        with pytest.raises(ToolException) as exc:
            await wf(file_path="blocked.txt", content="x")
        return str(exc.value)

    msg = asyncio.run(_attempt_write())
    assert "SandboxReadOnly" in msg
