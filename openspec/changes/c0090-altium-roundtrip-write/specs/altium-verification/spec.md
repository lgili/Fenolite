## ADDED Requirements

### Requirement: RT-A2 on a written model
For a project that Fenolite built or wrote from a model, the level RT-A2 SHALL compare every kind of `RT_A2_SCOPE` between the stored model and the reading of the written documents: components, nets, no-connect marks, net classes, footprints, pads, tracks, arcs, vias, zones and the rules of the kinds that `rulemap` marks exact, within 2 nm.
- No kind of the scope MAY be only counted. A built project whose stored model predates this change (no footprint in its board) MUST skip the stage with the reason `model-predates-board`.
- The stage's evidence MUST be `INFERRED` with `H-A-VER-RTA2-3` combined with the readings' evidence.

#### Scenario: Copper compared
- **GIVEN** the routed blink built for Altium, with one track of the PCB document moved by record edit
- **WHEN** `fenolite check <dir> --stages roundtrip.rta2 --json` runs
- **THEN** the exit code is 5, and `check.rta2-failed` names the track

### Requirement: Round-trip level RT-A3
The level RT-A3 SHALL hold for Altium documents when the model that their import gives equals the model that the import gives after Fenolite wrote that model as new documents: `roundtrip.rt_a3(documents)` SHALL import, write to a temporary folder with `AltiumBackend.write`, import again and compare the two models inside `RT_A3_SCOPE` within 2 nm.
- `RT_A3_SCOPE` MUST be the written scope of the writers, as `AltiumBackend.written_scope()` returns it, and `docs/altium.md` MUST hold it as a table.
- The result MUST hold `equal`, the located differences, and `unwritten`: for each record kind of the first reading that the write does not carry, its count. `unwritten` MUST NOT change `equal`.
- The stage `roundtrip.rta3` MUST be opt-in on document input, MUST write nothing under the input folder, and MUST report each difference as `check.rta3-failed` (error) and the unwritten kinds as one `check.rta3-unwritten` (info) with the counts.
- Its evidence MUST be `roundtrip.EVIDENCE_RT_A3` (`H-A-VER-RTA3`) combined with the readings' evidence, and `UNVERIFIED` when the comparison could not run.
- `fenolite roundtrip PATH --level rta0|rta1|rta2|rta3` MUST accept Altium input and run the level of that name.

#### Scenario: Own sample
- **WHEN** `fenolite roundtrip tests/data/altium/board6 --level rta3 --json` runs
- **THEN** the exit code is 0, `result.unwritten` is empty, and no file is written under the sample folder

#### Scenario: Corpus documents
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -rA` runs with the corpus cached
- **THEN** every listed document is equal inside the scope, and the test prints the unwritten counts per kind for the evidence page

#### Scenario: A writer defect is caught
- **GIVEN** a writer patched to drop the last via
- **WHEN** `rt_a3` runs on a board with vias
- **THEN** `equal` is false and one difference names a via

### Requirement: Round-trip claims of the Altium kinds
`backends/altium/claims.py` SHALL state for each Altium kind what the round-trip levels support: its docstring MUST no longer say that no Altium file is read and written back, and each kind's note MUST name the highest level that holds over the corpus (`RT-A1`, or `RT-A3 inside the written scope`) with its hypothesis.
- A `roundtrip_exact` cell MUST be set only when RT-A3 holds on the corpus list with no unwritten record for that kind; otherwise it MUST stay empty.
- No cell MAY be set from files that Fenolite wrote itself.

#### Scenario: Matrix follows the run
- **WHEN** `uv run python tools/gen_evidence_matrix.py --check` runs after the corpus run was recorded
- **THEN** the matrix is up to date, and the rows of the Altium kinds name the level and the hypothesis of the run
