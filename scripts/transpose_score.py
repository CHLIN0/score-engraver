"""Transpose a finished score without redoing any of the engraving.

    python transpose_score.py score.ly out.ly --from ges --to f [--tag "F major"]

Every engraving decision lives in score.ly — hand assignment, ties, voices, arpeggio marks, chord
symbols, lyrics, line and page breaks.  LilyPond's \\transpose moves pitches, key signatures and
chord symbols together and leaves all of that untouched, so transposing is one wrapper around the
\\score block rather than a second engraving pass.  Pitch names are Dutch (c d e f g a b, -is sharp,
-es flat: ges = G-flat, bes = B-flat, cis = C-sharp).

After running this, ALWAYS re-render and re-check — four things really do change with the key:
  1. spelling: the target may land on double flats/sharps; try the enharmonic (`--to fis` vs `--to ges`)
     and take the key signature with fewer accidentals (this script prints both counts)
  2. \\ottava and ledger lines: a passage moved up or down can cross the "three ledger lines" line
  3. hand geometry: the same interval on white keys is not the same stretch as on black keys —
     playability_lint numbers are unchanged, so look at the flagged bars yourself
  4. line breaks: a different number of accidentals changes bar widths — run page_balance.py
"""

import argparse, pathlib, re

STEP = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
LETTER = {0: "C", 2: "D", 4: "E", 5: "F", 7: "G", 9: "A", 11: "B"}
FIFTHS = {  # key signature -> number of accidentals, major keys by tonic pitch class + spelling
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": 1, "Bb": 2, "Eb": 3, "Ab": 4, "Db": 5, "Gb": 6, "Cb": 7,
    "G#": 8, "D#": 9, "A#": 10, "Fb": 8, "Bbb": 9,
}


def parse_pitch(name: str):
    """Dutch LilyPond pitch name -> (letter index 0-6, alteration in semitones)."""
    m = re.fullmatch(r"([a-g])((?:is|es|s)*)", name)
    if not m:
        raise SystemExit(f"not a Dutch pitch name: {name!r} (use c d e f g a b with -is / -es)")
    letter, rest = m.group(1), m.group(2)
    alt = 0
    while rest:
        if rest.startswith("is"):
            alt += 1; rest = rest[2:]
        elif rest.startswith("es"):
            alt -= 1; rest = rest[2:]
        elif rest.startswith("s") and letter in "ea":   # es / as
            alt -= 1; rest = rest[1:]
        else:
            raise SystemExit(f"cannot read accidentals in {name!r}")
    return "cdefgab".index(letter), alt


def semitones(name: str) -> int:
    i, alt = parse_pitch(name)
    return STEP["cdefgab"[i]] + alt


def transposed_key(src_key: str, frm: str, to: str) -> str:
    """Key signature name (English, e.g. 'Gb') after the transposition, keeping letter arithmetic."""
    si, sa = parse_pitch(src_key)
    fi, fa = parse_pitch(frm)
    ti, ta = parse_pitch(to)
    letter_shift = (ti - fi) % 7
    semi_shift = (semitones(to) - semitones(frm)) % 12
    ni = (si + letter_shift) % 7
    base = (STEP["cdefgab"[ni]] - (STEP["cdefgab"[si]] + sa) - semi_shift) % 12
    alt = -(base if base <= 6 else base - 12)
    return LETTER[STEP["cdefgab"[ni]]] + ("#" * alt if alt > 0 else "b" * -alt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score_ly")
    ap.add_argument("out_ly")
    ap.add_argument("--from", dest="frm", required=True, help="the score's own tonic, Dutch name (e.g. ges)")
    ap.add_argument("--to", required=True, help="target tonic, Dutch name (e.g. f, fis)")
    ap.add_argument("--tag", help="text appended to the subtitle, e.g. \"F major\"")
    a = ap.parse_args()
    src = pathlib.Path(a.score_ly).read_text()

    keys = re.findall(r"\\key\s+([a-g](?:is|es|s)*)\s+\\(major|minor)", src)
    if not keys:
        raise SystemExit("no \\key found — is this a score.ly?")
    report = []
    for k, mode in keys:
        new = transposed_key(k, a.frm, a.to)
        acc = FIFTHS.get(new, "?")
        report.append(f"{k} \\{mode} -> {new} ({acc} accidentals)" if acc != "?" else f"{k} \\{mode} -> {new}")

    m = re.search(r"(\\score\s*\{\s*\n?\s*)(<<)", src)
    if not m:
        raise SystemExit("could not find `\\score { <<` — wrap the score's music in << >> first")
    out = src[:m.end(1)] + f"\\transpose {a.frm} {a.to} " + src[m.start(2):]
    if a.tag:
        out = re.sub(r'(subtitle\s*=\s*")([^"]*)(")', lambda x: x.group(1) + x.group(2) + f" — {a.tag}" + x.group(3), out, count=1)
    out = out.replace("\\version", f"%% transposed {a.frm} -> {a.to} by transpose_score.py; edit the original, not this file\n\\version", 1)
    pathlib.Path(a.out_ly).write_text(out)
    print(f"wrote {a.out_ly}")
    for line in report:
        print("  key:", line)
    print("  now: render, then re-run playability_lint.py and page_balance.py; check \\ottava and ledger lines")


if __name__ == "__main__":
    main()
