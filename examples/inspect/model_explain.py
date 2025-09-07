#!/usr/bin/env python3
"""Small CLI to inspect model resolution.

Examples:
  python examples/inspect/model_explain.py --model openai/gpt-4o-mini --json
  python examples/inspect/model_explain.py --role coder
  python examples/inspect/model_explain.py --provider openai  # will error without OPENAI_API_KEY

The CLI prints a human-readable table by default, or JSON with --json.
It is repo-friendly: when run from a source checkout, it adds ./src to sys.path.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any


def _maybe_inject_src_path() -> None:
    # Add repo ./src to sys.path when running from a checkout
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


_maybe_inject_src_path()

from inspect_agents import (  # noqa: E402
    ResolveModelError,
    resolve_model_explain,
)


def as_json(obj: Any) -> str:
    def default(o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return str(o)

    return json.dumps(obj, default=default, indent=2, sort_keys=True)


def print_table(final: str, trace) -> None:  # type: ignore[no-untyped-def]
    print(f"Resolved: {final}")
    print("Steps:")
    for i, s in enumerate(trace.steps):
        print(f"  [{i}] path={s.path} final={s.final_candidate}")
        print(
            f"      provider_arg={s.provider_arg!r} model_arg={s.model_arg!r} role={s.role!r} role_env_model={s.role_env_model!r} role_env_provider={s.role_env_provider!r} env_inspect_eval_model={s.env_inspect_eval_model!r}"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Explain how model/provider was resolved.")
    p.add_argument("-p", "--provider", help="Provider hint (e.g., ollama, openai, openai-api/lm-studio)")
    p.add_argument("-m", "--model", help="Model (optionally with provider prefix, e.g., openai/gpt-4o-mini)")
    p.add_argument("-r", "--role", help="Role indirection (e.g., coder, researcher)")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = p.parse_args(argv)

    try:
        final, trace = resolve_model_explain(provider=args.provider, model=args.model, role=args.role)
    except ResolveModelError as e:
        if args.json:
            print(
                as_json(
                    {
                        "ok": False,
                        "error": str(e),
                        "final_step": e.final_step,
                        "trace": e.trace,
                    }
                )
            )
        else:
            print("Resolution failed:", str(e))
            print_table("<error>", e.trace)
        return 2

    if args.json:
        print(as_json({"ok": True, "final": final, "trace": trace}))
    else:
        print_table(final, trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
