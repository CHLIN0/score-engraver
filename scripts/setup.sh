#!/usr/bin/env bash
# Create the skill's Python environment (uv) and check MuseScore.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "install uv: https://docs.astral.sh/uv/"; exit 1; }
[ -x .venv/bin/python ] || uv venv .venv --python 3.11
uv pip install --python .venv/bin/python music21 pretty_midi mido numpy librosa soundfile pypdfium2
if command -v mscore >/dev/null 2>&1 || [ -x "/Applications/MuseScore 4.app/Contents/MacOS/mscore" ]; then echo "MuseScore: ok"; else echo "MuseScore 4 not found: install it or set MSCORE=/path/to/mscore"; fi
.venv/bin/python -c "import music21, pretty_midi, librosa, pypdfium2; print('python deps ok, music21', music21.__version__)"
