## ADDED Requirements

### Requirement: Net-class rules are enforced by kicad-cli
`tests/kicad/project/test_netclass_drc.py` (marker `needs_kicad`) SHALL prove on the running `kicad-cli` that a net class written by Fenolite is enforced, and SHALL judge every case from the DRC JSON report read with c0017's `read_drc_report`, never from the exit code. A clean report MUST NOT count as evidence that the project or the rules were read.

The bench is built by `tests/_netclass_bench.py` through the model and written with `write_triad` as `bench.kicad_pcb`, `bench.kicad_pro` and `bench.kicad_dru`:
- F.Cu tracks 0.25 mm wide in rows at least 5 mm apart; each of `+3V3`, `SIG1`, `SIG10`, `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3`, the decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3`, and `SW1_A` runs beside its own `GND` track with a 1.0 mm gap;
- class HV with clearance 2 mm, assigned in the model to `+3V3` and `SIG1`, so that synthesis writes their exact-name patterns; every other row is in `Default`;
- the canary: a 3 mm clearance rule restricted by a `net` condition to `CANARY_A`, whose track runs 0.75 mm from a `CANARY_B` track, at least 10 mm from other copper. The canary is scoped because the unconditional canary of "Rules proofs carry a canary" would flag every 1.0 mm row.

A row's HV violation is a `clearance` violation whose items are that row's two tracks, and the canary violation is the `clearance` violation between the two canary tracks; both MUST be identified by item uuids. Every run MUST go through c0009's `KicadCli` on a temporary copy with an empty `KICAD_CONFIG_HOME`. On 10.0 the target-10 and target-9 sets run; on 9.0 the target-9 set runs, and the target-10 cases are skipped by `kicad_min_major(10)`.
- In every case that loads the project, a report without the canary violation MUST fail the test with a message saying the rules file was not loaded, and MUST NOT pass or skip. In the no-project case, a canary violation MUST fail the test. The outcome MUST be computed by the pure function `judge(report, *, case, design)` of `tests/_netclass_bench.py`, and the failure raised by `assert_loaded(outcome, case)`, so that both are tested without KiCad.
- Each case MUST be a probe of `tests/kicad/_probes.py` with id `pro-<case>-t<target>`, and the tests MUST assert on `run(…)`. The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, so that `tests/kicad/test_probe_results.py` detects a change of behaviour in a later image.

#### Scenario: Full set
- **GIVEN** the bench set for the running major
- **WHEN** `uv run pytest tests/kicad/project/test_netclass_drc.py::test_full_set` runs
- **THEN** the report has the HV violation of `+3V3`, of `Net-(R1-Pad1)` and of `D[0]`, and the canary violation

#### Scenario: No project file
- **GIVEN** the same set without `bench.kicad_pro`
- **WHEN** `test_three_way` runs it
- **THEN** the report has neither an HV violation nor the canary violation

#### Scenario: Class removed
- **GIVEN** the set synthesised from the bench without class HV
- **WHEN** `test_three_way` runs it
- **THEN** the report has the canary violation and no HV violation

#### Scenario: Minimal project
- **GIVEN** the full set whose `bench.kicad_pro` is cut to its `meta` and `net_settings` keys
- **WHEN** `test_minimal_project` runs it
- **THEN** the HV and canary violations are the same, by type and item uuids, as in the full set

#### Scenario: Patterns as wildcards and regular expressions
- **GIVEN** the full set plus the pattern entries `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3` and `SW?_*`, each for HV, added by the test
- **WHEN** `test_patterns` runs it
- **THEN** the rows of `+3V3`, `SIG1`, the four added names and `SW1_A` have HV violations and the canary fires, the outcomes of the decoy rows `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3` (expected `present`, S-0046) and of `SIG10` in the full set (expected `absent`) are recorded as the probes `pro-decoys` and `pro-anchor`, and a measurement other than the expected one fails the test until `pattern_matches` and a `-2` successor of `H-K-PRO-PATTERNS` follow it

#### Scenario: Board-setup floor governs
- **GIVEN** the bench with HV clearance 0.5 mm, once with the template floor and once with `board.design_settings.rules.min_clearance` set to `1.5` in `bench.kicad_pro`
- **WHEN** `test_floor` runs both
- **THEN** the first report has no HV violation, the second has the HV violation of every HV row, and the canary fires in both

#### Scenario: Canary missing
- **GIVEN** an authored DRC report text holding the HV violations of the bench and no canary violation, read with c0017's `read_drc_report`
- **WHEN** `uv run pytest tests/unit/test_netclass_bench.py -k canary` judges it as the `full` case, and judges a report holding the canary as the `noproject` case
- **THEN** `judge` returns `inconclusive` for both, and `assert_loaded` fails with a message saying the rules file was not loaded

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after the project tests
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds `present` for `pro-full-t10`, `absent` for `pro-noproject-t10`, `pro-noclass-t10` and `pro-anchor-t10`, and `equal` for `pro-minimal-t10`

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/project -q` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, the target-10 cases are skipped by `kicad_min_major(10)`, and none fails

### Requirement: Project files survive kicad-cli runs
`tests/kicad/project/test_project_files.py` (marker `needs_kicad`) SHALL run `pcb drc` through c0017's `KicadCli.drc` and `pcb export svg -l Edge.Cuts --mode-single` through c0009's `KicadCli.run`, each with `files` naming the three files of the target-9 bench set, and SHALL settle `H-K-PRO-PRL` from `CliRun.outputs`, which maps every file a run created or changed in its temporary copy.
- `bench.kicad_pro` MUST be absent from the `outputs` of each run, which means its SHA-256 is unchanged.
- Whether `bench.kicad_prl` is in the `outputs` of each run MUST be recorded in the test output and in `docs/hypotheses.md`.
- The outcomes MUST be the probes `pro-file-drc` and `pro-file-export` (`equal` when `bench.kicad_pro` is absent from `outputs`, `different` otherwise) and `pro-prl-drc` and `pro-prl-export` (`present` when `bench.kicad_prl` is in `outputs`, `absent` otherwise) of `tests/kicad/_probes.py`.
- The test MUST NOT run `kicad-cli` outside `KicadCli`. Files of the repository MUST NOT change: `git status --porcelain` is the same before and after `uv run pytest tests/kicad/project`.

#### Scenario: Project file untouched
- **GIVEN** the target-9 bench set written by `write_triad` into `tmp_path`
- **WHEN** `uv run pytest tests/kicad/project/test_project_files.py::test_prl_and_pro` runs on 10.0.6 and on 9.0.9
- **THEN** `bench.kicad_pro` is in neither run's `outputs`, and whether `bench.kicad_prl` is in each run's `outputs` is reported

#### Scenario: Repository untouched
- **GIVEN** a clean working tree
- **WHEN** `uv run pytest tests/kicad/project -q` runs
- **THEN** `git status --porcelain` prints the same as before, and no `.kicad_prl` exists under the repository
