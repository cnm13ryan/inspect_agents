#!/usr/bin/env bash

set -euo pipefail

# remove_worktrees.sh — interactively remove git worktrees (and optionally branches)
#
# - Defaults to only listing worktrees whose paths live under repo-local
#   ".worktrees/" or ".worktree/" folders, mirroring how this repo creates them.
# - You can include all worktrees by answering the scope prompt accordingly
#   or passing --all on the command line.
# - Inspired by the interactive style of env_templates/configure.py.
#
# Usage:
#   scripts/remove_worktrees.sh [--all] [--force]
#                               [--select <spec>] [--yes]
#                               [--delete-branch] [--force-branch]
#
# Flags:
#   --all            Include all worktrees (not just those under .worktrees/.worktree)
#   --force          Pass --force to `git worktree remove` when needed (dirty worktrees)
#   --select <spec>  Non-interactive selection: 'a' for all, or list like '1,3-5'
#   --yes            Non-interactive: proceed without prompts (use defaults unless flags set)
#   --delete-branch  Also delete local branches for selected worktrees (safe -d)
#   --force-branch   Force delete local branches (uses `git branch -D`)
#   -h|--help        Show this help

usage() {
  sed -n '1,60p' "$0" | sed -n '1,60p' | sed -n '1,40p' 1>/dev/null 2>&1 || true
  cat <<'USAGE'
Interactive Git Worktree Remover
--------------------------------
Lists worktrees and lets you select which to remove, with an option to
also delete their local branches. Defaults to scanning .worktrees/ and
.worktree/ under the repo root.

Usage:
  scripts/remove_worktrees.sh [--all] [--force]
                              [--select <spec>] [--yes]
                              [--delete-branch] [--force-branch]

Options:
  --all            Include all worktrees (not only under .worktrees/.worktree)
  --force          Force remove worktrees (passes --force to git worktree remove)
  --select <spec>  Non-interactive selection: 'a' for all, or '1,3-5'
  --yes            Non-interactive: skip prompts; combine with --select
  --delete-branch  Also delete local branches for selected worktrees (safe -d)
  --force-branch   Force delete local branches (uses `git branch -D`)
  -h, --help       Show this help and exit
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

# ----- Small UX helpers (similar vibe to configure.py) -----
truthy() { case "${1:-}" in [Yy1]|[Yy][Ee][Ss]|on|true|TRUE) return 0;; *) return 1;; esac; }

ask() {
  local prompt=$1 default=${2:-}
  local suffix=""
  [[ -n "$default" ]] && suffix=" [default: $default]"
  read -r -p "$prompt$suffix: " ans || ans=""
  [[ -z "$ans" && -n "$default" ]] && ans="$default"
  printf '%s' "$ans"
}

ask_bool() {
  local prompt=$1 def=${2:-false} hint=" [y/N]"
  $def && hint=" [Y/n]"
  read -r -p "$prompt$hint: " ans || ans=""
  if [[ -z "$ans" ]]; then $def && return 0 || return 1; fi
  truthy "$ans"
}

choose() {
  # choose "Prompt" "opt1" "opt2" ...; echoes chosen option
  local prompt=$1; shift
  local opts=("$@")
  local def_idx=0
  for i in "${!opts[@]}"; do
    local mark=" "; [[ $i -eq $def_idx ]] && mark='*'
    printf '  %d. %s %s\n' $((i+1)) "${opts[$i]}" "$mark"
  done
  while true; do
    read -r -p "$prompt (1-${#opts[@]}, default $((def_idx+1))): " sel || sel=""
    if [[ -z "$sel" ]]; then echo "${opts[$def_idx]}"; return; fi
    if [[ "$sel" =~ ^[0-9]+$ ]]; then
      local idx=$((sel-1))
      if (( idx >= 0 && idx < ${#opts[@]} )); then
        echo "${opts[$idx]}"; return
      fi
    fi
    echo "Please enter a valid number." >&2
  done
}

# ----- Parse flags -----
INCLUDE_ALL=0
FORCE_REMOVE=0
YES_MODE=0
SELECTION_SPEC=""
DEL_BRANCH=0
FORCE_BRANCH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) INCLUDE_ALL=1; shift;;
    --force) FORCE_REMOVE=1; shift;;
    --select|-s) SELECTION_SPEC="${2:-}"; [[ -z "$SELECTION_SPEC" ]] && die "--select requires an argument"; shift 2;;
    --yes|-y) YES_MODE=1; shift;;
    --delete-branch) DEL_BRANCH=1; shift;;
    --force-branch) FORCE_BRANCH=1; shift;;
    -h|--help) usage; exit 0;;
    *) die "Unknown option: $1";;
  esac
done

# ----- Verify repo context -----
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
[[ -z "$REPO_ROOT" ]] && die "Not inside a git repository."

echo "🧹 Worktree Cleaner"
echo "==================="
cat <<'INTRO'
This interactive tool safely removes Git worktrees created for parallel development.

What this does:
- Removes selected worktree directories (the extra checkouts), not your main repo.
- Leaves local branches intact by default; you can opt to delete them.
- Never touches remote branches (e.g., origin/*).

Notes:
- If a worktree has uncommitted changes, standard removal will fail; you may choose
  a forced removal, which discards uncommitted files in that worktree only.
- Deleting a local branch with -d works only if fully merged; -D force-deletes it.
 - Deleting a local branch with -d works only if fully merged; -D force-deletes it.

How to answer prompts:
- When you see numbered options (1, 2, ...), type the number and press Enter.
- Press Enter with no input to accept the default shown in the prompt.
INTRO

# ----- Enumerate worktrees (porcelain) -----
PORCELAIN=$(git -C "$REPO_ROOT" worktree list --porcelain)

declare -a WT_PATHS WT_BRANCHES
cur_path=""; cur_branch=""
while IFS= read -r line; do
  if [[ "$line" == worktree* ]]; then
    cur_path=${line#worktree } ; cur_branch=""
  elif [[ "$line" == branch* ]]; then
    cur_branch=${line#branch }
  elif [[ -z "$line" ]]; then
    # end of record
    if [[ -n "$cur_path" ]]; then
      # Skip the primary checkout at repo root
      if [[ "$cur_path" != "$REPO_ROOT" ]]; then
        WT_PATHS+=("$cur_path")
        WT_BRANCHES+=("$cur_branch")
      fi
    fi
    cur_path=""; cur_branch=""
  fi
done <<<"$PORCELAIN"

# Handle last record without trailing blank
if [[ -n "$cur_path" && "$cur_path" != "$REPO_ROOT" ]]; then
  WT_PATHS+=("$cur_path"); WT_BRANCHES+=("$cur_branch")
fi

TOTAL=${#WT_PATHS[@]}
if (( TOTAL == 0 )); then
  echo "No secondary worktrees found for this repo. Nothing to do."; exit 0
fi

# ----- Filter to .worktrees/.worktree unless --all or chosen interactively -----
filter_paths() {
  local i
  local -a FPATHS FBRANCHES
  for i in "${!WT_PATHS[@]}"; do
    local p="${WT_PATHS[$i]}"
    if (( INCLUDE_ALL == 1 )); then
      FPATHS+=("$p"); FBRANCHES+=("${WT_BRANCHES[$i]}")
    else
      case "$p" in
        "$REPO_ROOT"/.worktrees/*|"$REPO_ROOT"/.worktree/*)
          FPATHS+=("$p"); FBRANCHES+=("${WT_BRANCHES[$i]}") ;;
      esac
    fi
  done
  WT_PATHS=("${FPATHS[@]}")
  WT_BRANCHES=("${FBRANCHES[@]}")
}

if (( INCLUDE_ALL == 0 )); then
  if (( YES_MODE == 1 )); then
    # Non-interactive: default to managed worktrees (.worktrees/.worktree)
    :
  else
    echo
    echo "Scope selection"
    echo "- Option 1 (default): Only .worktrees/.worktree — lists worktrees created by this repo's"
    echo "  helper scripts under $REPO_ROOT/.worktrees or $REPO_ROOT/.worktree. Safer and simpler."
    echo "- Option 2: All worktrees — lists every worktree for this repo wherever it lives. Useful"
    echo "  if you created worktrees manually in custom locations."
    echo "Enter 1 for the safer, repo-managed scope (default), or 2 to include all worktrees."
    scope=$(choose "Choose scope" \
           "Only .worktrees/.worktree — repo-managed worktrees (recommended)" \
           "All worktrees — include every worktree for this repo")
    [[ "$scope" == *"All worktrees"* ]] && INCLUDE_ALL=1
  fi
fi

filter_paths
COUNT=${#WT_PATHS[@]}
if (( COUNT == 0 )); then
  echo "No worktrees matched the chosen scope. Nothing to do."; exit 0
fi

# ----- Present menu -----
echo
echo "Found $COUNT removable worktree(s):"
echo "(Removing a worktree deletes that directory; the Git branch remains unless you opt to delete it.)"
for i in "${!WT_PATHS[@]}"; do
  p="${WT_PATHS[$i]}"; b="${WT_BRANCHES[$i]}"
  rel="${p#$REPO_ROOT/}"; [[ "$rel" == "$p" ]] && rel="$p"
  shortb=${b#refs/heads/}
  [[ -z "$shortb" || "$shortb" == "$b" ]] && shortb="(detached)"
  printf '  %2d) %-40s  branch: %s\n' $((i+1)) "$rel" "$shortb"
done

if [[ -n "$SELECTION_SPEC" ]]; then
  SELECTION="$SELECTION_SPEC"
elif (( YES_MODE == 1 )); then
  echo "Running non-interactively (--yes). Please provide --select <spec>." >&2
  exit 2
else
  echo
  echo "Selection help"
  echo "- Enter numbers like '1' or multiple like '1,3,5' or ranges '2-4'."
  echo "- Enter 'a' to select all listed worktrees. Press Enter with no input to abort."
  read -r -p "Select items to remove (e.g., 1,3-5 or 'a' for all; Enter to abort): " SELECTION || SELECTION=""
fi
[[ -z "$SELECTION" ]] && echo "Aborted." && exit 0

SEL_IDX=()
if [[ "$SELECTION" == "a" || "$SELECTION" == "A" || "$SELECTION" == "all" ]]; then
  for i in "${!WT_PATHS[@]}"; do SEL_IDX+=("$i"); done
else
  IFS=',' read -r -a toks <<<"$SELECTION"
  for t in "${toks[@]}"; do
    if [[ "$t" =~ ^[0-9]+-[0-9]+$ ]]; then
      lo=${t%-*}; hi=${t#*-}
      for ((k=lo; k<=hi; k++)); do idx=$((k-1)); (( idx>=0 && idx<COUNT )) && SEL_IDX+=("$idx"); done
    elif [[ "$t" =~ ^[0-9]+$ ]]; then
      idx=$((t-1)); (( idx>=0 && idx<COUNT )) && SEL_IDX+=("$idx")
    fi
  done
fi

if (( ${#SEL_IDX[@]} == 0 )); then echo "No valid selections. Aborting."; exit 1; fi

if (( YES_MODE == 1 )); then
  # Keep DEL_BRANCH / FORCE_BRANCH / FORCE_REMOVE as set by flags; otherwise defaults remain safe (0)
  :
else
  echo
  ask_bool "Also delete local Git branches for the selected worktrees? (does NOT affect remotes)" false && DEL_BRANCH=1 || DEL_BRANCH=0
  if (( DEL_BRANCH == 1 )); then
    ask_bool "Force delete unmerged branches with 'git branch -D'? (unsafe; use only if you know the branch is expendable)" false && FORCE_BRANCH=1 || FORCE_BRANCH=0
  else
    FORCE_BRANCH=0
  fi

  if (( FORCE_REMOVE == 0 )); then
    ask_bool "Force remove worktrees if they have uncommitted changes using 'git worktree remove --force'? (this discards uncommitted files in those directories)" false && FORCE_REMOVE=1 || FORCE_REMOVE=0
  fi

  ask_bool "Proceed with removal of ${#SEL_IDX[@]} selected worktree(s)?" true || { echo "Aborted."; exit 0; }
fi

# ----- Execute removals -----
removed=0; br_removed=0; failures=0
# de-duplicate while preserving order (macOS bash 3.2 compatible)
SEEN=""
for i in "${SEL_IDX[@]}"; do
  case " $SEEN " in *" $i "*) continue;; *) SEEN+=" $i";; esac
  path="${WT_PATHS[$i]}"; ref="${WT_BRANCHES[$i]}"; short=${ref#refs/heads/}
  echo "- Removing worktree: $path"
  if (( FORCE_REMOVE == 1 )); then
    if ! git -C "$REPO_ROOT" worktree remove --force "$path"; then failures=$((failures+1)); continue; fi
  else
    if ! git -C "$REPO_ROOT" worktree remove "$path"; then
      echo "  Failed (dirty or busy). Re-run with --force or choose force at prompt." >&2
      failures=$((failures+1)); continue
    fi
  fi
  removed=$((removed+1))

  if (( DEL_BRANCH == 1 )) && [[ -n "$short" && "$short" != "$ref" ]]; then
    echo "  Deleting local branch: $short"
    if (( FORCE_BRANCH == 1 )); then
      if git -C "$REPO_ROOT" branch -D "$short" >/dev/null 2>&1; then br_removed=$((br_removed+1)); else echo "    (warn) Could not force-delete $short"; fi
    else
      if git -C "$REPO_ROOT" branch -d "$short" >/dev/null 2>&1; then br_removed=$((br_removed+1)); else echo "    (warn) Branch not fully merged; not deleted (use force to override)"; fi
    fi
  fi
done

echo "Pruning stale worktree metadata ..."
git -C "$REPO_ROOT" worktree prune >/dev/null 2>&1 || true

echo
echo "Summary:"
echo "  Worktrees removed: $removed"
echo "  Branches deleted:  $br_removed"
echo "  Failures:          $failures"

if (( failures > 0 )); then
  echo "Some removals failed. You may need to close running processes in those worktrees, commit or stash changes, or retry with --force."
fi

echo "Done."
