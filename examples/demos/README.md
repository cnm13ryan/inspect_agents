Examples Demos

This folder organizes runnable demos by theme for quick onboarding.

Simple Architecture (choose one)
- Minimal: `examples/demos/simple_arch/minimal.py`
  - Offline smoke run (recommended):
    - `NO_NETWORK=1 uv run python examples/demos/simple_arch/minimal.py "What is x?"`
  - Logs: writes a redacted JSONL transcript to `.inspect/logs/events.jsonl` and prints the file path.

- Enriched: `examples/demos/simple_arch/enriched.py`
  - Adds a tiny environment and in-process memory tools; supports `--mode` and `--dev-approvals` flags.
  - Run: `uv run python examples/demos/simple_arch/enriched.py --mode supervisor "Research topic..."`

Approvals (policy behavior)
- Sub‑agent handoff exclusivity: `examples/demos/approvals/subagent.py`
  - Demonstrates `handoff_exclusive_policy()`: a handoff tool approves while other tools in the same turn are skipped.
  - Run: `uv run python examples/demos/approvals/subagent.py --preset dev`

Common Environment Flags
- Approvals: `INSPECT_APPROVAL_PRESET=ci|dev|prod` (auto‑initialized when set).
- Web search (optional):
  - `TAVILY_API_KEY=...` or `GOOGLE_CSE_ID=...` + `GOOGLE_CSE_API_KEY=...`
  - `INSPECT_ENABLE_WEB_SEARCH=1`
- Exec tools (off by default): `INSPECT_ENABLE_EXEC=1` (enables `bash` and `python`). Use with approvals.
- Browser tools (heavy, off by default): `INSPECT_ENABLE_WEB_BROWSER=1`
- Filesystem sandbox: `INSPECT_AGENTS_FS_MODE=sandbox` (+ `INSPECT_AGENTS_FS_READ_ONLY=1` for audited read‑only)
- Logs: override directory with `INSPECT_LOG_DIR=.inspect/logs`

Notes
- Standard tools (`think`, `web_search`, `bash`, `python`, browser) are enabled strictly by env; see docs/reference/environment.md.
- Per‑agent limits can be applied via env, e.g., `INSPECT_LIMIT_MESSAGES__researcher=8`.

Legacy paths
- `examples/demos/simple_architecture.py` and `examples/demos/simple_arch_demo.py` now print redirects to the new simple_arch/ files.
- `examples/demos/subagent_approvals_demo.py` prints a redirect to `examples/demos/approvals/subagent.py`.
