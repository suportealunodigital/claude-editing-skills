#!/usr/bin/env bash
# Independent auto-reels runtime; keeps the legacy setup/version intact.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for tool in ffmpeg ffprobe node npm curl python3; do
  command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }
done
node -e 'if(Number(process.versions.node.split(".")[0])<22)process.exit(1)'
python3 -c 'import sys; assert sys.version_info >= (3,12)'
if [ ! -x "$KIT/.venv/bin/python" ]; then python3 -m venv "$KIT/.venv"; fi
"$KIT/.venv/bin/python" -m pip install -r "$KIT/requirements-auto.txt"
mkdir -p "$KIT/.hyperframes" "$KIT/vendor" "$KIT/.npm-cache"
# HF's optional Node ONNX install script broke the legacy 0.8.34 setup.
# This HTML renderer uses Python ONNX for matting and a system Chromium; skip
# unrelated Node lifecycle scripts. The render smoke test remains the real check.
cp "$KIT/hyperframes-auto/package.json" "$KIT/hyperframes-auto/package-lock.json" "$KIT/.hyperframes/"
npm_config_cache="$KIT/.npm-cache" npm ci --prefix "$KIT/.hyperframes" --ignore-scripts --no-audit --no-fund
node "$KIT/.hyperframes/node_modules/hyperframes/dist/cli.js" --version
if [ ! -s "$KIT/vendor/gsap.min.js" ]; then
  curl --fail --silent --show-error --location --proto '=https' https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js -o "$KIT/vendor/gsap.min.js.download"
  mv "$KIT/vendor/gsap.min.js.download" "$KIT/vendor/gsap.min.js"
fi
if [ ! -s "$KIT/vendor/gsap-3.15.0.min.js" ]; then
  curl --fail --silent --show-error --location --proto '=https' https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js -o "$KIT/vendor/gsap-3.15.0.min.js.download"
  mv "$KIT/vendor/gsap-3.15.0.min.js.download" "$KIT/vendor/gsap-3.15.0.min.js"
fi
if [ "${1:-}" = '--cutout' ]; then
  "$KIT/.venv/bin/python" -c "import sys;sys.path.insert(0,sys.argv[1]);from cutout import model_path;model_path('mobilenetv3')" "$KIT"
fi
if ! command -v chromium >/dev/null && [ -z "${HYPERFRAMES_BROWSER_PATH:-}" ]; then
  echo 'Install system Chromium or configure HYPERFRAMES_BROWSER_PATH. No browser security flags are disabled.' >&2
  exit 1
fi
echo 'Runtime dependencies prepared. Run ./auto-reels --doctor; a real audio render is still required.'
