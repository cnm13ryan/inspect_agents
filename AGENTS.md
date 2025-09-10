# Repository Guidelines

This file governs engineering norms for this repository only. If your editor or machine also injects a global `~/.codex/AGENTS.md`, this repo's local file takes precedence within the repo. Do not stack rules from the global file here.

## 1. Quick Start

### Project Structure
- `src/inspect_agents/`: Inspect-AI-native library (agents, tools, state, config).
- `tests/inspect_agents/`: Pytest suite for library behavior and shims.
- `examples/inspect/`: CLI demos (`prompt_task.py`, `run.py`).
- `env_templates/`: Example env file (`inspect.env`).
- `external/inspect_ai/`: Inspect-AI source (submodule/checkout for local dev).
- `.inspect/logs/` and `logs/`: Runtime transcripts and traces.

### Installation & Essential Commands
- Install: `uv sync` (or `python3.11 -m venv .venv && pip install -e .`).
- Run CLI task: `uv run inspect eval examples/inspect/prompt_task.py -T prompt="..."`.
- Run Python runner: `uv run python examples/inspect/run.py "..."`.
- Test: `CI=1 NO_NETWORK=1 PYTHONPATH=src:external/inspect_ai uv run pytest -q tests/inspect_agents`

## 2. Development Guidelines

### Coding Standards
- Python 3.11+, 4-space indent, type hints required for public APIs.
- Naming: modules/files `snake_case.py`; functions `snake_case`; classes `PascalCase`.
- Keep imports light at module top; prefer local imports when heavy/optional (pattern used across repo).
- Docstrings: short, imperative, first line ≤ 80 chars.

### Git Workflow & Commits

**Conventional Commits**: `<type>[optional scope]: <description>`
- Types: feat | fix | docs | style | refactor | perf | test | build | ci | chore | revert
- Keep commits atomic and logically independent
- PRs: concise description, linked issues, reproduction (if bug), test updates

**Safe, Path-Restricted Commands** (Multi-Agent):

Never use (forbidden):
- `git add .` / `git add -A` / `git commit -a`
- `git diff --no-index` / manual `git apply`

Always use:
- Show changes for specific paths: `git diff -- <path ...>`
- Pre-index new files: `git add -N -- <newfile ...>`
- Stage only intended hunks: `git add -p -- <path ...>`
- Commit only selected paths: `git commit -m "<type>(<scope>): <desc>" -- <path ...>`

## 3. Configuration & Environment

### Environment Variables Reference

| Category | Variable | Default | Description |
|----------|----------|---------|-------------|
| **Filesystem** | INSPECT_AGENTS_FS_MODE | store | store\|sandbox mode |
| | INSPECT_AGENTS_FS_ROOT | /repo | Absolute root path for sandbox |
| | INSPECT_AGENTS_FS_READ_ONLY | 0 | Block writes in sandbox mode |
| | INSPECT_AGENTS_FS_MAX_BYTES | - | Byte ceiling for read/write/edit |
| | INSPECT_SANDBOX_PREFLIGHT | auto | auto\|skip\|force preflight checks |
| | INSPECT_SANDBOX_PREFLIGHT_TTL_SEC | 300 | Preflight cache TTL |
| **Limits** | INSPECT_ITERATIVE_TIME_LIMIT | - | Time limit in seconds |
| | INSPECT_ITERATIVE_MAX_STEPS | - | Max agent steps |
| | INSPECT_PRUNE_AFTER_MESSAGES | - | Message pruning threshold (≤0 disables) |
| | INSPECT_PRUNE_KEEP_LAST | - | Messages to keep when pruning |
| | INSPECT_PER_MSG_TOKEN_CAP | - | Token cap per message |
| | INSPECT_TRUNCATE_LAST_K | - | Truncate last K messages |
| | INSPECT_PRODUCTIVE_TIME | 0 | Subtract retry/backoff from time budget |
| **Tool Output** | INSPECT_MAX_TOOL_OUTPUT | 16384 | Default tool output cap (bytes) |
| **Tool Toggles** | INSPECT_ENABLE_THINK | 1 | Enable think() tool |
| | INSPECT_ENABLE_WEB_SEARCH | 0 | Enable web_search() (needs creds) |
| | INSPECT_ENABLE_EXEC | 0 | Enable bash() and python() |
| | INSPECT_ENABLE_WEB_BROWSER | 0 | Enable browser tools |
| | INSPECT_ENABLE_TEXT_EDITOR_TOOL | 0 | Expose text_editor() directly |
| **Parallelism** | INSPECT_TOOL_PARALLELISM_DISABLE | 0 | Disable parallel tool execution |
| | INSPECT_DISABLE_TOOL_PARALLEL | 0 | Alternative parallelism disable flag |
| **Model** | DEEPAGENTS_MODEL_PROVIDER | ollama | Default model provider |
| | INSPECT_ROLE_<ROLE>_MODEL | - | Role-specific model mapping |
| **Logging** | INSPECT_LOG_DIR | .inspect/logs | Log directory path |
| | INSPECT_TRACE_FILE | - | Trace file path |
| | INSPECT_ENV_FILE | - | Override env file location |

### Configuration Files
- Load secrets from `.env` or `env_templates/inspect.env`
- Override with `INSPECT_ENV_FILE` environment variable
- Never commit secrets to the repository

## 4. Safety & Security

### Approval System
- Prefer safe defaults locally: use approval presets when enabling risky tools.
  - Python API: `from inspect_agents.approval import approval_preset, activate_approval_policies; activate_approval_policies(approval_preset("dev"))`.
  - CLI/evals: pass approval policies via your runner as documented in `docs/how-to/approvals.md`.
- Handoff exclusivity: when a handoff tool (`transfer_to_*`) appears alongside other tools in one assistant turn, only the first handoff should execute.
  - Included by default in `approval_preset("dev")` and `approval_preset("prod")` via `handoff_exclusive_policy()`; `ci` does not include it. See `src/inspect_agents/approval.py` and `docs/adr/0005-tool-parallelism-policy.md`.
  - To opt out, build a custom approval chain instead of using `dev`/`prod` presets.
- Parallelism kill-switch (non-handoff tools): set `INSPECT_TOOL_PARALLELISM_DISABLE=1` (or `INSPECT_DISABLE_TOOL_PARALLEL=1`) to approve only the first non-handoff tool in a batch; others are skipped. Useful for deterministic tests and ops.

### Filesystem Sandbox
**Modes**:
- `store` (default): In-memory virtual FS; safe for CI
- `sandbox`: Routes file ops to Inspect's `text_editor`/`bash_session` against host-mounted sandbox

**Guardrails**:
- Root confinement under `INSPECT_AGENTS_FS_ROOT` (absolute; default `/repo`)
- Symlink denial on read/write/edit
- Byte ceilings via `INSPECT_AGENTS_FS_MAX_BYTES`
- Delete is intentionally disabled in sandbox mode by design
- Read-only mode: `INSPECT_AGENTS_FS_READ_ONLY=1` blocks write/edit/delete
- Preflight checks: Use `inspect_agents.fs.reset_sandbox_preflight_cache()` to force recheck

## 5. Testing

### Running Tests
**Default command**: `CI=1 NO_NETWORK=1 PYTHONPATH=src:external/inspect_ai uv run pytest -q tests/inspect_agents`

**Options**:
- Subset testing: append `-k <expr>` (e.g., `-k sandbox`, `-k migration`)
- Framework: pytest (tests in `tests/inspect_agents/`, named `test_*.py`)
- Default offline: `NO_NETWORK=1` for deterministic, fast tests
- Lint (optional): `uv run ruff check`
- Docs (optional): `uv run mkdocs serve`

### Writing Tests
- Add tests for new behavior and regressions
- Cover env-flag branches (e.g., `INSPECT_ENABLE_*`, FS modes)
- Prefer deterministic limits (message/tool-call) for assertions
- Tool-output truncation defaults to 16 KiB envelope

### Test Isolation & Global State Management

**Critical**: Inspect + inspect_agents use module-level registries (approvals), env-driven toggles, and optional tool stubs. Leaked state between tests is a common source of flakiness. Use these patterns to keep tests isolated and deterministic:

**Reset approval registries explicitly**:
  ```python
  try:
      from inspect_ai.approval._apply import init_tool_approval  # type: ignore
      init_tool_approval(None)
  except Exception:
      pass  # tests may stub _apply
  ```

**Best practices**:
- Scope configuration via env, never globals (use `monkeypatch.setenv/delenv`)
- Avoid `importlib.reload` on `inspect_ai.*` / `inspect_agents.*`
- Stub tool modules via `sys.modules` when needed
- Capture logs with the right logger name
- Filesystem sandbox toggles are per-test
- Triage isolation failures with deterministic subsets
- Design resilient tests: set/clear required env state explicitly

**Key insight**: Most isolation bugs combine (1) lingering approval registrations, (2) env leakage, and (3) module stub drift. Address all three systematically rather than fixing symptoms in one place.

## 6. Tools & Features

### Tool Output Truncation
- Default effective cap: 16 KiB per tool call output when no explicit cap is provided
- Precedence: per-call arg `max_output` > per-run `GenerateConfig.max_tool_output` > env `INSPECT_MAX_TOOL_OUTPUT` > default 16 KiB
- On the first tool event, logs a one-time structured line with effective limit and source

### Runner Limits API
- Use `inspect_agents.run.run_agent(agent, input, limits=[...])` to apply Inspect limits (time/message/token) at the call site
- Error handling:
  - `return_limit_error=True` returns `(state, err)` without raising
  - `raise_on_limit=True` raises the limit error (e.g., `LimitExceededError`)

### Model Selection
- Prefer `inspect_agents.model.resolve_model(...)` to build model strings from env
- Local default provider is `ollama` (override via `DEEPAGENTS_MODEL_PROVIDER`)
- Role mapping via `INSPECT_ROLE_<ROLE>_MODEL` is supported

## 7. Operations & Monitoring

### Logging & Artifacts
- Transcript writer: `inspect_agents.logging.write_transcript()` appends JSONL events to `.inspect/logs/events.jsonl`
- Path override via `INSPECT_LOG_DIR`
- Tracing: set `INSPECT_TRACE_FILE` and `INSPECT_LOG_DIR` to capture artifacts for reviews

## 8. Documentation References

- Getting started: `docs/getting-started/inspect_agents_quickstart.md`
- Approvals: `docs/how-to/approvals.md`
- Filesystem & sandbox: `docs/how-to/filesystem.md`
- Tools reference: `docs/tools/README.md`
- Environment: `docs/reference/environment.md`
- Architecture & ADRs: `docs/ARCHITECTURE.md`, `docs/adr/README.md`
- Iterative agent behavior: `docs/reference/iterative-agent-behavior.md`
- Operations logging: `docs/how-to/operations_logging_tracing.md`
- Supervisor limits: `docs/guides/supervisor-limits.md`
- Tool output truncation: `docs/adr/0004-tool-output-truncation.md`
- Tool parallelism: `docs/adr/0005-tool-parallelism-policy.md`
