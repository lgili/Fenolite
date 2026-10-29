## ADDED Requirements

### Requirement: Silkscreen clipping
`fenolite silk BOARD --clip` SHALL cut every silkscreen line, arc, circle and rectangle or polygon outline of the board and of its footprints where its ink comes within the margin of a mask opening of its side (a pad's copper grown by its positive mask expansion) or of a pad's hole, writing the rest as lines and arcs. A piece shorter than its stroke MUST be dropped; a filled shape MUST NOT be cut.

#### Scenario: Outline over a pad
- **GIVEN** a footprint whose silkscreen outline crosses its pads
- **WHEN** `uv run pytest tests/unit/silk/test_clip.py -k outline` runs `fenolite silk <board> --clip --confirm`
- **THEN** no silkscreen stroke lies inside a mask opening, and the result holds one `silk.footprint-changed` for that footprint

#### Scenario: Pieces of a line, an arc and a circle
- **GIVEN** a line, an arc and a circle written out with openings across them
- **WHEN** `uv run pytest tests/unit/silk/test_cut.py` cuts them
- **THEN** each piece keeps the reach from every opening, the arc pieces lie on the circle, and a short piece is dropped

### Requirement: Clipped strokes checked
Before writing, every piece SHALL be judged again from what was written, as a thick stroke, against every opening of its side with the margin; a miss MUST be `silk.check-failed` (error) and nothing is written. An uncut item MUST be written byte for byte as read.

#### Scenario: KiCad finds no silkscreen over copper
- **GIVEN** benches whose outlines cross their own pads and a neighbour's pads, on both sides
- **WHEN** `uv run pytest tests/kicad/silk/test_clip_oracle.py` runs `fenolite silk --clip --drc --confirm`
- **THEN** KiCad reports `silk_over_copper` before and none after, and `silk_overlap` and `silk_edge_clearance` do not grow

### Requirement: Clipped footprints and their library
A footprint's own graphics SHALL be cut by its own openings once per group of identical instances and written alike into each, so that `fenolite library` derives one footprint. Each changed footprint name MUST be one `silk.footprint-changed` (info) naming its references; a further cut by another part's opening MUST be `silk.cut-by-other` (warning).

#### Scenario: One footprint for the library
- **GIVEN** three instances of one footprint at 0, 90 and 30 degrees, and one of them beside a foreign pad
- **WHEN** `uv run pytest tests/unit/silk/test_clip.py -k library` clips the board and derives its library
- **THEN** the clean instances give one footprint whose silkscreen drifts from the old library, and the crossed one is `silk.cut-by-other`

### Requirement: Clip options
`--margin LENGTH` SHALL default to the largest `min` of the project's `silk_clearance` rules, else 0. `silk` MUST need `--designators` or `--clip`; with both, the clip MUST run first and the designators be placed against the clipped strokes. Without `--drc` the evidence is `INFERRED` (`H-K-SILK-CLIP`).

#### Scenario: Margin and refusals
- **GIVEN** the authored clip bench with a project rule `silk_clearance` of 0.1 mm
- **WHEN** `uv run pytest tests/unit/silk/test_clip.py -k "margin or refus or both"` runs the command
- **THEN** the rule is the default margin, `--margin` overrides it, a negative margin and a run with neither option exit 2, and both options together place the designators on the clipped board
