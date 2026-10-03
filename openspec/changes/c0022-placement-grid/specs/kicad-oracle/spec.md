## ADDED Requirements

### Requirement: Moved footprints pass the oracle
Footprints moved by `move_footprint`, and the legality verdicts, SHALL be proved on `kicad-cli` 9.0.9 and 10.0.6, probes first:
- **Move.** For the authored project, `pcb export pos` MUST give the requested position, rotation and side after a translation, after rotations to 90° and 30°, and after a flip to the bottom, and the IPC-D-356 pad nets MUST equal those before the move (`H-K-PLACE-MOVE`; probes `place-move-translate`, `place-move-rotate`, `place-move-flip` = `equal`).
- **Touching.** Two courtyards sharing an edge and two sharing a corner MUST be run through `pcb drc`, with a pair overlapping by 20 µm as the positive control in the same board (`H-K-PLACE-TOUCH`; probe `place-touch` records `absent` or `present` for the touching pairs, and is `inconclusive` when the control does not fire).
- **Agreement.** On a bench of six placed parts with known overlapping and clear pairs on both sides, the set of pairs with `place.courtyard-overlap` MUST equal the set of pairs in KiCad's `courtyards_overlap` violations.
- **Rebuild.** A blink variant with two staged parts, placed by `fenolite place --strategy grid --confirm` and built again, MUST keep both placements, report no `layout.unplaced`, and write the same bytes on a second build.

If a move probe records `different`, the fallback of the design (translation only) MUST be applied and recorded in the register row.

#### Scenario: Move proved
- **WHEN** `uv run pytest tests/kicad/place/test_place_probes.py::test_move` runs on 9.0.9 and on 10.0.6
- **THEN** the three probes record `equal`

#### Scenario: Touching settled
- **WHEN** `uv run pytest tests/kicad/place/test_place_probes.py::test_touch` runs on both majors
- **THEN** the control pair gives one `courtyards_overlap`, the probe records the outcome for the touching pairs, and `placement.legality.TOUCHING_OVERLAPS` equals it

#### Scenario: Legality matches DRC
- **WHEN** `uv run pytest tests/kicad/place/test_place_oracle.py::test_legality_matches_drc` runs on both majors
- **THEN** the two sets of pairs are equal

#### Scenario: Placed then rebuilt
- **WHEN** `uv run pytest tests/kicad/place/test_place_oracle.py::test_placed_then_rebuilt` runs on both majors
- **THEN** both parts are inside the outline after `place`, stay where they are after the rebuild, and a second rebuild changes no byte
