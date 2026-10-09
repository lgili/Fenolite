## ADDED Requirements

### Requirement: Copper locks from an Altium board
`import_board` SHALL give each `Track`, `Arc` and `Via` that "Tracks, arcs and vias" maps the `locked` of its primitive: `True` when `Prefix.locked` is true (bit 2 of the first flag byte clear; `docs/formats/altium/pcb-read.md`, row `Prefix.locked`), `False` otherwise (`design-model`, "Copper locks in the board model"). This requirement adds one field beside "Tracks, arcs and vias" and changes none of its rules.
- A document without a locked free primitive MUST import to the model it imported to before this change.
- A document that Fenolite wrote from a model with locked copper MUST import with the same items locked ("Own files import to the model they were written from"), for the kinds of `pcbrecords.LOCK_WRITTEN`.
- The level is that of the read row, `INFERRED`, until `H-A-PCB-CU-LOCK` is settled.

#### Scenario: Locks survive the round trip
- **GIVEN** the routed sample's model with one track, one arc and one via locked, built for Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_own_files.py -k locked` imports the written project
- **THEN** exactly the track, the arc and the via that were locked have `locked == True`

#### Scenario: A document without locks
- **WHEN** the PCB document of `tests/data/altium/routed/` is imported
- **THEN** no track, arc or via has `locked == True`, and the imported model equals the one of before this change
