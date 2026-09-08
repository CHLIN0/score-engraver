"""Do the engraved verticals exist in the performance?  A one-command guard against the two staves
drifting apart (one hand written an eighth late), octave errors from \\ottava, and invented chords.

    python verticals_lint.py compare.midi perf.mid [--window 0.09] [--json out.json]

compare.midi = your score's MIDI (from score_midi_for_compare.sh; articulations stripped).
For every onset cluster in the score (notes starting within 20 ms), the same pitches must start
within --window seconds of each other somewhere in the performance (pitch-exact; octave errors fail).
Reports the pass ratio overall and per bar (bars from the score MIDI's own time signature), lists the
bars with the most failures, and flags octave-shifted clusters separately (they pass at ±12 semitones).
"""

import argparse, json
from collections import defaultdict
import pretty_midi


def clusters(pm, tol=0.02):
    notes = sorted(
        (n.start, n.pitch) for i in pm.instruments if not i.is_drum for n in i.notes
    )
    out, cur, t0 = [], [], None
    for t, p in notes:
        if t0 is None or t - t0 <= tol:
            cur.append(p)
            t0 = t if t0 is None else t0
        else:
            out.append((t0, sorted(set(cur))))
            cur, t0 = [p], t
    if cur:
        out.append((t0, sorted(set(cur))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score_midi")
    ap.add_argument("perf_midi")
    ap.add_argument("--window", type=float, default=0.09)
    ap.add_argument("--beats", help="beats.json of the performance (exact bar mapping for the attack-count check)")
    ap.add_argument("--anacrusis-beats", type=float, default=0.0)
    ap.add_argument("--json")
    a = ap.parse_args()
    sc = pretty_midi.PrettyMIDI(a.score_midi)
    pf = pretty_midi.PrettyMIDI(a.perf_midi)
    perf = [
        (n.start, n.pitch) for i in pf.instruments if not i.is_drum for n in i.notes
    ]
    perf.sort()
    by_pitch = defaultdict(list)
    for t, p in perf:
        by_pitch[p].append(t)
    ts = sc.time_signature_changes
    num, den = (ts[0].numerator, ts[0].denominator) if ts else (4, 4)
    bar_beats = num * 4.0 / den
    total, ok, oct_ok = 0, 0, 0
    per_bar = defaultdict(lambda: [0, 0])
    failures = []
    for t, pitches in clusters(sc):
        if len(pitches) < 2:
            continue
        total += 1
        beat = sc.time_to_tick(t) / sc.resolution
        bar = int(beat // bar_beats) + 1
        per_bar[bar][1] += 1

        def found(ps):
            # some performance time where all these pitches start within the window
            cand = [t0 for t0 in by_pitch.get(ps[0], [])]
            for t0 in cand:
                if all(
                    any(abs(t1 - t0) <= a.window for t1 in by_pitch.get(p, []))
                    for p in ps[1:]
                ):
                    return True
            return False

        if found(pitches):
            ok += 1
            per_bar[bar][0] += 1
        elif found([p + 12 for p in pitches]) or found([p - 12 for p in pitches]):
            oct_ok += 1
            failures.append(
                {
                    "bar": bar,
                    "t": round(t, 2),
                    "pitches": pitches,
                    "why": "found an octave away — \\ottava or octave error",
                }
            )
        else:
            failures.append(
                {
                    "bar": bar,
                    "t": round(t, 2),
                    "pitches": pitches,
                    "why": "not co-sounding in the performance",
                }
            )
    worst = sorted(
        ((b, v[1] - v[0], v[1]) for b, v in per_bar.items() if v[1] - v[0] > 0),
        key=lambda x: -x[1],
    )[:12]
    # attacks per bar: a tie written as a re-strike (or vice versa) is invisible to cluster matching;
    # compare attack counts per bar, mapping performance time onto score bars proportionally
    sc_on = defaultdict(int)
    for t_, ps_ in clusters(sc):
        sc_on[int(sc.time_to_tick(t_) / sc.resolution // bar_beats) + 1] += len(ps_)
    perf_clusters = clusters(pf)
    pf_on = defaultdict(int)
    n_bars = max(sc_on) if sc_on else 0
    if n_bars and perf_clusters:
        beats = None
        if a.beats:
            import bisect
            bj = json.load(open(a.beats))
            beats = [float(x) for x in (bj["beats"] if isinstance(bj, dict) else bj)]
        t_end = max(t_ for t_, _ in perf_clusters) + 0.01
        for t_, ps_ in perf_clusters:
            if beats:
                i = bisect.bisect_right(beats, t_) - 1
                if i < 0:
                    continue
                frac = (t_ - beats[i]) / max(1e-6, (beats[i + 1] - beats[i]) if i + 1 < len(beats) else (beats[i] - beats[i - 1]))
                beat_pos = i + frac - a.anacrusis_beats
                bar = int(beat_pos // bar_beats) + 1
            else:
                bar = int(t_ / t_end * n_bars) + 1
            pf_on[bar] += len(ps_)
    attack_diff = sorted(((b, sc_on[b], pf_on.get(b, 0)) for b in sc_on if sc_on[b] > pf_on.get(b, 0) + 3),
                         key=lambda x: -(x[1] - x[2]))[:10]
    rep = {
        "clusters": total,
        "pass": ok,
        "pass_ratio": round(ok / total, 3) if total else None,
        "octave_shifted": oct_ok,
        "worst_bars": [{"bar": b, "failed": f, "of": n} for b, f, n in worst],
        "failures": failures[:200], "attacks_score_vs_perf_suspect": [{"bar": b, "score_attacks": x, "perf_attacks_approx": y} for b, x, y in attack_diff],
        "window_s": a.window,
        "bar_beats": bar_beats,
    }
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=1)
    print(json.dumps({k: rep[k] for k in ("clusters", "pass", "pass_ratio", "octave_shifted", "worst_bars", "attacks_score_vs_perf_suspect")}))



if __name__ == "__main__":
    main()
