#!/usr/bin/env bash
# Engrave MusicXML with MuseScore 4 and rasterize every page for visual checking.
#   scripts/render_score.sh score.musicxml outdir [dpi]
# Produces outdir/score.pdf, outdir/page-1.png … (via pypdfium2, default 110 dpi), outdir/score.mid (MuseScore playback MIDI).
set -euo pipefail
IN="$1"; OUT="$2"; DPI="${3:-110}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MS="${MSCORE:-}"
if [ -z "$MS" ]; then
  if command -v mscore >/dev/null 2>&1; then MS=mscore; elif [ -x "/Applications/MuseScore 4.app/Contents/MacOS/mscore" ]; then MS="/Applications/MuseScore 4.app/Contents/MacOS/mscore"; else echo "MuseScore not found; set MSCORE" >&2; exit 1; fi
fi
mkdir -p "$OUT"
"$MS" -o "$OUT/score.pdf" "$IN" >/dev/null 2>&1 || true
"$MS" -o "$OUT/score.mid" "$IN" >/dev/null 2>&1 || true
[ -s "$OUT/score.pdf" ] || { echo "MuseScore produced no PDF for $IN" >&2; exit 1; }
"$HERE/../.venv/bin/python" - "$OUT/score.pdf" "$OUT" "$DPI" <<'EOF'
import sys, pypdfium2 as pdfium
pdf, out, dpi = sys.argv[1], sys.argv[2], float(sys.argv[3])
doc = pdfium.PdfDocument(pdf)
for i in range(len(doc)):
    img = doc[i].render(scale=dpi / 72).to_pil()
    img.save(f"{out}/page-{i + 1}.png")
print(f"{len(doc)} page(s) -> {out}/page-N.png at {int(dpi)} dpi")
EOF
