## ADDED Requirements

### Requirement: Placement rules stage
`fenolite check` SHALL gain the stage `placement.rules` in both of its pipelines. In `STAGE_ORDER` it stands after `copper.clearance` and after `length.rules` when a change has inserted that stage, and before `zone.fill`, as "Check stages and statuses" allows. In `DOCUMENT_STAGES` ("Document check pipeline") it stands after `copper.clearance` and before `parity`. It MUST be a default stage of both, MUST NOT be in `ORACLE_STAGES`, MUST run no subprocess, and MUST be run by `checks.placement.placement_stage(design, *, model, built, frame, rules_source, project, evidence) -> StageResult` with the board model of the run (`Validation.read.design` in `run_checks`, the PCB reading in `run_document_checks`), the `.fenolite/` model and `built`, the validator as `frame` when it satisfies `BoardFrame` and as `rules_source` when it satisfies `DesignRulesSource` (`None` otherwise), and the evidence of that reading.
- **What runs.** On a built project the stage MUST run `judge` ("Placement rules judged", capability `placement`) with `rules_of(model)`, and `measure` ("Placement measures"); on native input `measure` only. `pads` MUST come from `frame.board_pads`. The `pitch` of `measure` MUST be the track width plus the clearance of the class `Default` of `rules_source.design_rules(design, project).design`, and `None` without a rules source or without that class.
- **Both backends.** The stage reads the model and the board frame only, so it MUST give the same verdict for one script built for KiCad and for Altium when the pad positions are equal.
- **Keep-outs** are not judged here. On a KiCad project, KiCad's DRC reports them in `drc.kicad`. On Altium documents no stage judges a part in a keep-out; `docs/altium.md` MUST say so.
- **Skips.** The stage MUST be skipped with reason `read-refused` when the board read was refused, with `cache-unreadable` when the project is built and its `.fenolite/` failed to load, with the new reason `no-frame` when `frame` is `None`, and on document input with `single-source` when the set holds no PCB document.
- **Status.** `errors` when an issue has severity `error`, `ok` otherwise.
- **Summary.** `rules`: the counts of `judge` by rule family, every count 0 on native input; `measures`: `Measures.to_json()`.
- **Evidence.** `evidence` when no rule was judged; `Evidence.combine(checks.placement.EVIDENCE, evidence)` when one was, `checks.placement.EVIDENCE` being `INFERRED`.
- The stage MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: A rule fails without kicad-cli
- **GIVEN** the blink built with `design.near("led", d1, r1.pad(2), within=mm(5))`, whose nearest pad of `D1` lies about 12.2 mm from that pad; no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/checks/test_placement_stage.py -k fails` runs `fenolite check <dir> --stages placement.rules --json`
- **THEN** the exit code is 5, no subprocess ran, the issues hold one `placement.too-far` error with `where == "D1"`, and `summary.rules.near` is `{"judged": 1, "failed": 1, "skipped": 0}`

#### Scenario: Native board measured
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages placement.rules --json` runs
- **THEN** the stage has status `ok`, no issue, `summary.rules` with every count 0, and `summary.measures.nets` above 0

#### Scenario: Default stage order
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6 that writes a DRC report and an IPC-D-356 export
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `placement.rules` after `copper.clearance` and before `zone.fill`

#### Scenario: The same rule on a built Altium project
- **GIVEN** the routed blink with `design.near("led", d1, r1.pad(2), within=mm(5))`, built with `--target altium --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_check_altium.py -k placement_rules` runs `fenolite check <dir> --json`
- **THEN** `result.stages` names `placement.rules` after `copper.clearance` and before `parity`, the issues hold one `placement.too-far` error with `where == "D1"`, the exit code is 5, and `summary.measures.nets` is above 0

#### Scenario: Altium documents without a script
- **WHEN** `fenolite check tests/data/altium/routed/routed.PcbDoc --stages placement.rules --json` runs
- **THEN** the stage has status `ok`, `summary.rules` has every count 0, and `summary.measures.nets` is above 0

#### Scenario: Skips
- **WHEN** `run_checks` runs the stage with a validator that raises `FormatError`, then on a built project whose cache fails to load, then with a validator that is not a `BoardFrame`
- **THEN** the stage is skipped with `read-refused`, `cache-unreadable` and `no-frame` in turn, and gives no issue

### Requirement: Placement stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. `place` and the placement guard of `build` emit the same codes, each with a severity no higher than `warning`. `src/fenolite/cli/data/explain.toml` MUST hold one table for each of them and for `place.keepout` and `place.keepout-no-courtyard` (`placement`, "Placement legality"), as `cli-contract`, "Explain command", asks of every code.

| code | severity | when |
|---|---|---|
| `placement.too-far` | error, warning | a part of a `near` rule has no selected pad within `within` of a pad of the anchor; the rule sets the severity |
| `placement.rule-unresolved` | error | a placement rule names something that the board does not hold: a part or a pad, or, for a rule that a later requirement adds, what that requirement says |
| `placement.rule-skipped` | info | a rule names a part that lies off the board, so it is not judged for it |

#### Scenario: Placement literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `placement.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Placement codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the three `placement.*` codes appear in `docs/cli-contract.md`

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain place.keepout --json`
- **THEN** the test passes with a table for `place.keepout`, `place.keepout-no-courtyard`, `placement.too-far`, `placement.rule-unresolved` and `placement.rule-skipped`, and the command exits 0 with a non-empty `result.meaning` and `result.fix`
