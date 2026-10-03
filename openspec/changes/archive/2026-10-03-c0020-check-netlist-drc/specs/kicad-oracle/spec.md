## ADDED Requirements

### Requirement: Netlist oracle from IPC-D-356
`fenolite.backends.kicad.oracle.KicadOracle.netlist(project, *, board) -> NetlistOutcome` SHALL run `pcb export ipcd356` through c0009's `KicadCli.export_ipcd356(<board path>, files=<project files without the board key>)`, read the text with `read_ipcd356`, and match its records to the pads of `board` with `fenolite.backends.kicad.padnets.match_pads(board, export)`.
- **Matching.** Via records (`ref == "VIA"` and an empty pin) MUST be skipped and counted. Every other `317` or `327` record MUST be paired with a distinct pad of `board` whose key (reference cut to `REF_WIDTH = 6` characters, pad number cut to `PIN_WIDTH = 4`) equals the record's, the nearest one within `BOUND_UNITS = 2` export units per axis, with positions taken relative to an anchor record whose key is unique in the export and in the board. This is c0009's comparison, moved from `tests/kicad/board/_frame.py` into `src`; `_frame.pad_report` MUST call `match_pads` and keep its behaviour.
- **Assignments.** `export_netlist(board, export) -> PadNetList` (source `export`) MUST give each paired record as `PadAssignment(f"{ref}-{number}", <record net>)`, with the pad's full reference and number. When two or more net names of `board` share their last `NET_WIDTH = 14` characters, the export cannot tell those nets apart, so every pad on them MUST become `Uncovered(element, "net-label-ambiguous")`.
- **Coverage.** A numbered pad of `board` that no record is paired with MUST become `Uncovered(element, "not-exported")`. A record paired with no pad MUST become `Uncovered(f"{ref}-{pin}", "unmatched-record")`, with the export's truncated fields.
- **Failures.** A non-zero exit, a missing export or a `FormatError` from `read_ipcd356` MUST give `netlist=None` and the message, and a timeout MUST give `outcome="timeout"`; no exception is raised, and nothing is written under `project.root`.
- **Evidence.** `NetlistOutcome.evidence` MUST be `Evidence.combine(padnets.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, and `UNVERIFIED` without an export. `padnets.EVIDENCE` MUST start `INFERRED` (`H-K-NET-IPC`) and MUST become `KICAD-VERIFIED` only when that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Authored project on both majors
- **GIVEN** c0013's authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k partition` runs on 9.0.9 and on 10.0.6
- **THEN** every numbered pad is assigned, `compare(board_netlist(design), outcome.netlist)` gives no difference, and the probe `netlist-partition` records `equal`

#### Scenario: Colliding long net names
- **GIVEN** an authored board whose nets `/A/LONG_SIGNAL_NAME` and `/B/LONG_SIGNAL_NAME` each join two pads
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k collision` runs `KicadOracle.netlist` on 9.0.9 and on 10.0.6
- **THEN** the four pads are `Uncovered` with reason `net-label-ambiguous`, the comparison with the board gives no difference, and the probe `netlist-label-collision` records `equal` when the export gives both nets one label and `different` otherwise

#### Scenario: Frame test unchanged
- **GIVEN** `tests/kicad/board/_frame.py::pad_report` calling `padnets.match_pads`
- **WHEN** `uv run pytest tests/kicad/board/test_board_frame.py -k ipcd356` runs with `FENOLITE_CENSUS_OUT` set, on 10.0.6 with the corpus and on 9.0.9 for the authored board
- **THEN** it passes, and the matched, via, truncated-key and ambiguous-key counts it writes equal those that `docs/evidence/kicad-board-read.md` records for 10.0.6

#### Scenario: Export failure
- **GIVEN** a fake `kicad-cli` whose `pcb export ipcd356` exits 3 without writing, and another that sleeps longer than the timeout
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k netlist` runs `KicadOracle.netlist`
- **THEN** the first gives `netlist is None` and a message, the second `outcome == "timeout"`, and neither raises

### Requirement: RT2 oracle
`fenolite.backends.kicad.oracle.KicadOracle.rt2(project) -> Rt2Outcome` SHALL produce the DRC reports that RT2 compares, without the check canary.
- **Re-dump.** The board MUST be read with `read_board`, rebuilt with `rebuild_board` and printed with `dumps`. The text MUST be staged under the board's own name in a private temporary folder outside `project.root`, removed afterwards.
- **Normalisation.** When the running major is 10 or more and the oracle was built with `rt2_normalise=True`, the default of `KicadOracle(cli, *, rt2_normalise=True)`, the original and the re-dump MUST each be re-saved with `KicadCli.upgrade_board` before DRC, and `normalised` MUST be true. On 9.0, which has no `pcb upgrade`, and with `rt2_normalise=False`, the files MUST be checked as they are, and `normalised` MUST be false.
- **Runs.** `KicadCli.drc` MUST run twice on the original, normalised or not, and once on the re-dump, each with the project files other than the board. `--exit-code-violations` MUST NOT be passed.
- **Repeats.** KiCad does not repeat its own report on boards with hundreds of violations (`H-K-RT2-STABLE-2`). When the entries of the re-dump report (`DrcReport.entries()`, with the run's temporary folder left out of the descriptions) differ from those of the first report of the original, the oracle MUST run DRC `RT2_REPEATS = 3` more times on the original and as many on the re-dump, appending the reports to `before` and to `repeats`, so that the caller can tell a difference from KiCad's own spread. When they are equal, no further run happens and `repeats` is empty.
- **Failures.** A board that Fenolite cannot read, a failed re-save or a run without a report MUST give the reports obtained so far and the message, and a timeout MUST give `outcome="timeout"`; no exception is raised.
- **Evidence.** `Rt2Outcome.evidence` MUST be `Evidence.combine(drc.EVIDENCE, RT2_EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, further combined with `NORMALISE_EVIDENCE` (`KICAD-VERIFIED`, `H-K-FMT-RESAVE`) when `normalised` is true, and `UNVERIFIED` when a report is missing. `RT2_EVIDENCE` MUST start `INFERRED` (`H-K-RT2-STABLE`) and MUST become `KICAD-VERIFIED` only when that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Normalised on 10
- **GIVEN** a fake `kicad-cli` whose `version` prints `10.0.6` and that records its arguments
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k rt2` runs `KicadOracle(cli).rt2(project)` on the authored project
- **THEN** the fake saw two `pcb upgrade --force` runs and three `pcb drc` runs, `normalised` is true, and `before` holds two reports

#### Scenario: No normaliser on 9
- **GIVEN** the same fake printing `9.0.9`
- **WHEN** `rt2` runs
- **THEN** the fake saw no `pcb upgrade` run and three `pcb drc` runs, and `normalised` is false

#### Scenario: Both sides repeated when the re-dump differs
- **GIVEN** a fake `kicad-cli` printing `9.0.9` whose third `pcb drc` run writes one violation more than the others
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k repeats` runs `rt2`
- **THEN** the fake saw nine `pcb drc` runs, `before` holds five reports and `repeats` three; with equal reports it saw three runs and `repeats` is empty

#### Scenario: Normalisation turned off
- **GIVEN** the 10.0.6 fake and `KicadOracle(cli, rt2_normalise=False)`
- **WHEN** `rt2` runs
- **THEN** no `pcb upgrade` run happens and `normalised` is false

#### Scenario: No canary and no writes
- **GIVEN** a fake that copies every board it receives to a log folder outside the project
- **WHEN** `rt2` runs on a project with a `<stem>.kicad_pro` and a `<stem>.kicad_dru`
- **THEN** no logged board holds a `FENOLITE_CANARY_A` net, the logged rules file equals the user's, and the project snapshot is unchanged

### Requirement: DRC finding facts proved per major
`tests/kicad/check/test_drc_facts.py` (markers `needs_kicad`, major-aware) SHALL settle `H-K-DRC-TYPES`, `H-K-PRO-SEV` and `H-K-DRC-UUID` on 9.0.9 and 10.0.6, with projects that `tests/kicad/check/_fixtures.py` writes into `tmp_path`, and SHALL record each outcome as a probe of c0017's `PROBES`:
- **Types.** The bridging-track project MUST give a `shorting_items` violation, the authored built project without its `R1`–`D1` track an `unconnected_items` entry, and the positive-control bench a `clearance` violation (probes `drc-type-shorting-items`, `drc-type-unconnected-items` and `drc-type-clearance`, outcome `present`). With `/board/design_settings/rule_severities/<type>` set to `ignore` in the project, the same run MUST give no entry of that type (probes `drc-type-<type>-ignored`, outcome `absent`). The `drc-type-clearance-ignored` run is the one exception to "Rules proofs carry a canary", because ignoring `clearance` also removes the canary's violation: it MUST follow a `drc-type-clearance` run of the same bench, on the same major and in the same session, whose canary fired; it MUST differ from that run only in the project key, which the test re-reads; and on 10.0.6 its report MUST list `clearance` in `ignored_checks` (design Decision 20).
- **Severities.** With the key set to `warning`, every entry of that type MUST have severity `warning`, and with `error`, severity `error` (probes `drc-sev-<type>-warning` and `drc-sev-<type>-error`, outcome `equal`). On 10.0.6 an ignored key MUST appear in `ignored_checks` (probes `drc-ignored-checks-<type>`, run on major 10 only); the 9.0.9.1 report schema has no such key (S-0056).
- **Item uuids.** Every item uuid of those entries MUST be a uuid of the written board, and the pad items MUST be the expected pads: `R1` pad 2 for the bridging track, and `R1` pad 2 and `D1` pad 2 for the missing track (probe `drc-item-uuids`, outcome `equal`).
- Oracle tests MUST assert on `run(…)`, and both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Types on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k types` runs on each
- **THEN** each of the three types is `present` with the default project and `absent` with its key set to `ignore`

#### Scenario: Severities follow the project
- **GIVEN** the bridging-track project with `shorting_items` set to `warning`
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k severities` runs on both majors
- **THEN** every `shorting_items` violation has severity `warning`, and `fenolite check` reports `kicad.drc.shorting-items` as a warning

#### Scenario: Ignored checks listed on 10
- **GIVEN** `kicad-cli` 10.0.6 and the bridging-track project with `shorting_items` set to `ignore`
- **WHEN** the same test runs
- **THEN** `report.ignored_checks` contains `shorting_items`

#### Scenario: Pads named by their file uuids
- **GIVEN** the bridging-track and missing-track projects
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k uuids` runs on both majors
- **THEN** the probe `drc-item-uuids` records `equal`, and `finding_issues` gives `where` values holding `R1-2`, and `D1-2` for the missing track

### Requirement: Corpus round trips RT0 to RT2
`tests/kicad/check/test_corpus_rt.py` (markers `needs_kicad`, `needs_corpus`, `slow`) SHALL run RT0, RT1 and RT2 over the corpus for v0.1 acceptance item 2.
- **Set.** On major 10: the 21 readable non-heavy demo boards (tags 10.0.6 and 9.0.9.1), and copies of `third-party-pcb-01`, `-02` and `-03` re-saved once with `KicadCli.upgrade_board` from the cached files (corpus-policy, "Upgraded copies keep their origin"). On major 9: exactly the rows tagged `rt2-9` (corpus-policy, "RT2 rows for KiCad 9.0").
- **Project.** Each board MUST be checked in a folder that c0013's `demo_project` writes into `tmp_path`, with a `{}` project and a `(version 1)` rules file; the cache MUST NOT be written.
- **Levels.** RT0 MUST hold: `tree_equal(parse(dumps(parse(t))), parse(t))`. RT1 MUST hold: `run_checks` with the stages `roundtrip` and `roundtrip.rt2` and `KicadOracle(cli, rt2_normalise=…)` gives `roundtrip` status `ok` with `opaque_equal` true, so `opaque_count` reappears after the write. RT2 MUST never fail: `roundtrip.rt2` has status `ok`, and either `summary.holds` is true or the stage says that RT2 is not judged (`summary.judged` false with `summary.unstable` above 0), because KiCad did not repeat its own report on that board. `rt2_normalise` MUST be false for `third-party-pcb-02`, whose two upgrades differ (`H-K-FMT-RESAVE`), and true otherwise.
- **Record.** For each board, the three verdicts, `opaque_count`, `normalised`, `judged`, `runs`, `before`, `after`, `unstable`, `differences` and the seconds MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-rt2.md`, as ids and counts only. The page MUST name the boards on which RT2 was not judged.
- **Missing rows.** On major 9 with `kicad` in `FENOLITE_REQUIRE`, a cache that is present but lacks an `rt2-9` row MUST fail the test, naming the row, instead of skipping that row. An absent cache MUST keep the `needs_corpus` skip of corpus-policy "Skip markers"; in the `kicad-9` job the fetch step fails first when a row cannot be fetched (`ci-baseline`, "KiCad 9.0 oracle job").

#### Scenario: Every board on 10.0.6
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_corpus_rt.py -rA` runs
- **THEN** all 24 boards pass RT0 and RT1, RT2 holds or is not judged on each and fails on none, and `third-party-pcb-02` reports `normalised` false

#### Scenario: The rt2-9 rows on 9.0.9
- **GIVEN** the `kicad-9` job with the `rt2-9` rows cached
- **WHEN** its `uv run pytest tests/kicad -q -rA` step runs the test
- **THEN** the five boards pass RT0 and RT1, RT2 holds or is not judged on each with `normalised` false, and the other rows are skipped

#### Scenario: Missing row on 9.0
- **GIVEN** `kicad-cli` 9.0.9, `FENOLITE_REQUIRE=kicad`, and a cache that holds four of the five `rt2-9` rows
- **WHEN** the test runs
- **THEN** it fails naming the fifth row

#### Scenario: Absent cache on 9.0
- **GIVEN** `kicad-cli` 9.0.9, `FENOLITE_REQUIRE=kicad`, and `FENOLITE_CORPUS_CACHE` naming an empty folder
- **WHEN** the test runs
- **THEN** it is skipped with the message `run: uv run python tools/corpus_fetch.py`

#### Scenario: Cache and repository untouched
- **WHEN** the test runs on either major
- **THEN** `git status --porcelain` and the SHA-256 of every cached file are unchanged afterwards

## MODIFIED Requirements

### Requirement: Check canary injection
`fenolite.backends.kicad.canary` and `fenolite.backends.kicad.oracle.KicadOracle` SHALL prove, with a canary run of its own on a major of `CANARY_TWO_RUN` and in the counted run otherwise, whether a project's custom rules were loaded, with a canary scoped to its own nets and placed only in temporary copies (exempt from c0018's "Fenolite lowers only the design's rules").
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
