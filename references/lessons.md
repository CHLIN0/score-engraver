# Lessons from the improvement loop

Each cycle of the engraving loop appends what went wrong and the rule that fixed it.
Read this before engraving; the newest lessons are at the bottom. Keep entries concrete: piece,
symptom, cause, fix, and which script/flag or checklist item encodes it now.

## Cycle 1 (2026-09-06, Sonnet, no references, Transkun MIDI of 4 pieces)

| piece | symptom on the page | cause | fix (where it lives now) |
|---|---|---|---|
| all | a ♮ printed before almost every note; ♭/♯ on notes already in the key | MIDI-derived pitches carried explicit natural accidentals; no respelling for the key | `quantize_to_score.py` respells for the key and runs `makeAccidentals` — only real accidentals print |
| Bach prelude, nocturne | 16th/32nd rests confetti between melody notes; 1 measure per system | model note-offs end before the next onset (staccato-ish); each gap became a rest | legato fill: gaps shorter than one grid unit are closed (`--no-legato-fill` to disable) |
| Bach prelude | held bass notes chopped into 16ths; urtext has half notes tied | overlapping notes were truncated at the next onset on the staff | held notes (≥ 2× the next note) are kept and put in a second voice (`makeVoices`); their offsets snap to an eighth grid or the next held note |
| Bach prelude | the two held notes of each arpeggio landed in the right hand | pitch split at middle C | `--hands function`: long notes under a moving figure go to the lower staff; short notes over a low bass go up; accompaniment under a sustained melody goes down |
| Chopin Op. 10-12, Scarlatti | unplayable 2–3-octave "chords" | windowed pivot occasionally threw an outlier across hands | pivot now chosen at the largest gap of the local pitch stack only when both sides stay within a 12th |
| Chopin Op. 10-12 | tracker found 96 bars for an 84-bar piece; onset F1 0.13 | DP beat tracker drifted under rubato (locked on a subdivision, then slipped) | prefer `align_to_reference.py` when a reference exists (0.13 → 0.89 on the same file); without one, verify the bar count against the repertoire entry and re-seed the tracker; count the accompaniment stream (4 LH 16ths per beat) when it is continuous |
| Chopin Op. 10-12 | `--pedal` produced nothing; `--dynamics` printed 5–8 marks per bar | pedal text was inserted at Part level after measures existed; dynamics fired on every velocity change | pedal marks go into the right measure on an eighth grid, re-pedals within half a beat collapse, presses closer than a beat collapse; dynamics are per 2-bar window with persistence |
| Chopin Op. 10-12 | MuseScore crashed (no PDF) when hands had different measure counts | parts of unequal length | both parts are padded to the same bar count |
| nocturne | `--triplets` crashed MuseScore | 1/6-quarter grid and tuplets spanning beats produced invalid MusicXML | triplets use only the 1/3-quarter grid and never cross the beat; in compound metres (12/8) do not use `--triplets` at all — the eighths already are the "triplets" |
| nocturne | tempo mark read ♩=66 for a 12/8 piece | metronome referent fixed to quarter | compound metres get a dotted-quarter mark; `--bpm` stays quarter-note BPM for the time map (dotted-quarter × 1.5) |
| all | 22–36 % of measures with a note outside the clef | no 8va / clef-change automation | still open: flagged by lint; put `8va` or a clef change by hand in MuseScore, or accept ledger lines |
| Scarlatti | tracker never locked on the quarter pulse of a 3/8 piece | fastest regular IOI (16th) dominated | seed the tracker at the subdivision and downsample beats (agent did this); repertoire note: Scarlatti sonatas are fast triple metres |

### What the numbers said (cycle 1, no references, Transkun input)
| piece | onset F1 | dur | staff | bars gt/est | verdict |
|---|---:|---:|---:|---|---|
| Bach prelude | 1.000 | 0.77 | 0.82 | 35/35 | structure right, page unreadable (naturals, rests, chopped bass) |
| Chopin nocturne | 0.548 | 0.48 | 0.71 | 38/38 | metre/key/bars right, ornaments and offsets wrong |
| Chopin Op. 10-12 | 0.134 | 0.80 | 0.84 | 84/96 | beat tracking failed under rubato |
| Scarlatti K. 525 | no GT | — | — | — | 3/8 F major plausible, tracker needed manual help |

After the script fixes above (same inputs, measured by the maintainer, not by an agent):
Bach prelude staff 0.85 / dur 0.75, naturals gone, held bass notes as tied half notes;
nocturne dur 0.48 → 0.83, staff 0.71 → 0.74, two measures per system; Chopin Op. 10-12 with a
reference alignment: onset F1 0.885, staff 0.89, 84/84 bars.

## Cycle 2 (2026-09-06, Sonnet, PDMX references allowed, fixed scripts)

| piece | onset F1 | dur | staff | bars | what happened |
|---|---:|---:|---:|---|---|
| Bach prelude | 1.000 | 0.95 | 1.00 | 35/35 | **pass**. Agent found `--hands function` mis-split bar 1 (local window too small at the start) and pre-split by a global duration threshold (held ≥ 1.0 s vs moving ≈ 0.25 s) fed through `--hands tracks`; plus "wide LH cluster keeps its bottom two notes". Both rules are now inside `quantize_to_score.py`. |
| Chopin nocturne | 0.991 | 0.87 | 0.87 | 38/38 | reference (PDMX, another edition) correctly **rejected** (similarity 0.22, coverage 0.64); constant tempo justified by tracker CV 1.1 %; `--split-pitch 67` cut wide chords 33 → 7. Remaining: staff assignment of accompaniment chord tops, ornaments as literal runs. |
| Chopin Op. 10-12 | 0.793 | 0.76 | 0.89 | 84/84 | reference (PDMX r4.92) **accepted** (sim 0.667, coverage 0.765, cost 0.197) → beat map; opening 3-octave run split across hands; the reference's own MusicXML had a corrupt key signature (fixed in `pdmx_to_midi.py`). |
| Scarlatti K. 525 | no GT | — | — | 78 bars | no reference in library (sim ≤ 0.05) → theory path; tracker seeded at the 8th level and downsampled; `--split-pitch 67`; pedal and dynamics now print at sane density. |

Rules learned (now in scripts or SKILL.md):
- Held-vs-moving is best decided globally when durations are bimodal (largest gap in sorted
  log-durations); the local window only as fallback.
- Runs (≥ 6 single notes, one direction, IOI ≤ 0.2 s) stay in one hand (majority vote).
- Two sequential notes that snap to the same slot are spread on the 32nd grid, not stacked as a chord.
- A note that overshoots the next onset by less than one grid unit is legato, not a second voice.
- A whole measure far outside its clef gets a clef change (hysteresis: LH ≥ C4 → treble; RH < G3 → bass).
- `quantize_to_score.py` cannot render a negative quantized onset (a true short pickup); use
  `--anacrusis-beats` to move the barline instead of negative offsets.
- Agents should not need to write their own pre-split; if they do, that is a script gap — record it.

## Cycle 3 (2026-09-06, Opus on the two Chopin pieces, Sonnet on the rest; acceptance round)

| piece | onset F1 | dur | staff | bars | what happened |
|---|---:|---:|---:|---|---|
| Bach prelude | 1.000 | 0.87 | 0.96 | 35/35 | built-in `--hands function` reproduced the urtext split; `--split-pitch 57` fixed the bar-33 pedal-point tail |
| Chopin nocturne | 0.992 | 0.90 | 0.95 | 38/39 | **anacrusis corrected**: the piece starts with a one-eighth upbeat; the agent proved it from the harmonic rhythm (bar basses E♭/C/B♭ every four bars) and shifted the barline with `--anacrusis-beats -5.5`; `--split-pitch 69` keeps the LH chord tops (G4/A♭4) in the lower staff. The extra bar is the silent shifted bar — now `--pickup` turns it into a real pickup measure. |
| Chopin Op. 10-12 | 0.804 | 0.79 | 0.95 | 84/84 | reference-aligned again; `--split-pitch 64`; the opening torrent is a scale with neighbour-note turns, so the strictly monotone run test never fired — run detection is now trend-based (net motion ≥ 7 semitones over ≥ 6 notes) and the torrent stays in the left hand |
| Scarlatti K. 525 | no GT | — | — | 78 | auto clef changes handled the hand-crossing stretch (mm. 61–72) but a recurring low pedal note inside a treble-clef stretch prints as a ledger tower; octave-doubled artifact chords are AMT errors, not engraving errors |

Rules learned (now in scripts or SKILL.md):
- A metronome mark is derived from the beat map when `--beats` is given without `--bpm`.
- A silent first bar plus upbeat (from a negative `--anacrusis-beats`) becomes a real pickup bar with `--pickup`.
- Two-note stacks wider than a tenth are split across staves too (not only ≥ 3-note stacks).
- The "accompaniment below a sustained melody" rule no longer depends on `--split-pitch`.
- Filler rests of the sparser voice are hidden; the two staves are one grand staff (PartStaff), so
  "Pno" is printed once, not per system.
- Staff size is set through MusicXML scaling (`--staff-mm`, default 6.5 mm) — the only layout lever
  that MuseScore honours from the CLI; dense pieces get 3 bars per system instead of 2.
- A PDMX export can be displaced staff-by-staff (one staff 3 eighths late): it looks like "another
  edition" to the fingerprint and fails coverage. Reject it, but its bar content can still corroborate
  a barline decision you derived independently.
- Low `gridness_16th` says nothing about rubato when the melody is ornamented: the direct test is the
  median onset deviation from a constant grid per 40 s window (< 5 ms → constant tempo).
- Still open: `8va` marks for extreme registers; mid-measure clef changes; ornament abstraction
  (fioriture engrave as measured 32nds/64ths); dynamics from a performance with flat velocities are
  meaningless (keep `--dynamics` off when velocity std < 8).

## Cycle 4 (2026-09-06, Sonnet on all four pieces, v4 scripts; acceptance confirmed)

| piece | onset F1 | dur | staff | bars | what happened |
|---|---:|---:|---:|---|---|
| Bach prelude | 1.000 | 0.87 | 0.96 | 35/35 | same as cycle 3, reached without any hand-written pre-split; all three PDMX references correctly rejected (coverage ≤ 0.61); `--dynamics` off by the velocity-std rule. The agent called the bar-1 "eighth rest + half note with the E a sixteenth later" an artifact — it is the urtext rhythm; a phase shift of ±1/16 was tested and drops onset F1 to 0.35/0.86. |
| Chopin nocturne | 0.992 | 0.90 | 0.95 | 38/38 | real pickup bar (`--anacrusis-beats -5.5 --pickup`), `--staff-mm 5.5` → 3 pages, dynamics off (velocity std 4.3). The 39th bar was the final chord's release spilling past the last barline — releases after the final onset now end with the final bar. |
| Chopin Op. 10-12 | 0.802 | 0.79 | 0.94 | 84/84 | reference-aligned to PDMX r4.92 (coverage 0.765). With the *exact* Mutopia edition as reference the same scripts reach 0.898 / 0.80 / 0.93 (coverage 0.883, cost 0.124): the remaining gap is the beat map's source, not the engraving. |
| Scarlatti K. 525 | no GT | — | — | 78 | tracker seeded at the eighth level, downsampled ×2 — the agent wrote its own script for the third time, so `beats_from_midi.py --downsample` now exists (energy-based phase, map extended to both ends). 3/8 F major, 5–7 bars per system, tempo printed as dotted-quarter = bar. |

Rules learned:
- Notes released after the final onset are cut at the end of the final bar — no tail bar of tied chords.
- `beats_from_midi.py --bpm <subdivision bpm> --tighten 400 --downsample 2` replaces hand-written
  downsampling for fast triple metres.
- Reference quality bounds the result under rubato: user edition (PDMX) → 0.80, exact edition → 0.89,
  no reference → 0.13. If the user owns a clean edition of the piece, use it.
- The LLM's visual check catches layout, clef, density and register problems reliably, but it also
  "finds" defects that are correct notation (prelude bar 1) and script gaps that do not exist (the
  tempo mark *is* derived from `--beats`): before reporting a script limitation, reproduce it with
  one command and quote the output.
- `compare_scores.py` counts measures; a GT converted from MIDI may hold the upbeat in a padded
  full bar, so `measure_ok` can differ by one for a correct pickup — read `shift_quarters` and
  onset F1 before treating it as an anacrusis error.
- MuseScore 4's CLI aborts on exit (SIGABRT) after writing complete files on this Mac;
  `render_score.sh` tolerates it. Not a score problem.

## v2 — the engraver writes LilyPond (2026-09-06 afternoon, Opus, real sources)

The reviewer's verdict on v1: numbers against Mutopia are not "optimising", nobody looked at the original
score page by page, the scripts (not the agent) were making the musical decisions, Sonnet needed
four rounds where Opus needs one, and the target is a popular, readable sheet — not an urtext.
v2: `source_dossier.py` → analysis → quantized draft → `score_to_lily.py` → **the agent edits the
LilyPond** → `render_ly.sh` → look at every page next to the reference → rubric → ≤ 2 revisions.

| piece | source | result | what the engraver had to do |
|---|---|---:|---|
| Reflection (Mulan, kno; TranscriptionsByPaul's score on screen) | YouTube frames (13 unique pages) + Transkun | 86 bars, 5 pages, rubric 19/20 every page; page-by-page identical structure, key changes and all 57 chord symbols to the human PDF the agent never saw | rejected constant tempo and the DP tracker (94 bars for 86); built a **score-anchored beat map** from 55 (bar, time) anchors read off chord changes; restored pedal-masked chord tones; wrote the climax run under 8va; two self-revisions (octave error, ledger towers, clef flip-flop) |
| 我的歌聲裡 (曲婉婷, Nice piano sheets) | YouTube frames (32 unique crops, lyrics visible) + Transkun | 58 bars, 4 pages, rubric 17/20; coda 6/8 → 3/8 → 4/4 rubato and the bar-43 key change reproduced from the frames | key spelled G♭ (frames) not F♯ (analysis); DP beat map (8 ms residual vs 52–66 ms constant); rewrote essentially every bar of the draft (spelling, legato values, hands, arpeggio signs, 8va, gliss., fermatas, dynamics); judge round asked for: 16ths instead of 32nds in m.16/36, lyrics, second voices, coda bar count, no clef change in m.1, cautionary accidentals off |

Rules learned:
- The draft is a frame, not a score: expect to rewrite most bars; keep the `% m.N` lines so bar
  checks still name the bar.
- When the source shows the score, read bar numbers off the frames and anchor the beat map to them
  (`beats_from_anchors.py`); trackers and constant tempi both fail on expressive playing.
- Read the reference for spelling (G♭ vs F♯), metre changes, coda structure, dynamics, "with pedal",
  chord symbols and lyrics — and for *what not to write* (this channel prints no chord symbols).
- `piano-cautionary` accidentals litter pop scores with (♭)/(♮); the house style now uses `modern`.
- Script fixes from this round: `quantize_to_score.py` spells scale degrees across the octave
  boundary (C♭4 was B3), `--beats` accepts a bare list, `source_dossier.py` keeps the chord-symbol
  row and lyrics in the crops, `beats_from_anchors.py` exists. Still missing: `--key` changes
  mid-piece in the quantizer (hand-edit the .ly), automatic 8va/clef pass.
- Copyright: a personal-use score of a commercial arrangement may carry the lyrics the reference
  prints; do not download the seller's PDF, and say in the report what was read from frames.
- Judge round on 我的歌聲裡: 6 of 8 requests were right (lyrics, second voices, invented coda bar,
  clef change in m.1, m.37/m.50 melody moved from the LH staff, gliss. text); one was the judge
  misreading dense 16th beams as 32nds — the engraver checked the source and kept them. Reproduce a
  reviewer's claim before acting on it; say so in the report.
- Scrolling-score videos: the "#N" bar label names the leftmost, usually half-hidden bar, and the
  view jumps every 3–4 bars; align bars by the playback cursor position against the beat map (or
  by counting bars from a known anchor), not by the label alone.
- LilyPond: `\accidentalStyle` set on `\Score` is overridden by PianoStaff's built-in `piano`
  style; the house style now sets `modern` on Score, PianoStaff and Staff.

## v2 on the classical benchmark (2026-09-07, Opus, `web_references.py` mandatory)

| piece | reference the agent found itself | result vs v1 |
|---|---|---|
| Bach BWV 846 | Mutopia `wtk1-prelude1` (title search; DTW coverage 1.0) | onset 1.000 / dur 1.000 / staff 1.000, 35/35 (v1: 1.000 / 0.87 / 0.96); two-voice LH like the urtext. The Mutopia file is byte-identical to the GT, so the number is not blind — it proves "right edition found, nothing lost". |
| Chopin Op. 10-12 | Mutopia `op-10-12-wfi` (Peters/Scholtz) — found via the **composer table**, the title search only returned Sor/Giuliani etudes | onset 0.997 / dur 0.954 / staff 0.992, 84/84 (v1: 0.802 / 0.79 / 0.94 with a PDMX user edition); seven AMT errors repaired and listed; slurs, accents, 8va, fff |
| Chopin Op. 9-2 | Mutopia `chopin_nocturne_op9_n2` (Schirmer 1881; DTW coverage 0.996, cost 0.008); John Field's B♭ nocturne (same metre) correctly rejected | onset 0.992 / staff 1.000, 38/38 with a real pickup (v1: 0.992 / 0.95, 38/39); ornaments as grace/acciaccatura/trill, fioriture as cue-size groups, the m.32 cadenza with `\cadenzaOn`; dur 0.86 is LilyPond's MIDI shortening staccato bass notes, not notation. The engraver cross-checked its own MIDI against the edition's MIDI and found two wrong notes that way — do this whenever a reference MIDI exists. |

| Scarlatti K. 525 | nothing downloadable: Mutopia has no K. 525, no YouTube video shows the score, IMSLP has three editions behind a disclaimer click the agent did not perform; it used the GitHub `scarlatti/sonatas-catalog` (K. 525 = **6/8**, F, Allegro), Wikipedia (L. 188) and recording durations (repeats omitted) | 74 bars + upbeat, 3 pages, rubric 17–18 (v1: 78 bars in 3/8). Removed 28 sub-octave 16′-stop artifacts. `beats_from_midi.py` drifts on a running-eighth harpsichord texture; the agent indexed eighths through the note stream instead. |

## v3 — layout like a human, reference read bar by bar (2026-09-07, Opus)

The reviewer's review of the v2 pages: Bach at 4 bars/system left page 2 one-third empty while page 1 was
crowded (the reference's 3 bars/system fills page 2 exactly); the étude's first system forced a
fourth bar that did not fit (the reference starts with 2 bars, then ~3); "plan the layout from bar
density and from why the reference breaks where it does, then judge your own pages and redo them";
and "when the reference score is visible, read its details and absorb them — MIDI is the cross-check".

| piece | what the reference read revealed | layout |
|---|---|---|
| Bach BWV 846 | mechanical diff of both LilyPond sources: 35/35 bars identical, one missing LH fermata (m.35) | 3 bars/system, 6 systems/page, both pages level (v2: 4/system → 5+4, page 2 half empty); the single 2-bar system goes first, under the title |
| Chopin Op. 10-12 | three machine passes (onset+pitch, +duration against the edition's MIDI with articulations stripped, spelling from both .ly files) + 260–340 dpi crops: 7 bars corrected — eighth-note bass over the new figure (m.9/49), a dotted-16th+32nd (m.27), a resonance C5 removed (m.64), third voices held (m.70/80), `ges` not `fis` (m.73). v2 had also printed ink past the right margin on every page — nothing in the pipeline had checked | width budget = note columns + 0.6 × accidentals per bar; 32 systems, the same count and nearly the same breaks as Peters; 2-bar systems where the enharmonic passages carry up to 37 accidentals; staff 18; `page-count = 6` + `\pageBreak` because `\pageBreak` alone was overridden |
| 我的歌聲裡 (on-screen score) | reading every system in three zoomed tiles changed 56 of 57 bars: the print's chord voicings are thicker than the AMT heard (pedal-masked tones), its signature rhythm is dotted-16th + 32nd tied on, it has no rests where v2 invented them, six bars belong to the other hand, three grace notes exist, there is no 8va (ledger lines), the coda is a two-hand arpeggio. Against the quantised draft onset F1 fell 0.907 → 0.688 — the score now follows the print, so that number measures the revision, not a regression | the arranger's own systems (3–4 bars, 2 in the coda) at staff size 16; the house 19 made LilyPond insert its own breaks and produced 6 uneven pages |
| Reflection (human PDF) | the PDF embeds one bitmap per system (sharper than a page render): extracted, barlines detected, every bar cropped with pitch annotations — 62 of 86 bars changed: 24 bars of pedal-masked chord tones the AMT never heard, 7 bars of inferred tones the print does not have, 14 missing arpeggio signs, 24 rhythm/tie errors (one whole LH figure an octave low, the climax run missing an octave), no dynamics in the print, F♭ spellings. The 57 chord symbols were all right | copied Paul's breaks exactly (4 systems on page 1, then 5); last page 0.66 → 0.84 |
| Scarlatti K. 525 | no edition; checking the score's own MIDI clusters against the performance found v2's RH written two eighths late for mm.3–16, two octave errors from `\ottava` (it moves the print, not the pitch), the ostinato's opening chords dropped, the LH an eighth early in mm.40–43; verticals lint 0.81 → 0.98 | 15 systems of near-equal density (39–49 units) snapped to phrase joints, 5 per page; the light ostinato bars get 6-bar systems, the two-voice 16th bars 4 |
| Chopin Op. 9-2 | per-bar note-letter diff against the Schirmer .ly found what eyes missed: B𝄫 spellings (m.28, 31), seven ornaments (pralls m.5/13/27, trills m.21/30, turns m.2/26), LH held voices (m.31/33/34), fioriture printed full size, the edition's hairpins and words, no opening `p` | mirrored the edition: 3 bars/system, 2 where a flourish sits — 13 systems on 3 pages (4/5/4), `ragged-last-bottom` off; four pages would leave two half-empty |

The reviewer's note after v3 (我的歌聲裡 m.5): the arranger gives one note of the verse figure to the right
hand because the left hand would otherwise span too far while holding two tied notes; v2 put that
note in the left hand (and a rest in the right), v3 dropped it altogether. Neither engraver asked
"can a hand do this?" — the rule now lives in SKILL step 5 (playability), rubric R2 and
`playability_lint.py` (span / reach-while-holding / fast leap / crossing, per bar).

v4 sweep of 我的歌聲裡 (all 57 bars, staff placement compared with the print notehead by notehead):
4 bars re-assigned (B♭3 in mm.5/9 to the RH, D♭4 in mm.18/35 to the LH), one hand-over re-timed
(m.43: the giving hand releases where the taking hand attacks), the four rolled 15-semitone LH
chords kept as printed (the uploader's own description names them), and seven bars where the RH
reaches two or three ledger lines below its staff while the LH holds a bass — right as printed,
wrong to a pitch threshold. The five patterns are written up in `hand-assignment.md`.

The reviewer's correction after v4 (authority): the performance MIDI is the *base* — the score records this
performance. A provided PDF, a found edition and on-screen frames are references to learn from:
catch AMT errors only with audio evidence, borrow notation and layout craft, resolve what MIDI cannot
tell (octaves, re-strike vs tie, ornament spelling). And a reference's layout is a lesson, not a
template: Paul's four systems per page are not a constraint on ours. The v3 rule "reference first"
over-corrected; SKILL step 0 and the hard rule now say this.

Rules learned:
- A note that does not fit the hand it was given is never dropped: it moves to the other hand,
  is rolled, or the tie is rewritten — and the reference usually shows which.
- Check staff placement against the print for every bar, not only where a lint flags; the lint
  cannot see a note that was deleted, and a rolled wide chord looks like a span violation.
- When a reference `.ly`/`.mid` exists, diff it against your score mechanically (normalise note
  names, resolve durations, compare per bar); reading pages catches layout, the diff catches notes.
- Layout arithmetic first: bars ÷ bars-per-system → systems ÷ systems-per-page must land on level
  pages; a uniform texture gets uniform systems, a flourish bar gets a shorter system; the first
  system under the title holds one bar fewer; `ragged-last-bottom = ##f` when the last page is ≥ ⅔ full.
- Pedal: reproduce the edition's marks only where they depart from "one press per bass note";
  say so in one italic line under bar 1.
- `page_balance.py`'s page-extent numbers are reliable; its system count is approximate on dense
  pages — use it for page balance, your eyes for crowding.
- Verify the metre from a catalogue before trusting a hint: four v1 cycles used 3/8 for a 6/8 piece.
- When no edition can be downloaded, say so explicitly (R9 = 1) rather than pretending a reference.
- Mutopia's title search is a substring match on a table; catalogue pieces (Op. 10 No. 12) are only
  reachable through the composer table. `web_references.py` now tries both and marks `via`.
- Wikipedia's first hit for "Op. 10 No. 12" was the No. 3 article: pick the hit whose title contains
  every number in the query (fixed in the script).
- With a machine-readable PD edition in hand, YouTube score videos are unnecessary; without one
  (Scarlatti) they are the reference.
- Dense sixteenth textures need staff size 17–18 (`score_to_lily.py --staff-size`, or edit the
  score file); the house 19 gives two bars per system.
- Copying spellings from a Mutopia `.ly`: check its `\include` language (deutsch: h/b/his).
- A reference that *is* the ground truth makes the gate meaningless as a test; say so in the report.

## v5 → audio evidence (2026-09-07, 我的歌聲裡)

The rule: the performance MIDI is the base; a note the reference prints but the AMT did not hear
may only be kept with audio evidence. `verticals_lint.py` (pass 0.766 on v5) could say *which* bars
had more attacks than the performance, not whether the recording supported them.
`scripts/audio_evidence.py` now answers that per note:

- v5: 1383 score notes, 1199 heard by the AMT, 184 not in the performance MIDI → 25 supported
  (pedal-masked tones the AMT missed — keep), 39 weak (editorial small notes or drop), 88 displaced
  (the pitch was played, ≥0.2 s from the written beat — check the rhythm), **32 unsupported in 18 bars
  (mm.12, 15, 21–26, 28, 29, 32, 38, 41, 46, 48, 50, 51, 55) — printed voicings the performer did not
  play; drop.** m.41 alone prints five such notes (G♯4 D♯5 at beat 2.5, D♯4 at 3 and 4, D♯2 at 3.5).
- Timing must come from the notes, not from `beats.json`: the beat map had 239 beats for a 228-beat
  score and stretched the coda's ritardando by ~3 s, which made the whole of m.53 look unplayed
  (24 false "unsupported"). Anchoring a piecewise warp on DTW-matched events (the same aligner as
  `align_to_reference.py`) fixed it; tracker beat maps are for quantising, not for evidence.
- Match score notes to performance notes one-to-one. With many-to-one matching a repeated-note
  figure (8 written, 6 played) reports nothing; one-to-one leaves two notes for the audio to judge.
- Thresholds are self-calibrated on the recording (rise of the notes the AMT heard: p10 8 dB,
  p25 11 dB, median 16 dB here); a fixed dB threshold was wrong by the same amount as the room.
- The onset tolerance is 0.2 s ≈ a sixteenth at 64 bpm; 0.12 s produced 40 extra "displaced" notes
  that were only warp error.

## Reflection v4 — hand sweep, MIDI-first (2026-09-07, Opus, 525k tokens, 52 min)

Correction applied: the performance MIDI is the base; the human PDF is a reference to learn from.
- 15 bars re-assigned, 11 of them with `\change Staff` (the print's cross-staff hand-over); seven
  patterns written into `hand-assignment.md`. Playability cross 8 → 1, verticals 0.849 → 0.879.
- Of v3's "restored pedal-masked tones" (taken from the PDF), ~20 notes in 13 bars were not played:
  the beat-2 G4 in mm.43/51/66/74/79 (the AMT resolves E♭4 inside that attack, never a G4), the
  F♭5 in mm.42/50/65/73 (the chord had been read an octave high), and single tones at mm.1, 11, 44,
  49, 56, 67, 68, 73, 79, 81, 82. Kept with audio support: m.12 A♭4, m.70 A♭2, m.86 A♭2; added from the
  performance: m.77 C4, m.54 B♭4. `audio_evidence`: 1178 notes, 1120 heard, 58 missing → 6
  supported / 12 weak / 36 displaced / 4 unsupported (the 4 explained: a tied octave, a chord struck
  0.6 beat early, one alignment slip).
- Three tests per doubtful note, in this order: bar-local diff on the beat map, the bar's onset
  dump with velocity + CC64 (pedal), `audio_evidence.py`. Roll-across-the-barline explains most
  "phantoms" before any audio is needed.
- Layout: 24 systems (4 + 5 + 5 + 5 + 5), the same count as Paul's print but a different division —
  each bar's width budget (note columns + 0.35 × extra noteheads) partitioned for equal system width:
  Paul's systems run 21.7–44.6 units (sd 7.4), ours 22.5–41.5 (sd 4.9). Breaks forced only at the
  key changes, *a tempo*, the climax and the coda. Five systems on page 1 do not fit under the title
  (0.246 + 5 × 0.172 > 1). Fill 0.69 / 0.86 / 0.81 / 0.85 / 0.83, rubric 19/20 per page.

## v7 — page count, not page fill (2026-09-07, a question about pages 3/4)

The reviewer asked why 我的歌聲裡 page 3 had four systems and page 4 five (v4–v6 all inherited v3's breaks).
Cause: the `\pageBreak` before m.44 put the modulated final chorus at the top of a page; 13 bars of
chorus texture made four systems on page 3, and `ragged-bottom = ##f` spread them over the page
(system gap 212 px vs 139 px elsewhere), so `page_balance` saw a "full" page (extent 0.843) and no
flag fired. Fix: move the break three bars later → 4+5+5+4, last page lighter (0.65) — the right
trade. Rules added: page breaks are decided *after* system breaks by counting systems; middle pages
carry the same number; a section start does not need a new page; `page_balance` now flags a
stretched page and only flags a last page under 60 %.
