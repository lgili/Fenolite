## ADDED Requirements

### Requirement: Generated copper calls
`Design.band`, `keepout_ring`, `barrier`, `body_keepout`, `fanout_zone` and `stitch_pieces` SHALL check their arguments at the call (`DslError`) and record plain data under `<call>.<name>`, returned by `fenolite.dsl.generated(design)` (requirement "DSL package"). The KiCad build MUST resolve them after placement and script copper into locked zones, rule areas, tracks and vias whose names and ids derive from the key, so a rebuild replaces them and nothing else.

#### Scenario: Recorded at the call
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k record` calls each of the six with valid and invalid arguments
- **THEN** `generated(design)` holds one record per call in key order, and a diagonal spine, an unknown forbid kind or a reused name raises `DslError`

### Requirement: Power band
`band(net, spine, *, width, layers, max_width=None, step=None, clearance=None, priority=0, name=None)` SHALL be one locked zone. Each side widens on its own in levels of `step` up to `max_width / 2` where it keeps `clearance` (else the net's class clearance) from other nets' copper; a level change MUST be a 45° edge, outer corners bevels, and a segment shorter than five widths MUST widen by at most one level.

#### Scenario: A band keeps its clearance
- **GIVEN** the blink with `band(vin, spine, width=mm(3), max_width=mm(6), step=mm(0.5), layers=("B.Cu",), clearance=mm(1))` along a spine 3.6 mm from the pads of `D1`
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k band` builds it
- **THEN** the band zone keeps 1 mm from other nets' copper, every edge is a multiple of 45°, the side near the pads stays at 2.5 mm and the far side reaches 3 mm

### Requirement: Keep-out ring around holes
`keepout_ring(part, *, setback, layers=None, forbid=("tracks", "vias", "pours"), sides=32, name=None)` SHALL write, around each hole of `part`, a rule area of `sides` sides whose every edge keeps `drill / 2 + setback` from the hole's centre (a slot: the hull of its two end polygons). A part without a hole MUST give `kicad.generate.no-hole`.

#### Scenario: A ring holds the circle
- **GIVEN** a 3 mm hole and `keepout_ring(hole, setback=mm(2), sides=16)`
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k ring` builds the script
- **THEN** one rule area of 16 points is written and every point of the circle of radius 3.5 mm lies inside it

### Requirement: Class barrier
`barrier(netclass, *, setback, layers=None, forbid=("tracks", "vias", "pours"), pieces=False, name=None)` SHALL group the class's copper into pieces whose envelopes grown by `setback` meet, and write for each piece the band between its convex envelope and that envelope grown by `setback`, as two rule areas. Several pieces MUST give `kicad.generate.pieces` unless `pieces=True`; another net's pad inside a band's outer envelope gives `kicad.generate.encloses`.

#### Scenario: A barrier in pieces is refused
- **GIVEN** a class `HV` whose copper lies in two regions 10 mm apart
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k barrier` builds `barrier("HV", setback=mm(2))`, then the same with `pieces=True`
- **THEN** the first build writes nothing and names `pieces=True`; the second writes four rule areas

### Requirement: Body keep-out
`body_keepout(part, *, setback, layers=None, forbid=("tracks", "vias", "pours"), name=None)` SHALL write one rule area: the convex hull of the part's plan view (its body outlines, else the courtyard of its own side) grown by `setback`. A part with neither MUST give `kicad.generate.no-plan`.

#### Scenario: Keep-out under a part on the other side
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k body` builds `body_keepout(r1, setback=mm(0.5), layers=("B.Cu",))`
- **THEN** one rule area on `B.Cu` holds the courtyard of `R1` grown by 0.5 mm

### Requirement: Fan-out to a zone
`fanout_zone(net, *, side="top", refs=None, width=None, diameter=None, drill=None, clearance=None, name=None)` SHALL give each SMD pad of `net` on `side` (of `refs`, when given) a short track and a through via placed by the rules of the plane fan-out. The net MUST hold a zone on another copper layer (`kicad.generate.no-zone`); a via MUST NOT overlap any pad's copper or another drill; sizes come from the arguments or the net's class (`kicad.generate.size-missing`).

#### Scenario: A pad joined to the bottom pour
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k fanout` builds the blink with a `GND` zone on `B.Cu` and `fanout_zone(gnd)`
- **THEN** the `GND` pad of `U1` gets one track and one via, clear of every other pad

### Requirement: Stitching of zone pieces
`stitch_pieces(net, *, pitch, layers=None, min_vias=2, diameter=None, drill=None, clearance=None, margin=None, name=None)` SHALL place through vias of `net` on a grid of `pitch` inside each overlap of two zones of the net on different listed layers, clear of other nets' zones there and filtered as `stitch()` filters its vias. An overlap with fewer than `min_vias` vias MUST give `kicad.generate.stitch-short`.

#### Scenario: Two pours tied
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k stitch` builds a `GND` zone on `F.Cu` over part of the board and one on `B.Cu`
- **THEN** every via lies inside both outlines, at least two are written, and none comes nearer other copper than the clearance

### Requirement: Generated copper codes
The codes `kicad.generate.altium`, `unknown`, `off-board`, `no-hole`, `no-plan`, `no-zone`, `size-missing`, `pieces`, `name-taken`, `crossing` (error), `unplaced`, `band-narrow`, `encloses` and `stitch-short` (warning) SHALL be the table `GENERATE_ISSUE_CODES` of `fenolite.backends.kicad.generate`, each explained by `fenolite explain`. An error of a call MUST create nothing for that call and stop the build's write.

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `kicad.generate.*` code has an entry
