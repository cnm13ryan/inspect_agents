#!/usr/bin/env bash
set -euo pipefail

SESSION_FILE=".session_files"

cmd="${1:-usage}"

usage() {
  cat <<EOF
Usage: scripts/session-init.sh [init|add|check|list|clear]
  init  - create .session_files if missing
  add   - append path(s) to .session_files
  check - ensure staged files ⊆ .session_files
  list  - print tracked session files
  clear - empty .session_files (keeps file)
EOF
}

case "$cmd" in
  init)
    if [[ ! -f "$SESSION_FILE" ]]; then
      : > "$SESSION_FILE"
      echo "Initialized $SESSION_FILE (ensure it is listed in .gitignore)."
    else
      echo "$SESSION_FILE already exists."
    fi
    ;;
  add)
    shift || true
    if [[ $# -eq 0 ]]; then
      echo "Usage: $0 add <path> [path ...]" >&2
      exit 2
    fi
    touch "$SESSION_FILE"
    added=0
    for f in "$@"; do
      if ! grep -Fxq -- "$f" "$SESSION_FILE" 2>/dev/null; then
        printf '%s\n' "$f" >> "$SESSION_FILE"
        added=$((added+1))
      fi
    done
    echo "Added $added path(s) to $SESSION_FILE."
    ;;
  list)
    if [[ -f "$SESSION_FILE" ]]; then
      cat "$SESSION_FILE"
    else
      echo "No $SESSION_FILE found. Run: $0 init"
    fi
    ;;
  clear)
    : > "$SESSION_FILE"
    echo "Cleared $SESSION_FILE."
    ;;
  check)
    if [[ ! -f "$SESSION_FILE" ]]; then
      echo "ERROR: $SESSION_FILE missing. Run: $0 init" >&2
      exit 1
    fi
    # Determine non-session staged files (staged minus tracked session list)
    non_session="$(git diff --name-only --cached | sort -u | grep -vxF -f "$SESSION_FILE" || true)"
    if [[ -n "$non_session" ]]; then
      echo "ERROR: Non-session files staged:" >&2
      printf '  %s\n' $non_session >&2
      exit 1
    fi
    echo "OK: Only session files are staged."
    ;;
  *)
    usage
    ;;
esac
