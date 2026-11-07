# Design

## Board comparison scope

`verify_conversion` compares `conversion.design` (the design the direction wrote) with the read-back of
the written `.kicad_pcb`. A board holds placed components only. When the conversion also wrote a
schematic, `_schematic` compares the source circuit with it at levels 1 and 2 (`SCHEMATIC_LEVEL = 2`), so
a component without a footprint is checked there. The board comparison therefore takes `conversion.design`
with only the components that have a footprint on its board, and the net members of the others removed.
Without a written schematic nothing changes: such a component stays a reported difference.

## One component, several footprints

A source board may link two footprints to one component (the same unique id, as an annotation that was
not refreshed). The KiCad board writes both footprints with the component's reference, and the read-back
holds two components of that reference, so level 1 reports `ref-ambiguous` (1 against 2). The KiCad
direction now counts such footprints in a new report kind, `shared-footprint` (group `footprint`, class
`report`), as changed with the reason "the source links several footprints to one component", and the
explanation table explains `ref-ambiguous` at the reference of a `shared-footprint` item. A repeated
designator whose two sides agree is already explained by `SOURCE` ("same").
