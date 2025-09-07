#!/usr/bin/env python3
"""Scaffold a minimal Inspect Agents agent (and optional smoke test).

Usage:
  python scripts/scaffold_agent.py NAME \
      [--package inspect_agents] [--path .] \
      [--include-test | --no-test] [--force]

Examples:
  # Create src/inspect_agents/my_agent.py and tests/inspect_agents/test_my_agent.py
  python scripts/scaffold_agent.py my_agent

  # Use a custom package path under src/<pkg>
  python scripts/scaffold_agent.py research_helper --package my_org.agents

This script is pure standard library and performs cautious file writes:
it refuses to overwrite existing files unless --force is provided. If a
target path exists and --force is not supplied, a y/N confirmation is
requested in interactive terminals.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from textwrap import dedent


def _snake_case(name: str) -> str:
    """Convert arbitrary name to snake_case suitable for filenames and symbols."""
    # Replace separators and invalid chars with underscore
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip())
    # Camel/Pascal -> snake (simple heuristic)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = s.lower().strip("_")
    # Avoid leading digits in identifiers
    if s and s[0].isdigit():
        s = f"a_{s}"
    return s or "agent"


def _confirm_overwrite(path: Path) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        ans = input(f"Path exists: {path}\nOverwrite? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in {"y", "yes"}


def _ensure_pkg_inits(base: Path, package: str) -> None:
    """Create package folders and __init__.py files under 'base' for a dotted pkg."""
    pkg_path = base.joinpath(*package.split("."))
    pkg_path.mkdir(parents=True, exist_ok=True)
    # Touch __init__.py up the package chain
    parts = []
    for part in package.split("."):
        parts.append(part)
        init_path = base.joinpath(*parts, "__init__.py")
        init_path.parent.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            init_path.write_text("\n")


def _agent_template(module_name: str, package: str) -> str:
    dotted = f"{package}.{module_name}" if package else module_name
    return dedent(
        f"""
        # Minimal agent factory for {dotted}.
        #
        # Edit the default prompt and parameters as desired. By default this
        # uses code-only tools (no exec/search/browser) so it runs safely in
        # offline tests. To enable more tools, configure environment flags per
        # `inspect_agents.tools.standard_tools()`.

        from __future__ import annotations

        from typing import Any

        from inspect_agents.agents import build_iterative_agent


        DEFAULT_PROMPT = (
            "You are a helpful, concise assistant. "
            "Prefer file read/edit tools; avoid executing code or using the web."
        )


        def build_agent(*, prompt: str | None = None, **kwargs: Any) -> Any:
            # Return a simple iterative agent.
            return build_iterative_agent(
                prompt=prompt or DEFAULT_PROMPT,
                code_only=True,
                # Keep loops tight for demos; customize as needed
                real_time_limit_sec=30,
                max_steps=10,
                **kwargs,
            )
        """
    ).lstrip()


def _test_template(module_name: str, package: str) -> str:
    dotted = f"{package}.{module_name}" if package else module_name
    return dedent(
        f'''
        import asyncio
        from typing import Any

        import pytest


        def _install_stub_run(monkeypatch, sleep_s: float = 0.01, return_tuple: bool = True):
            """Install a stub for `inspect_ai.agent._run.run` to avoid provider calls."""
            import inspect_ai.agent._run as real_run_module  # type: ignore

            class _State:
                pass

            async def run(_agent: Any, _input: Any, **_kwargs: Any):
                await asyncio.sleep(sleep_s)
                st = _State()
                return (st, None) if return_tuple else st

            monkeypatch.setattr(real_run_module, "run", run, raising=False)


        @pytest.mark.asyncio
        async def test_{module_name}_smoke(monkeypatch):
            monkeypatch.setenv("NO_NETWORK", "1")

            # Provide a tiny runner time limit; our stub returns quickly.
            from inspect_ai.util._limit import time_limit  # type: ignore
            from inspect_agents.run import run_agent

            _install_stub_run(monkeypatch)

            from {dotted} import build_agent

            agent = build_agent()
            state = await run_agent(agent=agent, input="ping", limits=[time_limit(0.01)])
            assert state is not None
        '''
    ).lstrip()


def scaffold(name: str, package: str, root: Path, include_test: bool, force: bool) -> list[Path]:
    mod = _snake_case(name)

    src_root = root / "src"
    tests_root = root / "tests"

    # Ensure package layout exists under src/ and tests/
    _ensure_pkg_inits(src_root, package)
    (tests_root / Path(*package.split("."))).mkdir(parents=True, exist_ok=True)
    tests_init = tests_root / Path(*package.split(".")) / "__init__.py"
    if not tests_init.exists():
        tests_init.write_text("\n")

    agent_path = src_root / Path(*package.split(".")) / f"{mod}.py"
    test_path = tests_root / Path(*package.split(".")) / f"test_{mod}.py"

    created: list[Path] = []

    # Write agent module
    if agent_path.exists() and not force:
        if not _confirm_overwrite(agent_path):
            print(f"Refusing to overwrite existing file: {agent_path}", file=sys.stderr)
            return created
    agent_path.write_text(_agent_template(mod, package))
    created.append(agent_path)

    # Write test module if requested
    if include_test:
        if test_path.exists() and not force:
            if not _confirm_overwrite(test_path):
                print(f"Refusing to overwrite existing file: {test_path}", file=sys.stderr)
                return created
        test_path.write_text(_test_template(mod, package))
        created.append(test_path)

    return created


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scaffold a minimal Inspect Agents agent and optional test.")
    p.add_argument("name", help="Agent name (module-safe; will be normalized to snake_case)")
    p.add_argument("--package", default="inspect_agents", help="Dotted package under src/ (default: inspect_agents)")
    p.add_argument("--path", default=".", help="Project root path containing src/ and tests/ (default: .)")
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--include-test", dest="include_test", action="store_true", default=True, help="Generate a smoke test (default)"
    )
    g.add_argument("--no-test", dest="include_test", action="store_false", help="Skip test generation")
    p.add_argument("--force", action="store_true", help="Overwrite existing files without prompting")

    args = p.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Error: path does not exist: {root}", file=sys.stderr)
        return 2

    created = scaffold(args.name, args.package, root, args.include_test, args.force)
    if not created:
        # Either user declined overwrite or nothing was created
        return 1

    rels = [str(pth.relative_to(root)) if str(pth).startswith(str(root)) else str(pth) for pth in created]

    agent_mod = _snake_case(args.name)
    pkg_path = args.package.replace(".", "/")
    print("\nScaffold complete:\n  - " + "\n  - ".join(rels))

    # Helpful next steps / README snippet
    test_hint = f" -k {agent_mod}" if args.include_test else ""
    print(
        dedent(
            f"""

            Next steps:
              1) Edit src/{pkg_path}/{agent_mod}.py to customize DEFAULT_PROMPT.
              2) Run the smoke test (offline, tiny limit):
                 CI=1 NO_NETWORK=1 PYTHONPATH=src:external/inspect_ai uv run pytest -q{test_hint}

            Import in your code:
                from {args.package}.{agent_mod} import build_agent
                agent = build_agent()

            """
        ).rstrip()
    )

    return 0


if __name__ == "__main__":  # pragma: no cover - manual CLI
    raise SystemExit(main())
