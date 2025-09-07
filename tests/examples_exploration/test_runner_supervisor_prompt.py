from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest


def _load_runner_module() -> object:
    import sys, importlib
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return importlib.import_module("examples.inspect.exploration.runner")


def test_supervisor_prompt_includes_planner_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner_module()

    captured: dict[str, str] = {}

    # Stub build_subagents to avoid creating real sub-agents/tools
    monkeypatch.setattr(runner, "build_subagents", lambda **_: [])

    # Capture supervisor prompt
    def _stub_build_supervisor(*, prompt: str, tools, attempts: int, model):  # type: ignore[no-untyped-def]
        captured["prompt"] = prompt
        return SimpleNamespace(name="agent", prompt=prompt, tools=tools, attempts=attempts, model=model)

    monkeypatch.setattr(runner, "build_supervisor", _stub_build_supervisor)

    # Provide a deterministic planner config
    planner_cfg = {"breadth": 2, "depth": 1, "max_queries": 5, "site_hints": ["arxiv.org", "*.edu"]}
    _ = runner.build_runner_agent(planner_cfg=planner_cfg, attempts=3, model="dummy-model")

    # Assert JSON appears in prompt footer
    prompt = captured.get("prompt", "")
    assert "Planner config (JSON):" in prompt
    expected_json = json.dumps(planner_cfg, ensure_ascii=False)
    assert expected_json in prompt

