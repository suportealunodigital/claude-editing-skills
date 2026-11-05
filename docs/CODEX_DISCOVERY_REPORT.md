# Codex auto-reels discovery verification — 2026-11-05

## Cause and source

The executor started on local branch `work` at `beff6b8`, with only
`+refs/heads/main:refs/remotes/origin/main` configured for fetch. A normal fetch
therefore did not bring in `codex-editing-skills`. An explicit fetch found remote
head `095375a745e398de7407af8f70fd33fca887c5db`. That commit already contains
auto-reels; history shows its addition in `095375a`, after Codex adaptation in
`07ce41b`. No recreation was needed. The checkout was switched to
`codex-editing-skills`, and its local fetch/tracking configuration now includes
that branch. These local Git settings are not inherited by fresh clones; the
branch selection and explicit-fetch recovery are documented in AUTO_REELS.md.

Canonical skill: `skills/auto-reels/SKILL.md`.
Tracked discovery link: `.agents/skills/auto-reels -> ../../skills/auto-reels`.
Entrypoints: `auto-reels`, `skills/auto-reels/build.py`, `kit/auto_reels.py`.
Implementation: `kit/autoreels/{transfer,media,planning,rendering}.py` and
`kit/autoreels/check_layout.mjs`. Dependencies: `kit/requirements-auto.txt` and
`kit/hyperframes-auto/{package.json,package-lock.json}` (HyperFrames 0.8.214).
The canonical skill and all eleven previous skill directories are preserved.

## Changes

- Installer requires all twelve SKILL.md sources, preflights collisions before
  modifying links, and supports read-only `--check`. `--skip-setup` performs no
  package installation.
- Launcher `--help`, `-h` and `--doctor` bypass setup, even without a renderer.
  During verification the previous `--help` behavior triggered setup; it was
  stopped. Pip reported the Python dependencies already satisfied; Groq was not
  reinstalled. This regression is now covered by an isolated launcher test.
- Skill instructions distinguish installation/diagnostics from permission to edit.
- Discovery recovery and new-task requirements are documented.

## Executed verification

- `bash install-codex.sh --skip-setup` and `bash install-codex.sh --check`: pass,
  twelve relative links including auto-reels.
- `kit/.venv/bin/python -m unittest discover -s tests -v`: 28 tests pass. Coverage
  includes twelve builders imported via discovery links, metadata and shared-kit
  resolution, installer idempotence, collision preservation, missing auto-reels,
  read-only checks, original Claude installer, diagnostic setup avoidance,
  mocked Drive transfers and real synthetic FFmpeg/audio validation.
- YAML frontmatter parsed for all twelve SKILL.md files: names match directory
  names, descriptions are nonempty strings within 1024 characters, names within
  64 characters; source resolution and build.py presence pass.
- `bash -n install.sh install-codex.sh kit/setup.sh kit/setup-auto.sh auto-reels`:
  pass.
- `node --check kit/autoreels/check_layout.mjs`: pass.
- `kit/.venv/bin/python -m compileall -q skills kit tests`: pass.
- `kit/.venv/bin/python -m pip check`: no broken requirements.
- Renderer package manifest and lockfile dependency declarations match.
- `./auto-reels --help` and `./auto-reels --doctor`: pass without setup after fix.
- `git diff --check`: pass.

## Discovery versus rendering

Executor `skills/list` returned an empty catalog in this already-running task,
including after the branch switch. Filesystem installation alone cannot prove
that the client has refreshed its skill catalog. Start a new task inside this
checkout on `codex-editing-skills`, inspect its catalog and invoke `$auto-reels`
(or its actual namespaced entry). A diagnostic-only prompt can be used first:
`$auto-reels apenas diagnóstico, sem editar`.

Existing Python runtime has groq/httpx/numpy/Pillow/onnxruntime; ffmpeg, ffprobe,
Node, npm and Chromium are present. GROQ_API_KEY presence was confirmed without
printing its value. No network permissions or secret bindings were changed.
HyperFrames runtime was absent before checks, and the matting model is absent;
a production render has not been validated in this task. No input video was
edited, transcribed, rendered or uploaded. Test media was synthetic and temporary.
