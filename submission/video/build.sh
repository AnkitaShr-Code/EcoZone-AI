#!/usr/bin/env bash
# Build the demo video from a recorded take.
#   ./build.sh --voice-dir audio/ --out out/final.mp4     final: per-segment narration audio/sNN.mp3
#   ./build.sh --tts say [--out out/rehearsal.mp4]       rehearsal: macOS `say -v Tara`
# Options: --take takes/<name> (default: takes/CURRENT), --no-music, --voice <say voice>, --rate <wpm>
set -euo pipefail
cd "$(dirname "$0")"
if [[ " $* " == *" --tts say "* && " $* " != *" --out "* ]]; then set -- "$@" --out out/rehearsal.mp4; fi
exec node tools/build.mjs "$@"
