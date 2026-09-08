#!/usr/bin/env bash
# MIDI of a LilyPond score with articulations neutralised, for compare_scores.py.
# LilyPond shortens staccato (×0.5) and staccatissimo (×0.12) notes in its MIDI output, which makes the
# duration-agreement metric lie about the notation. This strips -. -! -> -_ \staccato \staccatissimo
# \accent \portato \tenuto \marcato from a temporary copy and renders MIDI only.
#   scripts/score_midi_for_compare.sh score.ly out.midi
set -u
src="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; out="$2"
outdir="$(mkdir -p "$(dirname "$out")" && cd "$(dirname "$out")" && pwd)"; out="$outdir/$(basename "$out")"
tmpdir="$outdir/.compare-tmp"; mkdir -p "$tmpdir"
# only on lines without Scheme code (#( … )) — `number->string` must survive
sed -E '/#\(/!{s/(-|\^|_)(\.|!|>|_|\+|-)//g; s/\\(staccato|staccatissimo|accent|portato|tenuto|marcato)([^A-Za-z]|$)/\2/g;}; s/\\new ChordNames/% (compare) \\new ChordNames/' "$src" > "$tmpdir/score_plain.ly"
( cd "$tmpdir" && lilypond -dno-print-pages -dno-point-and-click -o score_plain score_plain.ly ) > "$tmpdir/lilypond.log" 2>&1
if [ -f "$tmpdir/score_plain.midi" ]; then mv "$tmpdir/score_plain.midi" "$out"; echo "compare MIDI -> $out"; else echo "no MIDI produced; see $tmpdir/lilypond.log"; exit 1; fi
