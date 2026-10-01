## ADDED Requirements

### Requirement: Slot source for model entities
A KiCad writer SHALL emit every model entity through `slots.rebuild`, with a `SlotSource` built from the entity's current model values (c0009's `pcb.model_source`) and with `canonical = pcb.CANONICAL_ORDER[head]`. The slot list MUST be chosen as follows:
- **Read entity.** An entity whose `kicad` bag holds slots MUST be rebuilt with the lists of `from_ext_all(bag)`: the list of `.` for the entity node and each relative list for its sub-list. Its children keep their source order, and a field new to it follows "Canonical insertion of new fields".
- **Created entity.** An entity without slots in its `kicad` bag MUST be rebuilt with the empty slot list, so its children appear exactly in canonical order, positional fields first. Its sub-lists, such as a zone's `polygon` and `filled_polygon` or a rule area's `keepout`, MUST follow the canonical order of their own heads, so `CANONICAL_ORDER` MUST hold an entry for each of them.
- A field that the source returns and that `CANONICAL_ORDER[head]` lacks MUST raise `ValueError` naming the head and the field, and so MUST a head without an entry in `CANONICAL_ORDER`.

Opaque fragments MUST be re-emitted tree-equal to their source, at their positions. The only exceptions are the changes that a `kicad-file-backend` requirement names, each applied by the writer and none by `rebuild`:
- `net` nodes rewritten into the target's form, with nets renumbered by name on every target-9 write ("Net form per target");
- the source's opaque root row `(net 0 "")`, replaced in place by the generated table's row 0 for target 9 and removed for target 10, and opaque `(net 0)` references removed for target 10 ("Net form per target");
- nodes of an `until_major = 9` inventory row converted or dropped for target 10 ("Board writing per target");
- opaque slots removed under `allow_lossy` ("Lossy writes are refused unless allowed");
- the value atom of a Reference or Value property, and spelling-only projections re-emitted from a changed model value ("Projected fields on write").

The `design-model` requirement "Slots for lossless round-trip" refers to this list for the KiCad writer.

#### Scenario: Created track in canonical order
- **GIVEN** a created `Track` on `F.Cu` with a net and no `kicad` bag
- **WHEN** it is written for target 10
- **THEN** the `segment` children appear in the order `CANONICAL_ORDER["segment"]` gives

#### Scenario: Read entity keeps its order
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and the width of one track changed
- **WHEN** the design is written for target 9
- **THEN** that `segment` node has its children in source order with the new width, and every other node of the board is tree-equal to the source apart from the header atoms and net numbers

#### Scenario: Created zone with a fill and a rule area
- **GIVEN** the created test board `tests/_boards.py::created_board()`, whose zone has one fill and whose rule area forbids tracks
- **WHEN** it is written for target 10
- **THEN** no `ValueError` is raised, and the children of the `zone`, its `filled_polygon` and the rule area's `keepout` appear in the orders `CANONICAL_ORDER` gives for those heads

#### Scenario: Field without canonical position
- **GIVEN** a created entity whose source returns a field absent from `CANONICAL_ORDER` for its head
- **WHEN** `write_board` runs
- **THEN** a `ValueError` naming the head and the field is raised

#### Scenario: Opaque child unchanged on a same-target write
- **GIVEN** `tests/data/kicad/board/dimension.kicad_pcb` read with `read_board`, and one segment moved
- **WHEN** it is written for target 9
- **THEN** the `dimension` node is tree-equal to the source node and at its source index
