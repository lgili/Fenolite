## ADDED Requirements

### Requirement: Slots pass the oracle
The shared fixture `tests/data/slots/design.py`, built for targets 9 and 10, SHALL load in `kicad-cli` 9.0.x and 10.0.x with no `invalid_outline`; its slots MUST reach no drill file and its round hole the NPTH file. `tests/kicad/board/_slotbench.py` SHALL record the probes of `H-K-SLOT-RING`, `H-K-SLOT-OVERLAP`, `H-K-SLOT-UNION` and `H-K-HOLE-OVERLAP` on both majors.

#### Scenario: Fixture on both majors
- **WHEN** `uv run pytest tests/kicad/board/test_slots.py -rA` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** no `invalid_outline` is reported, and the probes hold the outcomes of the design's register

#### Scenario: Re-saved board reads back
- **GIVEN** the fixture's board re-saved by `pcb upgrade --force` (10.0.x)
- **WHEN** `edge_outline` and `slots_of` read it
- **THEN** they give the model's slots within 1 µm, every arc still an arc
