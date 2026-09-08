# LilyPond cookbook for the engraver (2.26, house style `assets/popular-piano.ily`)

The draft from `score_to_lily.py` compiles as-is. You edit it; you do not start from a blank file.
Absolute pitches (`c'` = middle C, `c` = C3, `c''` = C5), explicit durations, one measure per line
ending in `|  % m.N`. Keep that shape — bar checks (`|`) make LilyPond tell you the exact measure
whose duration is wrong.

## Skeleton (already in the draft)
```lilypond
\include ".../popular-piano.ily"
\header { title = "…" subtitle = "…" composer = "…" arranger = "…" tagline = ##f }
global = { \time 4/4 \key f \major \partial 8 }          % \partial only for a real upbeat
chordsPart = \chordmode { f1 d1:m7 c1/bes bes1 bes1:m }   % one entry per bar; verify or delete
rh = { \global \clef treble \tempoWord "Moderately" 76  … measures … \bar "|." }
lh = { \global \clef bass … \bar "|." }
\score { << \new ChordNames \chordsPart \new PianoStaff << \new Staff = "up" \rh \new Staff = "down" \lh >> >>
         \layout { } \midi { } }
```

## Things you will do constantly
| want | write |
|---|---|
| move a note to the other hand | cut it from one staff's measure, paste into the same `% m.N` line of the other; fix both bars' durations with rests `r` or spacers `s` |
| held note under moving notes (two voices) | `<< { c''2 d''4 e''4 } \\ { g'1 } >>` — upper voice first (stems up), lower second (stems down) |
| chord | `<c' e' g'>4` ; tied chord `<c' e' g'>2~ <c' e' g'>8` |
| tie / slur | `c'4~ c'8` (tie, same pitch) ; `c'4( d' e')` (slur) |
| grace / appoggiatura / turn / trill / mordent | `\grace { d'16 }  c'4` ; `\appoggiatura d'8 c'4` ; `c'4\turn` ; `c'2\trill` ; `c'4\mordent` |
| fioriture (a fast written-out run) | keep as small notes: `\grace { c'16 d' e' f' g' a' }` or as a tuplet `\tuplet 7/4 { c'16 d' e' f' g' a' b' }` |
| 8va / 8vb | `\ottavaOn c'''4 d''' e''' \ottavaOff` ; `\ottavaBassa … \ottavaOff` (use when ≥ 3 ledger lines for a whole beat or more). **Write the sounding pitch**: `\ottava` only moves where the note is printed — `\ottava #1 c'''` sounds C6 and prints C5; the MIDI stays at the written pitch |
| clef change inside a measure | `\clef treble` before the note, `\clef bass` after |
| dynamics / hairpins | `c'4\mp` ; `c'4\< d' e' f'\!` ; `\dim` `\cresc` as text: `c'4\cresc … \!` |
| tempo word / change | `\tempoWord "Moderately" 76` ; compound metre `\tempoWordDur "Andante" 4. 44` ; mid-piece `\tempo "rit."` or `^\markup \italic "poco rit."` |
| pedal | write `\withPedal` on the first LH note (`c4\withPedal`) and nothing else, unless the reference shows explicit pedal marks; `c4\sustainOn … c4\sustainOff` if needed |
| rests | `r4` ; whole-bar rest `R1` (4/4), `R1*3/4`, `R1*12/8` ; invisible filler `s4` |
| triplets | `\tuplet 3/2 { c'8 d' e' }` |
| line break / page break | `\break` at the end of a measure line (only to hit 3–5 bars per system); `\pageBreak` |
| repeat / volta | `\repeat volta 2 { … } \alternative { { … } { … } }` |
| D.S. / coda | `\mark \markup { \musicglyph "scripts.coda" }` ; text `\mark "D.S. al Coda"` |
| lyrics (pop songs, optional) | `\addlyrics { 茫 茫 人 海 之 中 }` under `\rh` — only when the reference shows lyrics |
| chord symbols | `\chordmode { c1 g2:7 a2:m f1/c ees1:maj7 d1:m7.5- }` ; slash bass `/e` ; `r1` for no chord |
| accidentals | LilyPond prints them from pitch names; `es`/`is`; cautionary `c'!4`, parenthesised `c'?4` |
| hide a bar number / force one | `\set Score.currentBarNumber = #17` after `\partial` |

## Copying spellings from a Mutopia .ly
Many Mutopia files start with `\include "deutsch.ly"` (or `english.ly`): in German names `h` = B natural,
`b` = B flat, `his` = B sharp; in English names accidentals are `-sharp`/`-flat` (`bf`, `cs`). The draft and
this cookbook use the default Dutch names (`b`, `bes`, `bis`); transliterate before pasting.

## Line and page breaks that actually hold
`\break` forces a line end but LilyPond will still squeeze the bars before it onto that line — if
they do not fit, the last bar prints past the right margin without any warning. Check
`page_balance.py`'s `right_edge` (> 0.955 of the width = clipped) and put fewer bars on that system.
`\pageBreak` alone does not pin the page count either; combine it with `\paper { page-count = N }`
or `systems-per-page = N` when the plan matters, and keep `ragged-last-bottom = ##f` for level pages.

## Dense classical textures
The house staff size (19) fits two bars of continuous sixteenths per system. For Bach preludes,
etudes and similar, put `#(set-global-staff-size 18)` (or 17) right after the `\include` in your
score file — that is your file, not the asset — to get 3–4 bars per system.

## Layout rules the style file already sets
A4, staff size 19, ≤ 5 systems per page, bar number at the start of each system, chord names small,
key cancellation off, piano-cautionary accidentals. You control bars-per-system only with `\break`.
Aim for 3–5 bars per system in 4/4 pop ballads, 4–6 in simpler textures, 2–3 in dense 12/8.

## Errors you will see
- `barcheck failed at: 1/8` → that measure's durations do not add up; count the tokens on that line.
- `warning: cannot resolve rest collision` → two voices with rests at the same time; make one `s`.
- `unterminated slur` → a `(` without `)`, or a slur across `<< \\ >>` voices.
- `Ottava spanner` warnings → `\ottavaOff` missing before a clef change or bar line.
- No output PNG → look at `lilypond.log`; the first `error:` line names file:line:column.

## Fidelity gate (only when a ground-truth score exists)
`\midi { }` makes LilyPond write `score.midi`; `scripts/compare_scores.py gt.musicxml out/score.midi --json out/compare.json`
compares on-beat onsets, durations and staff assignment (through MIDI the same score reads ≈ 0.05 lower than through MusicXML, so the gate is 0.90). Notes you deliberately simplified
(ornament → symbol, doubled octave dropped) lower the number — say so in the report instead of undoing them.
