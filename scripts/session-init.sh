#!/usr/bin/env bash

# Compatibility shim: moved to scripts/dev/session-files.sh

set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  bash "$script_dir/dev/session-files.sh" --help 2>/dev/null || true
  cat <<EOF
Usage: scripts/dev/session-files.sh [init|add|check|list|clear]
(Command moved from scripts/session-init.sh)
EOF
  exit 0
fi

echo "[deprecated] scripts/session-init.sh has moved to scripts/dev/session-files.sh" >&2
exec bash "$script_dir/dev/session-files.sh" "$@"
