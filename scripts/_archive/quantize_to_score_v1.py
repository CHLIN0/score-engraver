"""v1 of quantize_to_score.py, kept for comparison only (no voices, no legato fill, explicit naturals). Do not use.

"""Turn a performance MIDI into an engraved-ready MusicXML (two-staff piano).

    python quantize_to_score.py in.mid out.musicxml --time-sig 4/4 --key "C major" \
        (--bpm 72 | --beats beats.json) [--anacrusis-beats 0] [--grid 16] [--triplets] \
        [--hands tracks|pitch|auto] [--split-pitch 60] [--dynamics] [--pedal] [--title T --composer C]

Time mapping: with --bpm a constant tempo (good for score-derived or steady MIDI); with --beats a
piecewise-linear map through tracked beat times (rubato). --anacrusis-beats shifts the barline so
that beat index `anacrusis` is the first downbeat. Every onset/offset is snapped to the nearest
1/grid-of-a-quarter position (default 16th); with --triplets each beat is also tried on a triplet
grid and the better fit wins. Notes that overlap the next onset on the same staff are truncated
(simple legato clean-up) so voices do not tangle; use --keep-overlaps to disable.
Hands: 'tracks' uses MIDI track names (falling:hands:left/right, Left/Right), 'pitch' splits at
--split-pitch, 'auto' uses tracks if present else a windowed pitch split.
Then music21 builds measures, ties, rests, clefs, key/time signatures, dynamics (from velocity,
per 2-bar window) and pedal marks (from CC64) and writes MusicXML for MuseScore to engrave.
"""

import argparse, json, math
from fractions import Fraction
import numpy as np
import pretty_midi
from music21 import (
    stream,
    note,
    chord,
    meter,
    key,
    tempo,
    clef,
    instrument,
    metadata,
    dynamics,
    expressions,
    duration,
    layout,
    tie,
    spanner,
)


def load_beats(path):
    d = json.load(open(path))
    return np.asarray(d["beats"], dtype=float)


def make_time_map(bpm=None, beats=None, first_onset=0.0):
    """Return f(seconds)->beats (float, in quarter notes)."""
    if beats is not None and len(beats) > 2:
        b = np.asarray(beats)
        idx = np.arange(len(b), dtype=float)

        def f(t):
            if t <= b[0]:
                return float((t - b[0]) / (b[1] - b[0]))
            if t >= b[-1]:
                return float(len(b) - 1 + (t - b[-1]) / (b[-1] - b[-2]))
            return float(np.interp(t, b, idx))

        return f
    qps = bpm / 60.0
    return lambda t: (t - first_onset) * qps


def snap(x, grid, triplets):
    """Snap a beat position to the nearest grid; returns Fraction in quarter notes."""
    g = Fraction(1, grid // 4)  # grid=16 -> 1/4 quarter
    cand = [Fraction(round(x / g)) * g]
    if triplets:
        g3 = Fraction(1, 3)
        cand.append(Fraction(round(x / g3)) * g3)
        g6 = Fraction(1, 6)
        cand.append(Fraction(round(x / g6)) * g6)
    return min(cand, key=lambda c: (abs(float(c) - x), c.denominator))


def split_hands(notes, mode, split_pitch, track_names):
    """Return (lh, rh). 'tracks': by track name (left/right/lower/upper/bass/treble) or, with exactly two
    note-bearing tracks, by track (lower mean pitch = left hand). 'pitch': fixed split. 'auto': tracks if
    they carry hand information, else a windowed pitch split around split_pitch."""
    lh, rh = [], []
    named = {}
    for n, tn in zip(notes, track_names):
        tnl = (tn or "").lower()
        if any(k in tnl for k in ("left", "lower", "bass", "lh")):
            named[id(n)] = "L"
        elif any(k in tnl for k in ("right", "upper", "treble", "rh")):
            named[id(n)] = "R"
    tracks = sorted({tn for tn in track_names})
    two_tracks = len(tracks) == 2
    if mode in ("tracks", "auto") and named:
        for n in notes:
            (lh if named.get(id(n), "R" if n.pitch >= split_pitch else "L") == "L" else rh).append(n)
        return lh, rh
    if mode in ("tracks", "auto") and two_tracks:
        means = {}
        for n, tn in zip(notes, track_names):
            means.setdefault(tn, []).append(n.pitch)
        low = min(tracks, key=lambda t: np.mean(means[t]))
        for n, tn in zip(notes, track_names):
            (lh if tn == low else rh).append(n)
        return lh, rh
    starts = np.array([n.start for n in notes])
    pitches = np.array([n.pitch for n in notes])
    for n in notes:
        m = (starts >= n.start - 0.5) & (starts <= n.start + 0.5)
        win = pitches[m]
        if len(win) >= 4 and win.max() - win.min() >= 12 and win.min() < split_pitch <= win.max():
            pivot = np.median(win)
        else:
            pivot = split_pitch
        (rh if n.pitch >= pivot else lh).append(n)
    return lh, rh


def velocity_to_dynamic(v):
    for thr, name in (
        (32, "pp"),
        (48, "p"),
        (64, "mp"),
        (80, "mf"),
        (96, "f"),
        (112, "ff"),
    ):
        if v < thr:
            return name
    return "fff"


def build_part(notes, tmap, args, staff_name, is_lower):
    events = []
    for n in notes:
        on = snap(tmap(n.start) - args.anacrusis_beats, args.grid, args.triplets)
        off = snap(tmap(n.end) - args.anacrusis_beats, args.grid, args.triplets)
        if off <= on:
            off = on + Fraction(1, args.grid // 4)
        events.append([on, off, n.pitch, n.velocity])
    events.sort(key=lambda e: (e[0], e[2]))
    if not args.keep_overlaps:
        # truncate a note at the next distinct onset on this staff (legato clean-up), keep chords intact
        onsets = sorted({e[0] for e in events})
        nxt = {
            o: (onsets[i + 1] if i + 1 < len(onsets) else None)
            for i, o in enumerate(onsets)
        }
        for e in events:
            n2 = nxt[e[0]]
            if n2 is not None and e[1] > n2:
                e[1] = n2
    part = stream.Part()
    part.insert(0, instrument.Piano())
    part.insert(0, clef.BassClef() if is_lower else clef.TrebleClef())
    ts = meter.TimeSignature(args.time_sig)
    part.insert(0, ts)
    part.insert(
        0,
        key.Key(
            args.key.split()[0],
            args.key.split()[1] if len(args.key.split()) > 1 else "major",
        ),
    )
    if args.bpm and not is_lower:
        part.insert(0, tempo.MetronomeMark(number=round(args.bpm)))
    # group simultaneous onsets into chords
    by_onset = {}
    for on, off, p, v in events:
        by_onset.setdefault(on, []).append((off, p, v))
    last_dyn = None
    for on in sorted(by_onset):
        grp = by_onset[on]
        off = max(o for o, _, _ in grp)
        ql = float(off - on)
        pitches = sorted({p for _, p, _ in grp})
        vel = max(v for _, _, v in grp)
        if len(pitches) == 1:
            el = note.Note(pitches[0])
        else:
            el = chord.Chord(pitches)
        el.quarterLength = ql
        el.volume.velocity = vel
        part.insert(float(on), el)
        if args.dynamics and not is_lower:
            dyn = velocity_to_dynamic(vel)
            bar = int(float(on) // ts.barDuration.quarterLength)
            if dyn != last_dyn and (last_dyn is None or bar % 2 == 0):
                part.insert(float(on), dynamics.Dynamic(dyn))
                last_dyn = dyn
    part.makeMeasures(inPlace=True)
    part.makeTies(inPlace=True)
    part.makeRests(fillGaps=True, inPlace=True, timeRangeFromBarDuration=True)
    part.partName = staff_name
    return part


def add_pedal(score, pm, tmap, args):
    """Pedal marks as text directions (Ped. / *) at CC64 transitions; MuseScore renders them as text."""
    cc = sorted(
        [c for i in pm.instruments for c in i.control_changes if c.number == 64],
        key=lambda c: c.time,
    )
    lower = score.parts[-1]
    state = False
    for c in cc:
        down = c.value >= 64
        if down == state:
            continue
        state = down
        pos = float(snap(tmap(c.time) - args.anacrusis_beats, args.grid, False))
        te = expressions.TextExpression("Ped." if down else "*")
        te.placement = "below"
        try:
            lower.insert(pos, te)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi")
    ap.add_argument("out")
    ap.add_argument("--time-sig", default="4/4")
    ap.add_argument("--key", default="C major")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--beats")
    ap.add_argument(
        "--anacrusis-beats",
        type=float,
        default=0.0,
        help="beats (quarters) before the first downbeat, in mapped beat units",
    )
    ap.add_argument(
        "--grid",
        type=int,
        default=16,
        help="smallest note value as a fraction of a whole note: 8, 16, 32",
    )
    ap.add_argument("--triplets", action="store_true")
    ap.add_argument("--hands", default="auto", choices=["auto", "tracks", "pitch"])
    ap.add_argument("--split-pitch", type=int, default=60)
    ap.add_argument("--dynamics", action="store_true")
    ap.add_argument("--pedal", action="store_true")
    ap.add_argument("--keep-overlaps", action="store_true")
    ap.add_argument("--title", default="")
    ap.add_argument("--composer", default="")
    ap.add_argument(
        "--start-at-first-onset",
        action="store_true",
        help="with --bpm: treat the first onset as beat 0",
    )
    args = ap.parse_args()
    if not args.bpm and not args.beats:
        ap.error("give --bpm or --beats")
    pm = pretty_midi.PrettyMIDI(args.midi)
    insts = [i for i in pm.instruments if not i.is_drum]
    notes, tnames = [], []
    for i in insts:
        for n in i.notes:
            notes.append(n)
            tnames.append(i.name)
    order = sorted(range(len(notes)), key=lambda k: (notes[k].start, notes[k].pitch))
    notes = [notes[k] for k in order]
    tnames = [tnames[k] for k in order]
    first = notes[0].start if args.start_at_first_onset else 0.0
    tmap = make_time_map(
        args.bpm, load_beats(args.beats) if args.beats else None, first
    )
    lh, rh = split_hands(notes, args.hands, args.split_pitch, tnames)
    sc = stream.Score()
    sc.insert(
        0, metadata.Metadata(title=args.title or None, composer=args.composer or None)
    )
    sc.insert(0, build_part(rh, tmap, args, "Right hand", False))
    sc.insert(0, build_part(lh, tmap, args, "Left hand", True))
    sc.insert(
        0,
        layout.StaffGroup(
            list(sc.parts), name="Piano", abbreviation="Pno.", symbol="brace"
        ),
    )
    if args.pedal:
        add_pedal(sc, pm, tmap, args)
    sc.write("musicxml", fp=args.out)
    print(
        json.dumps(
            {
                "out": args.out,
                "rh_notes": len(rh),
                "lh_notes": len(lh),
                "measures": len(sc.parts[0].getElementsByClass("Measure")),
                "time_sig": args.time_sig,
                "key": args.key,
                "bpm": args.bpm,
                "beats": bool(args.beats),
                "grid": args.grid,
                "triplets": args.triplets,
            }
        )
    )


if __name__ == "__main__":
    main()
