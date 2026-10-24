## ADDED Requirements

### Requirement: Text ink extents
`fenolite.silk.extents.ink_box(text, *, size, stroke, font=None) -> Box` SHALL return the box of the ink of a stroke text in its own frame, from the start of its skeleton, including half the stroke on each side.
- With `kicad-cli` present, the box MUST come from a render of the text on a scratch board (`kicad-cli pcb export svg`), cached per font, size, stroke and string under the cache folder; the result's evidence is `KICAD-VERIFIED`.
- Without it, the box MUST be an estimate from the font's advance widths that Fenolite records with their source, and the evidence MUST be `INFERRED`.

#### Scenario: Extent of a designator
- **GIVEN** `kicad-cli` and the text `R12` at 1 mm with a 0.15 mm stroke
- **WHEN** `uv run pytest tests/kicad/silk/test_extents.py -k r12` measures it
- **THEN** the box equals the ink of the rendered text within 10 µm, and a second call reads it from the cache

### Requirement: Designator placement
`fenolite silk BOARD --designators [--keep] [--sizes LENGTHS] [--angles 0,90]` SHALL place the reference text of every part on its silkscreen side, under the mutation protocol (schema `fenolite.silk.v0`).
- The obstacles of a text MUST be, on its side: pads with their mask margin, drills, other silkscreen, the courtyards of other parts, the board edge and slots.
- The candidates of a part MUST be positions around its courtyard at each allowed angle and size; the cost of a candidate MUST grow with its distance to its own part and with its nearness to a foreign part, and MUST prefer the part's axis angle and the largest size.
- The search MUST start greedy (most constrained part first) and improve by best-response sweeps until no text moves or a round limit is reached; similar parts in a row or a column MUST get aligned texts when the alignment costs no overlap.
- `--keep` MUST move only texts that overlap an obstacle.
- A part whose text has no free candidate MUST be reported with `silk.no-place` (warning) and keep its text where it was.
- The placements MUST be written into the board and into a record beside it (`silk-placements.toml`), which a rebuild applies.

#### Scenario: Dense row of resistors
- **GIVEN** an authored board with ten 0603 resistors in a row at 1.6 mm pitch
- **WHEN** `fenolite silk <board> --designators --confirm` runs
- **THEN** no text overlaps a pad, a drill or another text, each text is nearer to its own part than to any other, and the texts of the row share one baseline or one column

### Requirement: Silkscreen clipping
`fenolite silk BOARD --clip [--margin LENGTH]` SHALL cut every silkscreen stroke and the footprints' own silkscreen at each mask opening grown by `--margin` (default the board's silk-to-mask rule), under the mutation protocol, and SHALL report each footprint whose own graphics changed with `silk.footprint-changed` (info), because its library must be made again from the board (`design-conversion`, "Library made from a board").

#### Scenario: Outline over a pad
- **GIVEN** a footprint whose silkscreen outline crosses its pads
- **WHEN** `fenolite silk <board> --clip --confirm` runs
- **THEN** no silkscreen stroke lies inside a mask opening, and the result holds one `silk.footprint-changed` for that footprint
