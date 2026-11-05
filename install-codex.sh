#!/usr/bin/env bash
# Project-local installation: no writes to HOME or Claude configuration.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_SETUP=false
CHECK_ONLY=false
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=true; SKIP_SETUP=true ;;
    --skip-setup) SKIP_SETUP=true ;;
    --cutout) ARGS+=("--cutout") ;;
    *) echo "Usage: $0 [--skip-setup | --check] [--cutout]" >&2; exit 2 ;;
  esac
done
DEST="$ROOT/.agents/skills"
# Fail before changing links or installing dependencies on an incomplete checkout.
# Keep the eleven original treatments and the coordinating skill mandatory.
REQUIRED=(auto-reels behind-the-person explainer orbit-reel picture-stack ranking-list
          scene-switch shape-shift split-screen storytelling trial-reels visual-notes)
for name in "${REQUIRED[@]}"; do
  if [ ! -s "$ROOT/skills/$name/SKILL.md" ]; then
    echo "Missing skills/$name/SKILL.md; check out the latest codex-editing-skills branch." >&2
    exit 1
  fi
done
# Preflight every destination so a collision cannot leave a partial installation.
SOURCES=()
for d in "$ROOT"/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  name=$(basename "$d")
  SOURCES+=("$name")
  if [ -e "$DEST/$name" ] || [ -L "$DEST/$name" ]; then
    if [ "$(readlink "$DEST/$name" || true)" != "../../skills/$name" ]; then
      echo "Refusing to replace existing $DEST/$name" >&2; exit 1
    fi
  elif [ "$CHECK_ONLY" = true ]; then
    echo "Missing discovery link: $DEST/$name; run $0 --skip-setup." >&2; exit 1
  fi
done
if [ "$CHECK_ONLY" = true ]; then
  echo "Codex: ${#SOURCES[@]} discovery links valid (including auto-reels); runtime/catalog not tested."
  exit 0
fi
mkdir -p "$DEST"
for name in "${SOURCES[@]}"; do
  [ -L "$DEST/$name" ] || ln -s "../../skills/$name" "$DEST/$name"
done
if [ "$SKIP_SETUP" = false ]; then
  bash "$ROOT/kit/setup.sh" "${ARGS[@]}"
fi
echo "Codex: skills available in $DEST; start a new task to refresh discovery."
