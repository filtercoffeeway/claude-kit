#!/usr/bin/env bash
# Install (or --uninstall) the status line in ~/.claude/settings.json.
# Usage: statusline/setup.sh [--uninstall] [--force]
set -euo pipefail

dir="$(cd "$(dirname "$0")" && pwd)"
settings="$dir/../lib/settings.py"

action=set
force=()
for arg in "$@"; do
  case "$arg" in
    --uninstall) action=unset ;;
    --force) force=(--force) ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo "  python3 is required" >&2; exit 1; }
if [[ $action == set ]]; then
  command -v git >/dev/null || echo "  warning: git not found; branch segment will be hidden"
  command -v gh >/dev/null || echo "  warning: gh not found; PR segment will be hidden"
fi

value="$(python3 -c 'import json,shlex,sys; print(json.dumps({"type": "command", "command": "python3 " + shlex.quote(sys.argv[1]), "padding": 0}))' "$dir/statusline.py")"
python3 "$settings" "$action" statusLine "$value" ${force[@]+"${force[@]}"}
