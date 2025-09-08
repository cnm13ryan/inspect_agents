# Worktree Helper Scripts

This folder contains utilities to streamline parallel feature development using Git worktrees.

## new_worktree.sh — Create and Bootstrap a Per‑Feature Worktree

- Purpose: spin up an isolated working directory on its own branch, set up a Python environment (uv or venv), and create a per‑worktree `.env` that keeps logs/traces separate.
- Location: `scripts/new_worktree.sh`
- Requirements: Git ≥ 2.5 (worktrees), bash, and either `uv` (preferred) or Python 3 for venv.

### Quick Start

```bash
# From your main repo clone (clean working tree recommended)
scripts/new_worktree.sh feat/fs-atomic

# Specify a custom path and push upstream
scripts/new_worktree.sh feat/profiles --path ../inspect_agents-profiles --push

# Force venv (no uv) with a specific Python
scripts/new_worktree.sh feat/docs --no-uv --venv --python python3.12
```

After the script finishes, cd into the printed worktree path and develop as usual (run tests, commit, push). Each worktree has its own branch and `.env` configured.

### What the Script Does (Step‑by‑Step)

1) Validates context
- Ensures you’re inside a Git repo; aborts on errors (`set -euo pipefail`).
- Fetches remotes when creating a new branch from a base ref.

2) Resolves paths and branch
- Derives repo root/name and computes a default worktree path `../<repo>-<branch>` (slashes in branch are replaced with `-`).
- Refuses to use a branch that is already checked out in another worktree.
- Creates the worktree:
  - Existing branch: `git worktree add <path> <branch>`
  - New branch: `git worktree add -b <branch> <path> <base-ref>` (default base `origin/main`).

3) Writes per‑worktree `.env` for logs/traces
- Creates `.inspect/` and sets unique paths based on the branch name:
  - `INSPECT_LOG_DIR=.inspect/logs-<branch>`
  - `INSPECT_TRACE_FILE=.inspect/trace-<branch>.log`
- Saves these to `<worktree>/.env` so you can point the runner to it (e.g., `INSPECT_ENV_FILE=.env`).

4) Bootstraps a Python environment
- Prefers `uv` if available (or if `--uv` is passed): runs `uv sync` in the worktree.
- Otherwise (or if `--no-uv`), optionally creates a local venv (`--venv`, default on) using `python3` or `--python`.

5) Optional: pushes the new branch
- If `--push` is provided, runs `git push -u <remote> <branch>` (default remote `origin`).

6) Prints next steps and handy commands
- Shows how to run tests, stage commits selectively, push, list worktrees, and remove the worktree.

### Usage and Options

```text
scripts/new_worktree.sh <branch> [options]

Arguments:
  <branch>                 New or existing branch name (e.g., feat/fs-atomic)

Options:
  --base <ref>             Base ref to branch from (default: origin/main)
  --path <dir>             Target directory for worktree (default: ../<repo>-<branch>)
  --remote <name>          Git remote to track/push (default: origin)
  --uv | --no-uv           Use uv sync if available (default: auto-detect)
  --venv | --no-venv       Create Python venv if uv is disabled/unavailable (default: on)
  --python <bin>           Python executable for venv (default: python3)
  --set-logs | --no-logs   Write .env with log/trace paths (default: on)
  --push                   Push new branch and set upstream (optional)
  -h, --help               Show help
```

### Working With Multiple Codex Sessions

- Start a separate session per worktree and set the session’s CWD to the worktree path (each session works on its own branch).
- Keep environments and logs isolated per worktree via the generated `.env`.
- If your runner requires it, export `INSPECT_ENV_FILE=.env` before running.

### Common Tasks

- List worktrees: `git worktree list`
- Remove a worktree after merge: `git worktree remove <path> && git worktree prune`
- Push branch later: `git push -u origin <branch>`
- Rebase worktree branch: `git fetch origin && git rebase origin/main`

### Troubleshooting

- "Branch is already checked out": create a new branch name; Git forbids checking the same branch in multiple worktrees.
- "Not inside a git repository": run the script from within a cloned repo.
- `uv` not found: use `--no-uv --venv` or install `uv`.
- Provider/submodule differences: if your feature changes submodules or provider configs, repeat any required `git submodule update` inside each worktree.

### Notes

- Worktrees share the same `.git` object store, so large binary files affect disk usage across all worktrees.
- Prefer selective staging (`git add -p -- <paths>`) to keep commits scoped per feature.
