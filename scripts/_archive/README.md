# Archived — kept for history, not on any current path

Nothing in the skill calls these. They are here rather than deleted so the v1 cycles in
`references/lessons.md` stay readable.

| file | why it is here |
|---|---|
| `render_score.sh` | v1 rendered through MuseScore (`mscore -o score.pdf`). v2 onward writes LilyPond directly and renders with `render_ly.sh`. |
| `quantize_to_score_v1.py`, `quantize_to_score_v2.py` | the first two quantizers; `quantize_to_score.py` (v4.1) replaced both. |
| `lint_score.py` | v1's single lint over the quantized MusicXML. Replaced by four narrower checks on the engraved score: `verticals_lint.py`, `playability_lint.py`, `audio_evidence.py`, `page_balance.py`. |

MuseScore itself is still a dependency, but only as a **converter**: `setup.sh` checks for `mscore`,
and `references/reference-sources.md` uses it to turn a Mutopia `.mid` into MusicXML for comparison.
It no longer engraves anything.
