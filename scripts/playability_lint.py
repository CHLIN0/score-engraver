"""Is the score playable by two human hands as written?  Objective checks per staff, from the
score's own MIDI (LilyPond writes one track per Staff, so hand = track).

    python playability_lint.py compare.midi [--json out.json] [--span 14] [--leap 19]

Per staff (upper = right hand, lower = left hand):
  span   : a simultaneous cluster wider than --span semitones (default 14 = a major 9th; a 10th is
           the practical limit for most hands, an 11th+ needs rolling or the other hand)
  reach  : a note sounds (held) while the same staff plays a note farther than --span from it —
           the hand must hold one key and reach another; if the reach exceeds a 10th it cannot be done
           without pedal, and a tie into such a reach is the classic "give it to the other hand" case
  leap   : consecutive attacks in one staff more than --leap semitones apart within 0.15 s (fast leaps
           over an octave and a half are a hand-assignment smell in the left hand)
  cross  : the lower staff's top note above the upper staff's bottom note at the same time (hands
           crossing) — sometimes intended, always worth a look
Bars come from the MIDI's own time signature. Numbers, not verdicts: the engraver decides whether a
note moves to the other hand, is rolled, is tied differently, or stays.
"""

import argparse, json
from collections import defaultdict
import pretty_midi


def bar_of(pm, t, bar_beats=None):
    """Bar number at time t, honouring every time-signature change in the file."""
    tick = pm.time_to_tick(t)
    changes = sorted(pm.time_signature_changes, key=lambda c: c.time) or []
    if not changes:
        return int(tick / pm.resolution // (bar_beats or 4)) + 1
    bar, prev_tick, prev_beats = 1, 0, changes[0].numerator * 4.0 / changes[0].denominator
    for c in changes[1:]:
        ct = pm.time_to_tick(c.time)
        if ct > tick:
            break
        bar += int((ct - prev_tick) / pm.resolution // prev_beats)
        prev_tick, prev_beats = ct, c.numerator * 4.0 / c.denominator
    return bar + int((tick - prev_tick) / pm.resolution // prev_beats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score_midi")
    ap.add_argument("--json")
    ap.add_argument("--span", type=int, default=14)
    ap.add_argument("--leap", type=int, default=19)
    a = ap.parse_args()
    pm = pretty_midi.PrettyMIDI(a.score_midi)
    ts = pm.time_signature_changes
    num, den = (ts[0].numerator, ts[0].denominator) if ts else (4, 4)
    bar_beats = num * 4.0 / den
    tracks = [i for i in pm.instruments if not i.is_drum and i.notes and "chord" not in (i.name or "").lower()]
    if not tracks:
        raise SystemExit("no notes")
    # upper/lower by mean pitch
    tracks.sort(key=lambda i: -sum(n.pitch for n in i.notes) / len(i.notes))
    names = ["upper (RH)", "lower (LH)"] + [
        f"track {k}" for k in range(3, len(tracks) + 1)
    ]
    findings = []
    per_bar = defaultdict(int)
    for name, tr in zip(names, tracks):
        notes = sorted(tr.notes, key=lambda n: (n.start, n.pitch))
        # clusters
        clusters, cur, t0 = [], [], None
        for n in notes:
            if t0 is None or n.start - t0 <= 0.02:
                cur.append(n)
                t0 = n.start if t0 is None else t0
            else:
                clusters.append((t0, cur))
                cur, t0 = [n], n.start
        if cur:
            clusters.append((t0, cur))
        for t, cl in clusters:
            ps = [n.pitch for n in cl]
            if max(ps) - min(ps) > a.span:
                findings.append(
                    {
                        "kind": "span",
                        "staff": name,
                        "bar": bar_of(pm, t, bar_beats),
                        "t": round(t, 2),
                        "semitones": max(ps) - min(ps),
                        "pitches": sorted(ps),
                    }
                )
        # reach: held note vs new attack in the same staff
        for n in notes:
            for m in notes:
                if (
                    m.start > n.start + 0.02
                    and m.start < n.end - 0.02
                    and abs(m.pitch - n.pitch) > a.span
                ):
                    findings.append(
                        {
                            "kind": "reach",
                            "staff": name,
                            "bar": bar_of(pm, m.start, bar_beats),
                            "t": round(m.start, 2),
                            "held": n.pitch,
                            "attack": m.pitch,
                            "semitones": abs(m.pitch - n.pitch),
                        }
                    )
                    break
        # leaps
        for (t1, c1), (t2, c2) in zip(clusters, clusters[1:]):
            if t2 - t1 <= 0.15:
                lo1, hi1 = min(n.pitch for n in c1), max(n.pitch for n in c1)
                lo2, hi2 = min(n.pitch for n in c2), max(n.pitch for n in c2)
                d = max(abs(lo2 - lo1), abs(hi2 - hi1))
                if d > a.leap:
                    findings.append(
                        {
                            "kind": "leap",
                            "staff": name,
                            "bar": bar_of(pm, t2, bar_beats),
                            "t": round(t2, 2),
                            "semitones": d,
                        }
                    )
    # crossing between the two staves
    if len(tracks) >= 2:
        up, lo = tracks[0].notes, tracks[1].notes
        for n in lo:
            for m in up:
                if m.start < n.end and n.start < m.end and n.pitch > m.pitch + 2:
                    findings.append(
                        {
                            "kind": "cross",
                            "bar": bar_of(pm, n.start, bar_beats),
                            "t": round(n.start, 2),
                            "lower_note": n.pitch,
                            "upper_note": m.pitch,
                        }
                    )
                    break
    seen, uniq = set(), []
    for f in findings:
        k = (f["kind"], f.get("staff"), f["bar"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
            per_bar[f["bar"]] += 1
    rep = {
        "findings": uniq,
        "by_kind": {
            k: sum(1 for f in uniq if f["kind"] == k)
            for k in ("span", "reach", "leap", "cross")
        },
        "worst_bars": sorted(per_bar.items(), key=lambda x: -x[1])[:10],
        "span_limit": a.span,
        "leap_limit": a.leap,
    }
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=1)
    print(
        json.dumps(
            {
                "by_kind": rep["by_kind"],
                "worst_bars": rep["worst_bars"][:8],
                "examples": [
                    {k: v for k, v in f.items() if k != "t"} for f in uniq[:6]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
