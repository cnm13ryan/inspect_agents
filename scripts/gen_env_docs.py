#!/usr/bin/env python3
"""
Generate environment docs and template blocks from a single machine‑readable spec.

Inputs
- config_spec.yaml (JSON subset accepted) — see repo root.

Outputs (in-place updates)
- docs/reference/environment.md — replaces content between:
  <!-- BEGIN GENERATED: ENV_REFERENCE --> ... <!-- END GENERATED: ENV_REFERENCE -->
  <!-- BEGIN GENERATED: ENV_TEMPLATE  --> ... <!-- END GENERATED: ENV_TEMPLATE  -->
- env_templates/inspect.env — replaces lines between:
  # BEGIN GENERATED: COMMON_ENV ... # END GENERATED: COMMON_ENV

Usage
  uv run python scripts/gen_env_docs.py --write
  uv run python scripts/gen_env_docs.py --check  # exit 1 if changes would be made

Notes
- YAML dependency is optional: the spec is valid JSON; we fall back to json if
  PyYAML is not available.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_spec(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # Try YAML first if available; else parse as JSON (valid YAML subset)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)  # type: ignore[no-any-return]
    except Exception:
        return json.loads(text)


@dataclass(frozen=True)
class EnvVar:
    name: str
    category: str
    type: str
    default: Any
    sensitive: bool
    description: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> EnvVar:
        return EnvVar(
            name=str(d["name"]).strip(),
            category=str(d.get("category", "Misc")).strip(),
            type=str(d.get("type", "string")).strip(),
            default=d.get("default", ""),
            sensitive=bool(d.get("sensitive", False)),
            description=str(d.get("description", "")).strip(),
        )


def _by_category(envs: Iterable[EnvVar]) -> dict[str, list[EnvVar]]:
    out: dict[str, list[EnvVar]] = {}
    for e in envs:
        out.setdefault(e.category, []).append(e)
    # Stable sort by name within category
    for lst in out.values():
        lst.sort(key=lambda x: x.name)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def _render_docs_table(envs: list[EnvVar]) -> str:
    cats = _by_category(envs)
    lines: list[str] = []
    lines.append("<!-- GENERATED: do not edit by hand -->")
    for cat, items in cats.items():
        lines.append(f"\n#### {cat}")
        lines.append("| Env | Type | Default | Sensitive | Description |")
        lines.append("|---|---|---:|---:|---|")
        for e in items:
            default = (
                "on when unset" if str(e.default) == "on-when-unset" else ("" if e.default is None else str(e.default))
            )
            sens = "yes" if e.sensitive else "no"
            lines.append(
                f"| `{_md_escape(e.name)}` | {_md_escape(e.type)} | {_md_escape(str(default))} | {sens} | {_md_escape(e.description)} |"
            )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_env_block(envs: list[EnvVar]) -> str:
    cats = _by_category(envs)
    lines: list[str] = []
    lines.append("# GENERATED: do not edit by hand")
    for cat, items in cats.items():
        lines.append(f"\n## {cat}")
        for e in items:
            # Commented by default; use example/default when helpful
            if e.sensitive:
                lines.append(f"# {e.name}=")
            else:
                default = e.default
                if isinstance(default, bool):
                    val = "1" if default else "0"
                    lines.append(f"# {e.name}={val}")
                elif default in ("", None, "on-when-unset"):
                    lines.append(f"# {e.name}=")
                else:
                    lines.append(f"# {e.name}={default}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _replace_between(text: str, start_marker: str, end_marker: str, payload: str, fence: str = "") -> str:
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        # Append a new block at end with markers
        block = []
        block.append("")
        block.append(start_marker)
        if fence:
            block.append(fence)
        block.append(payload.rstrip("\n"))
        if fence:
            block.append(fence)
        block.append(end_marker)
        block.append("")
        return text.rstrip() + "\n\n" + "\n".join(block) + "\n"

    # Keep everything up to start_marker, then inject, then keep after end_marker
    head = text[: start_idx + len(start_marker)]
    tail = text[end_idx:]
    mid = "\n" + (fence + "\n" if fence else "") + payload + ("\n" + fence if fence else "")
    return head + mid + tail


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate env docs/template from config_spec.yaml")
    ap.add_argument("--spec", default="config_spec.yaml", help="Path to config spec (YAML or JSON)")
    ap.add_argument("--docs", default="docs/reference/environment.md", help="Env reference markdown path")
    ap.add_argument("--template", default="env_templates/inspect.env", help=".env template path")
    ap.add_argument("--check", action="store_true", help="Dry-run: exit 1 if changes would be made")
    ap.add_argument("--write", action="store_true", help="Write changes to files (default)")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec)
    docs_path = Path(args.docs)
    tpl_path = Path(args.template)

    spec = _load_spec(spec_path)
    envs = [EnvVar.from_dict(x) for x in spec.get("envs", [])]
    gen = spec.get("generated", {})

    table_md = _render_docs_table(envs)
    env_block_md = _render_env_block(envs)

    doc_text = docs_path.read_text(encoding="utf-8")
    new_doc = _replace_between(
        _replace_between(
            doc_text,
            f"<!-- {gen.get('doc_marker_start', 'BEGIN GENERATED: ENV_REFERENCE')} -->",
            f"<!-- {gen.get('doc_marker_end', 'END GENERATED: ENV_REFERENCE')} -->",
            table_md,
        ),
        f"<!-- {gen.get('doc_tpl_marker_start', 'BEGIN GENERATED: ENV_TEMPLATE')} -->",
        f"<!-- {gen.get('doc_tpl_marker_end', 'END GENERATED: ENV_TEMPLATE')} -->",
        env_block_md,
        fence="```bash",
    )

    tpl_text = tpl_path.read_text(encoding="utf-8")
    new_tpl = _replace_between(
        tpl_text,
        f"# {gen.get('template_marker_start', 'BEGIN GENERATED: COMMON_ENV')}",
        f"# {gen.get('template_marker_end', 'END GENERATED: COMMON_ENV')}",
        env_block_md,
    )

    changed = (new_doc != doc_text) or (new_tpl != tpl_text)
    if args.check and changed:
        print("Drift detected: run generator to update files.")
        return 1

    if not changed:
        print("No changes.")
        return 0

    if args.check:
        # --check and no changes
        return 0

    # Default behavior: write
    docs_path.write_text(new_doc, encoding="utf-8")
    tpl_path.write_text(new_tpl, encoding="utf-8")
    print(f"✓ Updated {docs_path}")
    print(f"✓ Updated {tpl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
