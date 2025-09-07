import os
import subprocess
import sys
from pathlib import Path


def _repo_root(start: Path) -> Path:
    cur = start
    for _ in range(6):
        if (cur / "pyproject.toml").exists():
            return cur
        cur = cur.parent
    return start.parents[2]


def _env(repo: Path) -> dict:
    env = os.environ.copy()
    src = str(repo / "src")
    ext = str(repo / "external" / "inspect_ai" / "src")
    env["PYTHONPATH"] = os.pathsep.join([src, ext, env.get("PYTHONPATH", "")])
    env.setdefault("NO_NETWORK", "1")
    env.setdefault("CI", "1")
    # Ensure no prior value leaks into the default test
    env.pop("INSPECT_MAX_TOOL_OUTPUT", None)
    return env


def _run(cmd, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def test_show_limits_default_prints_default_cap_and_source():
    repo = _repo_root(Path(__file__).resolve())
    script = repo / "examples" / "debug" / "show_limits.py"
    proc = _run([sys.executable, str(script)], cwd=repo, env=_env(repo))
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    assert out == "Tool-output cap: 16384 bytes (default)"


def test_show_limits_respects_env_override():
    repo = _repo_root(Path(__file__).resolve())
    script = repo / "examples" / "debug" / "show_limits.py"
    env = _env(repo)
    env["INSPECT_MAX_TOOL_OUTPUT"] = "12345"
    proc = _run([sys.executable, str(script)], cwd=repo, env=env)
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    assert out == "Tool-output cap: 12345 bytes (env)"
