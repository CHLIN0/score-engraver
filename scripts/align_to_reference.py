"""Align a performance MIDI to a reference score (MusicXML/MXL/MIDI) and emit a beat map.

    python align_to_reference.py perf.mid reference.musicxml --out beats.json [--json report.json]

Both sides are reduced to onset events (notes starting within 50 ms in the performance / at the same
beat position in the score) carrying a pitch-class set. The three most plausible transpositions
(by chroma-histogram correlation) are tried; DTW with cost = 1 − Jaccard(pitch-class sets) and a
skip penalty gives a monotonic mapping performance-time → score-beat. From it we write beats.json
(the performance time of every integer score beat, so quantize_to_score.py --beats reproduces the
score's bar structure) and report: transposition (semitones the performance is above the
reference), the reference's time signature / key / bar length, the first-downbeat offset
(anacrusis in quarters), coverage (fraction of performance onsets matched with cost < 0.5) and mean
path cost. Coverage below ~0.7 or mean cost above ~0.4 means the reference is probably a different
piece or version — do not use it (SKILL.md rule).
"""

import argparse, json
import numpy as np
import pretty_midi
from music21 import converter, chord

POP = np.array([bin(i).count("1") for i in range(4096)], dtype=np.int16)


def score_events(path):
    if path.endswith(".mid") or path.endswith(".midi"):
        pm = pretty_midi.PrettyMIDI(path)
        tempo = pm.get_tempo_changes()[1]
        qps = (tempo[0] if len(tempo) else 120.0) / 60.0
        notes = [
            (n.start * qps, n.pitch)
            for i in pm.instruments
            if not i.is_drum
            for n in i.notes
        ]
        ts = pm.time_signature_changes
        bar_ql = 4.0 * ts[0].numerator / ts[0].denominator if ts else 4.0
        ts_str = f"{ts[0].numerator}/{ts[0].denominator}" if ts else None
        key_sharps = (
            pm.key_signature_changes[0].key_number if pm.key_signature_changes else None
        )
    else:
        sc = converter.parse(path)
        notes = []
        for el in sc.flatten().notes:
            ps = (
                [n.pitch.midi for n in el.notes]
                if isinstance(el, chord.Chord)
                else [el.pitch.midi]
            )
            notes += [(float(el.offset), p) for p in ps]
        tss = sc.recurse().getElementsByClass("TimeSignature")
        bar_ql = float(tss[0].barDuration.quarterLength) if tss else 4.0
        ts_str = tss[0].ratioString if tss else None
        ks = sc.recurse().getElementsByClass("KeySignature")
        key_sharps = ks[0].sharps if ks else None
    return cluster(notes, 1e-3), bar_ql, ts_str, key_sharps


def perf_events(path):
    pm = pretty_midi.PrettyMIDI(path)
    notes = [
        (n.start, n.pitch) for i in pm.instruments if not i.is_drum for n in i.notes
    ]
    return cluster(notes, 0.05)


def cluster(notes, tol):
    notes = sorted(notes)
    out = []
    for t, p in notes:
        if out and t - out[-1][0] <= tol:
            out[-1][1] |= 1 << (p % 12)
        else:
            out.append([t, 1 << (p % 12)])
    return out


def rotate(mask, shift):
    return ((mask << shift) | (mask >> (12 - shift))) & 0xFFF


def chroma_hist(events):
    h = np.zeros(12)
    for _, m in events:
        for k in range(12):
            if m >> k & 1:
                h[k] += 1
    return h / max(1, h.sum())


def dtw(ref_masks, perf_masks, skip=0.6):
    A = np.asarray(ref_masks, dtype=np.int64)[:, None]
    B = np.asarray(perf_masks, dtype=np.int64)[None, :]
    inter = POP[A & B].astype(np.float64)
    union = POP[A | B].astype(np.float64)
    cost = 1.0 - inter / np.maximum(union, 1)
    n, m = cost.shape
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    j_idx = np.arange(1, m + 1)
    for i in range(1, n + 1):
        c = cost[i - 1]
        base = c + np.minimum(D[i - 1, :-1], D[i - 1, 1:] + skip)  # diag or up
        C = np.cumsum(c)
        F = np.minimum.accumulate(base - j_idx * skip - C)
        D[i, 1:] = F + j_idx * skip + C  # left moves folded in
    i, j = n, m
    path = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        moves = (D[i - 1, j - 1], D[i - 1, j] + skip, D[i, j - 1] + skip)
        k = int(np.argmin(moves))
        if k == 0:
            i -= 1
            j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    path.reverse()
    return D[n, m] / max(n, m), path, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("perf")
    ap.add_argument("reference")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json")
    ap.add_argument(
        "--shifts", type=int, default=3, help="how many transposition candidates to try"
    )
    a = ap.parse_args()
    perf = perf_events(a.perf)
    ref, bar_ql, ts_str, key_sharps = score_events(a.reference)
    hp = chroma_hist(perf)
    hr = chroma_hist(ref)
    scores = [(float(np.dot(np.roll(hr, s), hp)), s) for s in range(12)]
    scores.sort(reverse=True)
    best = None
    for _, shift in scores[: a.shifts]:
        c, path, cost = dtw([rotate(m, shift) for _, m in ref], [m for _, m in perf])
        if best is None or c < best[0]:
            best = (c, shift, path, cost)
    mean_cost, shift, path, cost = best
    good = [(i, j) for i, j in path if cost[i, j] < 0.5]
    coverage = len({j for _, j in good}) / max(1, len(perf))
    t_arr, b_arr = [], []
    for i, j in good:
        t, b = perf[j][0], ref[i][0]
        if not b_arr or (b >= b_arr[-1] and t >= t_arr[-1]):
            t_arr.append(t)
            b_arr.append(b)
    t_arr, b_arr = np.array(t_arr), np.array(b_arr)
    beats = []
    if len(t_arr) > 3:
        b0, b1 = int(np.floor(b_arr[0])), int(np.ceil(b_arr[-1]))
        for k in range(b0, b1 + 1):
            beats.append(float(np.interp(k, b_arr, t_arr)))
    first_ref_beat = ref[0][0]
    anacrusis = (
        (bar_ql - (first_ref_beat % bar_ql)) % bar_ql
        if first_ref_beat % bar_ql
        else 0.0
    )
    out = {
        "beats": [round(x, 4) for x in beats],
        "beat0_score_offset": int(np.floor(b_arr[0])) if len(b_arr) else 0,
        "source": "reference-aligned",
        "reference": a.reference,
        "transposition_semitones": shift,
        "time_sig": ts_str,
        "bar_quarters": bar_ql,
        "key_sharps": key_sharps,
        "anacrusis_quarters": anacrusis,
        "coverage": round(coverage, 3),
        "mean_cost": round(float(mean_cost), 3),
        "perf_events": len(perf),
        "ref_events": len(ref),
    }
    json.dump(out, open(a.out, "w"))
    rep = {k: v for k, v in out.items() if k != "beats"}
    rep["n_beats"] = len(beats)
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
