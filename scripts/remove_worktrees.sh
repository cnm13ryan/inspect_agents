#!/usr/bin/env bash

# Compatibility shim: moved to scripts/git/worktrees-remove.sh
#
# New path:
#   scripts/git/worktrees-remove.sh

set -euo pipefail

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  bash "$(dirname "$0")/git/worktrees-remove.sh" --help
  exit 0
fi

echo "[deprecated] scripts/remove_worktrees.sh has moved to scripts/git/worktrees-remove.sh" >&2
exec bash "$(dirname "$0")/git/worktrees-remove.sh" "$@"
