# Notation rules the engraver must obey (piano, two staves)

These are the conventions a pianist expects. Violating them is what makes a page "correct but
unplayable". Every rule maps either to one of the score checks — `verticals_lint.py` (simultaneities that the
performance does not have), `playability_lint.py` (span, reach, leap, crossing),
`audio_evidence.py` (printed notes the recording does not support), `page_balance.py` (page fill,
right margin, a stretched page) — or to the visual checklist you run on the rendered pages.

## Metre and barlines
- Choose the time signature from the recurring accent pattern, not from the first bar. 3/4 vs 6/8:
  6/8 groups eighths in two threes (dotted-quarter pulse); 3/4 groups in three twos.
- The first downbeat is where the harmonic/accent pattern starts. An upbeat (anacrusis) before it
  becomes a partial first measure; the last measure is shortened to complement it.
- A change of metre mid-piece is rare in this repertoire; if the tracker suggests one, suspect
  rubato or a wrong pulse level first.

## Pulse level and grid
- Pick the beat level so that the most common note value is an eighth or sixteenth. If most notes
  become 32nds, halve the tempo (the tracker locked onto a subdivision); if most become quarters or
  longer with many ties, double it.
- Default grid: 16th notes. Allow 32nds only when a passage genuinely has them (ornaments, fast
  scales in slow tempo). Allow triplets per beat when a beat's onsets fit thirds better than
  quarters (compound feel, triplet accompaniments as in Nocturne Op. 9 No. 2's 12/8 feel).
- Never leave rests shorter than a 16th between notes of the same voice: those are unquantized
  offsets. Extend the note to the next onset (legato) or to the beat.

## Key
- Use the key-profile estimate but confirm from the final cadence and the most frequent
  accidentals. Minor keys: prefer the harmonic-minor reading (raised 7th appears as accidental).
- Write accidentals consistently with the key: in F major spell B♭, not A♯. music21's
  `Key` + MuseScore respelling handle most of this; check the first page for odd enharmonics.

## Hands and staves
- Upper staff = right hand (treble clef), lower staff = left hand (bass clef). Split by musical
  function, not only by pitch: accompaniment figures belong to the left hand even when they rise
  above middle C; a melody in the bass register may move to the lower staff with a treble clef.
- A chord wider than a tenth in one hand is unplayable for most pianists; split it across staves
  or arpeggiate.
- Change clef when a staff stays far outside its range for more than a bar; do not flip clefs
  every bar. Use 8va for long high passages instead of ledger-line towers.

## Voices
- Sustained notes under a moving line are a second voice (stems down), not truncated notes and not
  rests. Two voices per staff maximum in this repertoire; more means the split is wrong.
- Ties: only across barlines or to notate a duration that has no single symbol. If more than
  ~30% of notes carry ties, the barline or grid is wrong.

## Rhythm spelling
- Beam by beat; dotted rhythms rather than tied pairs where the grid allows.
- Tuplets need a bracket and a number; do not mix triplet and duplet subdivisions inside one beat
  unless the music really does.

## Dynamics, articulation, pedal
- One dynamic at the start and one at each change of level that lasts at least two bars; derive
  levels from velocity bands (pp <32, p <48, mp <64, mf <80, f <96, ff <112, fff).
- Hairpins for gradual changes over a bar or more (optional in v0).
- Pedal: "Ped." at CC64 ≥ 64 and "*" at release, under the lower staff; collapse changes closer
  than a beat.
- Tempo: one metronome mark at the top (rounded to a common value: 60, 66, 72, 80, 88, 96, 104,
  112, 120, 132, 144, 160); add an Italian term when the character is obvious (Andante, Allegro).

## Layout (MuseScore defaults are good; check these)
- 4–6 measures per system for dense music, up to 8 for sparse. No system with a single bar.
- Title and composer at the top; page numbers; no orphan last system with one bar.
- The first page must show clef, key, time signature and the tempo mark.
