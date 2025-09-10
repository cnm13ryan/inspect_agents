#!/usr/bin/env bash

# Compatibility shim: moved to scripts/git/worktrees-create.sh
#
# For one release window, keep this wrapper so existing docs/commands continue
# to work. New path:
#   scripts/git/worktrees-create.sh

set -euo pipefail

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  bash "$(dirname "$0")/git/worktrees-create.sh" --help
  exit 0
fi

echo "[deprecated] scripts/create_feature_worktrees.sh has moved to scripts/git/worktrees-create.sh" >&2
exec bash "$(dirname "$0")/git/worktrees-create.sh" "$@"
