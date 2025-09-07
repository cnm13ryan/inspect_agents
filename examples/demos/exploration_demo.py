#!/usr/bin/env python3
"""
Exploration planner demo (examples-only).

What it does
- Loads the examples planner tool (offline, deterministic).
- Plans a small set of exploration queries from a prompt.
- Prints the JSON plan to stdout and writes plan.json by default.

Usage
  uv run python examples/demos/exploration_demo.py \
    --breadth 2 --depth 2 --max-queries 6 "Explore Inspect‑AI agent patterns"
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any


def _load_planner_tool():
    import importlib.util

    here = Path(__file__).resolve()
    mod_path = here.parents[1] / "inspect" / "exploration" / "planner_tool.py"
    spec = importlib.util.spec_from_file_location("_examples_planner_tool", str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load planner_tool from {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return getattr(mod, "planner_tool")()


async def _main() -> int:
    ap = argparse.ArgumentParser(description="Exploration planner demo (examples)")
    ap.add_argument("prompt", nargs="+", help="User prompt text")
    ap.add_argument("--breadth", type=int, default=3)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--max-queries", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="plan.json", help="Output JSON file")
    args = ap.parse_args()

    prompt = " ".join(args.prompt).strip()
    cfg: dict[str, Any] = {
        "breadth": args.breadth,
        "depth": args.depth,
        "max_queries": args.max_queries,
        "seed": args.seed,
    }

    planner = _load_planner_tool()
    plan = await planner(prompt=prompt, config=cfg)

    text = json.dumps(plan, indent=2)
    print(text)

    Path(args.out).write_text(text)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
