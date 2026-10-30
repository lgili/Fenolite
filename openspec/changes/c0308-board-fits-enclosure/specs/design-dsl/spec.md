## ADDED Requirements

### Requirement: Fitting a board to an enclosure
`Design.fit(box, *, mount, at, rot=0)` SHALL record one fit and return a `Fit`; `fenolite.dsl` SHALL re-export `Enclosure`, `Fit` and `Aperture`. `mount` MUST name a mount with derived `usable` and `zones`, `rot` MUST be 0, 90, 180 or 270, and a second call MUST raise `DslError`. The call alone MUST add no item to the design.

#### Scenario: Recorded, nothing generated
- **GIVEN** the blink and the fixture `corner-bosses`
- **WHEN** `uv run pytest tests/unit/dsl/test_fit.py -k recorded` calls `design.fit(box, mount="bosses", at=(mm(60), mm(40)))` and `to_model(design)`
- **THEN** the model equals the blink's without the call, and `fit_record(design).pose` is `(60_000_000, 40_000_000, 0)`

#### Scenario: Refused calls
- **WHEN** `design.fit(box, mount="nope", at=(0, 0))`, `design.fit(box, mount="bosses", at=(0, 0), rot=45)` and a second valid call are made
- **THEN** each raises `DslError`

### Requirement: Fit outline and holes
`Fit.outline` SHALL be the mount's usable ring in the board frame as a closed path with its arcs, and `Fit.holes(prefix="H", pad=None)` SHALL call `design.hole()` once per boss in name order, drill from the screw, courtyard the head plus twice the obstacle clearance, locked, with a `MechanicalIntent` anchor naming box, mount and boss.

#### Scenario: Four holes
- **WHEN** `uv run pytest tests/unit/dsl/test_fit.py -k holes` builds the blink with `design.board(outline=fit.outline)` and `fit.holes()`
- **THEN** the model holds parts `H1` to `H4` at the transformed boss centres, each locked, and `placements(design)` gives each an anchor whose key starts with `enclosure/`

### Requirement: Fit zones
`Fit.zones()` SHALL add one rule area per zone, `enc.top.<zone>` on `F.Cu` or `enc.bottom.<zone>` on `B.Cu`, and record each limit computed from the zone's Z, the board thickness and the clearances. A zone whose limit is 0 or less MUST forbid footprints. No `HeightLimit` MAY be added.

#### Scenario: Limits and keep-outs
- **GIVEN** the fixture with `lid.underside_z` 35 mm, `pcb_bottom_z` 6 mm, boss tops at 6 mm and the clearances 0.5 mm, and a stack-up of 1.6 mm declared first
- **WHEN** `uv run pytest tests/unit/dsl/test_fit.py -k zones` calls `fit.zones()`
- **THEN** `enc.top.lid` has the limit 26.9 mm, each `enc.bottom.B<n>` forbids footprints, and `RuleSet.heights` is empty

### Requirement: Fit faces and apertures
`Fit.face(part, face, *, aperture, gap=mm(1), protrude=0)` SHALL record a face rule for one of the six faces. `Aperture.rect`, `Aperture.circle` and `Aperture.path` SHALL give the opening in the face frame with a clearance; a wall face MUST have `z`, and `top` or `bottom` MUST NOT.

#### Scenario: A wall aperture without height
- **WHEN** `fit.face(j1, "front", aperture=Aperture.rect(mm(9), mm(3)))` is called
- **THEN** `DslError` names `z`

### Requirement: Fit record in a build
`fenolite build` SHALL write `.fenolite/enclosure.json` (`fenolite.enclosure-fit.v0`) with the box embedded, its SHA-256, mount, pose, thickness and source, generated holes and zones, and face rules, for both targets. A design without `fit` MUST write no such file and the bytes it wrote before.

#### Scenario: Record written and unchanged designs
- **WHEN** `uv run pytest tests/unit/cli/test_build_fit.py` builds `examples/enclosure/fit_box.py` and the blink with `--dry-run --json`
- **THEN** the first plan holds `.fenolite/enclosure.json` that loads with the fit reader, and the blink's plan holds no such file and its usual bytes
