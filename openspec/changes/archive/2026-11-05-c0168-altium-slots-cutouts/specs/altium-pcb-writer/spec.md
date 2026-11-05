## MODIFIED Requirements

### Requirement: Non-plated holes and slots
A hole of the board SHALL be written as a free pad record with a hole and no copper, its plated byte the hole's `plated`. A hole with a `length` (`design-model`, "Slotted board holes") SHALL be written as a slot: hole shape 2, the slot length `length` and the slot rotation 0 in subrecord 6, the pad's size (`length`, `drill`), its shape round and its rotation the hole's `rotation`, so that the copper equals the hole.
- A hole without a positive drill MUST give `altium.not-lowered` with `where` `hole/<id>`.

#### Scenario: Mounting hole
- **GIVEN** a non-plated hole of 3.2 mm
- **WHEN** the document is written and read back
- **THEN** a free pad with a 3.2 mm hole, plating off and no copper is read

#### Scenario: A turned slot
- **GIVEN** a non-plated hole of drill 2 mm, length 12 mm and rotation 30°
- **WHEN** `uv run pytest tests/unit/backends/altium/test_slot_records.py` writes the document and reads it back
- **THEN** a free pad on Multi-Layer with hole shape 2, hole size 2 mm, slot length 12 mm and rotation 30° within the units' rounding is read, without name, net or component

## ADDED Requirements

### Requirement: Board cut-out regions
`pcbrecords.cutout_region(ring)` SHALL write one inner ring of `lowered_outline` as a board cut-out region with the keys of the fact rows of `docs/formats/altium/pcb-records.md`, "Board cut-outs", and no net. The build writes such regions only when `pcbdoc.CUTOUT_REGIONS` is true, which MUST stay false until the maintainer's kit cases S3 to S5 are recorded.

#### Scenario: The merged L as one region
- **GIVEN** the lowered ring of slots `S2` and `S3` of the shared fixture
- **WHEN** `uv run pytest tests/unit/backends/altium/test_cutout_regions.py` writes it and Fenolite's reader reads it back
- **THEN** one region is read whose keys make a board cut-out and whose ring lies within 1 µm of the written one

#### Scenario: KiCad imports the region
- **WHEN** `uv run pytest tests/kicad/altium/test_slots_import.py -k region -rA` imports the written document with `kicad-cli pcb import` (10.0.6)
- **THEN** the imported board's `Edge.Cuts` holds the cut-out ring within 1 µm
