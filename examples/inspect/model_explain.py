#!/usr/bin/env python3
"""Deprecated shim for model_explain.

This script moved to `examples/debug/model_explain.py`. It remains as a
compatibility wrapper that prints a DeprecationWarning and delegates to the
new location.
"""

from __future__ import annotations

import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_new_module():
    new_path = Path(__file__).resolve().parents[1] / "debug" / "model_explain.py"
    spec = spec_from_file_location("examples.debug.model_explain", str(new_path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Unable to load new model_explain at {new_path}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        "examples/inspect/model_explain.py is deprecated; use examples/debug/model_explain.py",
        DeprecationWarning,
        stacklevel=2,
    )
    mod = _load_new_module()
    return int(mod.main(argv))  # type: ignore[attr-defined]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
