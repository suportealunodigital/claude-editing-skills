#!/usr/bin/env bash
# Project-local installation: no writes to HOME or Claude configuration.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_SETUP=false
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --skip-setup) SKIP_SETUP=true ;;
    --cutout) ARGS+=("--cutout") ;;
    *) echo "Usage: $0 [--skip-setup] [--cutout]" >&2; exit 2 ;;
  esac
done
DEST="$ROOT/.agents/skills"
mkdir -p "$DEST"
for d in "$ROOT"/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  name=$(basename "$d")
  if [ -e "$DEST/$name" ] || [ -L "$DEST/$name" ]; then
    if [ "$(readlink "$DEST/$name" || true)" = "../../skills/$name" ]; then
      continue
    fi
    echo "Refusing to replace existing $DEST/$name" >&2; exit 1
  fi
  ln -s "../../skills/$name" "$DEST/$name"
done
if [ "$SKIP_SETUP" = false ]; then
  bash "$ROOT/kit/setup.sh" "${ARGS[@]}"
fi
echo "Codex: skills available in $DEST; start a new task to refresh discovery."
