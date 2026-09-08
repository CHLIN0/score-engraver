#!/usr/bin/env bash
# Render a LilyPond source to PDF + page PNGs (+ MIDI if the score has a \midi block).
#   scripts/render_ly.sh score.ly outdir [dpi]
# Writes outdir/score.pdf, outdir/score.png or outdir/score-page{N}.png, outdir/score.midi, outdir/lilypond.log
set -u
src="$1"; out="$2"; dpi="${3:-110}"
mkdir -p "$out"
# stale pages from a previous, longer render would be counted below: park them in stale/
if ls "$out"/page-*.png >/dev/null 2>&1; then mkdir -p "$out/stale" && mv "$out"/page-*.png "$out/stale/"; fi
lilypond -dno-point-and-click -dresolution="$dpi" --pdf --png -o "$out/score" "$src" >"$out/lilypond.log" 2>&1
status=$?
# normalise page names: score.png (1 page) or score-page1.png ...
if [ -f "$out/score.png" ]; then mv "$out/score.png" "$out/page-1.png"; fi
for f in "$out"/score-page*.png; do
  [ -f "$f" ] || continue
  n=$(echo "$f" | sed -E 's/.*score-page([0-9]+)\.png/\1/')
  mv "$f" "$out/page-$n.png"
done
pages=$(ls "$out"/page-*.png 2>/dev/null | wc -l | tr -d ' ')
warn=$(grep -ci "warning" "$out/lilypond.log" || true)
err=$(grep -ci "error" "$out/lilypond.log" || true)
echo "lilypond exit $status; $pages page(s) -> $out/page-N.png at $dpi dpi; warnings $warn, errors $err (see lilypond.log)"
[ "$pages" -gt 0 ]
