## ADDED Requirements

### Requirement: Footprints are re-placed on a read board
`fenolite.backends.kicad.replace.move_footprint(design, footprint_id, *, at=None, rotation=None, side=None, definitions=None, force=False) -> Design` SHALL return `design` with that footprint at the new placement and nothing else changed.
- **Translation.** When the rotation and the side stay, only `FootprintInstance.position` MUST change; every slot of the footprint MUST stay.
- **Rotation or side change.** The footprint MUST be replaced by `embed.place_footprint` of `definitions[<lib_ref>]` at the new placement, with its component, its lock, and `key` equal to its `fenolite.path` property when it has one and to its reference otherwise. The new footprint MUST keep the old one's uuid, user properties, Reference and Value, and each pad MUST take the net of the old pad with the same number.
- Without a definition for the footprint's `lib_ref`, a rotation or side change MUST raise `PlacementError` carrying `place.no-definition` naming the reference.
- A locked footprint MUST raise `PlacementError` carrying `place.locked` unless `force` is true.
- An unknown `footprint_id` MUST raise `PlacementError` carrying `place.unknown-ref`.
- The board order of footprints MUST be kept, and the written board MUST pass `roundtrip.rt1`.

#### Scenario: Translation keeps every slot
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb` read with `read_board`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_replace.py -k translate` moves `R1` by 2 mm and writes the board
- **THEN** the footprint node differs from the original only in its `at` position, and every other root child is tree-equal

#### Scenario: Rotation from the definition
- **GIVEN** the authored project and the definitions of its `fp-lib-table`
- **WHEN** `move_footprint` rotates `U1` to 90° and flips `R1` to the bottom
- **THEN** each new footprint equals `place_footprint` of its definition at that placement, with the old uuid, Reference, Value and pad nets

#### Scenario: No definition
- **GIVEN** a board whose `R1` has a `lib_ref` that `definitions` lacks
- **WHEN** `move_footprint` is asked to rotate it
- **THEN** `PlacementError` is raised with `place.no-definition` naming `R1`, and a translation of the same footprint succeeds

#### Scenario: Locked footprint
- **GIVEN** a locked footprint
- **WHEN** `move_footprint` runs without `force`
- **THEN** `PlacementError` is raised with `place.locked`

### Requirement: Board outline as rings
`fenolite.backends.kicad.outline.board_outline(design) -> BoardOutline` SHALL give the board outline as closed rings in the board frame, without a snapping tolerance (`H-G-EDGE-EXACT`):
- from `Board.outline.points` when the model has an outline (`source == "model"`);
- otherwise from the root graphics on the layer of kind `edge`, chained by `geometry.assemble_rings` (`source == "edge"`); circles are rings by themselves;
- `rings[0]` MUST be the ring of largest area, and the others its cut-outs;
- when no ring closes, `rings` MUST be empty and `problem` MUST be one of `open-contour`, `no-edge-content` and `footprint-edges-only`;
- `exact` MUST be false when an arc was approximated.

`H-G-PLACE-OUTLINE` MUST be measured over the readable non-heavy demo boards and its counts recorded.

#### Scenario: Model outline
- **GIVEN** a built blink model
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_outline.py -k model` calls `board_outline`
- **THEN** `source` is `model` and the ring holds the outline's points

#### Scenario: Edge graphics with a cut-out
- **GIVEN** an authored board with four `gr_line` items forming a rectangle and a `gr_circle` inside it, all on `Edge.Cuts`
- **WHEN** `board_outline` runs
- **THEN** `source` is `edge`, `rings[0]` is the rectangle and `rings[1]` the circle's ring

#### Scenario: Open contour named
- **GIVEN** the same board with one line removed
- **WHEN** `board_outline` runs
- **THEN** `rings` is empty and `problem` is `open-contour`

#### Scenario: Demo outlines counted
- **WHEN** `uv run pytest tests/corpus/test_outline_corpus.py` runs over the cached readable non-heavy demo boards
- **THEN** no call raises, and the counts of `model`, `edge` and each `problem` are recorded for `H-G-PLACE-OUTLINE`
