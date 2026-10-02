## ADDED Requirements

### Requirement: Board-setup minimums are proved by kicad-cli
`tests/kicad/project/test_minimums_drc.py` (marker `needs_kicad`) SHALL prove on the running `kicad-cli` that the five keys of `lowering.MINIMUM_KEYS` are read, that a minimum above the `min` of a board-wide custom rule governs it, and that the project Fenolite writes lets the rule values take effect, and SHALL measure whether a custom clearance rule without a condition overrides a larger class clearance. Every case MUST be judged from the DRC JSON report read with c0017's `read_drc_report`, by violation type and item uuid, never by exit code.

The bench is built by `tests/_minimum_bench.py` through the model and written with `write_triad` as `bench.kicad_pcb`, `bench.kicad_pro` and `bench.kicad_dru`:
- one probe item per kind, each at least 4 mm from other copper, and each between the bench rule of its kind and the minimum of the template runs below (the template value, and 0.2 mm for `min_clearance`): two 0.25 mm tracks with a 0.15 mm gap (`clearance`), a 0.15 mm track (`track_width`), a via of 0.45 mm diameter and 0.24 mm drill (`via_diameter`), a via of 0.6 mm diameter and 0.25 mm drill (`hole_size`), and a 0.25 mm track whose copper edge is 0.35 mm from the board edge (`edge_clearance`);
- a row of class HV (clearance 2 mm) beside a `GND` track with a 1.0 mm gap, and a model class `Default` with clearance 0.05 mm, so that no class value flags a probe item;
- five board-wide rules of severity `error` and priority 0: `clearance` 0.1 mm, `track_width` 0.1 mm, `via_diameter` 0.35 mm, `hole_size` 0.2 mm and `edge_clearance` 0.2 mm;
- the canary of c0010's net-class bench: a 3 mm `clearance` rule on `net CANARY_A` with priority 1, so that it is written last, and a `CANARY_A` track 0.75 mm from a `CANARY_B` track, at least 10 mm from other copper.

The violation type of each kind MUST be the one c0018 observed for its custom rule: `clearance`, `track_width`, `via_diameter`, `drill_out_of_range` and `copper_edge_clearance`. Four runs MUST be made per target, each through c0009's `KicadCli` on a temporary copy with an empty `KICAD_CONFIG_HOME`:
- `keys-template`: the bench without its five board-wide rules, with the five keys at the template's values and `min_clearance` set to `0.2` by the test;
- `keys-lowered`: the same, with the five keys set by the test to `0.1`, `0.1`, `0.35`, `0.2` and `0.2`;
- `rules-template`: the bench with its rules, with the five keys reset by the test as in `keys-template`;
- `rules-lowered`: the bench as `write_triad` writes it.

Each run MUST be the source of probes of `tests/kicad/_probes.py`: `pro-min-<run>-<kind>-t<target>` for each kind (`present` when the probe item has its violation, `absent` otherwise), `pro-min-class-t<target>` (the HV row in `rules-lowered`) and `pro-min-class-control-t<target>` (the HV row in `keys-template`). Target-10 runs MUST run on major 10, and target-9 runs on majors 9 and 10.
- A run without the canary violation MUST give `inconclusive` for each of its probes, and the test MUST then fail with a message saying that the rules file was not loaded; it MUST NOT pass or skip. The outcomes MUST be computed by pure functions of `tests/_minimum_bench.py`, tested without KiCad.
- For each kind of `MINIMUM_KEYS[target]`, the tests MUST assert `present` in `keys-template` and `absent` in `keys-lowered` and `rules-lowered`. They MUST assert `present` for `pro-min-class-control`. For `rules-template` they MUST assert `present` exactly when the kind's entry of `lowering.FLOOR_OVER_RULES` holds the running major, and for `pro-min-class` `absent` exactly when `lowering.RULES_OVER_CLASSES` holds it.
- A measurement that disagrees MUST fail the test until the table in `rules-model` ("Conflicts with board-setup minimums are reported" or "Class clearances against board-wide clearance rules are reported") and a `-2` successor of the hypothesis follow it. A `present` outcome in `rules-lowered` stops the change: the written project does not let a rule take effect.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, so that `tests/kicad/test_probe_results.py` detects a change of behaviour in a later image.
- This bench departs from "Rules proofs carry a canary" in two points, as c0010's net-class bench does: the canary is scoped to `CANARY_A` and written last, because a board-wide `clearance` rule written after an unconditional canary would govern the canary pair; and the project is the one `write_triad` writes, because it is under test. Every other part of that requirement applies.

#### Scenario: Keys read
- **GIVEN** the target-10 bench on the local `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/project/test_minimums_drc.py::test_keys` runs
- **THEN** each probe item has its violation in `keys-template` and none in `keys-lowered`, and the canary fires in both

#### Scenario: Minimum over a lower rule
- **GIVEN** the `rules-template` run of the same bench, and `FLOOR_OVER_RULES` holding both majors for every key
- **WHEN** `test_floor_over_rules` runs
- **THEN** each probe item has its violation, the hole probe's being `drill_out_of_range`, and the canary fires

#### Scenario: Written project lets the rules take effect
- **GIVEN** the `rules-lowered` run, whose project holds `min_through_hole_diameter == JsonNumber("0.2")`
- **WHEN** `test_written` runs
- **THEN** no probe item has its violation and the canary fires

#### Scenario: Custom rule against a class clearance
- **GIVEN** the HV row in the `keys-template` and `rules-lowered` runs, and `RULES_OVER_CLASSES` holding both majors
- **WHEN** `test_rules_over_classes` runs
- **THEN** the HV row has its `clearance` violation in `keys-template` and none in `rules-lowered`, and the outcomes are recorded as `pro-min-class-control-t10` and `pro-min-class-t10`

#### Scenario: Canary missing
- **GIVEN** an authored DRC report text holding the violation of every probe item and no canary violation, read with c0017's `read_drc_report`
- **WHEN** `uv run pytest tests/unit/test_minimum_bench.py -k canary` judges it for each run
- **THEN** every outcome is `inconclusive`, and `assert_loaded` fails with a message saying the rules file was not loaded

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after the minimum tests
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `pro-min-*` probe of targets 9 and 10

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/project -q` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, and the target-10 cases are skipped by `kicad_min_major(10)`
