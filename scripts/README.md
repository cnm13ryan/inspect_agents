# Scripts Index (by concern)

This directory now groups scripts by concern to make them easier to find and to keep generated artifacts out of version control. The legacy top‑level filenames remain as thin wrappers for one release cycle and print a deprecation note when used.

## Git
- `scripts/git/worktrees-create.sh` — create one or many Git worktrees (moved from `scripts/create_feature_worktrees.sh`).
- `scripts/git/worktrees-remove.sh` — interactive Git worktree remover (moved from `scripts/remove_worktrees.sh`).

Quick help:
- `bash scripts/git/worktrees-create.sh single -h`
- `bash scripts/git/worktrees-remove.sh -h`

## Eval
- `scripts/eval/export-log-json.sh` — export Inspect logs to JSON (moved from `scripts/export_eval_json.sh`).
  - Note: when called via the old path, the default output remains `scripts/eval.json`; the new path defaults to `scripts/eval/eval.json`.
- `scripts/eval/read-log-eval.py` — inspect latest `.eval` log (moved from `scripts/read_log_eval.py`).

Quick help:
- `bash scripts/eval/export-log-json.sh -h`
- `uv run python scripts/eval/read-log-eval.py -h`

## Docs
- `scripts/docs/status-sweep.py` — sweep/verify docs status (moved from `scripts/sweep_status.py`).
- `scripts/docs/gen-env-docs.py` — generate env docs/templates (moved from `scripts/gen_env_docs.py`).

Quick help:
- `uv run python scripts/docs/gen-env-docs.py -h`
- `uv run python scripts/docs/status-sweep.py -h`

## Dev
- `scripts/dev/session-files.sh` — manage `.session_files` (moved from `scripts/session-init.sh`).

## Scaffold
- `scripts/scaffold/agent.py` — scaffold a minimal agent and optional test (moved from `scripts/scaffold_agent.py`).

## Examples
- `examples/inspect/quickstart_toy.py` — toy example moved from `scripts/quickstart_toy.py`.

## Removed / No longer used
- `scripts/hooks.py` (MkDocs post‑build): removed — `mkdocs-exclude-search` handles backlog filtering.

---

## Worktrees — Quick Start

Create a single worktree:

```bash
bash scripts/git/worktrees-create.sh single --branch feat/fs-atomic
```

Batch modes (auto‑detected by inputs in `prompts/`): run with no args:

```bash
bash scripts/git/worktrees-create.sh
```

Filters via env vars:

```bash
PHASES=1,2 GROUPS=A bash scripts/git/worktrees-create.sh
```

Common tasks:
- List worktrees: `git worktree list`
- Remove worktrees: `bash scripts/git/worktrees-remove.sh`

Notes:
- Per‑worktree `.env` sets `INSPECT_LOG_DIR` and `INSPECT_TRACE_FILE` for isolation.
- Worktrees share the same Git object store; prefer selective staging (`git add -p -- <paths>`).
