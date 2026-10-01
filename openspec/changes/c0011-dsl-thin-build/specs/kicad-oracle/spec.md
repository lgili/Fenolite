## ADDED Requirements

### Requirement: Built projects pass the build oracle
`tests/kicad/build/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that projects written by `fenolite build` are what the DSL describes. Every case MUST build `examples/blink_2layer/design.py` (or a variant built in the test) into a temporary folder, run `kicad-cli` through c0009's `KicadCli` on a copy with an empty `KICAD_CONFIG_HOME`, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code (c0017, "DRC verdicts come from the JSON report").
- **Load.** The target-9 blink MUST load on 9.0.9 and 10.0.6, and the target-10 blink on 10.0.6.
- **Positions.** `pcb export pos` MUST give each part its DSL position plus `BOARD_ORIGIN`, its rotation and its side, compared through c0009's `tests/kicad/board/_frame.py`.
- **Clean DRC.** The report MUST hold no violation of severity `error`. `unconnected_items` are a separate list and are allowed. The only exception MUST be a violation type that the baseline probe shows a clean placement cannot avoid, named in the design with its probe outcome; no exception by severity or count is allowed.
- **Canary.** On a separate copy whose `.kicad_dru` has c0018's canary rule inserted right after `(version 1)` by `tests/kicad/rules/_bench.py::with_canary` (c0018; last on a major where `H-K-DRU-ORDER` says the earlier rule governs), a `clearance` violation absent from the plain run MUST appear. The blink holds no canary pair, so c0018's `require_canary(report, bench)` does not apply: this change's pure judge `tests/_build_judge.py::canary_outcome(plain, canary)` MUST give `present` when such a violation appears and `inconclusive` otherwise, and `assert_loaded(outcome, case)` MUST fail an `inconclusive` case with "rules file not loaded". The unconditional canary MUST NOT share a run with the class case.
- **Violated class.** A variant whose `PWR` class has a 2 mm clearance MUST give a `clearance` violation whose items are the uuids of the two adjacent `U1` pads on `VIN` and `GND`. The same set without `blink.kicad_pro` MUST give no violation for those pads, and the as-built blink MUST give none either. An item uuid that is no pad uuid MUST make the probe `different`, recorded as data for c0020's DRC item attribution.
- **Vendored table.** On 10.0.6, for targets 9 and 10, the built project MUST give no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the same copy without `fp-lib-table` MUST give `lib_footprint_issues`; otherwise the case is `inconclusive`. On 9.0.9 the outcomes MUST be recorded and not asserted while `H-K-LIB-DRC` is open there.
- **Path property.** After `pcb upgrade --force` on 10.0.6, `read_board` of the re-saved board MUST give `properties["fenolite.path"]` equal to the component path for all three footprints, and each property node MUST still hold `(hide yes)`.
- **Probes first.** The cases MUST be probes of c0017's `tests/kicad/_probes.py` with the ids `build-pathprop-t<M>`, `build-libtable-t<M>`, `build-baseline-t<M>`, `build-offboard-t<M>`, `build-canary-t<M>` and `build-class-t<M>` for target `M`. Each probe MUST map its result to one outcome of c0017's closed set, as design Decisions 25 and 26 define it per probe.
- The `pathprop`, `libtable`, `baseline` and `offboard` probes MUST run before the DSL exists, on boards made in the test with `layers.created_layers` and `embed.place_footprint`, and every stop rule of design Decision 25 MUST be applied before the DSL code starts: a refuted `H-K-BUILD-PATHPROP` (either `pathprop` probe) removes the property from the build; a `different` libtable outcome on 10.0.6 makes library parity recorded data; an `absent` (the table is not read) or `inconclusive` libtable outcome on 10.0.6 stops the change until the table form, or the reading of `H-K-LIB-DRC`, is corrected; an error-severity type of a `present` baseline is excluded from the acceptance by name only, never by severity or count.
- The violation types, their severities and the `unconnected_items` count that the `baseline` and `offboard` probes see MUST be recorded as fact rows of `docs/formats/kicad/drc.md` with `H-K-BUILD-TRIAD`, not in the probe files.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, which hold only the version, the probe ids and their outcomes (c0017), so `tests/kicad/test_probe_results.py` detects a change of behaviour. Built files MUST NOT be committed.

#### Scenario: Blink builds clean
- **GIVEN** the blink built for target 10 on the local KiCad 10.0.6
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_blink_builds_clean` runs
- **THEN** the board loads, `pcb export pos` gives `U1`, `R1` and `D1` at their DSL positions plus (100 mm, 100 mm) with their rotations and sides, the DRC report holds no violation of severity `error`, and the canary copy holds a `clearance` violation that the plain run lacks

#### Scenario: Violated class, three ways
- **GIVEN** the blink built for target 9 and its `PWR` variant at 2 mm clearance
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_violated_class` runs on 10.0.6
- **THEN** the variant's report holds the `clearance` violation between the two `U1` pads on `VIN` and `GND`, while the variant without `blink.kicad_pro` and the as-built blink hold none for those pads

#### Scenario: Vendored table with a missing-table control
- **GIVEN** the blink built for target 10, whose `fp-lib-table` has the row `Mini` -> `${KIPRJMOD}/lib/Mini.pretty`
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_vendored_table` runs on 10.0.6
- **THEN** the report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the copy without `fp-lib-table` holds `lib_footprint_issues`

#### Scenario: Path property survives a re-save
- **GIVEN** the blink built for target 10
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_path_property` runs `pcb upgrade --force` on a copy on 10.0.6
- **THEN** `read_board` of the re-saved board gives `properties["fenolite.path"]` equal to `U1`, `R1` and `D1` for the three footprints, each with `(hide yes)`

#### Scenario: Canary missing fails
- **GIVEN** a plain report and a canary-copy report authored in the test, the second holding no `clearance` violation that the first lacks
- **WHEN** the hermetic `uv run pytest tests/unit/test_build_judge.py` passes them to `canary_outcome` and the outcome to `assert_loaded`
- **THEN** the outcome is `inconclusive`, and `assert_loaded` fails with the message "rules file not loaded"

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after `uv run pytest tests/kicad/build/test_build_probes.py -rA`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `build-*` probe of targets 9 and 10

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/build -rA` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, the vendored-table outcomes are recorded without assertion, and the target-10 cases are skipped by `kicad_min_major(10)`
