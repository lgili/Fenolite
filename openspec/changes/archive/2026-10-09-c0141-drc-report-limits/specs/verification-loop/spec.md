## ADDED Requirements

### Requirement: DRC report limits in check
`checks.drc.drc_stage` SHALL say, for each type of the DRC report whose count reached the limit at which the tool stops writing entries, that the count is a lower bound, because KiCad's report holds no key that says so and `check` otherwise gives a cut count as complete (`H-K-DRC-LIMITS`).
- **Summary.** The summary of the stage MUST gain `limits`: `null` when there is no report or when the oracle does not satisfy `LimitedOracle` (`backend-protocol`, "DRC report limits of an oracle"), and otherwise a list, sorted by `type`, with one `{type, reported, limit}` for every violation type, and for `unconnected_items`, whose count in the counted report is at least `oracle.report_limits().limit(type)`. The counts MUST be those of `by_type` and `unconnected`: taken after the canary's own violations are removed, on the report the summary counts. An empty list says that every count is complete; `null` says that nothing is known.
- **Issue.** Each entry MUST give one `check.report-limit` warning, after the findings of the stage: `where` MUST be the issue code of the type (`<oracle>.drc.<type with dashes>`, `kicad.drc.unconnected-items` for the unconnected items), and the message MUST name the type, the count reported and the limit, and say that the board holds at least that many. Its hint MUST say that the other findings of the type are not in the report and that repairing the reported ones and checking again shows the next ones.
- **Code.** `fenolite.checks.codes.ISSUE_CODES` MUST gain `check.report-limit` (warning). The code is not a `<oracle>.drc.*` code: it describes the report, not the board, so a rule that silences or waives DRC findings by their code never covers it. `src/fenolite/cli/data/explain.toml` MUST hold one table for it, and `docs/cli-contract.md` MUST document it under `check`.
- **Nothing else moves.** The status of the stage, its evidence, the canary verdict, `violations_judged`, the findings and the exit code MUST be what they are without this requirement: a warning never turns `ok` into `errors`, and a count under its limit is complete, so a report without an error still means that KiCad found none.
- **At least, not equal.** A count equal to its limit MUST be marked even though the board may hold exactly that many: 9.0.9 writes up to a few more than 499 `clearance` entries, and a type that no probe measured is taken to stop at `others`. The mark then says "at least", which stays true.
- `check --format concise` MUST keep `summary.limits` as it keeps every stage summary.
- `docs/cli-contract.md` MUST state the limits per type and major with their evidence label, and that above a limit the count is a lower bound.

#### Scenario: Two types at their limits
- **GIVEN** a fake `Oracle` named `fake` that also has `report_limits()` returning `DrcLimits({"unconnected_items": 499}, others=199)`, whose report holds 499 unconnected items, 199 `silk_overlap` warnings and 150 `track_dangling` warnings, and canary `fired`
- **WHEN** `uv run pytest tests/unit/checks/test_drc_stage_limits.py -k two_types` runs `drc_stage`
- **THEN** `summary.limits` is `[{"type": "silk_overlap", "reported": 199, "limit": 199}, {"type": "unconnected_items", "reported": 499, "limit": 499}]`, the issues end with two `check.report-limit` warnings whose `where` are `fake.drc.silk-overlap` and `fake.drc.unconnected-items`, and no entry names `track_dangling`

#### Scenario: Every count under its limit
- **GIVEN** the same fake with 12 `silk_overlap` warnings and no unconnected item
- **WHEN** the stage runs
- **THEN** `summary.limits` is `[]`, no `check.report-limit` is reported, and the status is `ok`

#### Scenario: An oracle that states no limits
- **GIVEN** a fake `Oracle` without `report_limits`, whose report holds 499 unconnected items
- **WHEN** the stage runs
- **THEN** `summary.limits` is `null` and no `check.report-limit` is reported

#### Scenario: The mark changes no verdict
- **GIVEN** the fake of the first scenario
- **WHEN** `uv run pytest tests/unit/checks/test_drc_stage_limits.py -k verdict` runs the stage with and without `report_limits`
- **THEN** both results have the same status, evidence, `canary` and findings, and differ only in `summary.limits` and the two warnings

#### Scenario: The code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py tests/consistency -k "explain or codes"` runs
- **THEN** `check.report-limit` has a table in `explain.toml` and a line in `docs/cli-contract.md`

## MODIFIED Requirements

### Requirement: Check output is deterministic
Two `fenolite check --json` runs on the same project with the same `kicad-cli` SHALL give byte-identical stdout apart from `elapsed_ms` whenever the tool repeats its own reports, and Fenolite SHALL add no difference of its own.
- The output MUST NOT hold the DRC report's `date`, a temporary path, the home directory or an absolute path. Paths MUST be relative to the project root.
- Stages MUST follow `STAGE_ORDER`. Issues within a stage MUST be sorted by code, then `where`, then message.
- `project.files`, `project.skipped`, `tool_writes` and the keys of `by_type` and `by_severity` MUST be sorted.
- **What the tool does not repeat.** `kicad-cli` 10.0.6 writes its DRC report in another order from run to run, which the sorting above removes, and on boards with hundreds of violations it does not repeat the entries of the types `clearance`, `hole_clearance` and `unconnected_items` (`H-K-DRC-REPEAT`, `H-K-RT2-STABLE-2`). On such a board two runs MAY differ in the `drc.kicad` issues `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items`, in the `drc.kicad` summary values counted from them (`violations`, `unconnected`, `by_type`, `by_severity`, `types`, and the entries of `limits` for those three types), in the `check.report-limit` warnings of those three types ("DRC report limits in check"), in the status of `drc.kicad` and in the exit code when those issues decide them. On a board with 499 or more `clearance` violations the canary state MAY also differ, between `fired` and `inconclusive` with reason `clearance-limit` (`H-K-DRC-LIMIT`; `kicad-oracle`, "Check canary injection"), and with it the issue `kicad.drc.rules-unchecked` and the evidence of `drc.kicad`. Nothing else MAY differ: the other stages, `tool_writes` and every issue of another code MUST be equal, and so MUST the canary state on a board below that count.
- `docs/cli-contract.md` MUST state under `check` which part of the output repeats and MUST name the three codes.

#### Scenario: Two runs on both majors
- **GIVEN** the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k deterministic` runs `fenolite check --json` twice on 9.0.9 and on 10.0.6
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no `<tmp>`, home or absolute path

#### Scenario: Hermetic stages
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,roundtrip --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`

#### Scenario: A board whose DRC report the tool does not repeat
- **GIVEN** `kicad-demo-10-0-6-pcb-07` with a `{}` project and a `(version 1)` rules file, on 10.0.6
- **WHEN** `uv run pytest "tests/kicad/check/test_canary.py::test_two_run_demo_boards[kicad-demo-10-0-6-pcb-07]"` runs the oracle of `drc.kicad` twice
- **THEN** the two outcomes agree in the canary state (the board holds fewer than 499 `clearance` violations), the return code, `tool_writes` and every entry of a type other than `clearance`, `hole_clearance` and `unconnected_items`

#### Scenario: The contract names what does not repeat
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k contract` reads `docs/cli-contract.md`
- **THEN** its `check` section names `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items` as the issues that can differ between two runs, and the reason `clearance-limit`

#### Scenario: Report limits repeat on a board the tool repeats
- **GIVEN** the authored limits bench of `kicad-oracle`, "DRC report limits are probed", with 700 copies of a `track_dangling` violation, on 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limits.py -k deterministic` runs `fenolite check <bench> --stages drc.kicad --json` twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`, `summary.limits` and the one `check.report-limit` warning included
