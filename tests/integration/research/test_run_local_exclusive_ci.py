import asyncio
import importlib.util
from pathlib import Path

from tests.fixtures.patching import patch_use_site


def _load_run_local_module():
    # tests/integration/research/ → parents[3] is repo root
    path = Path(__file__).resolve().parents[3] / "examples" / "runners" / "research_runner.py"
    spec = importlib.util.spec_from_file_location("run_local_ci", str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_ci_appends_handoff_exclusive_policy(monkeypatch, tmp_path):
    # Arrange: ensure offline-friendly env
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("INSPECT_LOG_DIR", str(tmp_path))

    # Capture approvals passed to run_agent
    captured: dict[str, object] = {}

    async def fake_run_agent(agent, user_input, approval=None, limits=None, **kwargs):  # noqa: ANN001, D401
        captured["approval"] = approval

        # Minimal result-like object with .output.completion
        class _Out:
            completion = "ok"

        class _Res:
            output = _Out()

        return _Res()

    # Patch inspect_agents hooks used by the runner
    # Patch modules at their use-site import paths with autospec enforcement
    with (
        patch_use_site(
            "inspect_agents.approval.handoff_exclusive_policy",
            new=lambda: ["EXCLUSIVE_SENTINEL"],
        ),
        patch_use_site(
            "inspect_agents.approval.approval_preset",
            new=lambda preset: [],
        ),
        patch_use_site(
            "inspect_agents.run.run_agent",
            new=fake_run_agent,
        ),
    ):
        # Load the runner module and invoke _main with --approval ci
        run_local = _load_run_local_module()

        argv = [
            "research_runner.py",
            "Quick check",
            "--approval",
            "ci",
        ]

        monkeypatch.setattr("sys.argv", argv, raising=False)

        # Act
        rc = asyncio.run(run_local._main())

        # Assert
        assert rc == 0
        approval = captured.get("approval")
        assert isinstance(approval, list)
        assert "EXCLUSIVE_SENTINEL" in approval, "handoff_exclusive_policy() not applied for ci"
