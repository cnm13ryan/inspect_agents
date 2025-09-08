from __future__ import annotations

import os
import re
from typing import Any

try:  # optional: prefer real YAML if available
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback implemented below
    yaml = None  # type: ignore

try:
    # Normal package-relative import when examples.* is resolvable
    from .planner import ExplorationConfig
except Exception:  # pragma: no cover - support import-by-path in tests/REPL
    import importlib.util
    from pathlib import Path

    _planner_path = Path(__file__).with_name("planner.py")
    spec = importlib.util.spec_from_file_location("examples.inspect.exploration._planner_fallback", str(_planner_path))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    ExplorationConfig = mod.ExplorationConfig  # type: ignore[attr-defined]


def _default_yaml_path() -> str:
    # examples/inspect/exploration/ -> examples/configs/research/exploration.yaml
    here = os.path.dirname(__file__)
    examples_root = os.path.abspath(os.path.join(here, os.pardir, os.pardir))
    return os.path.join(examples_root, "configs", "research", "exploration.yaml")


def _coerce_scalar(val: str) -> Any:
    s = val.strip()
    # strip surrounding quotes
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    # booleans
    low = s.lower()
    if low in {"true", "false"}:
        return low == "true"
    # ints/floats
    try:
        if re.fullmatch(r"[-+]?\d+", s):
            return int(s)
        if re.fullmatch(r"[-+]?\d*\.\d+", s):
            return float(s)
    except Exception:
        pass
    return s


def _parse_site_hints_block(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    items: list[str] = []
    i = start_idx
    # detect indent of the list items relative to the key line
    key_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    i += 1
    while i < len(lines):
        line = lines[i]
        # stop when indentation decreases to key level or another top-level key
        if (len(line) - len(line.lstrip())) <= key_indent and line.strip().endswith(":"):
            break
        m = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if m:
            items.append(_coerce_scalar(m.group(1)))
        i += 1
    return items, i - 1


def _fallback_load(path: str) -> dict[str, Any]:
    """Very small YAML subset parser for our expected shape.

    Supports top-level keys or keys nested under `policy:` and a simple list for `site_hints`.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    keys = {
        "breadth",
        "depth",
        "seed",
        "convergence_delta",
        "max_queries",
        "synonym_expansion",
        "site_hints",
    }

    lines = raw.splitlines()
    data: dict[str, Any] = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        # inline list form: site_hints: ["a", "b"]
        m_inline = re.match(r"^\s*site_hints\s*:\s*\[(.*)\]\s*$", line)
        if m_inline:
            inner = m_inline.group(1).strip()
            items: list[str] = []
            if inner:
                parts = re.split(r"\s*,\s*", inner)
                for p in parts:
                    items.append(_coerce_scalar(p))
            data["site_hints"] = items
            i += 1
            continue

        # block list form: site_hints:\n  - a\n  - b
        if re.match(r"^\s*site_hints\s*:\s*$", line):
            items, i = _parse_site_hints_block(lines, i)
            data["site_hints"] = items
            i += 1
            continue

        # simple scalar: key: value
        m = re.match(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", line)
        if m:
            k, v = m.group(1), m.group(2)
            if k in keys:
                data[k] = _coerce_scalar(v)
        i += 1

    return data


def load_exploration_config(path: str | None = None) -> ExplorationConfig:
    """Load ExplorationConfig from YAML.

    Tries PyYAML first; falls back to a tiny parser that understands the keys
    used by ExplorationConfig either at the top-level or nested under `policy:`.
    Unknown keys are ignored.
    """
    if path is None:
        path = _default_yaml_path()

    if yaml is not None:  # type: ignore[truthy-function]
        try:
            with open(path, encoding="utf-8") as f:
                doc = yaml.safe_load(f)  # type: ignore[attr-defined]
            src = doc or {}
            if isinstance(src, dict) and "policy" in src and isinstance(src["policy"], dict):
                src = src["policy"]
            if not isinstance(src, dict):
                src = {}
            # Filter only known fields
            fields = {
                k: src.get(k)
                for k in (
                    "breadth",
                    "depth",
                    "seed",
                    "convergence_delta",
                    "max_queries",
                    "synonym_expansion",
                    "site_hints",
                )
                if k in src
            }
            return ExplorationConfig(**fields)
        except Exception:
            # Fall back to minimal parser
            pass

    raw = _fallback_load(path)
    return ExplorationConfig(**raw)
