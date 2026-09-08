# Hand assignment — the engraver's craft, not a pitch threshold

A transcription gives you *which notes*; engraving decides *which hand*. The staff a note sits on
is a performance instruction. Get it wrong and the page is unplayable even when every pitch is right.
The rule of thumb "below middle C = left hand" is where the draft starts, not where the score ends.

## What a hand can do
- **Span**: most hands hold an octave comfortably, a 9th with effort, a 10th only stretched (or
  rolled). Two simultaneous notes wider than a 10th in one hand are not a chord, they are two hands
  or an arpeggio sign.
- **Holding while reaching**: a hand that keeps a key down (a held bass, a tied note, a dotted
  inner voice) can only reach what its remaining fingers cover — about a 6th above a held thumb-side
  note, less below a held little-finger note. A tied bass plus a chord a 10th above it in the same
  hand is the classic impossibility; the print solves it by giving the top note to the other hand
  or by letting the pedal hold the bass.
- **Leaps at tempo**: the left hand jumps octaves all day, but an octave-and-a-half leap inside a
  sixteenth with no rest, or a leap that lands on a chord, is a smell — check whether the print
  splits the figure between hands.
- **Crossing**: hands may cross (the print shows it with staff changes or cross-staff beams), but a
  crossing that the print does not show is usually a mis-assignment.

## Which hand takes a note
1. **The line owns the note.** A note that continues a melodic line stays with the hand playing
   that line; the accompaniment does not borrow melody notes even when they lie low.
2. **The busy hand gives, the free hand takes.** A chord tone that the accompaniment hand cannot
   reach while holding its bass goes to the melody hand — written in the melody staff as a second
   voice (stems down) or as the bottom note of the melody chord, *not* as an extra note stacked
   into the left-hand chord.
3. **Ties never change hands.** If a tied note forces an impossible reach, move the *moving* notes,
   not the tied one.
4. **Broken chords wider than a 10th are split** at the point where the hand would have to jump:
   bottom notes left, top notes right (pop ballads: bass + 5th/octave left, the chord's upper tones
   right under the melody), or the figure is beamed across staves when the print does so.
5. **Rolled chords** (`\arpeggio`) let one hand "play" a wide chord in sequence — use them where the
   print prints the wavy line, never as a way to keep an unplayable stack in one hand.
6. **Inner voices** in a two-voice texture go to whichever hand's position already covers them; the
   stem direction tells the player which hand (up = right, down = left within a shared staff).
7. **Doublings** the AMT heard (octave ghosts, pedal resonance) that no hand could add are artifacts,
   not assignment problems — remove them and say so.

## How the print tells you
- Which staff a note sits on, its stem direction, cross-staff beams, `\change Staff`, brackets and
  the "l.h./r.h." (m.g./m.d.) marks — read them bar by bar; when our assignment differs from the
  print, the print is right unless it is physically impossible for the performance you transcribed.
- Popular-sheet conventions: LH = bass note + fifth/octave + at most one chord tone within a 10th;
  RH = melody on top + harmony tones within an octave below it; verse figures often put the chord's
  top note in the RH so the LH can hold a rolled two-note bass.

## Editorial aids a performer is grateful for (use sparingly)
- `l.h.` / `r.h.` (or m.g./m.d.) at a hand-over that the staff placement alone does not make obvious.
- An arpeggio sign where a chord must be rolled; `\arpeggio` across both staves when the roll spans hands.
- A fingering number only at the one awkward spot per page (a thumb-under in a run, a stretch), never
  everywhere.
- An ossia (small staff) for a passage most hands cannot manage as written — the print's solution
  and a simpler one side by side.
- Pedal: one line at the start plus marks only where the pattern changes; a `senza Ped.` where the
  texture must stay dry.
- Ties vs re-strikes: write what the pianist should do, not what the AMT heard twice.

## Check it, every time
- `scripts/playability_lint.py compare.midi` — span / reach-while-holding / fast leap / crossing per
  bar. Answer every flag in the report: changed (how) or playable because … (the print shows a roll,
  the crossing is intended, the span is a 9th for a large-hand arrangement).
- Then read your own pages as a pianist: where would *you* put each hand? A note that cannot be
  played by the hand it is given is moved, rolled or re-tied — never deleted.

## Patterns seen in practice (from 我的歌聲裡, Nice piano sheets — v4 sweep)

- **rolled-bass keeps the hand; the line's note goes to the melody hand** (bars 5, 9): the LH rolls a wide bass chord (G-flat2/D-flat3/A-flat3, 14 semitones) and holds it as a half note; the verse figure's first 16th, B-flat3, is a whole tone above the held top note and a major 10th above the held bottom note → the B-flat3 is printed in the TREBLE staff on a ledger line and beamed as the first 16th of the RH group; the LH chord keeps only its three rolled tones — the B-flat3 is not a chord tone of the bass roll, it is the first note of the A-flat/B-flat alternation that runs through the whole bar - the line owns it. A hand fully stretched from G-flat2 to A-flat3 has no finger left above its thumb.
- **inner tone under the melody goes to the accompaniment hand** (bars 18, 35): beat 4 carries the melody B-flat4 plus a D-flat4 a sixth below it; the LH is otherwise idle on that beat and its next event is D-flat2/D-flat3 → B-flat4 alone in the treble staff; D-flat4 in the bass staff, beamed into the following bass eighth — the D-flat4 belongs to the bass line (it is the anticipation of the next bar's D-flat), not to the melody chord; giving it to the free hand keeps the RH melody a single line and removes a needless rest from the LH
- **hand-over on the same keys: the giving hand releases where the taking hand attacks** (bars 43): the RH plays a low <bes ees' f' g'> dotted eighth and the LH then plays <ees' f' g'> - the same three keys → the print's horizontal spacing puts the RH chord a 16th earlier (beat 2.25) so its dot runs out exactly on the LH's attack at beat 3; the closing RH group is printed 16th + 8th + 16th — two hands cannot hold the same key; the release has to be written, not left to the player
- **the melody hand reaches down under the bass** (bars 16, 21, 27, 33, 37, 39, 40): the accompaniment hand is holding a low octave or a bass pedal, and a mid-register chord (E-flat3 to C-flat4, i.e. two or three ledger lines below the treble staff) has to sound → the chord is printed in the TREBLE staff on ledger lines, not moved into the bass staff — the LH cannot leave its bass; the RH is free between melody notes. Reading three ledger lines is cheaper than an impossible stretch.
- **wide bass chords are rolled, never split or thinned** (bars 5, 6, 9, 10): LH chords of 14-15 semitones (G-flat2/D-flat3/A-flat3, F2/D-flat3/A-flat3, E-flat2/B-flat2/G-flat3) → an arpeggio sign on every one of them; the uploader's own video description says so: '5~9 小節左手第一拍有音程跨度較大的琶音, 這邊可以做一點彈性速度' (bars 5-9, the LH's first beat has a wide-interval arpeggio; take a little rubato there) — a roll converts a span the hand cannot grasp into a sequence it can; the sustain pedal holds what the fingers leave

## Patterns seen in practice (from Reflection, kno Piano Music — v4 sweep, 86 bars against a human print)

- **roll across the barline is an AMT artefact, not a missing note** (20 bars: 2, 4, 8, 18, 19, 21, 24,
  25, 32, 41, 45, 49, 53, 62, 64, 72, 76, 81, 82, 86): the lower tones of a rolled chord are struck in
  the last eighth of the previous bar, so a bar-local diff files them one bar early and calls the
  chord "phantom". Print one arpeggio sign with every tone on the beat; check the roll before you
  remove anything. This was the single largest source of false alarms.
- **the line owns the note — print it once** (bars 1, 11, 25, 26, 82): the top of the LH's rising
  figure lies in the RH's register; it is easy to write it in the RH chord *and* in the LH figure.
  Print it once, with the hand whose line it continues (cross-staff stem from the lower staff if it
  sits in the treble).
- **cross-staff hand-over at the end of the bar** (bars 11, 23, 41, 42, 49, 50, 52, 61, 64, 65, 72, 75,
  80): the LH's closing two or three eighths rise above the RH's held chord — a crossing on paper, a
  hand-over in fact. Print those notes in the treble staff with a cross-staff beam (`\change Staff`)
  so the reader sees the hand-over and the RH chord is not asked to keep the keys; when the LH stays
  high for several bars (m.23, m.80–82) a clef change in the bass staff reads better than repeated
  staff changes. Playability "cross" flags went 8 → 1 with this alone.
- **ledger lines beat a clef change for a short rising figure** (bars 13, 18, 19, 38, 40, 48, 54, 58,
  63, 67, 71, 83): the LH reaches A♭4/B♭4 for one or two eighths while the treble staff is busy with
  the melody — three or four ledger lines above the bass staff; a clef change or cross-staff stem
  would collide with the melody.
- **the release is written, not left to the player** (bars 41, 49, 64, 72): when the LH takes keys
  the RH is still holding, the RH chord becomes a half note, the LH's notes go cross-staff, the pedal
  carries the sound. Two hands cannot hold the same key.
- **a print solution can be rejected — with the reason** (m.1): the print beams F3–C4–G4–A4 across
  staves; LilyPond cannot find a beam slope and pushes C4/G4 into the inter-staff gap with fresh
  ledger lines. Three ledger lines in one staff is the better page. Say so in the report.
