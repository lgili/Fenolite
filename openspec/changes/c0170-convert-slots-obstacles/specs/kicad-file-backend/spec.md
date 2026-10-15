## ADDED Requirements

### Requirement: Board holes as generated footprints in a conversion
`fenolite.model.holes.hole_footprint(drill, *, length=None, pad=None, courtyard=None)` SHALL build the `Fenolite_Holes` footprints that `design.hole` uses, and `fenolite.dsl.holes` SHALL re-export it with the same bytes. A conversion to KiCad SHALL replace each board `Hole` with a board-only footprint of that definition, placed at the hole and turned by its rotation, its library written beside the board.

#### Scenario: Same footprint from a script and a conversion
- **GIVEN** `design.hole("H1", mm(10), mm(10), drill=mm(1), length=mm(3))` and a model `Hole` of drill 1 mm and length 3 mm at the same place
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k holes` builds the first and converts the second
- **THEN** both boards hold the footprint `Fenolite_Holes:NPTH_Slot_1x3mm` at the same place with equal pads
