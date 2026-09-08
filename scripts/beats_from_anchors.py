"""Turn (bar, time) anchors into a beat map for quantize_to_score.py --beats.

    python beats_from_anchors.py anchors.json --beats-per-bar 4 --out beats.json [--end-time 246]

anchors.json: [{"bar": 1, "t": 0.52}, {"bar": 7, "t": 17.64}, ...] — the downbeat time of each bar
you could pin from the on-screen score, a chord change, or a bass note. Bars between anchors get
evenly spaced beats (tempo is piecewise constant); before the first / after the last anchor the
neighbouring tempo is extrapolated to time 0 / --end-time. Bar numbers may start at 0 (pickup bar).
Output: {"beats": [...], "beat0_bar": <first bar>, "beat0_score_offset": 0, "source": "anchors"}.
"""

import argparse, json
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anchors")
    ap.add_argument("--beats-per-bar", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--end-time", type=float, default=None)
    a = ap.parse_args()
    anc = sorted(json.load(open(a.anchors)), key=lambda x: x["bar"])
    if len(anc) < 2:
        raise SystemExit("need at least two anchors")
    bpb = a.beats_per_bar
    first_bar = anc[0]["bar"]
    beats = []
    for (b0, t0), (b1, t1) in zip(
        [(x["bar"], x["t"]) for x in anc[:-1]], [(x["bar"], x["t"]) for x in anc[1:]]
    ):
        n = (b1 - b0) * bpb
        if n <= 0 or t1 <= t0:
            raise SystemExit(f"anchors not increasing: bar {b0}@{t0} -> bar {b1}@{t1}")
        beats.extend(np.linspace(t0, t1, n, endpoint=False).tolist())
    beats.append(anc[-1]["t"])
    # extrapolate after the last anchor with the last tempo
    period = (anc[-1]["t"] - anc[-2]["t"]) / ((anc[-1]["bar"] - anc[-2]["bar"]) * bpb)
    end = a.end_time if a.end_time is not None else anc[-1]["t"] + bpb * period
    while beats[-1] + period <= end + period:
        beats.append(beats[-1] + period)
        if len(beats) > 20000:
            break
    # extrapolate before the first anchor with the first tempo
    period0 = (anc[1]["t"] - anc[0]["t"]) / ((anc[1]["bar"] - anc[0]["bar"]) * bpb)
    pre = []
    t = beats[0] - period0
    while t >= 0:
        pre.insert(0, t)
        t -= period0
    beats = pre + beats
    out = {
        "beats": [round(x, 4) for x in beats],
        "beat0_bar": first_bar - (len(pre) // bpb) - (1 if len(pre) % bpb else 0),
        "beat0_score_offset": 0,
        "bpm": round(60 / period, 2),
        "source": "anchors",
        "n_anchors": len(anc),
        "n": len(beats),
    }
    json.dump(out, open(a.out, "w"))
    print(
        json.dumps({k: v for k, v in out.items() if k != "beats"}),
        f"first beats {out['beats'][:4]}; pass --anacrusis-beats to align bar 1 if beat 0 is not a downbeat",
    )


if __name__ == "__main__":
    main()
