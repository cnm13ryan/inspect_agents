Simple Architecture Demo

This folder contains a minimal, runnable demo that wires together the public Inspect Agents APIs (supervisor + one sub‑agent + approvals + limits + filesystem + logging) without relying on the CLI.

- Script: `examples/demos/simple_architecture.py`
- Output: writes a redacted JSONL transcript to `.inspect/logs/events.jsonl` and prints the file path.

Quick Start
- Offline smoke run (recommended):
  - `NO_NETWORK=1 uv run python examples/demos/simple_architecture.py "What is x?"`
- With dev approvals (handoff exclusivity + escalations):
  - `NO_NETWORK=1 INSPECT_APPROVAL_PRESET=dev uv run python examples/demos/simple_architecture.py "What is x?"`

Environment Flags (common)
- Approvals: `INSPECT_APPROVAL_PRESET=ci|dev|prod` (auto‑initialized by the runner when set).
- Web search: set a provider and enable the tool (optional)
  - `TAVILY_API_KEY=...` or `GOOGLE_CSE_ID=...` + `GOOGLE_CSE_API_KEY=...`
  - `INSPECT_ENABLE_WEB_SEARCH=1`
- Exec tools (off by default):
  - `INSPECT_ENABLE_EXEC=1` (enables `bash` and `python` tools). Use with approvals.
- Web browser tools (heavy, off by default):
  - `INSPECT_ENABLE_WEB_BROWSER=1`
- Filesystem sandbox:
  - `INSPECT_AGENTS_FS_MODE=sandbox`
  - Optional audited read‑only: `INSPECT_AGENTS_FS_READ_ONLY=1`
- Logging:
  - Override log directory: `INSPECT_LOG_DIR=.inspect/logs`

Notes
- Standard tools (`think`, `web_search`, `bash`, `python`, browser) are enabled strictly by env; see docs/reference/environment.md for full details.
- The demo also accepts per‑agent handoff budgets via env (e.g., `INSPECT_LIMIT_MESSAGES__researcher=8`). Explicit code limits take precedence.

Troubleshooting
- If you run without `uv sync`/install, the script adds `<repo>/src` and `<repo>/external/inspect_ai/src` to `sys.path` automatically so imports succeed when invoked with `uv run python ...`.
