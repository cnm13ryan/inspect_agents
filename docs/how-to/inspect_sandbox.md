---
title: "Troubleshooting — Sandbox Required (Exec/Browser Tools)"
---

# Troubleshooting: Sandbox Required for Exec/Browser Tools

This guide helps you quickly resolve the error shown when enabling execution or browser tools without a sandbox:

> ProcessLookupError: No sandbox environment has been provided for the current sample or task …

Example trace (captured during an Inspect CLI run): see `scripts/eval.json` lines 82–90. 【F:scripts/eval.json‑ L82-L90】

Why this happens
- Exec tools (`bash()`, `python()`) and browser tools run inside an Inspect sandbox. If a task/run doesn’t specify a sandbox, these tools raise a `ProcessLookupError` at first use. The Inspect CLI exposes a `--sandbox` option (also `INSPECT_EVAL_SANDBOX`) to set this. 【F:external/inspect_ai/src/inspect_ai/_cli/eval.py‑ L164-L182】
- Filesystem tools in this repo can use a separate “FS sandbox mode” for host file access, but that is independent and does not provide an execution sandbox for `bash()`/`python()`/browser. See Filesystem guide for details.

Quick fixes

- Inspect CLI (recommended)
  - Add a sandbox to your eval command:
    ```bash
    # Local process sandbox (dev only)
    uv run inspect eval examples/tasks/prompt_task.py \
      --sandbox local -T prompt="List files and summarize"

    # Or via env
    INSPECT_EVAL_SANDBOX=local \
    uv run inspect eval examples/tasks/prompt_task.py -T prompt="..."
    ```
  - If you need containers or a browser, pass a provider config (e.g., Docker):
    ```bash
    uv run inspect eval examples/tasks/prompt_task.py \
      --sandbox 'docker:compose.yaml' -T prompt="..."
    ```

- Python runners (programmatic)
  - Prefer the profiled runner, which maps profiles to a Task sandbox for you:
    ```bash
    # T0=exec enabled, H1=docker sandbox, N1=restricted egress (example profile)
    uv run python examples/runners/profiled_runner.py --profile T0.H1.N1 \
      "Create docs/OUTLINE.md and add 3 sections"
    ```
  - Or construct a Task with `sandbox="local"` (or another provider) when using Inspect’s programmatic eval APIs.

Minimal repro → resolution
1) Repro (no sandbox):
   ```bash
   INSPECT_ENABLE_EXEC=1 \
   uv run inspect eval examples/tasks/prompt_task.py -T prompt="Try `bash`"
   # → ProcessLookupError: No sandbox environment has been provided …
   ```
2) Fix (CLI):
   ```bash
   INSPECT_ENABLE_EXEC=1 \
   uv run inspect eval examples/tasks/prompt_task.py \
     --sandbox local -T prompt="Try `bash`"
   # → Runs inside a local sandbox; exec tools work.
   ```
3) Alternative (use task that sets a sandbox):
   ```bash
   uv run inspect eval examples/tasks/iterative_task.py \
     -T enable_exec=true -T prompt="List repo files"
   # iterative_task.py configures sandbox="local" by default.
   ```

Notes and tips
- Approvals: When enabling exec or browser tools, attach an approvals preset (e.g., `--approval dev`) for safety.
- Browser tools: Require a sandbox and a compatible browser runtime; see the Browser tools reference and the sandboxing guide for setup details. 【F:docs/tools/web_browser.md‑ L29-L31】
- FS sandbox vs exec sandbox: Setting `INSPECT_AGENTS_FS_MODE=sandbox` affects the file tools only; it does not create an execution sandbox for `bash()`/`python()`.

Related docs
- Filesystem tools — Store vs Sandbox: `docs/how-to/filesystem.md`
- Sandboxing in inspect_agents (deep dive): `docs/how-to/sandboxing_inspect_agents.md`

