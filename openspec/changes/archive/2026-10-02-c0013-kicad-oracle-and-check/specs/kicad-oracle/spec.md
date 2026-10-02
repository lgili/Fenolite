## ADDED Requirements

### Requirement: Check project copy set
`fenolite.backends.kicad.projectset` SHALL plan, without writing anything, the closed set of project files that `kicad-cli pcb drc` reads, and c0009's runner SHALL copy them through c0017's `KicadCli.drc(board, files=…)`.
- **Board.** `resolve_board(path) -> Path` MUST accept a `.kicad_pcb` file; a `.kicad_pro` file (the board of the same stem); or a folder holding exactly one `.kicad_pro` (the board of its stem), or else exactly one `.kicad_pcb`. A folder with several candidates or none MUST raise `ProjectResolutionError` (`cli_code` `FEN-2001`) whose `candidates` list them. A missing path or board MUST raise a `FenoliteError` with `cli_code` `FEN-3001`.
- **Included.** `project_set(path, *, max_bytes=MAX_COPY_BYTES) -> ProjectSet` MUST include, under names relative to the board's folder: the board; `<stem>.kicad_pro` and `<stem>.kicad_dru` when present (`has_project`, `has_rules`), because KiCad reads rules only with a project file next to the board (`H-K-TOK-RULES-SILENT`) and pairs them by stem (`H-K-CHECK-COPYSET`); the top-level `fp-lib-table`, read with c0008's `read_lib_table`, and each library folder that a row names as `${KIPRJMOD}/<rel>` inside the root, under `<rel>`; and the drawing sheet named at `WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"` of the project (read with c0010's `read_project` and `_json.get`) when it is a `${KIPRJMOD}` or relative path inside the root.
- **Never included.** `.kicad_prl`, `.kicad_sch`, `sym-lib-table`, backups, `fp-info-cache`, `.fenolite/` and every other file. Absolute library rows and an absolute drawing-sheet path MUST stay as written and be read in place by KiCad.
- **Skips.** Each named file or folder that is not copied MUST give a `SkippedFile(name, reason)`: `outside-root`, `variable` (a variable other than `${KIPRJMOD}`), `relative` (a library row without a variable), `missing`, `nested-table` (a `Table` row), `too-large`, or `reserved-name` (a name whose first path part is `config`, which c0009's runner reserves for `KICAD_CONFIG_HOME` and refuses in `files`).
- **Size.** `MAX_COPY_BYTES` MUST be `256 * 2**20`. The board, project, rules file and table MUST always be included. The drawing sheet, then the library folders in table order, MUST be skipped with `too-large` when adding them would bring the total over `max_bytes`.
- `H-K-CHECK-COPYSET` MUST be settled before `projectset.py` is final: DRC on the copy set gives the same violations and unconnected items as DRC on a copy of the whole project folder. If it is refuted, the missing kind MUST join the include list.

#### Scenario: Closed include list
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, decoys=True)`, with a `${KIPRJMOD}` library row, `notes.txt`, a `sym-lib-table` and a `.kicad_prl`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_projectset.py -k include` calls `project_set` on it
- **THEN** the keys of `files` are exactly the board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, `fp-lib-table` and the library folder, `skipped` is empty, and the folder snapshot is unchanged

#### Scenario: Skipped rows
- **GIVEN** an `fp-lib-table` with rows `${KIPRJMOD}/../Other.pretty`, `${MYLIBS}/X.pretty`, `Rel.pretty`, `${KIPRJMOD}/config/Y.pretty` (an existing folder) and one `Table` row
- **WHEN** `project_set` runs
- **THEN** `skipped` holds the reasons `outside-root`, `variable`, `relative`, `reserved-name` and `nested-table`, and none of the five is in `files`

#### Scenario: Size limit
- **GIVEN** the authored project and `max_bytes` smaller than its library folder
- **WHEN** `project_set(path, max_bytes=…)` runs
- **THEN** the library folder is skipped with `too-large`, and the board, project, rules file and table are in `files`

#### Scenario: Ambiguous folder
- **GIVEN** a folder holding `a.kicad_pcb` and `b.kicad_pcb` and no project file
- **WHEN** `resolve_board(folder)` is called
- **THEN** `ProjectResolutionError` is raised with `cli_code == "FEN-2001"` and both boards in `candidates`

#### Scenario: Copy set equals the folder
- **GIVEN** the authored built project with a KiCad-written `.kicad_prl`, a `sym-lib-table` and `notes.txt`
- **WHEN** `uv run pytest tests/kicad/check/test_copy_set.py::test_copy_set_equals_folder` runs on 9.0.9 and on 10.0.6
- **THEN** both runs give equal multisets of (type, severity, excluded, sorted item uuids) over violations and unconnected items, and the probe `check-copyset` records `equal`

### Requirement: Check canary injection
`fenolite.backends.kicad.canary` and `fenolite.backends.kicad.oracle.KicadOracle` SHALL prove, in the same DRC run, whether a project's custom rules were loaded, with a canary scoped to its own nets and placed only in temporary copies (exempt from c0018's "Fenolite lowers only the design's rules").
- **Applicability.** The canary MUST apply only when the copy set holds both `<stem>.kicad_pro` and `<stem>.kicad_dru`. Otherwise the state MUST be `not-applicable`.
- **Rule.** `canary_rule_text(major)` MUST build the rule `CANARY_RULE_NAME = "fenolite_check_canary"`, a `clearance` of `CANARY_MIN_NM = 3_000_000` on net `FENOLITE_CANARY_A`, with c0018's `rulemap.rule_nodes` for that major. It MUST return `None` when `SELECTOR_SUPPORT["net"]` lacks the major. `append_rule(rules: bytes, rule_text: str, *, major) -> bytes` MUST place it where it takes precedence over the user's rules: after them when the later rule governs (`H-K-DRU-ORDER`), or where c0018's measured `rule_order` puts the governing rule on that major. It MUST keep every byte of the user's file, and MUST raise `CanaryError("names-taken")` when those bytes already contain `CANARY_RULE_NAME`. When the placement needs the `(version N)` offset and the bytes do not parse, it MUST append the rule at the end, and KiCad's verdict on the broken file stands.
- **Tracks.** `inject_board(data: bytes, *, file="") -> bytes` MUST insert two `segment`s of width `CANARY_WIDTH_NM = 250_000` on `F.Cu`, on nets `FENOLITE_CANARY_A` and `FENOLITE_CANARY_B`, from x = X to x = X + 2 mm at y = 0 and y = `CANARY_PITCH_NM` (1 mm). X is M + `CANARY_MARGIN_NM` (25 mm). M is the largest absolute number of the `at`, `xy`, `start`, `end`, `mid` and `center` nodes outside footprints, plus twice the largest one inside footprints. Their uuids MUST be `CANARY_UUIDS`, `uuid5(FENOLITE_NS, "kicad-canary:A")` and `uuid5(FENOLITE_NS, "kicad-canary:B")`. Their children MUST follow c0017's `CANONICAL_ORDER["segment"]`, and their net form the board's own (c0017, "Net form per target").
- **Text insertion.** The board MUST be parsed with `sexpr.parse_bytes`, so invalid UTF-8 raises `FormatError`, and the canary MUST be inserted as UTF-8 text at the byte offsets of the parsed nodes: in the numbered form, two `net` rows with fresh numbers before the root child that follows the last root `net` row; the segments before the root's closing parenthesis. Every other byte and every net number MUST be kept.
- **Proven per major.** `CANARY_SUPPORT` MUST hold exactly the majors whose committed probe files record `check-canary-fired` = `present` and `check-canary-broken` = `absent`, and `CANARY_TWO_RUN` every major that records `check-canary-neutral` = `different` and every major on which the register row of `H-K-CHECK-CANARY` records a corpus board whose stripped canary report differs from its plain report in runs that each repeat. Both start empty.
- **Inconclusive.** The state MUST be `inconclusive` with one reason: `placement-unproven` (the major is not in `CANARY_SUPPORT`), `selector-unproven`, `clearance-ignored` (the project sets `/board/design_settings/rule_severities/clearance` to `ignore`), `names-taken` (the rule name, a canary net name or a canary uuid is already used), `board-unparsed` (`inject_board` raised `FormatError`), `extent-too-large` (X + 2 mm over 2 000 mm), `no-front-copper`, or `no-report` (KiCad wrote no report). When the state is decided before the run, the copy set MUST be passed unchanged.
- **Verdict.** `canary_fired(report)` MUST be true when a `clearance` violation's items are exactly the two canary uuids. `strip_canary(report)` MUST remove every violation and unconnected item that names a canary uuid and MUST return their count.
- **Oracle.** `KicadOracle(cli)` MUST have `name = "kicad"`, `version()`, `major()` and `drc(project) -> DrcOutcome`. `drc` MUST stage the canary board and rules in a private temporary folder outside the project and call `KicadCli.drc(<staged or original board>, files=<project.files without the board key, the rules entry replaced by the staged rules when staged>)`, so the board is passed only positionally. It MUST read the report with c0017's `read_drc_report` and strip the canary. `tool_writes` MUST be the names in `CliRun.outputs` other than the report. `oracle.EVIDENCE` MUST start `INFERRED` (`H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`) and MUST become `KICAD-VERIFIED` only when both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `DrcOutcome.evidence` MUST be the level and hypotheses of `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>` when a report exists, and `UNVERIFIED` otherwise. On a major where a row is refuted, it MUST cite the `-2` successor id instead. It MUST NOT pass `--exit-code-violations`.
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
- **THEN** the canary state is `fired` and the report, from the plain run, holds no canary item (`canary_removed` = 0)

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

### Requirement: Subcommand matrix from help text
`fenolite.backends.kicad.helpmatrix` SHALL tell which `kicad-cli` subcommands and options exist by reading `kicad-cli <words> --help` pages, run through c0009's `KicadCli`, because even `--help` writes a configuration folder (observed on 10.0.6).
- `parse_help(text) -> HelpPage | None` MUST read the `Usage:` line: its `{a,b,…}` group gives a group's subcommands, and its `[--name …]` groups give a leaf's long options. It MUST return `None` when no `Usage:` line is found. The grammar MUST be recorded in `docs/formats/kicad/cli.md` from observed runs (`H-K-CLI-HELP`); no KiCad or argument-parser source is read, and unit tests use authored synthetic pages.
- `MATRIX` MUST be a closed tuple of `MatrixEntry(command, options)`: `pcb drc` (`--format`, `--severity-all`, `--schematic-parity`, `--refill-zones`, `--save-board`), `pcb upgrade`, `pcb import`, `pcb render`, `pcb export ipcd356`, `pos`, `svg`, `gerbers`, `drill`, `stats`, `ipc2581` and `odb`, `fp upgrade`, `sym upgrade`, `sch erc`, `sch export netlist` and `jobset run`.
- `command_matrix(cli) -> CommandMatrix(version, rows, unparsed)` MUST give one boolean row per command and per option of `MATRIX`. A command exists when its last word is a subcommand of its parent's page; an option exists when it is an option of the command's page. A page that does not parse MUST be listed in `unparsed`, and its rows MUST be left out of `rows`.
- Each row MUST be recorded as the probe `check-help-<words>[-<option>]`, such as `check-help-pcb-drc-refill-zones`, with outcome `present` or `absent`.

#### Scenario: Group page
- **GIVEN** the authored page `Usage: kicad-cli pcb [--help] {drc,export,upgrade}`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_helpmatrix.py -k group` calls `parse_help`
- **THEN** `subcommands` is `{"drc", "export", "upgrade"}`

#### Scenario: Leaf page
- **GIVEN** the authored page `Usage: kicad-cli pcb drc [--help] [--format VAR] [--severity-all] INPUT_FILE`
- **WHEN** `parse_help` is called
- **THEN** `options` is `{"--help", "--format", "--severity-all"}`

#### Scenario: Page without a usage line
- **WHEN** `parse_help("Error: unknown command")` is called
- **THEN** it returns `None`

#### Scenario: Matrix matches the documented command sets
- **GIVEN** kicad-cli 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_help_matrix.py::test_matrix_matches_facts` runs on each
- **THEN** every `MATRIX` page parses; `pcb import`, `pcb upgrade` and `pcb drc --refill-zones` and `--save-board` are present exactly on 10.0.6 (agreeing with `H-K-00` and `H-K-01`); `pcb drc --format`, `--severity-all`, `pcb export ipcd356`, `pos` and `svg` are present on both; and every row is recorded as a `check-help-*` probe
