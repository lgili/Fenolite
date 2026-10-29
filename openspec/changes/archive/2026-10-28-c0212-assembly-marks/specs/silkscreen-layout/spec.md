## ADDED Requirements

### Requirement: Text ink extents
`fenolite.silk.extents.ink_box(text, *, size, stroke, measure=None, cache=None) -> Ink` SHALL give the box of a stroke text's ink relative to its anchor in its reading frame, half the drawn stroke included. With `measure` (a `kicad-cli` render of a scratch board) the box MUST be read from the plot, cached per tool version, string, size, stroke and justification, and be `KICAD-VERIFIED`; without it, estimated and `INFERRED`.

#### Scenario: Extent of a designator
- **GIVEN** `kicad-cli` and the text `R12` at 1 mm with a 0.15 mm stroke
- **WHEN** `uv run pytest tests/kicad/silk/test_extents.py -k r12` measures it
- **THEN** the box equals the ink of the same text drawn on a board within 10 µm, and a second call reads it from the cache

### Requirement: Glyph table
`fenolite.silk.extents.estimate(key)` SHALL lay out the text's glyphs by the advances and ink boxes that `tools/measure_glyphs.py` measured with `kicad-cli` (`silk/data/glyphs.toml`), with the measured baseline, stroke clamp and justification shifts, grown by 1 µm. A glyph the table lacks MUST only grow the box. The table MUST hold boxes and advances only.

#### Scenario: The estimate holds the render
- **GIVEN** `kicad-cli` and thirteen designators at three widths, strokes and justifications
- **WHEN** `uv run pytest tests/kicad/silk/test_extents.py -k "estimate or table"` runs
- **THEN** each estimate holds the drawn ink within 10 µm, and the table measured again equals the shipped one

### Requirement: Designator placement
For each part whose visible `Reference` field is on a silkscreen layer, the search SHALL try twelve places beside its courtyard box per height and board angle (0 or 90°), on its side's silkscreen, mirrored on the bottom. A place MUST keep the clearance from pad copper of that side, holes, silkscreen strokes, other texts, other parts' courtyards and the board edge, and lie inside the board.

#### Scenario: Dense row of resistors
- **GIVEN** an authored board with ten two-pad parts in a row at 1.6 mm pitch, each designator over its pads
- **WHEN** `uv run pytest tests/unit/silk/test_designators.py -k dense` runs `fenolite silk <board> --designators --confirm`
- **THEN** no text comes within the clearance of a pad or another text, each is nearer to its own part than to any other, and the edges of the texts that face the row lie on one line

### Requirement: Designator search
The cost SHALL grow with distance and offset from the own part, nearness to a foreign part, an angle across the part's long side and a smaller size. Identical parts in a row or column MUST share one slot when all are free there; the others go greedily, most constrained first, then a blocked part may push one text aside. `--keep` MUST keep every free text; a part without room keeps its text with `silk.no-place`.

#### Scenario: Search rules
- **GIVEN** parts and obstacles written out as rectangles
- **WHEN** `uv run pytest tests/unit/silk/test_layout.py` runs the search
- **THEN** a row shares one slot, an obstacle moves a text, a repair pushes one text aside, `keep` holds a free text, and a text that stays is kept clear

### Requirement: Placed designators checked
Before writing, each placed designator SHALL be boxed again from its written field and MUST keep the clearance from every obstacle and every other designator, lie inside the board, read at 0 or 90°, be mirrored exactly on the bottom, and be at least the project's `min_text_height` and `min_text_thickness` (else 0.8 mm and 0.08 mm). A miss MUST be `silk.check-failed` (error) and nothing is written.

#### Scenario: KiCad finds no silkscreen fault
- **GIVEN** the row bench and a bench of top and bottom parts at 0°, 90° and 30° with a hole, every designator over its pads
- **WHEN** `uv run pytest tests/kicad/silk/test_designators_oracle.py` runs `fenolite silk --designators --drc --confirm`
- **THEN** KiCad reports `silk_over_copper` and `silk_overlap` before and no silkscreen or text finding after, and draws each designator within 1 µm of Fenolite's box

#### Scenario: A failed check writes nothing
- **GIVEN** a search that puts a designator on its own pads
- **WHEN** `uv run pytest tests/unit/silk/test_designators.py -k failed_check` runs the command
- **THEN** it exits 5 with `silk.check-failed` and the board is unchanged

### Requirement: Silk command
`fenolite silk PATH --designators [--keep] [--refs GLOB]... [--sizes LENGTHS] [--angles 0,90] [--clearance LENGTH] [--gap LENGTH] [--measure auto|kicad|estimate] [-o FILE] [--drc]` SHALL place designators under the mutation protocol (schema `fenolite.silk.v0`). `--drc` MUST compare `kicad-cli` DRC before and after: a grown type is `silk.drc-new`, else `KICAD-VERIFIED`.

#### Scenario: Options and refusals
- **GIVEN** the authored benches
- **WHEN** `uv run pytest tests/unit/silk/test_designators.py` runs the command with `--keep`, `--refs`, `--sizes`, `--angles` and bad values
- **THEN** only the asked texts move, the looks follow the options, and a missing `--designators`, an angle of 45 or a size below the least text height exits 2
