## ADDED Requirements

### Requirement: Mechanical primitives and locked anchors
As an extension of "DSL package", `fenolite.dsl` SHALL re-export `MechanicalIntent`.
`Part.place` SHALL accept a `MechanicalIntent` as `anchor` only when `locked=True`; the board-origin translation MUST be applied once. Holes and keep-outs are `Design.hole` (c0102) and `Design.rule_area` (c0103) and carry no intent: `fenolite.dsl.KEYS` SHALL hold no row `hole` or `keepout`. The intent SHALL stay in the DSL `placements` output only.

#### Scenario: Board origin and fixed interface
- **GIVEN** a part placed with `place(mm(7), mm(4), locked=True, anchor=intent)` on a board declared by `Design.board`
- **WHEN** `placements(design)` and `to_model(design)` are read
- **THEN** the placement is at `BOARD_ORIGIN + (7 mm, 4 mm)`, translated once, it carries `intent` unchanged, and the model's board holds no hole

#### Scenario: No neutral hole or keep-out call
- **WHEN** `Design` and a `Design` instance are inspected
- **THEN** neither offers `keepout` nor `keepouts`, and `fenolite.dsl.KEYS` has no row `hole` or `keepout`

## MODIFIED Requirements

### Requirement: Board and placements in the DSL
`Design.board(width, height, copper=2, planes=None)` SHALL declare a rectangular board, its copper layer count and its internal planes, and `Part.place(x, y, rot=0, side="top", locked=False, anchor=None)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline, with Y down. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the outline is written from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` is written at `BOARD_ORIGIN + (x, y)`.
- `width` and `height` MUST be positive lengths. `copper` MUST be 2 or 4.
- An inner copper layer is a signal layer unless `planes` names it. `planes` MUST be `None` or a mapping from an inner layer name (`"In1.Cu"`, `"In2.Cu"`) to a `Net` or a net name: that layer is an internal plane on that net. `DslError` MUST be raised at the call for `planes` with `copper=2`, a key that is not an inner layer name, and a value that is neither a `Net` nor a valid net name. A plane holds one net; split planes cannot be declared.
- `Design.planes` MUST hold the mapping from layer name to net name, in layer order, empty by default. `planes(design) -> Mapping[str, str]` (`dsl/convert.py`, re-exported by `fenolite.dsl` as "DSL package" allows) MUST return it and MUST raise `DslError` naming a net that the design does not hold.
- A plane is a build parameter, as `copper` is: `to_model` MUST NOT change, the model gets no plane entity, and a plane layer stays a layer of kind `copper`. What a target does with a plane is its build's rule ("Planes in a build").
- `rot` is the model rotation, the stored footprint angle on both sides (c0017).
- `placements(design) -> Mapping[str, Placement]` MUST map each placed component path, in path order, to `Placement(at, rotation, side, locked, anchor=None)`. Unplaced parts MUST be absent.

#### Scenario: Placement in board coordinates
- **GIVEN** `r1.place(mm(10), mm(5), rot=90, side="bottom", locked=True)`
- **WHEN** `placements(design)["R1"]` is read
- **THEN** it equals `Placement(Point(110_000_000, 105_000_000), 90_000_000, "bottom", True)`

#### Scenario: Unsupported copper count
- **WHEN** `design.board(mm(50), mm(30), copper=3)` is called
- **THEN** `DslError` is raised

#### Scenario: Unplaced parts are absent
- **GIVEN** a design with `R1` placed and `R2` not placed
- **WHEN** `placements(design)` is called
- **THEN** its keys are exactly `("R1",)`

#### Scenario: Ground plane declared
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})`, where `gnd` is the net `GND` of the design
- **WHEN** `planes(design)` is read
- **THEN** it equals `{"In1.Cu": "GND"}`, and `to_model(design)` equals the model of the same script without `planes`

#### Scenario: Malformed planes fail at the call
- **WHEN** `design.board(mm(50), mm(30), planes={"In1.Cu": gnd})`, `design.board(mm(50), mm(30), copper=4, planes={"F.Cu": gnd})` and `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": 3})` are called on fresh designs
- **THEN** each raises `DslError`, the second naming `F.Cu`

#### Scenario: Plane on a net that is not in the design
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In2.Cu": "NOPE"})` and no net `NOPE`
- **WHEN** `planes(design)` is called
- **THEN** `DslError` is raised naming `NOPE`

An `anchor` SHALL be a `MechanicalIntent` and SHALL require `locked=True`. It SHALL be retained in the DSL `placements` output only; build and rebuild do not persist it in native files or `.fenolite/`.

#### Scenario: Anchor requires a lock
- **WHEN** `Part.place` is called with an anchor and `locked=False`
- **THEN** it raises `DslError` naming `locked=True`
