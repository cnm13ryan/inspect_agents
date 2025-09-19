from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_NETWORK", "1")


@pytest.fixture
def harness_module(monkeypatch: pytest.MonkeyPatch):
    import importlib
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module = importlib.import_module("examples.vending_bench.run")
    return module


def _fake_state(message_count: int = 3, completion: str = "Episode complete") -> Any:
    return SimpleNamespace(
        output=SimpleNamespace(completion=completion),
        messages=[SimpleNamespace(role="user")] * message_count,
    )


@pytest.mark.parametrize("include_defaults", [False, True])
def test_run_episode_collects_metrics(monkeypatch: pytest.MonkeyPatch, harness_module, include_defaults: bool) -> None:
    records: dict[str, Any] = {}

    async def fake_run_agent(agent, input, limits, raise_on_limit):  # type: ignore[no-untyped-def]
        records["input"] = input
        records["limits"] = limits
        records["agent"] = agent
        return _fake_state()

    captured: dict[str, Any] = {}

    def fake_build_supervisor_agent(model, include_defaults=False):  # type: ignore[no-untyped-def]
        captured["model"] = model
        captured["include_defaults"] = include_defaults
        return SimpleNamespace(tag="supervisor", model=model, include_defaults=include_defaults)

    monkeypatch.setattr(harness_module, "run_agent", fake_run_agent)
    monkeypatch.setattr(harness_module, "build_supervisor_agent", fake_build_supervisor_agent)

    metrics = harness_module.run_episode(seed=11, model="stub-model", include_defaults=include_defaults)

    # Metrics should include config, conversation summary, and tool counts
    assert metrics["config"]["seed"] == 11
    assert metrics["config"]["model"] == "stub-model"
    assert metrics["config"]["include_defaults"] is include_defaults
    assert metrics["conversation"]["message_count"] == 3
    assert metrics["telemetry"]["seed"] == 11
    assert metrics["tool_counts"] == {}

    # Supervisor builder invoked with forwarded arguments
    assert captured["model"] == "stub-model"
    assert captured["include_defaults"] is include_defaults

    # Limits should include message cap from EnvConfig
    message_limit = next(limit for limit in records["limits"] if getattr(limit, "limit", None) == 2000)
    assert getattr(message_limit, "limit", None) == 2000
    assert records["input"].startswith("Manage the vending machine")


def test_cli_writes_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, harness_module) -> None:
    output_path = tmp_path / "metrics.json"

    monkeypatch.setattr(harness_module, "run_episode", lambda **_: {"ok": True})
    monkeypatch.setattr(harness_module, "resolve_model", lambda provider=None, model=None: "stub-model")
    monkeypatch.setattr(harness_module._utils, "apply_tool_env_from_args", lambda args: None)
    monkeypatch.setattr(harness_module._utils, "ensure_repo_src_on_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(harness_module._utils, "load_env_files", lambda *args, **kwargs: None)

    argv = [
        "run.py",
        "--seed",
        "5",
        "--provider",
        "offline",
        "--model",
        "toy",
        "--output",
        str(output_path),
    ]

    monkeypatch.setattr("sys.argv", argv)

    harness_module.main()

    data = json.loads(output_path.read_text())
    assert data == {"ok": True}
