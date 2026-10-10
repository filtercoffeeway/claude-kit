#!/usr/bin/env bash
# Install every tool, or only the ones named.
# Usage: ./setup.sh [tool ...] [--uninstall] [--force]
set -euo pipefail

root="$(cd "$(dirname "$0")" && pwd)"

tools=()
flags=()
for arg in "$@"; do
  case "$arg" in
    --*) flags+=("$arg") ;;
    *) tools+=("${arg%/}") ;;
  esac
done

if [[ ${#tools[@]} -eq 0 ]]; then
  for script in "$root"/*/setup.sh; do
    tools+=("$(basename "$(dirname "$script")")")
  done
fi

failed=0
for tool in "${tools[@]}"; do
  script="$root/$tool/setup.sh"
  if [[ ! -f $script ]]; then
    echo "$tool: no setup.sh" >&2
    failed=1
    continue
  fi
  echo "$tool:"
  bash "$script" ${flags[@]+"${flags[@]}"} || failed=1
done

[[ $failed -eq 0 ]] && echo "Done. Start a new Claude Code session to pick up changes."
exit $failed
