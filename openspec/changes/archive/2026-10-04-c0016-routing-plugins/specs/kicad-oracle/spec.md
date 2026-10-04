## ADDED Requirements

### Requirement: Routed boards pass the oracle
The KiCadRoutingTools plugin SHALL be proved against `kicad-cli` on 9.0.9 and 10.0.6 at `PINNED_TAG`, feasibility gate first, in tests marked `needs_router` and `needs_kicad`:
- **Arguments and outputs** (`H-K-KRT-CLI`): for the built blink of each target, the tool exits 0, writes its output, the output reads with `read_board`, and routed tracks have the width passed to it.
- **Route** (`H-K-KRT-ROUTE`): after `fenolite route --router kicadroutingtools --confirm` (and `fenolite fill --confirm` on 10.0.6), `pcb drc` of the board's own major MUST report no unconnected item and no violation type of severity error that the unrouted board lacks.
- **Keep** (`H-K-KRT-KEEP`): the tool's output and its input, read with `read_board` and compared without tracks, arcs, vias and provenance, are recorded as `equal` or `different` with what differs.
- **Repeat** (`H-K-KRT-REPEAT`): two runs are compared by the geometry of their tracks and vias, and the outcome is recorded.
- **Loop**: `build`, `route`, `fill` (10.0.6) and `build` again MUST keep every routed item, and a further `build` MUST change no byte.

The outcomes MUST be recorded in `docs/evidence/routing.md` with the tool's version and commit, and MUST NOT be written to `docs/evidence/kicad/probes/`. The gate passes when the route outcome holds on both majors; when it fails on a major, the register row MUST be refuted with a successor that names the nets left unrouted or the violations added.

#### Scenario: Gate on 10.0
- **GIVEN** `FENOLITE_KRT` naming a checkout at `PINNED_TAG`
- **WHEN** `uv run pytest tests/routing/test_krt_gate.py -rA` runs on the local KiCad 10.0.6
- **THEN** `test_cli`, `test_route`, `test_keep` and `test_repeat` record their outcomes, and `test_route` passes with 0 unconnected items

#### Scenario: Gate on 9.0
- **WHEN** the same command runs inside the pinned 9.0.9 image with the tool mounted
- **THEN** `test_route` passes for the target-9 blink without the fill step, and the outcome is recorded

#### Scenario: Loop keeps routes
- **WHEN** `uv run pytest tests/routing/test_route_oracle.py::test_loop` runs on both majors
- **THEN** the rebuilt board holds the routed tracks and vias with their uuids, and the last build writes the bytes of the one before

#### Scenario: Skipped without the tool
- **GIVEN** no `FENOLITE_KRT` and `FENOLITE_REQUIRE` without `router`
- **WHEN** `uv run pytest tests/routing -rs` runs
- **THEN** every test is skipped with a reason naming `FENOLITE_KRT`
