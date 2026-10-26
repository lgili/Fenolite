## ADDED Requirements

### Requirement: Slots and cut-outs in the round trips
RT-A0 and RT-A1 SHALL pass on the document of the shared fixture with slotted holes and cut-out regions, and RT-A2 SHALL compare board holes by position, drill, plating, length and rotation, and the cut-out rings of `edge_outline` with the written ones within 1 µm. A difference MUST be a finding naming the hole or the cut-out.

#### Scenario: Fixture passes RT-A0 to RT-A2
- **WHEN** `uv run pytest tests/unit/checks/test_rta2_slots.py` runs the three levels on the written fixture
- **THEN** every level passes, and a cut-out moved by 2 µm in the read model gives one RT-A2 finding naming it

### Requirement: Detached hole pads in RT-A3
RT-A3 SHALL expect a pad that the write detaches as a free pad (a pad without a number) and whose copper is its hole as the board hole that the import makes of that free pad, with the pad's board position, drill, plating and, for a slot, length and rotation; any other detached pad stays expected as a free-pad footprint. A moved or resized hole MUST remain a difference of kind `hole`.

#### Scenario: Round and slotted pads detached from a component
- **GIVEN** a component footprint with an unnumbered round non-plated pad whose size is its drill and an unnumbered slotted one whose size is (length, drill)
- **WHEN** the document is written, read again and judged by RT-A3
- **THEN** the second reading holds both as board holes, the trip is equal, and the first hole moved by 0.1 mm gives differences of kind `hole` only

### Requirement: Kit cases for slots and cut-outs
`docs/evidence/altium-pcb.md` SHALL hold Part S, cases S1 to S8 of the design of change c0168, each with its expected outcome, and the maintainer's report SHALL be recorded in the form of the native acceptance inventory (date, version, case, file hash, step, expected and observed outcome, level) before `pcbdoc.CUTOUT_REGIONS` is set to true.

#### Scenario: Gate follows the report
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_s` runs
- **THEN** it passes only when `CUTOUT_REGIONS` is false or Part S records S3, S4 and S5 as passed
