"""Analyze a performance-level MIDI before engraving.

    python analyze_midi.py in.mid [--json out.json]

Reports what the engraver has to decide: whether the file already carries a tempo map / time
signature (score MIDI) or not (performance MIDI), key estimate (global + per 16-second window),
beat-period candidates from the inter-onset-interval (IOI) histogram and onset autocorrelation,
"gridness" of each candidate (how many onsets fall near a 16th grid at that tempo), pitch range,
polyphony, hand information present in track names, pedal and velocity statistics.
Nothing here is a decision; the agent reads this and decides (or asks for a reference score).
"""

import argparse, json, math, sys
from collections import Counter
import numpy as np
import pretty_midi


def key_estimate(notes, t0=None, t1=None):
    from music21 import stream, note, analysis

    s = stream.Stream()
    for n in notes:
        if t0 is not None and (n.end < t0 or n.start > t1):
            continue
        nn = note.Note(n.pitch)
        nn.quarterLength = max(0.25, min(4.0, (n.end - n.start) * 2))
        nn.offset = n.start * 2
        s.insert(nn)
    if len(s.notes) < 8:
        return None
    k = s.analyze("key")
    return {
        "key": f"{k.tonic.name} {k.mode}",
        "sharps": k.sharps,
        "confidence": round(float(k.correlationCoefficient), 3),
        "alternates": [
            f"{a.tonic.name} {a.mode}" for a in k.alternateInterpretations[:2]
        ],
    }


def beat_candidates(onsets, weights):
    """Return tempo candidates (BPM) from IOI histogram + autocorrelation of an onset-strength signal."""
    onsets = np.asarray(onsets)
    weights = np.asarray(weights)
    out = []
    if len(onsets) < 8:
        return out
    # IOI histogram between successive distinct onsets (merge chords within 30 ms)
    uniq = [onsets[0]]
    for t in onsets[1:]:
        if t - uniq[-1] > 0.03:
            uniq.append(t)
    uniq = np.array(uniq)
    ioi = np.diff(uniq)
    ioi = ioi[(ioi > 0.05) & (ioi < 2.0)]
    hist, edges = np.histogram(ioi, bins=np.arange(0.05, 2.0, 0.01))
    top = np.argsort(hist)[::-1][:5]
    ioi_peaks = [
        (round(float(edges[i] + 0.005), 3), int(hist[i])) for i in top if hist[i] > 0
    ]
    # onset strength at 100 Hz + autocorrelation
    sr = 100
    length = int(uniq[-1] * sr) + 200
    env = np.zeros(length)
    for t, w in zip(onsets, weights):
        env[int(t * sr)] += w
    env = np.convolve(env, np.hanning(9), mode="same")
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1 :]
    lo, hi = int(sr * 60 / 240), int(sr * 60 / 40)  # 240..40 BPM
    seg = ac[lo:hi]
    peaks = []
    for i in range(1, len(seg) - 1):
        if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1] and seg[i] > 0:
            peaks.append((seg[i], i + lo))
    peaks.sort(reverse=True)
    for val, lag in peaks[:6]:
        period = lag / sr
        out.append(
            {
                "bpm": round(60 / period, 1),
                "period_s": round(period, 3),
                "ac_strength": round(float(val / (ac[0] or 1)), 3),
            }
        )
    return {"ioi_peaks_s": ioi_peaks, "autocorr_bpm": out}


def gridness(onsets, bpm, subdiv=4, tol=0.12):
    """Fraction of onsets within tol*subbeat of a 1/subdiv-beat grid at bpm (phase searched)."""
    onsets = np.asarray(onsets)
    sub = 60.0 / bpm / subdiv
    best = 0.0
    for phase in np.linspace(0, sub, 12, endpoint=False):
        d = np.abs(((onsets - phase) / sub) - np.round((onsets - phase) / sub)) * sub
        best = max(best, float(np.mean(d < tol * sub)))
    return round(best, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi")
    ap.add_argument("--json")
    a = ap.parse_args()
    pm = pretty_midi.PrettyMIDI(a.midi)
    insts = [i for i in pm.instruments if not i.is_drum]
    notes = sorted(
        [n for i in insts for n in i.notes], key=lambda n: (n.start, n.pitch)
    )
    if not notes:
        sys.exit("no notes")
    tempi_t, tempi = pm.get_tempo_changes()
    ts = [
        (t.numerator, t.denominator, round(t.time, 3))
        for t in pm.time_signature_changes
    ]
    ks = [(k.key_number, round(k.time, 3)) for k in pm.key_signature_changes]
    has_score_tempo = (
        len(tempi) > 1 or (len(tempi) == 1 and abs(tempi[0] - 120.0) > 0.01) or bool(ts)
    )
    onsets = [n.start for n in notes]
    vel = [n.velocity for n in notes]
    pitches = [n.pitch for n in notes]
    dur = pm.get_end_time()
    # polyphony: max simultaneous notes at onsets
    poly = Counter()
    for n in notes:
        poly[round(n.start, 2)] += 1
    # per-window keys
    win_keys = []
    step = 16.0
    t = 0.0
    while t < dur:
        k = key_estimate(notes, t, t + step)
        if k:
            win_keys.append(
                {"t0": round(t, 1), "t1": round(min(t + step, dur), 1), **k}
            )
        t += step
    cands = beat_candidates(onsets, vel)
    grid = []
    seen = set()
    for c in cands["autocorr_bpm"] if cands else []:
        for mult in (0.5, 1, 2):
            bpm = round(c["bpm"] * mult, 1)
            if 40 <= bpm <= 240 and bpm not in seen:
                seen.add(bpm)
                grid.append(
                    {
                        "bpm": bpm,
                        "gridness_16th": gridness(onsets, bpm, 4),
                        "gridness_8th_triplet": gridness(onsets, bpm, 3),
                    }
                )
    grid.sort(key=lambda g: -g["gridness_16th"])
    pedal = [c for i in insts for c in i.control_changes if c.number == 64]
    report = {
        "file": a.midi,
        "duration_s": round(dur, 2),
        "notes": len(notes),
        "tracks": [
            {"name": i.name, "program": i.program, "notes": len(i.notes)} for i in insts
        ],
        "has_score_tempo_map": bool(has_score_tempo),
        "tempo_changes": [
            (round(float(t), 3), round(float(b), 2)) for t, b in zip(tempi_t, tempi)
        ][:10],
        "time_signatures": ts[:5],
        "key_signatures_in_file": ks[:5],
        "pitch_range": [min(pitches), max(pitches)],
        "mean_pitch": round(float(np.mean(pitches)), 1),
        "notes_per_second": round(len(notes) / dur, 2),
        "max_polyphony_at_onset": max(poly.values()),
        "velocity": {
            "min": min(vel),
            "max": max(vel),
            "mean": round(float(np.mean(vel)), 1),
            "std": round(float(np.std(vel)), 1),
        },
        "pedal_events": len(pedal),
        "pedal_down_fraction": None,
        "hand_tracks": [
            i.name
            for i in insts
            if "hand" in (i.name or "").lower()
            or "left" in (i.name or "").lower()
            or "right" in (i.name or "").lower()
        ],
        "key_global": key_estimate(notes),
        "key_windows": win_keys,
        "beat_candidates": cands,
        "grid_fit_by_bpm": grid[:8],
        "first_onset_s": round(notes[0].start, 3),
    }
    if pedal:
        down = 0.0
        last_t = None
        state = False
        for c in sorted(pedal, key=lambda c: c.time):
            if state and last_t is not None:
                down += c.time - last_t
            state = c.value >= 64
            last_t = c.time
        if state and last_t is not None:
            down += dur - last_t
        report["pedal_down_fraction"] = round(down / dur, 3)
    out = json.dumps(report, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    if a.json:
        open(a.json, "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
