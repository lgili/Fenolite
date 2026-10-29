## ADDED Requirements

### Requirement: Relative placement resolution
The build SHALL resolve every relative request to a position in integer nanometres: `right_of` puts the subject's box left edge at the reference's right edge plus `gap`, `left_of` its right edge at the left edge minus `gap`, `above` its bottom edge at the top edge minus `gap`, `below` its top edge at the bottom edge plus `gap`; an edge key puts that edge of the box at its value; `align` aligns centres, start edges or end edges on the other axis.

#### Scenario: A capacitor by its pad
- **GIVEN** `examples/relative/pads.py`, where `c5.place(right_of=u1.pad("VDD"), gap=mm("0.5"), by=c5.pad(1))`
- **WHEN** `uv run pytest tests/unit/placement/test_relative.py -k by_pad` resolves it
- **THEN** the left edge of `C5`'s pad 1 box lies 500 000 nm right of the right edge of `U1`'s `VDD` pad box, and both pad centres have the same Y

### Requirement: Measuring boxes
A part's box SHALL be its `footprint_extent` box turned by its rotation and mirrored for the bottom side, or, with `by`, that pad's box; a block instance's box the union of its placed children's boxes; the board's box `outline.outline_box`. A box turned by other than a quarter turn MUST be its axis-aligned bounds rounded outward, and a centre MUST be `(a + b) // 2`.

#### Scenario: Turned part
- **GIVEN** `sen.place(right_of=mcu, gap=mm(3), rot=90)`
- **WHEN** it is resolved
- **THEN** the left edge of the courtyard box of `SEN` turned by 90° lies 3 mm right of the right edge of `MCU`'s courtyard box, and their centres have the same Y

### Requirement: Resolution order
Requests SHALL be resolved in topological order of their references, ties in component-path order. In one frame, positions become known in this order: precedence levels 1 to 3, absolute requests, the frame's strategy, relative requests (which may reference strategy-placed parts), staging. A cycle MUST give `layout.relative-cycle` (error) naming its paths, and the build MUST write nothing.

#### Scenario: A cycle
- **GIVEN** `a.place(right_of=b)` and `b.place(right_of=a)`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` hold `layout.relative-cycle` naming both parts, and nothing is written

### Requirement: Unresolved references
A request whose reference has no placement when its turn comes SHALL give `layout.relative-unresolved` (warning) naming the part and the reference, and the part MUST be staged.

#### Scenario: Reference left in staging
- **GIVEN** `c5.place(right_of=u1)` where `U1` has no placement from any source
- **WHEN** the build runs with `--confirm`
- **THEN** both are staged, `issues` hold one `layout.relative-unresolved` naming `C5` and `U1` and two `layout.unplaced`, and the exit code is 0

### Requirement: Recorded resolutions
Each resolution SHALL be recorded in `result.placement.relative` with `path`, the canonical `request` text, the reference positions used, and `at`, `rotation` and `side`; each block's pose and strategy in `result.placement.blocks`. `.fenolite/build.json` MUST record the resolved block poses. Equal inputs MUST give equal records and equal bytes.

#### Scenario: Read back what was resolved
- **WHEN** `uv run pytest tests/kicad/build/test_relative_build.py` builds `examples/relative/` for targets 9 and 10 and reads the boards back
- **THEN** every footprint lies at the `at` of its record, and every relation holds on the read-back footprints within 1 nm

### Requirement: Block poses applied
Each placement made in a block frame SHALL be composed with the block's pose, and with the poses of every enclosing block; a block without a pose MUST have the identity pose. Quarter turns MUST be exact, and other turns MUST round each coordinate half to even.

#### Scenario: A block moved and turned
- **GIVEN** a block whose parts `U` at (0, 0) and `L` right of `U` with a 1 mm gap, and `p1.place(mm(10), mm(8), rot=90)`
- **WHEN** it is built
- **THEN** `buck1/U` is at (10 mm, 8 mm) from the frame origin, `buck1/L` lies 1 mm above `U`'s turned box (the model's turn is counter-clockwise as shown, Y down), and both are turned by 90°

### Requirement: Rigid block moves
When a block's resolved pose differs from the pose recorded by the previous build, each child placed by the board or the placements file SHALL be moved by the new pose composed with the inverse of the old one, with the copper that c0227's group move moves, and the build MUST give `layout.block-moved` (info).

#### Scenario: Moving a laid-out block in code
- **GIVEN** a confirmed build in which `buck1`'s parts and tracks were laid out in KiCad, after which the script changes `p1.place(mm(10), mm(8))` to `p1.place(mm(20), mm(8))`
- **WHEN** the build runs again with `--confirm`
- **THEN** every part and every track among `buck1`'s pads is 10 mm further right, `issues` hold one `layout.block-moved` naming `buck1`, and copper to parts outside the block stays with `place.copper-left`

### Requirement: Row and column strategies
`row` SHALL place the frame's boxes left to right from `at`, `gap` apart, aligned on their top edges, centres or bottom edges; `column` top to bottom, aligned on left edges, centres or right edges. A strategy MUST take only parts with no request and no placement from levels 1 to 3, and instances without a pose as one box, in creation order.

#### Scenario: A row of three
- **GIVEN** a block with `b.layout(row(gap=mm(1)))` and three unplaced parts created in the order `R1`, `C1`, `R2`
- **WHEN** it is built
- **THEN** their boxes lie in that order from the block origin, 1 mm apart, with equal top edges

### Requirement: Grid and pack strategies
`grid` SHALL use cells of the largest box's size plus `gap`, `columns` per row, each box centred in its cell. `pack` SHALL sort boxes by height, tallest first, then creation order, and place each right of the previous on the current shelf when it fits within `width`, else on a new shelf; a box wider than `width` MUST get its own shelf and `layout.strategy-overflow` (warning).

#### Scenario: Pack within a width
- **WHEN** `uv run pytest tests/unit/placement/test_strategies.py -k pack` packs authored boxes into `pack(width=mm(10), gap=mm(1))`
- **THEN** no box crosses the width except one 12 mm wide box on its own shelf with one `layout.strategy-overflow`, and two runs give the same positions

### Requirement: Strategy groups without a pose
A block with a strategy and no pose, at a top level without its own strategy, SHALL be staged as one box in the staging row, its parts keeping their strategy positions relative to each other.

#### Scenario: A group stays together
- **GIVEN** a block with `b.layout(row())` and an instance without a pose
- **WHEN** it is built
- **THEN** the instance's parts form one row right of the outline at the staging offset, with one `layout.unplaced` per part

### Requirement: Placement-in-code codes
`layout.relative-cycle` (error), `layout.relative-unresolved`, `layout.strategy-overflow` (warning) and `layout.block-moved` (info) SHALL join the layout issue codes, each explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Placement in code".

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** each of the four codes has an entry whose `see` is the heading `build`
