## ADDED Requirements

### Requirement: Negative silk clearance
`design.rules.rule(name, "silk_clearance", min=...)` SHALL accept a `min` below zero, which lets silkscreen
overlap by up to that much; every other kind SHALL refuse a negative `min` with `DslError` (change c0427,
`H-K-DRU-NEG-SILK`).

#### Scenario: KiCad reads it
- **WHEN** `uv run pytest tests/kicad/rules/test_negative_silk.py -q` runs DRC on two footprints whose silkscreen lines overlap by 0.05 mm, on 9.0.9 and 10.0.6
- **THEN** a board-wide minimum of 0 reports `silk_overlap`, -0.1 mm reports none, and the canary fires both times

#### Scenario: The import says it
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k negative -q` imports a rule `silk_clearance (min -0.254mm)`
- **THEN** the script holds `design.rules.rule("silk", "silk_clearance", ...)` and the built rules file holds -0.254 mm

### Requirement: Drawings on paste layers
A drawing call (`line`, `rect`, `circle`, `arc`, `polygon`, `text`) SHALL accept `F.Paste` and `B.Paste`
(change c0427, `H-K-PASTE-DRAWING`).

#### Scenario: A paste polygon builds
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k paste -q` builds the imported script
- **THEN** the board holds a filled `gr_poly` on `B.Paste`

### Requirement: A user drawing arc may have zero width

`Design.arc` SHALL accept an explicit zero width on a standard user drawing layer or a declared
`User.N` layer. Its three points MUST form a curved arc. Other layers SHALL still require positive
width.

#### Scenario: A zero-width drawing arc builds

- **WHEN** a board declares a curved arc of width `0mm` on `Dwgs.User`
- **THEN** its generated KiCad file holds the arc with `(width 0)`

### Requirement: A board may have no closed outline

`Design.board(outline=())` SHALL declare the board and its layer table without generating a closed
outline. Existing drawing calls on `Edge.Cuts` SHALL remain available to record individual edges.
A zone on such a board MUST provide its own outline, and a cut-out or milled slot requires a closed
board outline.

#### Scenario: An open edge builds

- **GIVEN** an outline-less board with one line on `Edge.Cuts`
- **WHEN** it is built as KiCad
- **THEN** the board holds the line with its stated width and no generated outline

### Requirement: Assign a net to an unnumbered copper pad

`Part.unnumbered_pad_net(index, net)` SHALL assign a concrete `Net` to one physical pad
with an empty number, indexed from zero among that footprint's unnumbered pads in stored
order. It SHALL leave symbol pins and net members unchanged. A duplicate index, a missing
pad or a pad that cannot carry copper SHALL be refused.

#### Scenario: A physical pad shares a net with a symbol pin

- **GIVEN** a footprint with a numbered pad and two unnumbered copper pads
- **WHEN** its numbered pin and the second unnumbered pad are assigned to the same net
- **THEN** the board has both connections and the schematic net still has only the numbered pin

## MODIFIED Requirements

### Requirement: Copper tables in the DSL
`Design.track_table(key, *, net, layer, width, rows_nm, locked=False)`, `Design.arc_table(key, *, net, layer, width, rows_nm, locked=False)` and `Design.via_table(key, *, net=None, diameter, drill, rows_nm, kind="through", layers=None, locked=False, protection=None)` SHALL each record one copper intent of many items. Rows MUST be tuples of `int` nanometres in the frame of `place()`: `(x1, y1, x2, y2)`, `(sx, sy, mx, my, ex, ey)` and `(x, y)`.

A via table without `net`, or with `net=None`, SHALL record and write vias on no net. The diameter,
drill, via kind and span MUST still be explicit as required for a table. `Design.via` and a via step
within a path retain their existing net requirements.

#### Scenario: Table of two segments
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.track_table("GND/F.Cu/1", net=gnd, layer="F.Cu", width=mm("0.25"), rows_nm=((0, 0, 5_000_000, 0), (5_000_000, 0, 5_000_000, 5_000_000)))`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the model holds two tracks of `GND` on `F.Cu`, from (100 mm, 100 mm) to (105 mm, 100 mm) and on to (105 mm, 105 mm), each 250 000 nm wide

#### Scenario: Via table on no net
- **WHEN** an authored design records a via table with no net and explicit diameter and drill
- **THEN** the written via has those dimensions and span and is on no net
