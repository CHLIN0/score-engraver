"""Convert PDMX (MusPy JSON) scores to score-MIDI and MusicXML so the other scripts can use them as references.

    python pdmx_to_midi.py <file.json | dir> [--out DIR]

PDMX v1 ships each score as a MusPy JSON (resolution, tempos, time/key signatures, barlines, tracks
with notes). muspy writes a MIDI with the tempo map and a MusicXML; both keep the bar structure, so
align_to_reference.py / compare_scores.py / find_reference.py accept them. Prints title, composer,
tracks, notes, time signature, key and bar count for each file so you can judge the edition
(rating and n_tracks are in PDMX.csv).
"""

import argparse, glob, json, os, pathlib
import muspy


def convert(path, out_dir):
    m = muspy.load_json(path)
    # muspy writes MIDI text meta events as latin-1; strip anything outside it
    def ascii_(x):
        return x.encode("ascii", "ignore").decode() if isinstance(x, str) else x
    md = m.metadata
    md.title = ascii_(md.title)
    md.copyright = ascii_(md.copyright)
    md.source_filename = ascii_(md.source_filename)
    md.creators = [ascii_(c) for c in (md.creators or [])]
    for t in m.tracks:
        t.name = ascii_(t.name)
    # muspy writes <fifths>10</fifths> for key signatures without a root; drop those
    m.key_signatures = [k for k in m.key_signatures if k.root is not None]
    for l in getattr(m, "lyrics", []) or []:
        l.lyric = ascii_(l.lyric)
    for an in getattr(m, "annotations", []) or []:
        an.annotation = ascii_(an.annotation) if isinstance(an.annotation, str) else an.annotation
    base = pathlib.Path(out_dir or os.path.dirname(path)) / pathlib.Path(path).stem
    m.write_midi(str(base) + ".mid")
    xml_ok = True
    try:
        m.write_musicxml(str(base) + ".musicxml")
    except Exception as e:
        xml_ok = False
    meta = m.metadata
    return {
        "file": os.path.basename(path),
        "title": meta.title,
        "creators": meta.creators,
        "tracks": len(m.tracks),
        "notes": sum(len(t.notes) for t in m.tracks),
        "time_sig": [(t.numerator, t.denominator) for t in m.time_signatures[:3]],
        "key": [(k.root, k.mode) for k in m.key_signatures[:2]],
        "tempo_qpm": [round(t.qpm) for t in m.tempos[:3]],
        "bars": len(m.barlines),
        "midi": str(base) + ".mid",
        "musicxml": (str(base) + ".musicxml") if xml_ok else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out")
    a = ap.parse_args()
    files = (
        sorted(glob.glob(os.path.join(a.src, "*.json")))
        if os.path.isdir(a.src)
        else [a.src]
    )
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    for f in files:
        try:
            print(json.dumps(convert(f, a.out), ensure_ascii=False, default=str))
        except Exception as e:
            print(
                json.dumps(
                    {
                        "file": os.path.basename(f),
                        "error": f"{type(e).__name__}: {e}"[:200],
                    }
                )
            )


if __name__ == "__main__":
    main()
