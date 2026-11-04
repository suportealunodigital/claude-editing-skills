# Video editing in OpenAI Codex Cloud

The canonical skills are in `skills/`. Eleven tracked relative symlinks in
`.agents/skills/` expose them to Codex without duplicating instructions or changing
the Claude plugin. Keep `skills/`, `kit/` and `assets/` together. Resolve the loaded
SKILL.md symlink before locating its sibling build.py or the shared kit.

## Setup in a fresh Cloud environment

Run from this repository, with Python 3.9+, Node.js 22+/npm and ffmpeg/ffprobe
installed. ffmpeg needs libx264, AAC and libvpx-vp9 for alpha cutouts.

```bash
bash install-codex.sh --skip-setup   # only checks/creates project discovery links
bash install-codex.sh              # links plus original Python/GSAP/renderer setup
# If the chosen workflow needs a new speaker cutout:
bash install-codex.sh --cutout
```

Configure setup before starting the editing task; start a new task after adding
skills if the catalog is stale. Tasks must run inside this checkout. The original
`install.sh`, `CLAUDE_SKILLS_DIR` and `.claude-plugin/` remain for Claude Code.
No global Codex install or Claude install is required for Cloud discovery.

Setup creates `kit/.venv` and installs groq, numpy, pillow and onnxruntime (currently
unpinned upstream dependencies). It fetches GSAP 3.12.5 and warms HyperFrames
0.8.34 for the six original workflows. The photographic builder separately fetches
GSAP 3.15.0 and uses HyperFrames 0.8.214. Preserve these distinct versions.
The renderer also needs Chromium and its Linux libraries; a version check alone
is not a successful render. Populate npm/browser caches during setup where needed.
If Chromium is already installed, select its actual path with
`HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium` (verify that path first).
The Cloud executor must permit browser subprocesses and local rendering services;
a restricted command sandbox can fail with `browser setup process exited without
a result` even when Chromium is installed. Use the platform permission mechanism
for the render and keep its network policy in effect. Do not disable browser or
platform security as a workaround. The five-template builder accepts
`HYPERFRAMES_CLI=/absolute/path/to/hyperframes/dist/cli.js` to reuse a verified
0.8.214 installation. This override does not apply to the original six workflows.

Network must allow PyPI, npm, cdnjs.cloudflare.com, cdn.jsdelivr.net and the
browser/package download hosts actually requested by HyperFrames. New cutouts
also download ONNX models from GitHub releases. Transcription calls api.groq.com.
If a host is denied, report it and request environment configuration; do not bypass
the network policy. Offline tasks need these caches prepared in advance.

## Invocation

Use the literal `$skill-name` in a Codex prompt, followed by a path available in the
Cloud filesystem. Local laptop paths such as `~/Downloads` are not uploaded by a
prompt. Read the selected SKILL.md before creating a spec or running its builder.
These are skill invocations, not ChatGPT slash commands. Claude keeps `/skill-name`.
Some Codex clients namespace the catalog using the retained Claude plugin manifest.
The native `skills/list` in this environment returned all eleven as
`editing-skills:NAME`; in that client use `$editing-skills:NAME` (for example
`$editing-skills:explainer /workspace/media/clip.mp4`). Follow the name actually
shown in the task catalog; the table below uses the short skill names.

| Codex prompt | Result |
|---|---|
| `$trial-reels /workspace/media/clip.mp4` | Three trial versions of one clip |
| `$behind-the-person /workspace/media/clip.mp4` | Real graphics behind a cutout speaker |
| `$explainer /workspace/media/clip.mp4` | Speaker below explanatory visuals |
| `$split-screen /workspace/media/clip.mp4` | Visuals above, speaker below |
| `$ranking-list /workspace/media/clip.mp4` | Word-timed tier list |
| `$storytelling /workspace/media/clip.mp4` | Three story cards and captions |
| `$shape-shift skills/shape-shift/example.json` | Circular photographic match cuts |
| `$picture-stack skills/picture-stack/example.json` | Stacked photographs and focus |
| `$scene-switch skills/scene-switch/example.json` | Photographic background changes |
| `$visual-notes skills/visual-notes/example.json` | Full image followed by detail |
| `$orbit-reel skills/orbit-reel/example.json` | Image cards orbit the speaker |

For the six original workflows, use `kit/.venv/bin/python skills/NAME/build.py SPEC`.
They require a real Groq credential for new transcripts, or an existing truthful
word-timed transcript supplied via the spec's `transcript` field. The words command
also supports `--transcript PATH`. Never fabricate words, timings, user metrics,
credentials or people. Set GROQ_API_KEY only through a real environment secret;
verify availability in the editing phase, not just the setup phase. Never print it.

For the five photographic skills, use `python3 skills/NAME/build.py SPEC`;
`--prepare-only` creates HTML without rendering, but still needs GSAP and ffprobe.
No API key is required. Defaults use bundled sample media, are silent, and last
4.2 seconds. For real footage, prepare the required 1080x1920 media and matched
alpha cutout where required. Follow `docs/style-showcase/README.md` for asset keys,
relative paths, timeline changes and audio limitations. Do not mistake sample
footage for the user's clip. Respect the separate asset licenses.

## Verification and delivery

Run `python3 -m unittest discover -s tests -v` and `bash -n install.sh install-codex.sh
kit/setup.sh`. Test discovery through Codex's `skills/list` when available; static
link checks alone do not prove that a running Cloud task has refreshed its catalog.
There was no upstream test suite in the baseline commit.

Validate output by fully decoding the MP4 with ffmpeg, inspecting metadata with
ffprobe and viewing frames/contact sheets for safe zones, mouth visibility,
synchronization and cutout quality. A prepared composition or renderer version
check does not establish a successful MP4 or visual approval. Report the exact
commands executed, failures, missing dependencies and output paths. Never claim
transcription, segmentation, rendering or visual checks that were not performed.
