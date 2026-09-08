"""v2 of quantize_to_score.py, kept for comparison only. Do not use.

"""Turn a performance MIDI into an engraved-ready MusicXML (two-staff piano).

    python quantize_to_score.py in.mid out.musicxml --time-sig 4/4 --key "C major" \
        (--bpm 72 | --beats beats.json) [--anacrusis-beats 0] [--grid 16] [--triplets] \
        [--hands auto|tracks|pitch|function] [--split-pitch 60] [--dynamics] [--pedal] \
        [--no-legato-fill] [--no-voices] [--title T --composer C]

What v2 does that v1 did not (each was a cycle-1 finding):
  * accidentals: MIDI-derived pitches carried explicit naturals and sharps-in-flat-keys; now pitches
    are respelled for the key and display is left to makeAccidentals (only real accidentals print).
  * legato fill: a note whose quantized offset leaves a gap shorter than one grid unit before the
    next onset on its staff is extended to that onset (no confetti of 16th/32nd rests); minimum
    duration is one grid unit.
  * voices: notes that keep sounding while shorter notes move on the same staff are kept (not cut)
    and music21's makeVoices puts them in a second voice — held bass notes under a figure now look
    like the urtext instead of being truncated.
  * hands = function: within each beat window, long notes below the moving figure go to the lower
    staff even above middle C; simultaneous stacks wider than a tenth across the split are divided
    at the largest gap so no hand gets an unplayable chord.
  * both parts are padded to the same number of measures (MuseScore crashes otherwise).
  * pedal marks land in the right measure; dynamics use a 2-bar window with persistence.
  * compound metres get a dotted-quarter metronome mark; --bpm is always quarter-note BPM for the
    time map (for 12/8 give dotted-quarter × 1.5).
  * --triplets only uses the 1/3-quarter grid and never lets a tuplet cross the beat.
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
    layout,
    pitch as m21pitch,
)


def load_beats(path):
    d = json.load(open(path))
    return np.asarray(d["beats"], dtype=float)


def make_time_map(bpm=None, beats=None, first_onset=0.0):
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
    g = Fraction(1, grid // 4)
    c = Fraction(round(x / g)) * g
    if triplets:
        g3 = Fraction(1, 3)
        c3 = Fraction(round(x / g3)) * g3
        if abs(float(c3) - x) < abs(float(c) - x) - 1e-9 and c3.denominator == 3:
            return c3
    return c


def spell_for_key(midi_num, k):
    """Choose the enharmonic spelling that fits the key signature (flats in flat keys, etc.)."""
    p = m21pitch.Pitch(midi=midi_num)
    p.accidental = None if p.accidental is None else p.accidental
    if p.accidental is not None and p.accidental.alter == 0:
        p.accidental = None
    sharps = k.sharps
    if p.accidental is not None:
        if sharps < 0 and p.accidental.alter > 0:
            p = p.getEnharmonic()
        elif sharps > 0 and p.accidental.alter < 0:
            p = p.getEnharmonic()
    # notes that are in the key's scale as altered degrees keep their spelling
    for sp in k.pitches:
        if sp.pitchClass == p.pitchClass and sp.name != p.name:
            q = m21pitch.Pitch(sp.name)
            q.octave = (
                p.octave
                if abs(q.ps - p.ps) < 6
                else (p.octave + (1 if q.ps < p.ps - 6 else -1))
            )
            if int(round(q.ps)) == midi_num:
                p = q
            break
    return p


def split_hands(notes, mode, split_pitch, track_names):
    lh, rh = [], []
    named = {}
    for n, tn in zip(notes, track_names):
        tnl = (tn or "").lower()
        if any(k in tnl for k in ("left", "lower", "bass", "lh")):
            named[id(n)] = "L"
        elif any(k in tnl for k in ("right", "upper", "treble", "rh")):
            named[id(n)] = "R"
    tracks = sorted({tn for tn in track_names})
    if mode in ("tracks", "auto") and named:
        for n in notes:
            (
                lh
                if named.get(id(n), "R" if n.pitch >= split_pitch else "L") == "L"
                else rh
            ).append(n)
        return lh, rh, "tracks:names"
    if mode in ("tracks", "auto") and len(tracks) == 2:
        means = {}
        for n, tn in zip(notes, track_names):
            means.setdefault(tn, []).append(n.pitch)
        low = min(tracks, key=lambda t: np.mean(means[t]))
        for n, tn in zip(notes, track_names):
            (lh if tn == low else rh).append(n)
        return lh, rh, "tracks:two"
    if mode == "tracks":
        mode = "function"
    starts = np.array([n.start for n in notes])
    ends = np.array([n.end for n in notes])
    pitches = np.array([n.pitch for n in notes])
    durs = ends - starts
    assign = []
    for i, n in enumerate(notes):
        m = (starts >= n.start - 0.6) & (starts <= n.start + 0.6)
        win_p = pitches[m]
        win_d = durs[m]
        pivot = split_pitch
        if (
            len(win_p) >= 4
            and win_p.max() - win_p.min() >= 12
            and win_p.min() < split_pitch <= win_p.max()
        ):
            srt = np.sort(win_p)
            gaps = np.diff(srt)
            # largest gap in the middle region decides the split when both sides are playable
            j = int(np.argmax(gaps + 1e-3 * (srt[:-1] < split_pitch)))
            cand = (srt[j] + srt[j + 1]) / 2.0
            if srt[j + 1] - srt[0] <= 19 and srt[-1] - srt[j + 1] <= 19:
                pivot = cand
        side = "R" if n.pitch >= pivot else "L"
        if mode in ("function", "auto") and len(win_p) >= 3:
            med_d = float(np.median(win_d))
            moving = win_d <= med_d
            if (
                side == "R"
                and durs[i] >= 2.0 * med_d
                and n.pitch <= float(np.median(win_p[moving])) - 1
                and n.pitch < split_pitch + 12
            ):
                side = "L"  # a held note under the moving figure belongs to the lower staff
            if (
                side == "L"
                and durs[i] <= med_d
                and n.pitch >= split_pitch + 5
                and pitches[m].min() < n.pitch - 12
            ):
                side = (
                    "R"  # a short high note over a low bass belongs to the upper staff
                )
            held = win_d >= 2.0 * med_d
            if held.any():
                held_p = win_p[held]
                if (
                    side == "R"
                    and durs[i] <= med_d
                    and n.pitch < held_p.min()
                    and n.pitch <= held_p.max() - 3
                    and n.pitch < split_pitch + 12
                ):
                    side = "L"  # accompaniment below a sustained melody note -> lower staff
        assign.append(side)
    for n, s in zip(notes, assign):
        (lh if s == "L" else rh).append(n)
    return lh, rh, mode


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


def build_events(notes, tmap, args, bar_ql):
    unit = Fraction(1, args.grid // 4)
    ev = []
    for n in notes:
        on = snap(tmap(n.start) - args.anacrusis_beats, args.grid, args.triplets)
        off = snap(tmap(n.end) - args.anacrusis_beats, args.grid, False)
        if on.denominator == 3:  # tuplet notes stay inside their beat
            beat_end = Fraction(math.floor(on) + 1)
            off = min(max(off, on + Fraction(1, 3)), beat_end)
        if off <= on:
            off = on + unit
        ev.append([on, off, n.pitch, n.velocity])
    ev.sort(key=lambda e: (e[0], e[2]))
    onsets = sorted({e[0] for e in ev})
    nxt = {
        o: (onsets[i + 1] if i + 1 < len(onsets) else None)
        for i, o in enumerate(onsets)
    }
    for e in ev:
        n2 = nxt[e[0]]
        if n2 is None:
            continue
        gap = n2 - e[1]
        if not args.no_legato_fill and 0 < gap <= unit:
            e[1] = n2  # close confetti rests
        if e[1] > n2:
            if args.no_voices or (e[1] - e[0]) < 2 * (n2 - e[0]):
                e[1] = n2  # short overlap: legato clean-up
            # else keep: a genuinely held note -> second voice
    if not args.no_voices:
        held = [e for e in ev if any(o[0] > e[0] and o[0] < e[1] for o in ev if o is not e)]
        held.sort(key=lambda e: e[0])
        for i, e in enumerate(held):
            nxt_held = next((h[0] for h in held[i + 1:] if h[0] > e[0]), None)
            q = Fraction(1, 2)                                  # long notes end on an eighth grid
            rounded = Fraction(round(e[1] / q)) * q
            if nxt_held is not None and nxt_held - e[1] <= Fraction(1) and nxt_held > e[0]:
                e[1] = nxt_held
            elif rounded > e[0]:
                e[1] = rounded
    return ev


def build_part(notes, tmap, args, staff_name, is_lower, k, ts, n_measures_hint=None):
    bar_ql = ts.barDuration.quarterLength
    ev = build_events(notes, tmap, args, bar_ql)
    part = stream.Part()
    part.insert(0, instrument.Piano())
    part.insert(0, clef.BassClef() if is_lower else clef.TrebleClef())
    part.insert(0, meter.TimeSignature(args.time_sig))
    part.insert(0, k)
    if args.bpm and not is_lower:
        num, den = [int(x) for x in args.time_sig.split("/")]
        if den == 8 and num % 3 == 0:
            part.insert(
                0,
                tempo.MetronomeMark(
                    number=round(args.bpm * 2 / 3), referent=1.5
                ),
            )
        else:
            part.insert(0, tempo.MetronomeMark(number=round(args.bpm)))
    by_onset = {}
    for on, off, p, v in ev:
        by_onset.setdefault(on, []).append((off, p, v))
    for on in sorted(by_onset):
        grp = by_onset[on]
        # split a simultaneous group by offset so held + short notes become separate elements (voices)
        by_off = {}
        if args.no_voices:
            mx = max(o for o, _, _ in grp)
            by_off[mx] = [(p, v) for _, p, v in grp]
        else:
            for off, p, v in grp:
                by_off.setdefault(off, []).append((p, v))
        for off, pv in by_off.items():
            pitches = sorted({p for p, _ in pv})
            vel = max(v for _, v in pv)
            spelled = [m21pitch.Pitch(midi=p) for p in pitches] if args.no_respell else [spell_for_key(p, k) for p in pitches]
            el = note.Note(spelled[0]) if len(spelled) == 1 else chord.Chord(spelled)
            el.quarterLength = float(off - on)
            el.volume.velocity = vel
            part.insert(float(on), el)
    part.makeMeasures(inPlace=True)
    part.makeTies(inPlace=True)
    if not args.no_voices:
        fails = 0
        for m in part.getElementsByClass("Measure"):
            try:
                m.makeVoices(inPlace=True)
            except Exception as e:
                fails += 1
        if fails:
            import sys
            print(f"makeVoices failed in {fails} measures of {staff_name}", file=sys.stderr)
    part.makeRests(fillGaps=True, inPlace=True, timeRangeFromBarDuration=True)
    try:
        part.makeAccidentals(
            inPlace=True, cautionaryPitchClass=True, overrideStatus=True
        )
    except Exception:
        pass
    part.partName = staff_name
    return part, ev


def add_dynamics(part, ev, bar_ql):
    """One dynamic per 2-bar window when the window's mean velocity changes band."""
    if not ev:
        return
    last = None
    n_bars = int(max(e[1] for e in ev) // bar_ql) + 1
    for b in range(0, n_bars, 2):
        lo, hi = b * bar_ql, (b + 2) * bar_ql
        vel = [e[3] for e in ev if lo <= e[0] < hi]
        if not vel:
            continue
        dyn = velocity_to_dynamic(float(np.mean(vel)))
        if dyn != last:
            m = part.measure(b + 1)
            if m is not None:
                m.insert(0.0, dynamics.Dynamic(dyn))
            last = dyn


def pad_parts(parts, ts):
    n = max(len(p.getElementsByClass("Measure")) for p in parts)
    for p in parts:
        ms = list(p.getElementsByClass("Measure"))
        while len(ms) < n:
            m = stream.Measure(number=len(ms) + 1)
            r = note.Rest()
            r.quarterLength = ts.barDuration.quarterLength
            m.append(r)
            p.append(m)
            ms.append(m)


def add_pedal(score, pm, tmap, args, bar_ql):
    cc = sorted(
        [c for i in pm.instruments for c in i.control_changes if c.number == 64],
        key=lambda c: c.time,
    )
    lower = score.parts[-1]
    measures = list(lower.getElementsByClass("Measure"))
    state = False
    last_pos = -10.0
    n_marks = 0
    events = []
    for c in cc:
        down = c.value >= 64
        if down == state:
            continue
        state = down
        pos = float(snap(tmap(c.time) - args.anacrusis_beats, 8, False))   # pedal on an eighth grid
        events.append([pos, down])
    # collapse: a release followed by a press within half a beat is a re-pedal -> keep the press only
    cleaned = []
    for i, (pos, down) in enumerate(events):
        if not down and i + 1 < len(events) and events[i + 1][1] and events[i + 1][0] - pos <= 0.5:
            continue
        if down and cleaned and cleaned[-1][1] and pos - cleaned[-1][0] < 1.0:
            continue
        if cleaned and cleaned[-1][1] == down:
            continue
        cleaned.append([pos, down])
    for pos, down in cleaned:
        if pos < 0:
            continue
        mi = int(pos // bar_ql)
        if 0 <= mi < len(measures):
            te = expressions.TextExpression("Ped." if down else "*")
            te.placement = "below"
            measures[mi].insert(pos - mi * bar_ql, te)
            n_marks += 1
    return n_marks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi")
    ap.add_argument("out")
    ap.add_argument("--time-sig", default="4/4")
    ap.add_argument("--key", default="C major")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--beats")
    ap.add_argument("--anacrusis-beats", type=float, default=0.0)
    ap.add_argument("--grid", type=int, default=16)
    ap.add_argument("--triplets", action="store_true")
    ap.add_argument(
        "--hands", default="auto", choices=["auto", "tracks", "pitch", "function"]
    )
    ap.add_argument("--split-pitch", type=int, default=60)
    ap.add_argument("--dynamics", action="store_true")
    ap.add_argument("--pedal", action="store_true")
    ap.add_argument("--no-legato-fill", action="store_true")
    ap.add_argument("--no-voices", action="store_true")
    ap.add_argument(
        "--keep-overlaps",
        action="store_true",
        help="(v1 compat) same as default voices behaviour",
    )
    ap.add_argument("--title", default="")
    ap.add_argument("--composer", default="")
    ap.add_argument("--start-at-first-onset", action="store_true")
    ap.add_argument("--no-respell", action="store_true")
    ap.add_argument("--no-accidentals", action="store_true")
    ap.add_argument("--no-pad", action="store_true")
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
    ks = args.key.split()
    k = key.Key(ks[0], ks[1] if len(ks) > 1 else "major")
    ts = meter.TimeSignature(args.time_sig)
    bar_ql = ts.barDuration.quarterLength
    lh, rh, hand_mode = split_hands(notes, args.hands, args.split_pitch, tnames)
    sc = stream.Score()
    sc.insert(
        0, metadata.Metadata(title=args.title or None, composer=args.composer or None)
    )
    rp, rev = build_part(rh, tmap, args, "Right hand", False, k, ts)
    lp, lev = build_part(lh, tmap, args, "Left hand", True, k, ts)
    if not args.no_pad:
        pad_parts([rp, lp], ts)
    if args.dynamics:
        add_dynamics(rp, rev, bar_ql)
    sc.insert(0, rp)
    sc.insert(0, lp)
    sc.insert(
        0,
        layout.StaffGroup([rp, lp], name="Piano", abbreviation="Pno.", symbol="brace"),
    )
    n_ped = add_pedal(sc, pm, tmap, args, bar_ql) if args.pedal else 0
    sc.write("musicxml", fp=args.out)
    print(
        json.dumps(
            {
                "out": args.out,
                "rh_notes": len(rh),
                "lh_notes": len(lh),
                "hands": hand_mode,
                "measures": len(rp.getElementsByClass("Measure")),
                "time_sig": args.time_sig,
                "key": args.key,
                "bpm": args.bpm,
                "beats": bool(args.beats),
                "grid": args.grid,
                "triplets": args.triplets,
                "pedal_marks": n_ped,
                "legato_fill": not args.no_legato_fill,
                "voices": not args.no_voices,
            }
        )
    )


if __name__ == "__main__":
    main()
