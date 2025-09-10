# Worktree Helper Scripts

This folder contains utilities to streamline parallel feature development using Git worktrees.

## create_feature_worktrees.sh — Single or Batch Worktree Creation

- Purpose: create one or many Git worktrees for feature development. The `single` subcommand creates one worktree quickly and writes a per‑worktree `.env`. Batch modes derive branches from phase files, a plan JSON, or feature files and write a `prompts/FEATURE_PROMPT.txt` into each worktree.
- Location: `scripts/create_feature_worktrees.sh`
- Requirements: Git ≥ 2.5 and bash.

### Quick Start (single worktree)

```bash
# From your main repo clone (clean working tree recommended)
bash scripts/create_feature_worktrees.sh single --branch feat/fs-atomic

# Specify a custom path and push upstream
bash scripts/create_feature_worktrees.sh single --branch feat/profiles --path ../inspect_agents-profiles --push
```

### Batch Modes (auto-detected)

- Mode C: uses `prompts/features_by_phase/phase-*.md` (merged phase files)
- Mode B: uses `prompts/plan/features_plan.json` plus `prompts/features/`
- Mode A: uses files in `prompts/features/` when no plan/phase files are present

Run:

```bash
bash scripts/create_feature_worktrees.sh
```

Filters via env vars: `PHASES=1,2 GROUPS=A bash scripts/create_feature_worktrees.sh`

### Working With Multiple Codex Sessions

- Start a separate session per worktree and set the session’s CWD to the worktree path (each session works on its own branch).
- Keep environments and logs isolated per worktree via the generated `.env` (written by `single` and by batch modes when creating prompts/FEATURE_PROMPT.txt).
- If your runner requires it, export `INSPECT_ENV_FILE=.env` before running.

### Common Tasks

- List worktrees: `git worktree list`
- Remove a worktree after merge: `git worktree remove <path> && git worktree prune`
- Push branch later: `git push -u origin <branch>`
- Rebase worktree branch: `git fetch origin && git rebase origin/main`

### Troubleshooting

- "Branch is already checked out": create a new branch name; Git forbids checking the same branch in multiple worktrees.
- "Not inside a git repository": run the script from within a cloned repo.
- Provider/submodule differences: if your feature changes submodules or provider configs, repeat any required `git submodule update` inside each worktree.

### Notes

- Worktrees share the same `.git` object store, so large binary files affect disk usage across all worktrees.
- Prefer selective staging (`git add -p -- <paths>`) to keep commits scoped per feature.
