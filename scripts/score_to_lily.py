"""Turn a quantized two-staff MusicXML (from quantize_to_score.py) into a clean, editable LilyPond
draft in the house style: one measure per line with a `% m.N` comment, absolute pitches, explicit
durations, ties, voices as `<< { } \\ { } >>`, plus a guessed chord-symbol line the engraver
verifies or deletes.

    python score_to_lily.py score.musicxml draft.ly --style /path/popular-piano.ily \
        [--title "..."] [--subtitle "..."] [--composer "..."] [--arranger "..."] [--tempo-word Moderately]

The draft compiles as-is (lilypond draft.ly). The engraver then edits it: hand assignment, voices,
ornaments (\\grace, \\trill, \\turn), 8va (\\ottavaOn … \\ottavaOff), slurs, dynamics, pedal,
chord symbols, line breaks (\\break) — see references/lilypond-cookbook.md.
"""

import argparse, pathlib
from fractions import Fraction
from music21 import (
    converter,
    note,
    chord,
    stream,
    key as m21key,
    meter,
    tempo,
    clef as m21clef,
)

LILY_DUR = [
    (Fraction(4), "1"),
    (Fraction(2), "2"),
    (Fraction(1), "4"),
    (Fraction(1, 2), "8"),
    (Fraction(1, 4), "16"),
    (Fraction(1, 8), "32"),
    (Fraction(1, 16), "64"),
]


def dur_tokens(ql):
    """LilyPond duration strings whose sum is ql (list of length > 1 means tie them)."""
    ql = Fraction(ql).limit_denominator(64)
    for base, name in LILY_DUR:
        if ql == base:
            return [name]
        if ql == base * Fraction(3, 2):
            return [name + "."]
        if ql == base * Fraction(7, 4):
            return [name + ".."]
    for base, name in LILY_DUR:
        if ql > base:
            rest = ql - base
            if rest > 0:
                return [name] + dur_tokens(rest)
    return ["64"]


def lily_pitch(p):
    step = p.step.lower()
    acc = p.accidental.alter if p.accidental is not None else 0
    acc = int(round(acc))
    if step in ("e", "a") and acc < 0:
        name = step + ("es" * (-acc))
    else:
        name = step + ("is" * acc if acc > 0 else "es" * (-acc))
    o = (p.octave if p.octave is not None else 3) - 3
    return name + ("'" * o if o > 0 else "," * (-o))


def key_to_lily(k):
    tonic = lily_pitch(k.tonic).rstrip("',")
    return f"\\key {tonic} \\{'major' if k.mode == 'major' else 'minor'}"


def measure_len_token(ts):
    return "1*" + f"{ts.numerator}/{ts.denominator}"


def emit_elements(elems, tuplet_ratio=None):
    """elems: sorted notes/rests of one voice. Returns lily tokens as a string."""
    out = []
    i = 0
    while i < len(elems):
        el = elems[i]
        tup = el.duration.tuplets[0] if el.duration.tuplets else None
        if tup is not None:
            # group consecutive tuplet elements
            j = i
            grp = []
            while j < len(elems) and elems[j].duration.tuplets:
                grp.append(elems[j])
                j += 1
            ratio = Fraction(tup.numberNotesActual, tup.numberNotesNormal)
            inner = " ".join(emit_one(e, ratio) for e in grp)
            out.append(
                f"\\tuplet {tup.numberNotesActual}/{tup.numberNotesNormal} {{ {inner} }}"
            )
            i = j
            continue
        out.append(emit_one(el))
        i += 1
    return " ".join(out)


def emit_one(el, ratio=None):
    ql = Fraction(el.quarterLength).limit_denominator(64)
    if ratio:
        ql = ql * ratio
    toks = dur_tokens(ql)
    if el.isRest:
        hidden = getattr(el.style, "hideObjectOnPrint", False)
        return " ".join(("s" if hidden else "r") + t for t in toks)
    if isinstance(el, chord.Chord):
        body = (
            "<"
            + " ".join(
                lily_pitch(n.pitch)
                for n in sorted(el.notes, key=lambda n: n.pitch.midi)
            )
            + ">"
        )
    else:
        body = lily_pitch(el.pitch)
    tie = el.tie is not None and el.tie.type in ("start", "continue")
    parts = []
    for k, t in enumerate(toks):
        last = k == len(toks) - 1
        parts.append(body + t + ("" if (last and not tie) else "~"))
    s = " ".join(parts)
    for a in getattr(el, "articulations", []):
        if a.name == "staccato":
            s += "-."
        elif a.name == "accent":
            s += "->"
    return s


def measure_body(m):
    voices = list(m.voices)
    dyn = m.getElementsByClass("Dynamic")
    dyn_tok = ""
    if dyn:
        dyn_tok = "\\" + dyn[0].value
    if len(voices) >= 2:
        parts = []
        for v in voices[:2]:
            els = sorted(v.notesAndRests, key=lambda e: e.offset)
            parts.append(emit_elements(els))
        body = "<< { " + parts[0] + " } \\\\ { " + parts[1] + " } >>"
    else:
        els = sorted((voices[0] if voices else m).notesAndRests, key=lambda e: e.offset)
        if not els:
            return None
        body = emit_elements(els)
    if dyn_tok:
        # attach dynamic to the first note token
        body = body.replace(" ", f"{dyn_tok} ", 1) if " " in body else body + dyn_tok
    return body


CHORD_TEMPLATES = {
    "": [0, 4, 7],
    "m": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "dim": [0, 3, 6],
    "m7.5-": [0, 3, 6, 10],
    "sus4": [0, 5, 7],
    "aug": [0, 4, 8],
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
}
PC_NAMES_FLAT = ["c", "des", "d", "ees", "e", "f", "ges", "g", "aes", "a", "bes", "b"]
PC_NAMES_SHARP = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]


def guess_chord(measures, sharps):
    """Pitch-class weights by duration across both staves -> best (root, quality, bass)."""
    w = [0.0] * 12
    bass = None
    for m in measures:
        for el in m.recurse().notes:
            ps = (
                [n.pitch for n in el.notes]
                if isinstance(el, chord.Chord)
                else [el.pitch]
            )
            for p in ps:
                w[p.midi % 12] += float(el.quarterLength) * (
                    1.5 if p.midi < 55 else 1.0
                )
                if bass is None or p.midi < bass:
                    bass = p.midi
    if sum(w) == 0:
        return None
    best, best_s = None, -1e9
    for root in range(12):
        for q, tpl in CHORD_TEMPLATES.items():
            inside = sum(w[(root + i) % 12] for i in tpl)
            outside = sum(w) - inside
            s = inside - 0.6 * outside - (0.15 * len(tpl))
            if s > best_s:
                best_s, best = s, (root, q)
    names = PC_NAMES_SHARP if sharps > 0 else PC_NAMES_FLAT
    root, q = best
    slash = ""
    if bass is not None and bass % 12 != root and w[bass % 12] > 0.2 * sum(w):
        slash = "/" + names[bass % 12]
    return names[root], (":" + q if q else ""), slash


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("out")
    ap.add_argument("--style", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--composer", default="")
    ap.add_argument("--arranger", default="")
    ap.add_argument("--tempo-word", default="")
    ap.add_argument("--no-chords", action="store_true")
    ap.add_argument("--staff-size", type=float, default=None, help="override the house staff size (e.g. 18 for continuous 16ths)")
    a = ap.parse_args()
    sc = converter.parse(a.xml)
    parts = list(sc.parts)

    # upper/lower by mean pitch
    def mean_pitch(p):
        ps = [
            n.pitch.midi
            for n in p.recurse().notes
            for n in ([n] if isinstance(n, note.Note) else n.notes)
        ]
        return sum(ps) / len(ps) if ps else 60

    parts.sort(key=mean_pitch, reverse=True)
    up, lo = parts[0], parts[1] if len(parts) > 1 else parts[0]
    ts = up.recurse().getElementsByClass(meter.TimeSignature)
    ts = ts[0] if ts else meter.TimeSignature("4/4")
    ks = up.recurse().getElementsByClass(m21key.KeySignature)
    k = ks[0] if ks else m21key.KeySignature(0)
    if not isinstance(k, m21key.Key):
        k = k.asKey("major")
    mm = up.recurse().getElementsByClass(tempo.MetronomeMark)
    tempo_line = ""
    if mm:
        ref = Fraction(mm[0].referent.quarterLength).limit_denominator(8)
        ref_tok = dur_tokens(ref)[0]
        bpm = int(round(mm[0].number))
        if a.tempo_word:
            tempo_line = (
                f'\\tempo \\markup {{ \\bold "{a.tempo_word}" }} {ref_tok} = {bpm}'
            )
        else:
            tempo_line = f"\\tempo {ref_tok} = {bpm}"
    elif a.tempo_word:
        tempo_line = f'\\tempo "{a.tempo_word}"'
    up_ms = list(up.getElementsByClass(stream.Measure))
    lo_ms = list(lo.getElementsByClass(stream.Measure))
    n = min(len(up_ms), len(lo_ms))
    bar_ql = Fraction(ts.barDuration.quarterLength)
    partial = ""
    if (
        up_ms
        and Fraction(up_ms[0].duration.quarterLength) < bar_ql
        and up_ms[0].number in (0, 1)
    ):
        partial = (
            "\\partial "
            + dur_tokens(Fraction(up_ms[0].duration.quarterLength))[0]
            + " "
        )

    def staff_lines(ms, default_clef):
        lines = []
        cur_clef = default_clef
        for m in ms[:n]:
            cl = m.getElementsByClass(m21clef.Clef)
            pre = ""
            if cl:
                want = "bass" if isinstance(cl[0], m21clef.BassClef) else "treble"
                if want != cur_clef:
                    pre = f"\\clef {want} "
                    cur_clef = want
            body = measure_body(m)
            if body is None:
                body = "R" + measure_len_token(ts)
            lines.append(f"  {pre}{body} |  % m.{m.number}")
        return lines

    rh = staff_lines(up_ms, "treble")
    lh = staff_lines(lo_ms, "bass")
    chords = []
    if not a.no_chords:
        mlen = (
            dur_tokens(bar_ql)[0]
            if len(dur_tokens(bar_ql)) == 1
            else measure_len_token(ts)
        )
        for i in range(n):
            g = guess_chord([up_ms[i], lo_ms[i]], k.sharps)
            txt = f"{g[0]}{mlen}{g[1]}{g[2]}" if g else f"r{mlen}"
            chords.append(f"  {txt}  % m.{up_ms[i].number}")
    style = pathlib.Path(a.style).resolve()
    hdr = "\n".join(
        f'  {kk} = "{vv}"'
        for kk, vv in (
            ("title", a.title),
            ("subtitle", a.subtitle),
            ("composer", a.composer),
            ("arranger", a.arranger),
        )
        if vv
    )
    chordnames_line = "\\new ChordNames \\chordsPart" if chords else "% \\new ChordNames \\chordsPart"
    ly = f'''\\version "2.26.0"
\\include "{style}"
{f"#(set-global-staff-size {a.staff_size})" if a.staff_size else "% #(set-global-staff-size 18)   % uncomment for dense 16th textures"}
%% DRAFT generated by score_to_lily.py from {pathlib.Path(a.xml).name}
%% time {ts.ratioString}  key {k.tonic.name} {k.mode}  measures {n}
%% Chord symbols below are GUESSED from pitch content — verify against the reference or delete.

\\header {{
{hdr}
  tagline = ##f
}}

global = {{ \\time {ts.ratioString} {key_to_lily(k)} {partial}}}

chordsPart = \\chordmode {{
{chr(10).join(chords) if chords else "  % none"}
}}

rh = {{
  \\global \\clef treble {tempo_line}
{chr(10).join(rh)}
  \\bar "|."
}}

lh = {{
  \\global \\clef bass
{chr(10).join(lh)}
  \\bar "|."
}}

\\score {{
  <<
    {chordnames_line}
    \\new PianoStaff <<
      \\new Staff = "up" \\rh
      \\new Staff = "down" \\lh
    >>
  >>
  \\layout {{ }}
  \\midi {{ }}
}}
'''
    pathlib.Path(a.out).write_text(ly)
    print(
        f"{a.out}: {n} measures, {ts.ratioString}, {k.tonic.name} {k.mode}, partial={'yes' if partial else 'no'}, chords={'guessed' if chords else 'off'}"
    )


if __name__ == "__main__":
    main()
