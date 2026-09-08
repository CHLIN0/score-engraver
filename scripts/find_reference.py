"""Find reference scores for a piece: by title/composer text, and by transposition-invariant melodic fingerprint.

    python find_reference.py --midi in.mid [--title "..."] [--composer "..."] [--library DIR ...] [--top 5]

Library = directories containing .musicxml/.mxl/.mid files (e.g. a curated ground-truth folder, a PDMX extract).
If a PDMX metadata CSV exists under a library dir (PDMX.csv), its title/composer columns are searched too.
Fingerprint: the top-voice pitch-interval trigrams of the first ~120 melody notes; similarity =
Jaccard over trigram sets (invariant to transposition, robust to a few wrong notes). Reports the
candidates with their similarity so the agent can decide whether a reference is trustworthy
(rule of thumb in SKILL.md: use a reference only when similarity >= 0.35 and the alignment in
align_to_reference.py covers most of the input).
"""

import argparse, csv, json, os, pathlib, re
import pretty_midi


def top_voice_intervals(notes, limit=160):
    """notes: list of (start, pitch). Keep the highest pitch per 60 ms onset cluster."""
    notes = sorted(notes)
    clusters = []
    for s, p in notes:
        if clusters and s - clusters[-1][0] < 0.06:
            clusters[-1][1] = max(clusters[-1][1], p)
        else:
            clusters.append([s, p])
    tops = [p for _, p in clusters[:limit]]
    return [b - a for a, b in zip(tops, tops[1:])]


def trigrams(iv):
    return {tuple(iv[i : i + 3]) for i in range(len(iv) - 2)}


def notes_from_file(path):
    path = str(path)
    if path.endswith(".mid") or path.endswith(".midi"):
        pm = pretty_midi.PrettyMIDI(path)
        return [
            (n.start, n.pitch) for i in pm.instruments if not i.is_drum for n in i.notes
        ]
    from music21 import converter, chord

    sc = converter.parse(path)
    out = []
    for el in sc.flatten().notes:
        ps = (
            [n.pitch.midi for n in el.notes]
            if isinstance(el, chord.Chord)
            else [el.pitch.midi]
        )
        out += [
            (float(el.offset) / 2.0, p) for p in ps
        ]  # quarter offsets -> pseudo-seconds at 120 bpm
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--midi")
    ap.add_argument("--title", default="")
    ap.add_argument("--composer", default="")
    ap.add_argument("--library", action="append", default=[])
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args()
    q_tri = None
    if a.midi:
        q_tri = trigrams(top_voice_intervals(notes_from_file(a.midi)))
    words = [
        w
        for w in re.findall(r"[a-z0-9]+", (a.title + " " + a.composer).lower())
        if len(w) > 2
    ]
    cands = []
    for lib in a.library:
        lib = pathlib.Path(lib).expanduser()
        csvp = next(lib.glob("**/PDMX.csv"), None)
        if csvp and words:
            with open(csvp, newline="", encoding="utf-8", errors="ignore") as f:
                for row in csv.DictReader(f):
                    text = " ".join(
                        str(row.get(k, ""))
                        for k in (
                            "title",
                            "subtitle",
                            "composer_name",
                            "artist_name",
                            "tags",
                        )
                    ).lower()
                    hit = sum(1 for w in words if w in text)
                    if hit >= max(1, len(words) - 1):
                        cands.append(
                            {
                                "path": str(lib / row.get("path", "")),
                                "title": row.get("title"),
                                "composer": row.get("composer_name"),
                                "rating": row.get("rating"),
                                "text_hits": hit,
                                "source": "pdmx-csv",
                            }
                        )
        for p in (
            list(lib.glob("**/*.musicxml"))
            + list(lib.glob("**/*.mxl"))
            + list(lib.glob("**/*.mid"))
        ):
            if "pdmx" in str(p).lower() and csvp:
                continue
            name = p.stem.lower()
            hit = sum(1 for w in words if w in name)
            cands.append(
                {"path": str(p), "title": p.stem, "text_hits": hit, "source": "file"}
            )
    # fingerprint similarity for file candidates (cap the number for speed)
    if q_tri:
        for c in cands[:60]:
            try:
                tri = trigrams(top_voice_intervals(notes_from_file(c["path"])))
                c["similarity"] = round(len(q_tri & tri) / max(1, len(q_tri | tri)), 3)
            except Exception as e:
                c["similarity"] = None
                c["error"] = str(e)[:80]
    cands.sort(key=lambda c: (-(c.get("similarity") or 0), -c.get("text_hits", 0)))
    print(
        json.dumps(
            {
                "query": {
                    "midi": a.midi,
                    "title": a.title,
                    "composer": a.composer,
                    "trigrams": len(q_tri) if q_tri else 0,
                },
                "candidates": cands[: a.top],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
