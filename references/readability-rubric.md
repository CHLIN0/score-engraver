# Readability rubric — "would a good amateur pianist put this on the stand?"

Score every page; the judge reads the rendered PNG next to the reference pages (dossier sheets,
ground-truth pages, or the style anchors). 0 = fails, 1 = acceptable, 2 = good. A page needs ≥ 15/20
and no 0 in R1–R4 to pass. Record per-page scores and the concrete defects (bar numbers) in
`engrave-report.json` → `readability`.

| # | criterion | 2 | 0 |
|---|---|---|---|
| R1 | Barlines and metre | downbeats land on the harmonic/accent changes; correct upbeat; time signature matches how the music moves | bars feel shifted; wrong metre; extra/missing bars |
| R2 | Hands (playability) | RH = melody + upper chord tones, LH = bass + accompaniment; no chord wider than a 10th in one hand; no melody note buried in the LH staff; no hand asked to hold a (tied) note while reaching more than a 10th away — such notes belong to the other hand; no LH leap over an octave and a half inside a sixteenth without a rest; `playability_lint.py` flags answered one by one | notes obviously in the wrong hand; unplayable stacks; a note silently dropped because it did not fit the hand it was given |
| R3 | Rhythm notation | note values readable at tempo: beams by beat, no confetti rests, ties only where needed, ornaments as symbols or grace notes | walls of 32nds, rests between every note, ties across every barline |
| R4 | Pitch notation | accidentals follow the key; enharmonics sensible (no B♯ in F major); clef and 8va keep notes within ~3 ledger lines | naturals everywhere; ledger towers; wrong key signature |
| R5 | Voices | ≤ 2 voices per staff, used only for held notes under motion; stems and rests of the second voice do not collide | voice spaghetti; hidden/overlapping rests |
| R6 | Chord symbols (pop / jazz) | one per harmonic change, correct root and quality, slash bass where the bass differs | wrong, missing, or one per beat |
| R7 | Dynamics, tempo, pedal | tempo word + metronome at the start; a few dynamics where the music changes; "with pedal" once or real pedal marks; no clutter | none at all, or marks on every bar |
| R8 | Layout | 3–5 bars per system (2–3 in dense 12/8), 4–5 systems per page, no orphan single-bar system, bar numbers at system starts, title block | 1–2 bars per system or 8+; page half empty; missing numbers |
| R9 | Faithfulness to the reference | same structure (intro/verse/chorus lengths), same key, the reference's own ornaments and voicings respected where the audio has them | different key/metre than the reference without justification; sections missing |
| R10 | Cleanliness | no LilyPond warnings that change the look (collisions, unterminated spanners); consistent fonts; no stray text | visible collisions; overlapping symbols; debug text |

Judge protocol (main session or a second-family reviewer):
1. Open our page N and the reference material that covers the same bars side by side (use bar numbers
   and the dossier timestamps: seconds ≈ bar × beats × 60 / bpm).
2. Fill the table for the page; write each defect as `m.<bar> <staff>: <what> → <fix>`.
3. Hand the defect list (not the scores) back to the engraver for the next revision.
4. Two revisions maximum; then deliver with the remaining defects listed under `residual_issues`.
