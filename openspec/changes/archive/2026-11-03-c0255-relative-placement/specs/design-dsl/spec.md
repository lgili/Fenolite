## ADDED Requirements

### Requirement: Relative placements in the DSL
`Part.place` SHALL also accept, as keywords, the relations `right_of`, `left_of`, `above` and `below` with `gap` (a length, default 0) and `align` (`"center"`, `"start"` or `"end"`), the edge keys `left`, `right`, `top`, `bottom`, `center_x` and `center_y`, and `by` (a pad of the part itself). A call with any of them MUST record a `RelativeRequest`, returned by `relative_requests(design)` and absent from `placements(design)`.

#### Scenario: A request is recorded, not resolved
- **GIVEN** `u1.place(mm(14), mm(15))` and `c5.place(right_of=u1.pad("VDD"), gap=mm("0.5"), by=c5.pad(1))`
- **WHEN** `placements(design)` and `relative_requests(design)` are read
- **THEN** the first holds only `U1`, and the second holds `C5` with the reference `U1.pad(VDD)`, the gap 500 000 nm and `by` pad `1`

### Requirement: Placement references
A relation SHALL take a `Part`, a `PadRef`, a block instance or the `BoardRef` that `Design.board` now returns. An edge key SHALL take a length of the frame or an edge expression: a reference's `left`, `right`, `top`, `bottom`, `center_x` or `center_y`, plus or minus a length. `by` MUST be a pad of the placed part; anything else MUST raise `DslError`.

#### Scenario: An edge expression
- **GIVEN** `board = design.board(mm(40), mm(30))`
- **WHEN** `j1.place(left=board.left + mm(2), center_y=board.center_y, rot=90)` is called
- **THEN** the request holds `left = board.left + 2 mm` and `center_y = board.center_y`, and `j1.place(left=board.left * 2)` raises `DslError`

### Requirement: Axis determination
Each axis SHALL be set by exactly one source: X by `x`, `left`, `right`, `center_x`, `right_of` or `left_of`; Y by `y`, `top`, `bottom`, `center_y`, `above` or `below`. A relation sets its other axis by `align` unless an explicit key sets it. Two sources for one axis, an axis with none, or `gap` or `align` without a relation MUST raise `DslError` at the call.

#### Scenario: Conflicting sources
- **WHEN** `c5.place(mm(1), right_of=u1)`, `c5.place(right_of=u1, left_of=u2)`, `c5.place(left=mm(1))` and `c5.place(mm(1), mm(1), gap=mm(1))` are called on fresh parts
- **THEN** each raises `DslError` naming the axis or the key

### Requirement: Locked relative placements
A locked relative request SHALL reference only locked parts or pads of locked parts, locked block instances, or the board; any other reference MUST raise `DslError` when the design's placements are converted, naming the unlocked reference.

#### Scenario: A locked part next to an unlocked one
- **GIVEN** `u1.place(mm(14), mm(15))` and `c5.place(right_of=u1, locked=True)`
- **WHEN** the design is converted for a build
- **THEN** `DslError` is raised naming `C5` and the unlocked reference `U1`

### Requirement: Block poses in the DSL
A c0251 block instance SHALL offer `place(x=None, y=None, rot=0, locked=False, **relation)`, with the relations and edge keys of a part, setting the block's pose in its parent frame. Requests made in a block body MUST be in the block frame, and MUST reference only parts and instances of the same block; a reference outside it, or to the board, MUST raise `DslError`.

#### Scenario: A reference out of the block
- **WHEN** a block body calls `l.place(right_of=mcu)`, where `mcu` is a top-level part
- **THEN** `DslError` is raised naming `L` and saying that a block's parts reference only parts of the same block

### Requirement: Layout strategies in the DSL
`fenolite.dsl` SHALL export `row(gap=0, align="start", at=None)`, `column(gap=0, align="start", at=None)`, `grid(columns, gap=0, at=None)` and `pack(width, gap=0, at=None)`. `layout(strategy)` SHALL be offered by a c0251 block builder (the block's default), by an instance (which wins) and by `Design` (the top level). A non-positive `columns` or `width`, a negative `gap`, or a second strategy on one frame MUST raise `DslError`.

#### Scenario: Instance strategy wins
- **GIVEN** a block whose body calls `b.layout(row(gap=mm(1)))`, and `p2 = design.use(buck, "buck2")` followed by `p2.layout(column())`
- **WHEN** the strategies of the design are read
- **THEN** `buck1` has the row and `buck2` the column

### Requirement: Block layout reuse in the DSL
`layout(reuse=PATH, copper=False)` SHALL be accepted by a c0251 block builder and instance, `PATH` relative to the file that defines the block for a builder and to the script for an instance. A frame MUST NOT take both a strategy and a reuse; `copper` MUST be a `bool`.

#### Scenario: Strategy and reuse together
- **WHEN** a block body calls `b.layout(row())` and then `b.layout(reuse="buck.kicad_pcb")`
- **THEN** `DslError` is raised saying that a frame has one strategy
