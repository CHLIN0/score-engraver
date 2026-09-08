"""Mechanical readability lint for an engraved MusicXML (piano, two staves).

    python lint_score.py score.musicxml [--json out.json]

Counts the things that make a page unplayable even when every pitch is right: very short rests,
ties across barlines, tuplets, chords wider than a hand span, notes far outside each staff's clef,
measures that are empty on both staves, measures whose contents do not fill the time signature,
and clef changes. Flags thresholds the skill's checklist cares about. Numbers, not opinions —
the agent decides what to fix.
"""

import argparse, json
from collections import Counter
from music21 import converter, note, chord, clef as m21clef


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("--json")
    a = ap.parse_args()
    sc = converter.parse(a.xml)
    parts = list(sc.parts)
    rep = {"file": a.xml, "parts": len(parts), "staves": []}
    total_flags = []
    for pi, p in enumerate(parts):
        measures = list(p.getElementsByClass("Measure"))
        ts = p.recurse().getElementsByClass("TimeSignature")
        bar_ql = ts[0].barDuration.quarterLength if ts else 4.0
        st = {
            "name": p.partName,
            "measures": len(measures),
            "notes": 0,
            "chords": 0,
            "rests": 0,
            "rests_shorter_than_16th": 0,
            "ties": 0,
            "tuplets": 0,
            "wide_chords_gt_10_semitones_span14": 0,
            "notes_outside_clef_range": 0,
            "clef_changes": 0,
            "overfull_measures": 0,
            "underfull_measures": 0,
            "empty_measures": 0,
            "max_notes_in_measure": 0,
            "dynamics": 0,
            "ledger_extremes": 0,
        }
        cur_clef = None
        for m in measures:
            cl = m.getElementsByClass("Clef")
            for c in cl:
                if cur_clef is not None and type(c) is not type(cur_clef):
                    st["clef_changes"] += 1
                cur_clef = c
            content_ql = 0.0
            per_voice = {}
            n_in_measure = 0
            for el in m.recurse().notesAndRests:
                if el.isRest:
                    st["rests"] += 1
                    if el.quarterLength < 0.25:
                        st["rests_shorter_than_16th"] += 1
                else:
                    n_in_measure += 1
                    if isinstance(el, chord.Chord):
                        st["chords"] += 1
                        ps = [n.pitch.midi for n in el.notes]
                        if max(ps) - min(ps) > 14:
                            st["wide_chords_gt_10_semitones_span14"] += 1
                        pitches = ps
                    else:
                        st["notes"] += 1
                        pitches = [el.pitch.midi]
                    if el.tie is not None and el.tie.type in ("start", "continue"):
                        st["ties"] += 1
                    if el.duration.tuplets:
                        st["tuplets"] += 1
                    lo, hi = (
                        (36, 72) if isinstance(cur_clef, m21clef.BassClef) else (55, 96)
                    )
                    for pp in pitches:
                        if pp < lo - 7 or pp > hi + 7:
                            st["ledger_extremes"] += 1
                        elif pp < lo or pp > hi:
                            st["notes_outside_clef_range"] += 1
                v = el.getContextByClass("Voice")
                vid = v.id if v is not None else "0"
                per_voice[vid] = per_voice.get(vid, 0.0) + float(el.quarterLength)
            content_ql = max(per_voice.values()) if per_voice else 0.0
            st["max_notes_in_measure"] = max(st["max_notes_in_measure"], n_in_measure)
            if n_in_measure == 0:
                st["empty_measures"] += 1
            if abs(content_ql - float(bar_ql)) > 1e-6 and m.number not in (0, 1):
                if content_ql > float(bar_ql) + 1e-6:
                    st["overfull_measures"] += 1
                else:
                    st["underfull_measures"] += 1
            st["dynamics"] += len(m.getElementsByClass("Dynamic"))
        flags = []
        if st["rests_shorter_than_16th"] > 0.05 * max(1, st["notes"]):
            flags.append(
                "many rests shorter than a 16th: grid too fine or offsets unquantized"
            )
        if st["ties"] > 0.3 * max(1, st["notes"]):
            flags.append(
                "ties on >30% of notes: barline/anacrusis or grid likely wrong"
            )
        if st["clef_changes"] > st["measures"] / 4:
            flags.append(
                "clef changes more than every 4 bars: hand split or clef choice unstable"
            )
        if st["ledger_extremes"]:
            flags.append(
                f"{st['ledger_extremes']} notes far outside clef range: consider clef change or 8va"
            )
        if st["overfull_measures"] or st["underfull_measures"]:
            flags.append(
                f"{st['overfull_measures']} overfull / {st['underfull_measures']} underfull measures"
            )
        if st["empty_measures"] > st["measures"] * 0.5:
            flags.append("more than half the measures are empty on this staff")
        st["flags"] = flags
        total_flags += [f"{p.partName}: {f}" for f in flags]
        rep["staves"].append(st)
    rep["flags"] = total_flags
    out = json.dumps(rep, indent=2, ensure_ascii=False)
    if a.json:
        open(a.json, "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
