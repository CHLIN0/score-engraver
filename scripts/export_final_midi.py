"""The finished score as a MIDI file — the portable twin of score.ly.

    python export_final_midi.py score.ly final.mid [--playback] [--with-chords] [--json final.mid.json]

score.ly is the master (it alone holds spelling, hands, ties, rolls, chord symbols, lyrics, layout).
This writes the one artifact every other program can read, carrying everything MIDI is able to carry:

  * bars and beats  — the conductor track keeps every \time change and the whole tempo map (rit. included)
  * key signatures  — LilyPond writes them, so an importer spells G-flat, not F-sharp
  * one track per hand — "RH (upper staff)" / "LH (lower staff)", named, so a notation program
    re-imports two staves instead of one blob
  * ties already merged into single notes; grace notes in place

By default the durations are the NOTATED ones: LilyPond shortens staccato (x0.5) and staccatissimo
(x0.12) in MIDI, which makes a re-import write 16th + rest where the score says quarter-staccato.
Pass --playback to keep those (a nicer-sounding file, a worse re-import).  Chord symbols are left
out unless --with-chords: LilyPond renders them as a third track of block chords, which a notation
program turns into a spurious extra staff.

What MIDI cannot carry, and why score.ly stays the master: enharmonic spelling per note, voice
assignment inside a staff, tie vs re-strike, arpeggio/ornament marks, dynamics and pedal marks as
notation, chord-symbol text, lyrics, and the whole layout.  Regenerate this file after every edit
to score.ly; never edit it by hand.
"""

import argparse, json, pathlib, re, shutil, subprocess, tempfile

import mido

ARTIC = re.compile(r"(?:-|\^|_)(?:\.|!|>|_|\+|-)|\\(?:staccato|staccatissimo|accent|portato|tenuto|marcato)(?![A-Za-z])")


def prepare(src: pathlib.Path, dst: pathlib.Path, playback: bool, with_chords: bool) -> None:
    out = []
    for line in src.read_text().splitlines():
        if "#(" not in line:                      # never touch Scheme (number->string etc.)
            if not playback:
                line = ARTIC.sub("", line)
            if not with_chords:
                line = line.replace("\\new ChordNames", "% (final midi) \\new ChordNames")
        out.append(line)
    dst.write_text("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score_ly")
    ap.add_argument("out_mid")
    ap.add_argument("--playback", action="store_true", help="keep articulation shortening (better playback, worse re-import)")
    ap.add_argument("--with-chords", action="store_true", help="keep the chord-symbol track (becomes an extra staff on import)")
    ap.add_argument("--json", help="also write a summary next to the MIDI")
    a = ap.parse_args()
    src = pathlib.Path(a.score_ly).resolve()
    out = pathlib.Path(a.out_mid).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "final.ly"
        prepare(src, tmp, a.playback, a.with_chords)
        r = subprocess.run(["lilypond", "-dno-print-pages", "-dno-point-and-click", "-o", "final", "final.ly"],
                           cwd=td, capture_output=True, text=True)
        mid = pathlib.Path(td) / "final.midi"
        if not mid.exists():
            raise SystemExit(f"lilypond produced no MIDI (does score.ly have a \\midi block?)\n{r.stderr[-2000:]}")
        m = mido.MidiFile(str(mid), charset="utf-8")

    # name the note tracks by staff, drop the empty ones LilyPond leaves behind
    kept, names = [], []
    for tr in m.tracks:
        notes = sum(1 for msg in tr if msg.type == "note_on" and msg.velocity > 0)
        name = next((msg.name for msg in tr if msg.is_meta and msg.type == "track_name"), "")
        meta = any(msg.is_meta and msg.type in ("time_signature", "set_tempo", "key_signature") for msg in tr)
        if not notes and not meta:
            continue
        if notes:
            low = name.split(":")[0].strip().lower()
            pretty = {"up": "RH (upper staff)", "down": "LH (lower staff)"}.get(low) or (name or "Chord symbols")
            for msg in tr:
                if msg.is_meta and msg.type == "track_name":
                    msg.name = pretty
                    break
            else:
                tr.insert(0, mido.MetaMessage("track_name", name=pretty, time=0))
            names.append((pretty, notes))
        kept.append(tr)
    m.tracks = kept
    m.save(str(out))

    con = m.tracks[0]
    summary = {
        "source": str(src), "midi": str(out), "durations": "playback" if a.playback else "notated",
        "chord_track": bool(a.with_chords), "ppq": m.ticks_per_beat,
        "tracks": [{"name": n, "notes": c} for n, c in names],
        "time_signatures": [f"{msg.numerator}/{msg.denominator}" for msg in con if msg.is_meta and msg.type == "time_signature"],
        "key_signatures": sorted({msg.key for tr in m.tracks for msg in tr if msg.is_meta and msg.type == "key_signature"}),
        "tempo_bpm": [round(60_000_000 / msg.tempo, 2) for msg in con if msg.is_meta and msg.type == "set_tempo"],
        "duration_s": round(m.length, 2),
    }
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
