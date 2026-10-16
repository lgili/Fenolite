## ADDED Requirements

### Requirement: Edge clearance agrees with KiCad
The bench `tests/kicad/checks/_edgebench.py` (tracks, arcs, vias, pads and a fill at stated gaps from the board ring, a round cut-out, a slot and a merged L) SHALL give the same items in Fenolite's `copper.edge-clearance` findings as in `kicad-cli pcb drc`'s `copper_edge_clearance` entries, on 9.0.x and 10.0.x, and SHALL record the probes of `H-K-EDGE-CENTRE`, `H-K-EDGE-RESOLVE` and `H-K-EDGE-AGREE`.

#### Scenario: Same items on both majors
- **WHEN** `uv run pytest tests/kicad/checks/test_edge_clearance.py -rA` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** the item sets are equal, and the probes hold their recorded outcomes
