#!/usr/bin/env python3
"""
Show effective tool-output truncation limit (bytes) and its source.

Usage
  uv run python examples/debug/show_limits.py

Environment sources (highest → lowest precedence in helpers):
  - Active GenerateConfig.max_tool_output → source: config
  - INSPECT_MAX_TOOL_OUTPUT (bytes)      → source: env
  - Default                               → source: default (16384)
"""

from __future__ import annotations

import importlib.util as _il
from pathlib import Path


def _load_examples_utils():
    utils_path = Path(__file__).resolve().parents[1] / "_utils.py"
    spec = _il.spec_from_file_location("_examples_utils_local", str(utils_path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Unable to load examples/_utils.py from {utils_path}")
    mod = _il.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    utils = _load_examples_utils()
    # Ensure local repo src is preferred and env files are loaded (repo/.env, examples/.env, template)
    utils.ensure_repo_src_on_path()
    utils.load_env_files(Path(__file__).parent, include_template=True)

    # Print the cap and its source
    utils.print_effective_tool_output_limit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
