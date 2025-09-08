from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_runner_module() -> object:
    import importlib
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return importlib.import_module("examples.inspect.exploration.runner")


def test_supervisor_prompt_includes_planner_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner_module()

    captured: dict[str, str] = {}

    # Capture the composed supervisor prompt by intercepting runner.build_runner_agent
    def _stub_build_runner_agent(
        *,
        planner_cfg,
        attempts: int,
        model,
        supervisor_prompts=None,
        scoring_cfg=None,
    ) -> object:  # type: ignore[no-untyped-def]
        # Use runner's local prompt helper to mirror production prompt text
        override = (supervisor_prompts or {}).get("supervisor") if supervisor_prompts else None
        prompt = runner._supervisor_prompt(planner_cfg, override_text=override)
        captured["prompt"] = prompt
        return SimpleNamespace(name="agent", prompt=prompt, tools=[], attempts=attempts, model=model)

    monkeypatch.setattr(runner, "build_runner_agent", _stub_build_runner_agent)

    # Provide a deterministic planner config
    planner_cfg = {"breadth": 2, "depth": 1, "max_queries": 5, "site_hints": ["arxiv.org", "*.edu"]}
    _ = runner.build_runner_agent(planner_cfg=planner_cfg, attempts=3, model="dummy-model")

    # Assert JSON appears in prompt footer
    prompt = captured.get("prompt", "")
    assert "Planner config (JSON):" in prompt
    expected_json = json.dumps(planner_cfg, ensure_ascii=False)
    assert expected_json in prompt
