## MODIFIED Requirements

### Requirement: Check canary injection
`fenolite.backends.kicad.canary` and `fenolite.backends.kicad.oracle.KicadOracle` SHALL prove, with a canary run of its own on a major of `CANARY_TWO_RUN` and in the counted run otherwise, whether a project's custom rules were loaded, with a canary scoped to its own nets and placed only in temporary copies (exempt from c0018's "Fenolite lowers only the design's rules").
- **Applicability.** The canary MUST apply only when the copy set holds both `<stem>.kicad_pro` and `<stem>.kicad_dru`. Otherwise the state MUST be `not-applicable`.
- **Rule.** `canary_rule_text(major)` MUST build the rule `CANARY_RULE_NAME = "fenolite_check_canary"`, a `clearance` of `CANARY_MIN_NM = 3_000_000` on net `FENOLITE_CANARY_A`, with c0018's `rulemap.rule_nodes` for that major. It MUST return `None` when `SELECTOR_SUPPORT["net"]` lacks the major. `append_rule(rules: bytes, rule_text: str, *, major) -> bytes` MUST place it where it takes precedence over the user's rules: after them when the later rule governs (`H-K-DRU-ORDER`), or where c0018's measured `rule_order` puts the governing rule on that major. It MUST keep every byte of the user's file, and MUST raise `CanaryError("names-taken")` when those bytes already contain `CANARY_RULE_NAME`. When the placement needs the `(version N)` offset and the bytes do not parse, it MUST append the rule at the end, and KiCad's verdict on the broken file stands.
- **Tracks.** `inject_board(data: bytes, *, file="") -> bytes` MUST insert two `segment`s of width `CANARY_WIDTH_NM = 250_000` on `F.Cu`, on nets `FENOLITE_CANARY_A` and `FENOLITE_CANARY_B`, from x = X to x = X + 2 mm at y = 0 and y = `CANARY_PITCH_NM` (1 mm). X is M + `CANARY_MARGIN_NM` (25 mm). M is the largest absolute number of the `at`, `xy`, `start`, `end`, `mid` and `center` nodes outside footprints, plus twice the largest one inside footprints. Their uuids MUST be `CANARY_UUIDS`, `uuid5(FENOLITE_NS, "kicad-canary:A")` and `uuid5(FENOLITE_NS, "kicad-canary:B")`. Their children MUST follow c0017's `CANONICAL_ORDER["segment"]`, and their net form the board's own (c0017, "Net form per target").
- **Text insertion.** The board MUST be parsed with `sexpr.parse_bytes`, so invalid UTF-8 raises `FormatError`, and the canary MUST be inserted as UTF-8 text at the byte offsets of the parsed nodes: in the numbered form, two `net` rows with fresh numbers before the root child that follows the last root `net` row; the segments before the root's closing parenthesis. Every other byte and every net number MUST be kept.
- **Proven per major.** `CANARY_SUPPORT` MUST hold exactly the majors whose committed probe files record `check-canary-fired` = `present` and `check-canary-broken` = `absent`, and `CANARY_TWO_RUN` every major that records `check-canary-neutral` = `different` and every major on which the register row of `H-K-CHECK-CANARY` records a corpus board whose stripped canary report differs from its plain report in runs that each repeat. Both start empty.
- **Inconclusive.** The state MUST be `inconclusive` with one reason: `placement-unproven` (the major is not in `CANARY_SUPPORT`), `selector-unproven`, `clearance-ignored` (the project sets `/board/design_settings/rule_severities/clearance` to `ignore`), `names-taken` (the rule name, a canary net name or a canary uuid is already used), `board-unparsed` (`inject_board` raised `FormatError`), `extent-too-large` (X + 2 mm over 2 000 mm), `no-front-copper`, `no-report` (KiCad wrote no report), or `clearance-limit` (decided after the run: the report of the canary run holds no canary pair and is saturated, see **Report limit**). When the state is decided before the run, the copy set MUST be passed unchanged.
- **Verdict.** `canary_fired(report)` MUST be true when a `clearance` violation's items are exactly the two canary uuids. `strip_canary(report)` MUST remove every violation and unconnected item that names a canary uuid and MUST return their count.
- **Report limit.** `kicad-cli` stops reporting `clearance` violations near 499 per run, and on a board with more the canary pair competes for a place, so it can be missing from a run that loaded the rules (`H-K-DRC-LIMIT`). `CLEARANCE_REPORT_LIMIT` MUST be `499`. `clearance_saturated(report) -> bool` MUST be true when the report holds at least `CLEARANCE_REPORT_LIMIT` violations of type `clearance`, the canary's own included. When the report of the canary run holds no canary pair, the state MUST be `inconclusive` with reason `clearance-limit` if `clearance_saturated` is true for that report, and `absent` otherwise. The oracle MUST NOT repeat the canary run to get another answer.
- **Oracle.** `KicadOracle(cli)` MUST have `name = "kicad"`, `version()`, `major()` and `drc(project) -> DrcOutcome`. `drc` MUST stage the canary board and rules in a private temporary folder outside the project and call `KicadCli.drc(<staged or original board>, files=<project.files without the board key, the rules entry replaced by the staged rules when staged>)`, so the board is passed only positionally. It MUST read the report with c0017's `read_drc_report` and strip the canary. `tool_writes` MUST be the names in `CliRun.outputs` other than the report. `oracle.EVIDENCE` MUST start `INFERRED` (`H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`) and MUST become `KICAD-VERIFIED` only when both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `DrcOutcome.evidence` MUST be the level and hypotheses of `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>` when a report exists, and `UNVERIFIED` otherwise. On a major where a row is refuted, it MUST cite the row's latest registered successor instead (`H-K-CHECK-CANARY-3` today). It MUST NOT pass `--exit-code-violations`.
- **Neutrality.** `H-K-CHECK-CANARY` MUST be settled on both majors. A major in `CANARY_TWO_RUN` MUST run DRC twice (a plain run gives the report, the canary run gives the verdict), and the register row MUST record it.

#### Scenario: Canary fires
- **GIVEN** the authored built project and the native `two_layer` project, each with a one-rule `<stem>.kicad_dru`
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_fires` runs on 9.0.9 and on 10.0.6
- **THEN** each report holds exactly one `clearance` violation between the two canary uuids, and the probe `check-canary-fired` records `present`

#### Scenario: Canary is neutral
- **GIVEN** the same projects
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_neutral` compares a canary run, stripped, with a run without the canary
- **THEN** the multisets of (type, severity, excluded, sorted item uuids) are equal, and the probe `check-canary-neutral` records `equal`

#### Scenario: Two runs on large boards
- **GIVEN** on 10.0.6 the 21 readable non-heavy demo boards with a `{}` project and a `(version 1)` rules file, where the canary tracks change other violations
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_two_run_demo_boards` runs `KicadOracle.drc` on each
- **THEN** the report, from the plain run, holds no canary item (`canary_removed` = 0), and the canary state is `fired`, or `inconclusive` with reason `clearance-limit` on a board whose report is saturated (`kicad-demo-10-0-6-pcb-01` and `-13`); on every other board it is `fired`

#### Scenario: Broken rules silence the canary
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru` as `<stem>.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there)
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_broken_rules` runs on both majors
- **THEN** the report holds no canary violation, the state is `absent`, and the probe `check-canary-broken` records `absent`

#### Scenario: Ignored clearance severity silences the canary
- **GIVEN** the authored built project whose `<stem>.kicad_pro` sets `/board/design_settings/rule_severities/clearance` to `ignore`
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_ignored` runs the canary copy on both majors, and `KicadOracle.drc` runs on the same project
- **THEN** the report holds no canary violation, the probe `check-canary-ignored` records `absent`, and the oracle's state is `inconclusive` with reason `clearance-ignored`

#### Scenario: Support follows the probe files
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_canary.py -k support` reads `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`
- **THEN** `CANARY_SUPPORT` and `CANARY_TWO_RUN` equal the majors that the recorded `check-canary-*` outcomes give

#### Scenario: Unproven major
- **GIVEN** `CANARY_SUPPORT` patched to an empty set and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k unproven` runs `KicadOracle.drc` on the authored project
- **THEN** the state is `inconclusive` with reason `placement-unproven`, and the board and rules file passed to `kicad-cli` are byte-equal to the originals

#### Scenario: User bytes kept
- **GIVEN** the bytes of `tests/data/kicad/board/two_layer.kicad_pcb`, and a copy with byte `0xFF` inside a string
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_canary.py -k inject` calls `inject_board` twice
- **THEN** both results are equal, removing the inserted spans gives the original bytes, and every net number is unchanged; the copy raises `FormatError` (`invalid UTF-8`), never `UnicodeDecodeError`

#### Scenario: Names already taken
- **GIVEN** a board that already has a net named `FENOLITE_CANARY_A`, and `CANARY_SUPPORT` and `SELECTOR_SUPPORT["net"]` patched to hold the fake's major
- **WHEN** `KicadOracle.drc` runs on its project with a fake `kicad-cli`
- **THEN** the state is `inconclusive` with reason `names-taken`, and the report is still read

#### Scenario: Staging outside the project
- **GIVEN** a fake `kicad-cli` that records its arguments and writes `x.kicad_prl`, and `CANARY_SUPPORT` and `SELECTOR_SUPPORT["net"]` patched to hold its major
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py` runs `KicadOracle.drc` on the authored project
- **THEN** the copied rules file starts with the user's bytes and contains `fenolite_check_canary`, no argument is `--exit-code-violations`, the project folder snapshot is unchanged, and `tool_writes` is `("x.kicad_prl",)`

#### Scenario: A saturated report gives no verdict
- **GIVEN** a fake `kicad-cli` whose canary run reports 499 `clearance` violations and no canary pair, and another whose canary run reports 498
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k saturated` runs `KicadOracle.drc` on each
- **THEN** the first state is `inconclusive` with reason `clearance-limit`, the second is `absent`, and each fake saw two `pcb drc` runs

## ADDED Requirements

### Requirement: Clearance report limit
`H-K-DRC-LIMIT` SHALL be settled on `kicad-cli` 9.0.9 and 10.0.6 by `tests/kicad/check/test_drc_limit.py` on an authored bench, before `KicadOracle.drc` relies on `CLEARANCE_REPORT_LIMIT`.
- **Bench.** `tests/kicad/check/_limitbench.py::limit_project(root, pairs) -> Path` MUST write `tests/data/kicad/board/two_layer.kicad_pcb` with `pairs` more pairs of `F.Cu` tracks, each pair on two nets of its own with a gap of 0.05 mm, a `{}` project and a `(version 1)` rules file. Every byte is authored for Fenolite.
- **Below the limit.** With 300 pairs the plain run MUST report 300 `clearance` violations more than the board without pairs, and the oracle's state MUST be `fired`.
- **At the limit.** With 700 pairs the plain run MUST report at least `CLEARANCE_REPORT_LIMIT` and fewer than 700 `clearance` violations; on 10.0.6 exactly `CLEARANCE_REPORT_LIMIT`.
- **Verdict.** With 700 pairs, each of five `KicadOracle.drc` outcomes MUST be `fired` or `inconclusive` with reason `clearance-limit`, and never `absent`.
- The measured counts per major MUST be recorded in `docs/evidence/kicad-check.md`.

#### Scenario: The count stops near 499
- **GIVEN** the bench with 300 pairs and with 700 pairs
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limit.py -k count` runs on 9.0.9 and on 10.0.6
- **THEN** 300 pairs give 300 more `clearance` violations than no pair, and 700 pairs give at least 499 and fewer than 700 (exactly 499 on 10.0.6)

#### Scenario: A saturated board never reads as rules not loaded
- **GIVEN** the bench with 700 pairs, whose rules file loads
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limit.py -k verdict` runs `KicadOracle.drc` five times on both majors
- **THEN** every state is `fired` or `inconclusive` with reason `clearance-limit`, and none is `absent`

### Requirement: DRC repeatability on the demo boards
`H-K-DRC-REPEAT` SHALL be settled on `kicad-cli` 10.0.6 by `tests/kicad/check/test_canary.py::test_two_run_demo_boards`, which MUST run `KicadOracle.drc` twice on each readable non-heavy demo board, in a folder with a `{}` project and a `(version 1)` rules file, and MUST compare the two outcomes with `tests/_drcrepeat.py`.
- **Strict part.** Each of the two outcomes MUST have `canary_removed` = 0 and a report that names no canary uuid, and its canary state MUST be `fired`; only when its report is saturated (`clearance_saturated`, "Check canary injection") MAY the state instead be `inconclusive` with reason `clearance-limit`. The two outcomes MUST be equal in `outcome`, `returncode` and `tool_writes`, and in `canary` and `canary_reason` unless a report is saturated.
- **Canonical form.** Reports MUST be compared as `DrcReport.entries()`: sorted, without item uuids, with the temporary folder of the run left out of the descriptions. The report order MUST NOT count.
- **Named types.** `UNREPEATABLE_TYPES` MUST be `frozenset({"clearance", "hole_clearance", "unconnected_items"})`. On every board, the entries of every other type MUST be equal between the two runs.
- **Named boards.** `UNREPEATABLE_BOARDS` MUST be the ids `kicad-demo-10-0-6-pcb-01`, `-07`, `-09`, `-11`, `-13` and `-16`. On every other board the whole canonical report MUST be equal.
- **Helper.** `repeat_problems(board_id: str, first: DrcOutcome, second: DrcOutcome) -> list[str]` MUST return one line per difference or broken rule, naming the board and the field, or the type with both counts, and an empty list when the two outcomes agree as stated above. An outcome without a report MUST be a problem.
- **No tolerance by retry.** The test MUST NOT retry, skip or be marked flaky. A board or a type MUST join a named set only with a measurement of at least 15 runs per board recorded in `docs/evidence/kicad-check.md` and in the register row.
- **Record.** `docs/evidence/kicad-check.md` MUST hold, per board and per `kicad-cli` build measured, as ids and counts only: the runs, how often the canary fired, the totals, the count of distinct reports and of distinct orders, the types whose count varies, and the unstable keys per type.

#### Scenario: A stable board repeats exactly
- **GIVEN** `kicad-demo-10-0-6-pcb-17`, which is not in `UNREPEATABLE_BOARDS`
- **WHEN** `uv run pytest "tests/kicad/check/test_canary.py::test_two_run_demo_boards[kicad-demo-10-0-6-pcb-17]"` runs on 10.0.6
- **THEN** both runs give `fired` with no canary item, and `repeat_problems` returns an empty list for the whole report

#### Scenario: A named board repeats outside the named types
- **GIVEN** `kicad-demo-10-0-6-pcb-11`, whose `clearance` count differs between runs
- **WHEN** the same test runs on it
- **THEN** both runs give `fired` with no canary item, and the entries of every type outside `UNREPEATABLE_TYPES` are equal

#### Scenario: A difference outside the named sets fails
- **GIVEN** two authored outcomes for a board in `UNREPEATABLE_BOARDS` that differ in one `track_dangling` entry, and two for another board that differ in one `clearance` entry
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k problems` calls `repeat_problems`
- **THEN** each pair gives one problem naming the board and the type, a pair differing only in report order gives none, a pair differing in the canary state gives a problem naming `canary`, and an `inconclusive` state on a report that is not saturated gives a problem

#### Scenario: The named sets match the record
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k record` reads `docs/evidence/kicad-check.md` and the register row of `H-K-DRC-REPEAT`
- **THEN** both name every id of `UNREPEATABLE_BOARDS` and every type of `UNREPEATABLE_TYPES`
