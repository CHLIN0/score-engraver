# Where reference scores come from, and how much to trust them

| source | what it is | how to search | trust | notes |
|---|---|---|---|---|
| Local GT library (`<repo>/engrave/gt/`) | Mutopia editions converted to MusicXML with MuseScore; curated by hand | `find_reference.py --library <dir>` (title words + melodic fingerprint) | high | used as ground truth by the benchmark harness; if you are being evaluated on the same piece, the harness tells you whether you may use it |
| Mutopia Project (mutopiaproject.org) | ~2 000 public-domain LilyPond editions, with PDF/MIDI | browse by composer: `cgibin/make-table.cgi?Composer=ChopinFF`; download `.mid` and convert with `mscore -o x.musicxml x.mid` | high (edited by humans, urtext-ish) | no MusicXML; the MIDI is score-exact so conversion is clean |
| PDMX (Zenodo 13763756, v1 tarball) | 254 077 public-domain MuseScore user scores as MusPy JSON (notes, tempo map, time/key signatures, barlines) + metadata CSV | index at `<repo>/data/pdmx/PDMX/PDMX.csv` (columns: title, composer_name, rating, n_tracks, path→`./data/X/Y/<CID>.json`); list members with `tar -tzf PDMX.tar.gz \| grep <CID>`, extract with `tar -xzf PDMX.tar.gz -T members.txt`, then `scripts/pdmx_to_midi.py <dir>` → score MIDI + MusicXML; keep converted refs in `<repo>/engrave/ref/pdmx/` with readable names and `index.json` | medium: user-made | filter: rating ≥ 4.5, `n_tracks` 1–2 for piano, avoid titles with "easy", "arr", "duet", "organ", "jazz"; 12 % of entries have license conflicts — prefer `subset:rated` rows; bar counts may include an empty pickup bar |
| IMSLP | scanned PDFs, some MusicXML | manual (browser, account for some downloads) | high for scans, not machine-readable | last resort; not automated here |
| MuseScore.com live | same population as PDMX but current | not automated (TOS); PDMX is the sanctioned snapshot | — | — |

Known PDMX defects seen so far: exports without key signature (spelled in sharps for a flat piece —
fixed in `pdmx_to_midi.py` by dropping rootless key signatures); a single flattened part with no
staff information (cannot inform hand assignment); one staff displaced by a few eighths relative to
the other (fails alignment coverage even though the notes are right). Check `bars`, `tracks` and the
rendered page before trusting one.

## Finding references yourself (v2: `scripts/web_references.py`)
Given a title/composer the script queries Mutopia (downloads the PD edition: .ly is the ground
truth for key/time/bar structure, the -a4.pdf is what you look at), IMSLP (list + links; open in a
browser, never script the download), YouTube (search "… sheet music": videos that show the score
on screen are the best visual reference for pieces without a PD edition — run `source_dossier.py`
on one), and Wikipedia (key, opus, form, tempo). Typical picks: classical → Mutopia .pdf + .mid;
film/pop → a sheet-music video; anything → Wikipedia to confirm the key and structure. Reject what
does not match the performance (transposition, arrangement, different version) and say why.

## Using a reference correctly
1. Fingerprint first (`find_reference.py --midi in.mid`), title second. Similarity ≥ 0.35 and the
   title agree → candidate. Similarity high but title different → still a candidate (titles lie).
2. `align_to_reference.py` must report coverage ≥ 0.7 and mean_cost ≤ 0.4; otherwise reject.
3. Adopt from the reference: time signature, bar length, anacrusis, key signature, the beat map
   (rubato-aligned), and staff/voice assignment as a *prior*. Do not copy notes, dynamics or
   ornaments the performance does not contain; do not "fix" wrong notes to match the reference.
4. Transposed reference (align reports `transposition_semitones` ≠ 0): keep the performance's key;
   only the structure transfers.
5. Record in `engrave-report.json` → `reference`: path, similarity, coverage, mean_cost, adopted,
   rejected.
