#!/usr/bin/env bash

# Compatibility shim: moved to scripts/eval/export-log-json.sh
#
# Backwards-compatible default: if caller does not pass -o/--out or --auto-name,
# preserve the old default output path of "scripts/eval.json".

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
default_out="$script_dir/eval.json"

has_out=0
has_auto=0
for arg in "$@"; do
  case "$arg" in
    -o|--out) has_out=1;;
    -a|--auto-name) has_auto=1;;
  esac
done

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  bash "$script_dir/eval/export-log-json.sh" --help
  exit 0
fi

if [[ $has_out -eq 0 && $has_auto -eq 0 ]]; then
  exec bash "$script_dir/eval/export-log-json.sh" -o "$default_out" "$@"
else
  exec bash "$script_dir/eval/export-log-json.sh" "$@"
fi
