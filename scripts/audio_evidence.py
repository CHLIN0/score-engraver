"""Does the recording support the notes the score prints but the AMT did not hear?

    python audio_evidence.py compare.midi perf.mid audio.wav [--json out.json] [--window 0.2]

The performance MIDI is the base; a reference may suggest chord tones the AMT missed (pedal-masked
inner voices). This script aligns the score to the performance in two steps — DTW on pitch-class
sets (the same aligner as align_to_reference.py) for a first warp score-beat → performance-time,
then a refined warp anchored on every score note that found its performance note — so ritardandi
and rubato inside a bar stay exact and no beat map is needed. Score notes are matched to
performance notes of the same pitch one-to-one and in time order (per-pitch monotone assignment:
a repeated-note pair cannot be crossed; 8 written / 6 played leaves two notes for the audio).

Every score note still without a performance note is measured in the audio: CQT energy (3 bins per
semitone) at the note's fundamental and 2nd harmonic in the 40–160 ms after the onset, relative to
the same bins' median over ±3 s (the "rise"). Thresholds are calibrated on the same recording: the
rise distribution of the notes the AMT DID hear. A missing note is
  supported   fundamental and 2nd harmonic both rise at least as much as the quietest quarter of the
              heard notes, and neither a semitone neighbour nor the octave below is ≥ 6 dB louder
              (leakage / the lower octave's 2nd partial)
  displaced   the same pitch WAS played, 0.2–0.6 s from where the score puts it, and not already
              explained by another score note — a rhythm / placement question, not a phantom
  weak        only one partial rises, or the fundamental reaches the heard notes' 10th percentile,
              or a louder neighbour / lower octave explains the energy
  unsupported nothing sounds there — the reference note was not played (or is in another octave /
              register). Drop it, or write it as an editorial (small / bracketed) note.
Output per bar (bar numbers follow the score's own time-signature changes; a partial bar counts as
one bar).
"""

import argparse, json, math
from collections import defaultdict
import numpy as np
import pretty_midi
import librosa
from align_to_reference import dtw, cluster


def score_bar_map(sc):
    """tick -> (bar, beat_in_bar), honouring time-signature changes (quarter-note units)."""
    changes = sorted(sc.time_signature_changes, key=lambda c: c.time)
    segs = [(0.0, 4.0)] if not changes else [
        # LilyPond emits the change at the first note of the bar, which grace notes pull earlier: snap to the half-quarter
        (round(sc.time_to_tick(c.time) / sc.resolution * 2) / 2, c.numerator * 4.0 / c.denominator) for c in changes]

    def f(tick):
        q = tick / sc.resolution
        bar = 1
        for k, (q0, bb) in enumerate(segs):
            q1 = segs[k + 1][0] if k + 1 < len(segs) else None
            if q1 is None or q < q1 - 1e-6:
                rel = round(q - q0, 3)
                return bar + int((rel + 1e-6) // bb), rel % bb
            bar += math.ceil((q1 - q0) / bb - 1e-6)
        return bar, 0.0

    return f


def assign(s_times, p_times, tol):
    """Monotone one-to-one assignment (max matches, then min total |dt|); returns {i: j}."""
    n, m = len(s_times), len(p_times)
    dp = [[(0, 0.0)] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best, k = dp[i - 1][j], 1
            if dp[i][j - 1] > best:
                best, k = dp[i][j - 1], 2
            d = abs(s_times[i - 1] - p_times[j - 1])
            if d <= tol:
                c = (dp[i - 1][j - 1][0] + 1, dp[i - 1][j - 1][1] - d)
                if c > best:
                    best, k = c, 3
            dp[i][j], bt[i][j] = best, k
    out, i, j = {}, n, m
    while i > 0 and j > 0:
        k = bt[i][j]
        if k == 3:
            out[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    return out


def make_warp(anchors_b, anchors_t):
    b, t = np.asarray(anchors_b, float), np.asarray(anchors_t, float)

    def f(beat):
        if beat <= b[0]:
            return float(t[0] + (beat - b[0]) * (t[1] - t[0]) / max(1e-6, b[1] - b[0]))
        if beat >= b[-1]:
            return float(t[-1] + (beat - b[-1]) * (t[-1] - t[-2]) / max(1e-6, b[-1] - b[-2]))
        return float(np.interp(beat, b, t))

    return f


def monotone(pairs):
    """[(beat, t)] -> sorted, one t per beat (median), strictly increasing in t."""
    by = defaultdict(list)
    for b, t in pairs:
        by[round(b, 3)].append(t)
    ab, at, last = [], [], -1.0
    for b in sorted(by):
        t = float(np.median(by[b]))
        if t > last:
            ab.append(b); at.append(t); last = t
    return ab, at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score_midi")
    ap.add_argument("perf_midi")
    ap.add_argument("audio")
    ap.add_argument("--window", type=float, default=0.2, help="onset tolerance (s) for 'the AMT heard it'")
    ap.add_argument("--json")
    a = ap.parse_args()
    sc = pretty_midi.PrettyMIDI(a.score_midi)
    pf = pretty_midi.PrettyMIDI(a.perf_midi)
    bar_of = score_bar_map(sc)
    snotes = sorted({(round(sc.time_to_tick(n.start) / sc.resolution, 3), n.pitch) for i in sc.instruments
                     if not i.is_drum and "chord" not in (i.name or "").lower() for n in i.notes})
    pnotes = sorted((n.start, n.pitch) for i in pf.instruments if not i.is_drum for n in i.notes)
    p_by_pitch = defaultdict(list)
    for t, p in pnotes:
        p_by_pitch[p].append(t)
    s_by_pitch = defaultdict(list)
    for k, (b, p) in enumerate(snotes):
        s_by_pitch[p].append(k)

    # warp 1: event-level DTW on pitch-class sets
    sc_ev = cluster([(b, p) for b, p in snotes], 1e-6)
    pf_ev = cluster(pnotes, 0.05)
    mean_cost, path, cost = dtw([m for _, m in sc_ev], [m for _, m in pf_ev])
    ab, at = monotone([(sc_ev[i][0], pf_ev[j][0]) for i, j in path if cost[i, j] < 0.5])
    align = {"mean_cost": round(float(mean_cost), 3), "dtw_anchors": len(ab), "score_events": len(sc_ev),
             "perf_events": len(pf_ev), "coverage": round(len({j for i, j in path if cost[i, j] < 0.5}) / max(1, len(pf_ev)), 3)}
    warp = make_warp(ab, at)

    # matching, twice: the second time on a warp anchored on the first round's matched notes
    for it in range(2):
        t_est = [warp(b) for b, _ in snotes]
        matched = {}  # score idx -> perf time
        for p, idxs in s_by_pitch.items():
            pt = p_by_pitch.get(p, [])
            if not pt:
                continue
            m = assign([t_est[k] for k in idxs], pt, a.window)
            for i, j in m.items():
                matched[idxs[i]] = pt[j]
        if it == 0:
            nb, nt = monotone([(snotes[k][0], t) for k, t in matched.items()])
            if len(nb) >= 20:
                warp = make_warp(nb, nt)
                align["note_anchors"] = len(nb)
    # second pass: unmatched score notes may claim a still-unused same-pitch onset within 0.6 s
    displaced = {}
    used = defaultdict(set)
    for k, t in matched.items():
        used[snotes[k][1]].add(t)
    for p, idxs in s_by_pitch.items():
        rest = [k for k in idxs if k not in matched]
        pt = [t for t in p_by_pitch.get(p, []) if t not in used[p]]
        if not rest or not pt:
            continue
        m = assign([t_est[k] for k in rest], pt, 0.6)
        for i, j in m.items():
            displaced[rest[i]] = abs(pt[j] - t_est[rest[i]])

    # audio
    y, sr = librosa.load(a.audio, sr=22050, mono=True)
    bpo = 36
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=256, fmin=librosa.midi_to_hz(21), n_bins=bpo * 7, bins_per_octave=bpo))
    CdB = librosa.amplitude_to_db(C, ref=np.max)
    hop_s = 256 / sr

    def rise(midi, t):
        b = int(round((midi - 21) * bpo / 12))
        if b < 0 or b >= CdB.shape[0]:
            return None
        f0, f1 = int((t + 0.04) / hop_s), int((t + 0.16) / hop_s)
        if f1 <= f0 or f1 >= CdB.shape[1]:
            return None
        seg = CdB[max(0, b - 1): b + 2, f0:f1].max()
        w0, w1 = max(0, int((t - 3) / hop_s)), min(CdB.shape[1], int((t + 3) / hop_s))
        return float(seg - np.median(CdB[max(0, b - 1): b + 2, w0:w1]))

    rows = []
    for k, (b, p) in enumerate(snotes):
        tick = b * sc.resolution
        bar, beat_in_bar = bar_of(tick)
        t_meas = matched.get(k, t_est[k])
        r0, r1 = rise(p, t_meas), rise(p + 12, t_meas)
        rn = max((rise(p + d, t_meas) or -99) for d in (-1, 1))
        ro = rise(p - 12, t_meas) or -99
        rows.append({"bar": bar, "beat": round(beat_in_bar + 1, 2), "pitch": p, "name": pretty_midi.note_number_to_name(p),
                     "t": round(t_est[k], 2), "matched": k in matched, "near": displaced.get(k), "r0": r0, "r1": r1, "rn": rn, "ro": ro})
    heard0 = np.array([r["r0"] for r in rows if r["matched"] and r["r0"] is not None])
    heard1 = np.array([r["r1"] for r in rows if r["matched"] and r["r1"] is not None])
    if len(heard0) < 20:
        raise SystemExit("too few heard notes to calibrate — is this the right performance? alignment: %s" % align)
    q10, q25, q25h = float(np.percentile(heard0, 10)), float(np.percentile(heard0, 25)), float(np.percentile(heard1, 25))
    results = []
    per_bar = defaultdict(lambda: {"checked": 0, "supported": 0, "weak": 0, "displaced": 0, "unsupported": 0, "notes": []})
    for r in rows:
        if r["matched"]:
            continue
        r0, r1, rn, ro = r["r0"], r["r1"], r["rn"], r["ro"]
        if r0 is None:
            v = "unknown"
        elif r["near"] is not None:
            v = "displaced (%.2fs)" % r["near"]
        elif r0 >= q25 and (r1 or -99) >= q25h:
            v = "supported" if rn - r0 < 6 and ro - r0 < 6 else ("weak (octave below louder)" if ro - r0 >= 6 else "weak (masked by neighbour)")
        elif r0 >= q10 or (r1 or -99) >= q25h:
            v = "weak"
        else:
            v = "unsupported"
        rec = {k_: r[k_] for k_ in ("bar", "beat", "pitch", "name", "t")}
        rec.update({"rise_f0_db": None if r0 is None else round(r0, 1), "rise_h2_db": None if r1 is None else round(r1, 1), "verdict": v})
        results.append(rec)
        pb = per_bar[r["bar"]]
        pb["checked"] += 1
        pb["supported" if v == "supported" else "unsupported" if v == "unsupported" else "displaced" if v.startswith("displaced") else "weak"] += 1
        pb["notes"].append(f"{rec['name']}@{rec['beat']}:{v.split(' ')[0]}")
    summary = {"alignment": align, "score_notes": len(rows), "heard_by_amt": int(sum(r["matched"] for r in rows)),
               "score_notes_missing_in_perf": len(results),
               "supported": sum(1 for r in results if r["verdict"] == "supported"),
               "weak": sum(1 for r in results if r["verdict"].startswith("weak")),
               "displaced": sum(1 for r in results if r["verdict"].startswith("displaced")),
               "unsupported": sum(1 for r in results if r["verdict"] == "unsupported"),
               "calibration_db": {"heard_f0_p10": round(q10, 1), "heard_f0_p25": round(q25, 1), "heard_f0_median": round(float(np.median(heard0)), 1), "heard_h2_p25": round(q25h, 1)},
               "worst_bars": sorted(((b, v["unsupported"]) for b, v in per_bar.items() if v["unsupported"]), key=lambda x: -x[1])[:12]}
    rep = {"summary": summary, "per_bar": {str(b): v for b, v in sorted(per_bar.items())}, "notes": results}
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
