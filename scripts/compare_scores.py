"""Compare an engraved score against a ground-truth score, symbolically.

    python compare_scores.py gt.musicxml out.musicxml [--json r.json] [--max-shift 2] [--tol 0.125]

Both scores are flattened to events (absolute beat position in quarter notes, pitch, duration, staff).
The measure structure is compared (count, time/key signatures); the event lists are aligned with a
constant beat shift searched over ±max_shift measures (to absorb anacrusis mistakes); then:
  onset_f1   — pitch equal and |beat difference| <= tol (default 1/8 quarter = 32nd)
  dur_agree  — among onset matches, fraction whose quarterLength matches within tol (ties merged)
  staff_agree— among onset matches, fraction on the same staff (upper/lower)
  measure_ok — measure counts equal (after shift) and time signature equal
plus the first 40 mismatches (missing / extra / wrong staff / wrong duration) with measure numbers,
so the critique can point at bars. Score-derived MIDI-to-MusicXML from MuseScore is fine as GT.
"""

import argparse, json
from collections import defaultdict
import numpy as np
from music21 import converter, chord


def flatten(path):
    """Events (beat, pitch, quarterLength, staff) with staff = 'upper'/'lower' decided by mean pitch
    when there are two staves (part order in MusicXML is not reliable), else 'upper'."""
    sc = converter.parse(path)
    parts = list(sc.parts)
    per_part = []
    for p in parts:
        flat = p.flatten()
        try:
            flat = p.stripTies().flatten()
        except Exception:
            pass
        evs = []
        for el in flat.notes:
            ps = [n.pitch.midi for n in el.notes] if isinstance(el, chord.Chord) else [el.pitch.midi]
            for pp in ps:
                evs.append((float(el.offset), pp, float(el.quarterLength)))
        per_part.append(evs)
    means = [sum(e[1] for e in evs) / max(1, len(evs)) if evs else None for evs in per_part]
    valid = [m for m in means if m is not None]
    if len(valid) >= 2:
        med = float(np.median(valid))
        labels = ["upper" if (m is not None and m >= med) else "lower" for m in means]
        if all(l == "upper" for l in labels):   # two parts with equal mean: lower index = upper
            labels[-1] = "lower"
    else:
        labels = ["upper"] * len(per_part)
    events = [(b, p, d, lab) for evs, lab in zip(per_part, labels) for (b, p, d) in evs]
    ts = sc.recurse().getElementsByClass("TimeSignature")
    ks = sc.recurse().getElementsByClass("KeySignature")
    n_meas = max((len(list(p.getElementsByClass("Measure"))) for p in parts), default=0)
    bar_ql = float(ts[0].barDuration.quarterLength) if ts else 4.0
    return {
        "events": sorted(events),
        "time_sig": ts[0].ratioString if ts else None,
        "key": (ks[0].sharps if ks else None),
        "measures": n_meas,
        "bar_ql": bar_ql,
    }


def match(gt, est, shift, tol):
    by_pitch = defaultdict(list)
    for i, (b, p, d, s) in enumerate(est):
        by_pitch[p].append((b + shift, i))
    used = set()
    pairs = []
    for gi, (b, p, d, s) in enumerate(gt):
        best = None
        for eb, ei in by_pitch.get(p, []):
            if ei in used:
                continue
            diff = abs(eb - b)
            if diff <= tol and (best is None or diff < best[0]):
                best = (diff, ei)
        if best:
            used.add(best[1])
            pairs.append((gi, best[1]))
    return pairs, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gt")
    ap.add_argument("est")
    ap.add_argument("--json")
    ap.add_argument("--max-shift", type=int, default=2)
    ap.add_argument("--tol", type=float, default=0.125)
    a = ap.parse_args()
    G, E = flatten(a.gt), flatten(a.est)
    gt, est = G["events"], E["events"]
    bar = G["bar_ql"]
    best = None
    shifts = [k * 0.5 for k in range(int(-2 * bar * 2), int(2 * bar * 2) + 1)]
    for sh in sorted(set(shifts)):
        pairs, used = match(gt, est, sh, a.tol)
        if best is None or len(pairs) > len(best[1]):
            best = (sh, pairs, used)
    sh, pairs, used = best
    tp = len(pairs)
    fn = len(gt) - tp
    fp = len(est) - tp
    prec = tp / max(1, len(est))
    rec = tp / max(1, len(gt))
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    dur_ok = sum(1 for gi, ei in pairs if abs(gt[gi][2] - est[ei][2]) <= a.tol) / max(
        1, tp
    )
    staff_ok = sum(1 for gi, ei in pairs if gt[gi][3] == est[ei][3]) / max(1, tp)
    mism = []
    matched_gt = {gi for gi, _ in pairs}
    for gi, (b, p, d, s) in enumerate(gt):
        if gi not in matched_gt:
            mism.append(
                {
                    "type": "missing",
                    "measure": int(b // bar) + 1,
                    "beat": round(b % bar + 1, 3),
                    "pitch": p,
                    "ql": d,
                    "staff": s,
                }
            )
    for ei, (b, p, d, s) in enumerate(est):
        if ei not in used:
            bb = b + sh
            mism.append(
                {
                    "type": "extra",
                    "measure": int(bb // bar) + 1,
                    "beat": round(bb % bar + 1, 3),
                    "pitch": p,
                    "ql": d,
                    "staff": s,
                }
            )
    for gi, ei in pairs:
        if gt[gi][3] != est[ei][3]:
            b = gt[gi][0]
            mism.append(
                {
                    "type": "wrong_staff",
                    "measure": int(b // bar) + 1,
                    "beat": round(b % bar + 1, 3),
                    "pitch": gt[gi][1],
                    "gt_staff": gt[gi][3],
                    "est_staff": est[ei][3],
                }
            )
        elif abs(gt[gi][2] - est[ei][2]) > a.tol:
            b = gt[gi][0]
            mism.append(
                {
                    "type": "wrong_duration",
                    "measure": int(b // bar) + 1,
                    "beat": round(b % bar + 1, 3),
                    "pitch": gt[gi][1],
                    "gt_ql": gt[gi][2],
                    "est_ql": est[ei][2],
                }
            )
    mism.sort(key=lambda m: (m["measure"], m["beat"]))
    per_measure = defaultdict(int)
    for m in mism:
        per_measure[m["measure"]] += 1
    worst = sorted(per_measure.items(), key=lambda kv: -kv[1])[:10]
    rep = {
        "gt": a.gt,
        "est": a.est,
        "gt_events": len(gt),
        "est_events": len(est),
        "shift_quarters": sh,
        "onset_f1": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "dur_agree": round(dur_ok, 4),
        "staff_agree": round(staff_ok, 4),
        "gt_measures": G["measures"],
        "est_measures": E["measures"],
        "gt_time_sig": G["time_sig"],
        "est_time_sig": E["time_sig"],
        "gt_key_sharps": G["key"],
        "est_key_sharps": E["key"],
        "measure_ok": (
            G["measures"] == E["measures"] and G["time_sig"] == E["time_sig"]
        ),
        "mismatch_counts": dict(
            sorted(
                defaultdict(
                    int,
                    {
                        m["type"]: sum(1 for x in mism if x["type"] == m["type"])
                        for m in mism
                    },
                ).items()
            )
        ),
        "worst_measures": worst,
        "first_mismatches": mism[:40],
    }
    out = json.dumps(rep, indent=2)
    if a.json:
        open(a.json, "w").write(out)
    print(
        json.dumps(
            {k: v for k, v in rep.items() if k not in ("first_mismatches",)}, indent=1
        )
    )


if __name__ == "__main__":
    main()
