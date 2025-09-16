from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_runner_module() -> object:
    """Import the examples exploration runner by file path.

    Mirrors other tests' import-by-path approach to avoid package import
    conflicts when a site-packages "examples" module exists.
    """
    import importlib
    import sys

    # Ensure repo root on path so the local examples package resolves
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    return importlib.import_module("examples.inspect.exploration.runner")


@pytest.mark.asyncio
async def test_yaml_supervisor_overrides_applied(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = _load_runner_module()
    # Import the consolidated runner module; the legacy shim delegates here
    import importlib

    new_runner = importlib.import_module("examples.runners.exploration_runner")

    # Build a minimal YAML with supervisor attempts + prompt overrides and scoring
    yaml_text = (
        "version: 1\n"
        "policy:\n  max_queries: 3\n  breadth: 2\n  depth: 1\n"
        "scoring:\n  w_authority: 0.4\n"
        "supervisor:\n  attempts: 7\n  prompts:\n"
        "    supervisor: SUPERVISOR-OVERRIDE\n"
        "    research: RESEARCH-OVERRIDE\n"
        "    critique: CRITIQUE-OVERRIDE\n"
    )
    cfg_path = tmp_path / "exploration.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")

    # Capture args passed into build_runner_agent
    captured = {}

    def _capture_build_runner_agent(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)

        async def _dummy_agent(state, *args, **kwargs):  # type: ignore[no-untyped-def]
            return state

        return _dummy_agent

    async def _stub_run_agent(agent, user_input, approval=None, limits=None):  # type: ignore[no-untyped-def]
        # Return a tiny object with an `output` attribute for compatibility
        return SimpleNamespace(output=SimpleNamespace(completion="OK"))

    # Stubs to keep _amain fast and offline (patch the new runner module)
    monkeypatch.setattr(new_runner, "build_runner_agent", _capture_build_runner_agent)
    monkeypatch.setattr(new_runner, "run_agent", _stub_run_agent)
    monkeypatch.setattr(new_runner, "approval_preset", lambda *_: [])
    monkeypatch.setattr(new_runner, "resolve_model", lambda *_, **__: "dummy-model")

    # Call the async entrypoint with a CLI attempts value that should be
    # overridden by YAML supervisor.attempts
    args = SimpleNamespace(prompt="Test topic", config=str(cfg_path), attempts=1)
    await runner._amain(args)  # type: ignore[arg-type]

    # Assert: runner honored YAML overrides when composing the agent
    assert captured.get("attempts") == 7  # YAML overrides CLI value
    prompts = captured.get("supervisor_prompts") or {}
    assert prompts.get("supervisor") == "SUPERVISOR-OVERRIDE"
    assert prompts.get("research") == "RESEARCH-OVERRIDE"
    assert prompts.get("critique") == "CRITIQUE-OVERRIDE"
