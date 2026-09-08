"""Estimate beat times for a performance MIDI (rubato-tolerant), for use as a tempo map in quantize_to_score.py.

    python beats_from_midi.py perf.mid --bpm 120 [--out beats.json] [--tighten 100] [--downsample 2]

When the tracker only locks at a subdivision (typical for fast triple metres: it follows the eighths,
not the quarters), seed it at the subdivision BPM and pass --downsample N: the script keeps every Nth
beat, choosing the phase whose kept beats carry the most onset energy. The map is extended to cover
the whole file (constant local period at both ends) so quantize_to_score.py never runs off its edge.

Builds an onset-strength signal from the MIDI note onsets (velocity-weighted, 100 Hz) and runs
librosa's dynamic-programming beat tracker anchored at the BPM you give (choose it with analyze_midi.py
or from a reference score). Writes {"beats": [t0, t1, ...], "bpm": <median>, "source": "dp-tracker"}.
Beat times are in seconds; beat index 0 is the first tracked beat, not necessarily a downbeat —
the engraver decides the downbeat/anacrusis separately (see SKILL.md).
"""

import argparse, json
import numpy as np
import pretty_midi
import librosa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--out")
    ap.add_argument(
        "--tighten",
        type=float,
        default=100.0,
        help="tempo tightness (librosa); higher = steadier tempo",
    )
    ap.add_argument(
        "--downsample",
        type=int,
        default=1,
        help="keep every Nth tracked beat (phase chosen by onset energy)",
    )
    a = ap.parse_args()
    pm = pretty_midi.PrettyMIDI(a.midi)
    notes = [n for i in pm.instruments if not i.is_drum for n in i.notes]
    sr = 100
    end = pm.get_end_time()
    env = np.zeros(int(end * sr) + sr)
    for n in notes:
        env[int(max(n.start, 0) * sr)] += n.velocity / 127.0
    env = np.convolve(env, np.hanning(5), mode="same")
    tempo, frames = librosa.beat.beat_track(
        onset_envelope=env,
        sr=sr,
        hop_length=1,
        start_bpm=a.bpm,
        tightness=a.tighten,
        units="frames",
    )
    frames = np.asarray(frames, dtype=int)
    if a.downsample > 1 and len(frames) > a.downsample:
        n = a.downsample
        energy = [
            float(sum(env[max(f - 2, 0) : f + 3].sum() for f in frames[ph::n]))
            for ph in range(n)
        ]
        frames = frames[int(np.argmax(energy)) :: n]
    beats = (frames / sr).tolist()
    if len(beats) > 4:  # extend with the local period so the map covers the whole file
        period = float(np.median(np.diff(beats[-8:])))
        while beats[-1] + period < end + period:
            beats.append(beats[-1] + period)
        period0 = float(np.median(np.diff(beats[:8])))
        while beats[0] - period0 >= 0:
            beats.insert(0, beats[0] - period0)
    med = float(60 / np.median(np.diff(beats))) if len(beats) > 2 else a.bpm
    out = {
        "beats": [round(b, 4) for b in beats],
        "bpm": round(med, 2),
        "source": "dp-tracker",
        "start_bpm": a.bpm,
        "downsample": a.downsample,
        "n": len(beats),
    }
    if a.out:
        json.dump(out, open(a.out, "w"))
    print(
        json.dumps({k: v for k, v in out.items() if k != "beats"}),
        f"first beats {out['beats'][:6]}",
    )


if __name__ == "__main__":
    main()
