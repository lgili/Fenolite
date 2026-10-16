## ADDED Requirements

### Requirement: Slots and cut-outs in a conversion
A conversion SHALL count every inner edge ring of the source under the kind `cutout` (group `board`, class `report`): `kept`, `changed` with the reason "merged" or "arcs polygonised", or `lost` with its reason. To Altium, inner rings MUST follow c0168's region lowering through `edge_outline`. To KiCad, overlapping rings MUST be merged; an overlap that cannot be merged MUST be a `refuse` loss, and each board `Hole` MUST become a generated `Fenolite_Holes` footprint.

#### Scenario: Fixture to Altium
- **GIVEN** the shared fixture built for KiCad 10
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k altium` converts it with `--to altium`
- **THEN** the report's `cutout` row counts three rings (written as regions and changed with "arcs polygonised" with the gate on, lost with its reason with the gate off), and no ring is reported under `outline`

#### Scenario: Overlapping Altium cut-outs to KiCad
- **GIVEN** an Altium document with two overlapping board cut-out regions and a free slot pad
- **WHEN** it is converted with `--to kicad`
- **THEN** the board holds one merged cut-out ring, `cutout` counts one ring changed with "merged", the slot is an `NPTH_Slot_…` footprint, and `kicad-cli pcb drc` reports no `invalid_outline`

### Requirement: Edge rings verified after a conversion
After writing, a conversion SHALL compare the edge rings of the source and of the written project read back, through `BoardFrame.board_edges`, within 1 µm plus the region chord, a merged ring against the union of its sources. A ring that differs and that the report does not explain MUST be a difference of the verification.

#### Scenario: A dropped ring is a difference
- **GIVEN** a conversion whose writer is patched in the test to drop one cut-out without reporting it
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k verify` runs it
- **THEN** the verification names that ring and the exit code is 5
