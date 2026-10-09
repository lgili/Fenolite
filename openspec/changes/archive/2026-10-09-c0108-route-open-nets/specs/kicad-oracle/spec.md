## ADDED Requirements

### Requirement: Open connections agree with unconnected items
`tests/kicad/copper/test_open_parity.py` (markers `needs_kicad`, major-aware) SHALL compare, on 9.0.9 and 10.0.6, the open connections of `analysis.connectivity` (`board-analyses`, "Open connections of a net") with the `unconnected_items` of `kicad-cli pcb drc` (`H-K-CONN-PARITY`).
- **Bench.** `tests/kicad/copper/_openbench.py` builds, with `_rulebench.Builder` and a board outline around every row, one net per case: two `Mini_R_0603` copies 10 mm apart, the first turned 180°, whose pads `1` are on the net, and the copper of the case. The cases are the 19 of the design's measurement 3: no copper; pad to pad; a stub; crossing tracks; a track across the far pad; tracks side by side; an end on a centre line, 0.1 mm off it and 0.2 mm off it; a floating track; two vias; one via missing; an arc; a fill over both pads; a fill between them; three pads; a fill island holding a track; a lone via; a fill touching one pad.
- **Counts.** KiCad's count for a net MUST be the number of unconnected items whose items all belong to that net, found by their uuids. The probe `copper-open-kicad` MUST record, per major, the counts of KiCad per case; `copper-open-parity` MUST record `equal` when every case's count equals that of the query, and `different` otherwise.
- **Fallback.** A `different` outcome MUST stop the selection part of this change until the rule of "Open connections of a net" is corrected from the rows.
- **Census.** `tests/corpus/test_open_census.py` (markers `needs_corpus`, `needs_kicad`) MUST run the query and `kicad-cli pcb drc` 10.0.6 on every readable corpus board and write, per board, the two totals and the nets whose counts differ through `tests/_boards.py::census` into `docs/evidence/routing.md`. A board whose KiCad total reaches the report's cap of 499 MUST be compared as "at least". The test MUST NOT fail on a count; it MUST name a board whose difference comes from a copper drawing that holds a net.
- **Hermetic half.** Without `kicad-cli`, the bench's expected counts per case MUST equal those of the query.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`; built files MUST NOT be committed.

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_open_parity.py -rA` runs on 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `copper-open-parity` records `equal` on both majors, KiCad giving 1 for the stub and 0 for the crossing tracks

#### Scenario: The census is recorded
- **GIVEN** the corpus cached
- **WHEN** `uv run pytest tests/corpus/test_open_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the census file holds one row per readable board with both totals, and the board with the copper drawings that hold a net is named with its 2 open connections

#### Scenario: Hermetic counts
- **WHEN** `uv run pytest tests/kicad/copper/test_open_parity.py -k hermetic` runs without `kicad-cli`
- **THEN** the query gives the expected count of every case for targets 9 and 10

### Requirement: Copper locks pass the oracle
`tests/kicad/board/test_copper_locks.py` (markers `needs_kicad`, major-aware) SHALL prove `H-K-LOCK-FORM` on a bench with a locked segment, a locked arc, a locked via and an unlocked segment, all on one net between two pads.
- `pcb-lock-form` (major 10): the bench written by `write_board` for target 10 and re-saved by `pcb upgrade --force` MUST give, for the four items, the children Fenolite wrote and the same uuids: `equal`, else `different`.
- `pcb-lock-load` (majors 9 and 10): the bench written for the running major MUST load, and its report MUST equal, by `DrcReport.entries`, that of the same bench without locks: `equal`, else `different`.
- A `different` outcome MUST stop the lock part of this change; the register row records what KiCad wrote.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.

#### Scenario: KiCad 10 keeps the place of a lock
- **WHEN** `uv run pytest tests/kicad/board/test_copper_locks.py -k form` runs on 10.0.6
- **THEN** `pcb-lock-form` records `equal`

#### Scenario: Both majors load locked copper
- **WHEN** `uv run pytest tests/kicad/board/test_copper_locks.py -k load` runs on 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `pcb-lock-load` records `equal` on both majors

### Requirement: Routing of open nets passes the oracle
`tests/routing/test_open_nets.py` (markers `needs_router`, `needs_kicad`) SHALL prove that one `fenolite route` run completes nets that already hold copper, on a bench of the design's measurement 6: a stub; three pads, two of them joined; a fan-out of a track, a via and a `B.Cu` stub; a via beside the pad; a floating via of the net.
- **Freerouting** (`H-G-DSN-PARTIAL`): `fenolite route <bench> --router freerouting --confirm` MUST give an empty `result.unrouted` and `result.connections.after` 0, and `kicad-cli` 10.0.6 MUST report no unconnected item for the bench's nets. Outcome `dsn-partial`: `equal`, else `different`.
- **KiCadRoutingTools** (`H-K-KRT-PARTIAL`), when a checkout is given: the same run, outcome `krt-partial` recorded `equal` or `different`; the test passes on either.
- The outcomes MUST be recorded in `docs/evidence/routing.md`, never in the `kicad-cli` probe files.

#### Scenario: Freerouting completes nets that hold copper
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming the 2.4.1 jar and Java 25 or newer
- **WHEN** `uv run pytest tests/routing/test_open_nets.py -m needs_router -k freerouting -rA` runs on 10.0.6
- **THEN** `dsn-partial` records `equal`, and every copper item of the bench from before the run is still on the board with its uuid

#### Scenario: KiCadRoutingTools is recorded either way
- **GIVEN** `FENOLITE_KRT` naming a checkout at the pinned tag
- **WHEN** `uv run pytest tests/routing/test_open_nets.py -m needs_router -k krt -rA` runs
- **THEN** `krt-partial` records `equal` or `different`, and the test passes
