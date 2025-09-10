"""
E2E: Hardened Docker provider checks (opt-in).

This test exercises ops/providers/docker/compose.yaml to ensure the
runtime container enforces key sandbox guarantees:
 - Non-root UID/GID
 - Read-only root filesystem
 - No-new-privileges and ALL capabilities dropped
 - PIDs limit set

Opt-in only (never in default CI). Enable with:
  INSPECT_E2E_SANDBOX=1 pytest -q -m sandbox_e2e

Skips gracefully when Docker is unavailable or the env flag is unset.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.sandbox_e2e


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "ops/providers/docker/compose.yaml"


def _enabled() -> bool:
    val = os.getenv("INSPECT_E2E_SANDBOX", "").lower()
    return val in {"1", "true", "yes", "on", "docker", "all"}


def _check_prereqs() -> None:
    if not _enabled():
        pytest.skip("INSPECT_E2E_SANDBOX not enabled; skipping docker e2e")
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available; skipping")
    # Prefer `docker compose`; fall back to legacy docker-compose if needed
    if shutil.which("docker") is None and shutil.which("docker-compose") is None:
        pytest.skip("docker compose not available; skipping")
    if not COMPOSE.exists():
        pytest.skip(f"compose template missing: {COMPOSE}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=True,
    )


def _compose_cmd() -> list[str]:
    # Use the v2 plugin if present
    return ["docker", "compose"] if shutil.which("docker") else ["docker-compose"]


def _docker_inspect(name: str) -> dict:
    out = _run(["docker", "inspect", name]).stdout
    data = json.loads(out)
    assert isinstance(data, list) and data, "docker inspect returned no data"
    return data[0]


@pytest.mark.network
def test_docker_sandbox_hardening_end_to_end(tmp_path: Path) -> None:
    _check_prereqs()

    # Bring up the sandbox container in detached mode
    up_cmd = _compose_cmd() + [
        "-f",
        str(COMPOSE),
        "up",
        "-d",
    ]
    down_cmd = _compose_cmd() + ["-f", str(COMPOSE), "down", "-v"]

    try:
        _run(up_cmd)

        # Wait briefly for the container to become running
        name = "inspect-sandbox"
        for _ in range(20):
            try:
                state = _docker_inspect(name)["State"]["Running"]
                if state:
                    break
            except Exception:
                pass
            time.sleep(0.25)

        info = _docker_inspect(name)

        # UID:GID non-root
        user = info["Config"].get("User", "")
        assert user in {"1000:1000", "1000"}, f"expected non-root user, got {user!r}"

        # Read-only rootfs
        assert info["HostConfig"].get("ReadonlyRootfs") is True

        # PIDs limit
        assert int(info["HostConfig"].get("PidsLimit", 0)) == 256

        # No new privileges and cap drop ALL
        sec_opts = info["HostConfig"].get("SecurityOpt", []) or []
        assert any(isinstance(s, str) and s.startswith("no-new-privileges:") for s in sec_opts), (
            f"no-new-privileges missing: {sec_opts}"
        )

        cap_drop = info["HostConfig"].get("CapDrop", []) or []
        assert "ALL" in cap_drop, f"cap_drop missing ALL: {cap_drop}"

    finally:
        try:
            _run(down_cmd)
        except Exception:
            # Best-effort teardown
            pass
