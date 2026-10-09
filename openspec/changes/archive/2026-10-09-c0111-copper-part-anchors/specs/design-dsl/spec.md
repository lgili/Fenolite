## ADDED Requirements

### Requirement: Copper anchors in the DSL
`Part.at(dx=None, dy=None) -> AnchorRef` and `PadRef.at(dx=None, dy=None) -> AnchorRef` SHALL name a point in the frame of the part's footprint as its library draws it (X to the right, Y down), measured from the footprint's origin or from the position of the pads the `PadRef` names, and the copper calls of "Copper intents in the DSL" SHALL accept an `AnchorRef` wherever they take a point, in addition to the forms that requirement gives. The build resolves the point after placement (`manual-copper`, "Anchored points in script copper").
- `dx` and `dy` MUST be lengths as "DSL lengths and angles" defines them; one left out is 0. `PadRef.at` keeps the number and the index of its reference.
- An `AnchorRef` MUST be accepted as a path element of `Design.track`, as the `mid` or the `end` of `arc_to`, as a point of the `along` or the `region` of `Design.stitch`, and as its `origin`. `via_step(at, *, to, diameter=None, drill=None, kind="through")` and `Design.via(key, at, *, net, diameter=None, drill=None, kind="through", layers=None)` MUST also take the point as one argument, an `AnchorRef` or an `(x, y)` pair, in place of `x` and `y`; the forms with `x` and `y` keep working, and `diameter`, `drill`, `kind` and `layers` MUST mean in the one-argument forms what "Copper intents in the DSL" says.
- `Design.stitch` MUST also take `region=part.pad(number, index=…)`: the copper of that pad (`manual-copper`, "Stitching vias"). Such a region is not a ring, so the three-point rule of "Copper intents in the DSL" does not apply to it, and its `origin` MUST be left out or be an `AnchorRef`.
- In a track path an `AnchorRef` is a point: it joins no pad and gives the track no net.
- `DslError` MUST be raised at the call for: a `dx` or `dy` that is not a length; an `AnchorRef` or a pair given to `via_step` or `Design.via` together with `y`, or a lone first argument that is neither; a `PadRef` where a point is expected (`at`, `mid`, `end`, an `along` or `region` point, `origin`), with a message naming `.at()`; a board-point `origin` given with a pad region; and two consecutive path elements that are equal `AnchorRef`s.
- `dsl.copper(design)` MUST return `Anchor(component, number, index, offset)`, a frozen dataclass of `dsl/intents.py`, wherever an `AnchorRef` was given: the part's component path, the pad number as text or `None`, the index, and the offset as a `Point` of `int` nanometres, not shifted by `BOARD_ORIGIN`. A pad region MUST be returned as `PadEnd(component, number, index)` in `StitchIntent.region`. An `AnchorRef` or a pad region of a part that is not in the design MUST raise `DslError` naming it.
- `fenolite.dsl` MUST re-export `AnchorRef` and `Anchor`, as "DSL package" allows. The package keeps importing only the standard library, `core` and `model`, and `to_model` MUST NOT change. A script without anchors MUST record the same intents as before.

#### Scenario: Anchors recorded
- **GIVEN** the blink with `design.via("fan9", u1.pad(9).at(mm(0), mm(1)), net=vin, diameter=mm(0.6), drill=mm(0.3))` and `design.track("stub", r1.pad(2), r1.pad(2).at(mm(1)), width=mm(0.3))`
- **WHEN** `copper(design)` is called
- **THEN** the via intent's `at` is `Anchor("U1", "9", None, Point(0, 1_000_000))`, and the track's path is `PadEnd("R1", "2", None)` then `Anchor("R1", "2", None, Point(1_000_000, 0))`

#### Scenario: A thermal stitch recorded
- **GIVEN** a design with a part `U1` and `design.stitch("ep", net=gnd, pitch=mm(1), region=u1.pad(33), diameter=mm(0.6), drill=mm(0.3), margin=mm(0.1))`
- **WHEN** `copper(design)` is called
- **THEN** the `StitchIntent` has `region == PadEnd("U1", "33", None)`, `along == ()` and the default `origin`, the board corner, which "Stitching vias" reads as the pad's position

#### Scenario: One-argument points and earlier forms
- **GIVEN** the blink with three track intents whose via step is `via_step(mm(36), mm(14), to="B.Cu")`, `via_step((mm(36), mm(14)), to="B.Cu")` and `via_step(u1.at(mm(2)), to="B.Cu")`
- **WHEN** `copper(design)` is called
- **THEN** the first two steps equal `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`, and the third has `at == Anchor("U1", None, None, Point(2_000_000, 0))`

#### Scenario: A blind via at an anchor
- **GIVEN** a four-layer design with `design.via("esc", u1.pad(9).at(mm(0), mm(1)), net=vin, kind="blind", layers=("F.Cu", "In1.Cu"))`
- **WHEN** `copper(design)` is called
- **THEN** the via intent has `at == Anchor("U1", "9", None, Point(0, 1_000_000))`, `kind == "blind"` and `layers == ("F.Cu", "In1.Cu")`

#### Scenario: Refused anchor calls
- **WHEN** `u1.at(1, 2)`, `design.via("v", u1.pad(1), net=gnd)`, `via_step(u1.at(), mm(1), to="B.Cu")`, `design.stitch("s", net=gnd, pitch=mm(1), region=u1.pad(33), origin=(mm(1), mm(1)))` and `design.track("t", u1.at(mm(1)), u1.at(mm(1)), net=gnd)` are called
- **THEN** each raises `DslError`, the second naming `.at()`

#### Scenario: Part not in the design
- **GIVEN** a via intent at `r9.pad(1).at()` of a part `R9` that was never added
- **WHEN** `copper(design)` is called
- **THEN** `DslError` is raised naming `R9`
