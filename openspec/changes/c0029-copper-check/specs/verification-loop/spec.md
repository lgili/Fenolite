## ADDED Requirements

### Requirement: Copper clearance stage
`fenolite.checks.copper.copper_stage(design, *, project, rules_source, frame, evidence) -> StageResult` SHALL run `check_copper` (`copper-check`) on the board model that `run_checks` read (`Validation.read.design`), for native and built input alike, because the board is the layout authority (`design-model`, "Layout authority"). `evidence` is `Validation.read.evidence`.
- **Rules.** When `rules_source` is given, `rules_source.design_rules(design, project)` (`backend-protocol`, "Design rules source") MUST give the design that is checked, `min_clearance`, `rules_over_classes` and `floor_over_rules`, which the stage passes to `check_copper`. Otherwise the design MUST be checked as read, and one `copper.rules-incomplete` warning MUST say that no rules source was given.
- **Incomplete rules.** `opaque_clearance_rules > 0` MUST give one `copper.rules-incomplete` warning with the count, and each `unread` entry one `copper.rules-incomplete` warning naming the file and its error.
- **Pads.** When `frame` is given, `pads` MUST be `frame.board_pads(<checked design>)` (c0028); otherwise `None`.
- **Skip.** The stage MUST be skipped with reason `read-refused` when the board read was refused.
- **No tool.** The stage MUST run no subprocess, so it needs no `kicad-cli`.
- **Status.** `ok` when no issue has severity `error`, `errors` otherwise.
- **Summary.** `CopperReport.summary`, plus `rules`: `{min_clearance, opaque_clearance_rules, unread}`.
- **Evidence.** `Evidence.combine` of `CopperReport.evidence`, `evidence` and `DesignRules.evidence` when a rules source was given; `UNVERIFIED` when the stage gave `copper.rules-incomplete` or `copper.item-unsupported`.
- The stage MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: Bridging track caught without KiCad
- **GIVEN** `tests/_copper.py::bridged_project(tmp_path, major=10)`: c0013's authored built project with one `F.Cu` track of net `VIN` added from pad 1 to pad 2 of `R1`, written with `write_board`; no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/checks/test_copper_stage.py -k bridging` runs `fenolite check <project> --stages copper.clearance --json`
- **THEN** the exit code is 5, the issues hold one `copper.short` error whose `where` contains `R1-2`, and no subprocess ran

#### Scenario: Clean authored project
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite check <project> --stages copper.clearance --json` runs
- **THEN** the stage has status `ok` and no `copper.short` or `copper.clearance` issue

#### Scenario: Refused read
- **GIVEN** a fake `Validator` that raises `FormatError`
- **WHEN** `run_checks` runs with `stages=("copper.clearance",)` on native input
- **THEN** the stage is skipped with reason `read-refused` and gives no issue

#### Scenario: Validator without a rules source
- **GIVEN** a fake `Validator` that satisfies neither `DesignRulesSource` nor `BoardFrame`, and whose board holds one footprint with two pads
- **WHEN** `uv run pytest tests/unit/checks/test_copper_stage.py -k no_source` runs the stage
- **THEN** it reports one `copper.rules-incomplete` warning naming the missing rules source and one `copper.item-unsupported` warning for the pads, and its level is `UNVERIFIED`

### Requirement: Copper stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. The build guard (`design-dsl`, "Copper guard before writing") emits the same codes into the `build` envelope, where they pass through unchanged as `design-dsl` "Build issue codes" allows for codes that later requirements add.

| code | severity | when |
|---|---|---|
| `copper.short` | error | copper of two nets touches or overlaps on a shared copper layer |
| `copper.clearance` | error, warning | a gap below the clearance in force; the governing rule sets the severity |
| `copper.zone-overlap` | warning | zones of different nets and equal priority overlap on a shared layer |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, per kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force |

#### Scenario: Copper literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `copper.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Copper codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the six `copper.*` codes appear in `docs/cli-contract.md`

## MODIFIED Requirements

### Requirement: Stages added for findings and round trips
`fenolite.checks.stages.STAGE_ORDER` SHALL be `("model.validate", "erc.lite", "copper.clearance", "drc.kicad", "netlist.assignment_compare", "roundtrip", "roundtrip.rt2")`: c0020 inserts `netlist.assignment_compare` before `roundtrip` and `roundtrip.rt2` after it, and c0029 inserts `copper.clearance` between `erc.lite` and `drc.kicad`, as "Check stages and statuses" allows.
- `OPT_IN_STAGES` MUST be `("roundtrip.rt2",)` and `DEFAULT_STAGES` MUST be `STAGE_ORDER` without them. `fenolite check` without `--stages` MUST run `DEFAULT_STAGES`, and `--stages` MUST accept every name of `STAGE_ORDER`.
- `ORACLE_STAGES` MUST be `("drc.kicad", "netlist.assignment_compare", "roundtrip.rt2")`. When any of them is selected, `cmd_check` MUST run the `kicad-cli` pre-flight of "Check exit codes" and MUST pass `KicadOracle(KicadCli(path, timeout=…))` as the oracle. `copper.clearance` MUST NOT be in `ORACLE_STAGES`: it runs no tool.
- `run_checks` MUST pass the `Validation` of its single `validator.validate` call, or `None` when that read was refused, to `assignment_stage`, and its board model (`Validation.read.design`), or `None`, to `drc_stage`. It MUST pass that board model with `Validation.read.evidence` and the project set to `copper_stage`, with the validator as `rules_source` when `isinstance(validator, DesignRulesSource)` is true and as `frame` when `isinstance(validator, BoardFrame)` is true, and `None` for each otherwise. It MUST still call `validator.validate` at most once per run.
- The functions of the two stages that c0020 adds MUST be `checks.assignment_compare.assignment_stage` and `checks.rt2.rt2_stage`. Each MUST be skipped with reason `read-refused` when the board read was refused, and with reason `unsupported-oracle` when `isinstance(oracle, NetlistOracle)`, respectively `isinstance(oracle, RoundTripOracle)`, is false (`backend-protocol`, "Netlist and round-trip oracles"). A stage skipped with `unsupported-oracle` MUST NOT count in the envelope evidence.
- The function of `copper.clearance` MUST be `checks.copper.copper_stage` ("Copper clearance stage").
- The stages that c0020 and c0029 add MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: Default stages leave RT2 out
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6 that writes a DRC report and an IPC-D-356 export, passed with `--kicad-cli`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `model.validate`, `erc.lite`, `copper.clearance`, `drc.kicad`, `netlist.assignment_compare` and `roundtrip` in this order, and no `roundtrip.rt2`

#### Scenario: RT2 selected
- **GIVEN** the same project and fake
- **WHEN** `fenolite check <project> --stages roundtrip.rt2,roundtrip --json` runs
- **THEN** `result.stages` names `roundtrip` then `roundtrip.rt2`

#### Scenario: New stages need kicad-cli
- **GIVEN** no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages netlist.assignment_compare --json` and the same command with `--stages roundtrip.rt2` run
- **THEN** both exit 6 with `FEN-6001`, and no stage runs

#### Scenario: Copper stage needs no kicad-cli
- **GIVEN** the same environment without `kicad-cli`, and `two_layer.kicad_pcb`, whose authored `GND_B` fill on `B.Cu` covers pad `2` of `D1` (net `LED_A`)
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages copper.clearance --json` runs
- **THEN** the stage runs, no `FEN-6001` is given, the exit code is 5, `copper.clearance` has status `errors`, and its issues hold exactly one `copper.short`, whose `where` contains `D1-2` and whose message names `GND`, `LED_A` and `B.Cu`

#### Scenario: Refused read skips the new stages
- **GIVEN** a fake `Validator` that raises `FormatError` and a fake oracle that satisfies `NetlistOracle` and `RoundTripOracle`
- **WHEN** `uv run pytest tests/unit/checks -k new_stages` calls `run_checks` with `stages=("netlist.assignment_compare", "roundtrip.rt2")` on native input
- **THEN** both stages are skipped with reason `read-refused` and give no issue

#### Scenario: Oracle without the operation
- **GIVEN** a fake `Oracle` that implements only `drc`
- **WHEN** `run_checks` runs `netlist.assignment_compare` with it
- **THEN** the stage is skipped with reason `unsupported-oracle`, and the envelope evidence does not count it

#### Scenario: New stages stay read-only
- **GIVEN** a fake `kicad-cli` that writes `x.kicad_prl` next to its input and rewrites its input board
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k new_stages` runs `fenolite check <project> --stages copper.clearance,netlist.assignment_compare,roundtrip.rt2`
- **THEN** the project snapshot is equal before and after, and no `.fenolite/`, `native/` or `.kicad_prl` entry was created
