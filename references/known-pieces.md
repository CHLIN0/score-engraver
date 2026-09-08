# Repertoire knowledge (use to sanity-check decisions, never to override the input MIDI)

## How to use this file
1. Identify the piece from the hint + the music (key, metre, texture). Write your confidence.
2. Look up the entry; compare bar count, metre, key, texture with what analyze_midi.py shows.
3. Disagreements are information: a performance may omit repeats, add a cadenza, be transposed,
   or be an arrangement. Note the disagreement in the report and follow the input.

## Textures that decide hands and voices
- **Broken-chord prelude (Bach BWV 846 type)**: each beat is one chord arpeggiated as 16ths; the
  urtext keeps the two lowest notes in the left hand as held notes (half notes tied), the upper
  three in the right hand as 16ths. A pitch split at middle C puts everything in the right hand —
  wrong. Split by function: notes that are held while the figure moves belong to the lower staff.
- **Nocturne / song-with-accompaniment (Chopin Op. 9 type)**: left hand = bass note + chord pattern
  in compound metre (12/8 or triplet 4/4); right hand = ornamented melody. Ornaments (turns,
  grace notes, runs of 7–11 notes against 3 beats) are *not* on the grid — quantize them as
  grace notes or small tuplets, do not let them push the melody off the beat.
- **Etude with continuous left-hand 16ths (Chopin Op. 10 No. 12 type)**: left hand is an unbroken
  16th-note line (4 per beat); right hand = octave/chord melody in dotted rhythms. Time signature
  4/4 (Mutopia edition) though some editions print 2/2; grid 16 is enough; pedal changes per bar.
- **Scarlatti sonata**: binary form with both halves repeated; performers may skip repeats, so a
  score-based bar count can be double the performed length. Fast triple metres (3/8, 3/4) and
  hand-crossings are common — a note below the left hand's range may still be the right hand.
- **Fugue / invention**: 2–4 independent voices; do not split by pitch only, keep voice identity;
  a voice may cross staves.

## Entries (verified from Mutopia / MuseScore public-domain sources)
| piece | key | metre | bars | tempo | notes |
|---|---|---|---:|---|---|
| Bach, WTC I Prelude in C, BWV 846 | C major | 4/4 | 35 | ♩≈60–72 | 16th arpeggios, two held LH notes per bar; bars 33–35 pedal points on G and C |
| Chopin, Nocturne Op. 9 No. 2 | E♭ major | 12/8 | 34 (+ coda; Mutopia edition prints 38) | ♪≈132 (Andante) | LH bass+chord triplets, ornamented RH; fioriture in bars 16, 24, 32; cadenza-like run before the end |
| Chopin, Etude Op. 10 No. 12 "Revolutionary" | C minor | 4/4 (2/2 in some editions) | 84 | ♩≈160 (Allegro con fuoco) | LH continuous 16ths; RH dotted-rhythm octaves; ends fortissimo on C major chord |
| Scarlatti, Sonata K. 525 (L. 188) | F major | 6/8 (catalogue: github.com/scarlatti/sonatas-catalog; the running eighths group in threes, LH rests on every third) | binary with repeats | Allegro | not in Mutopia/PDMX as of 2026-09; no symbolic reference — judge visually |

Add a row whenever a new piece is engraved and its reference verified.
