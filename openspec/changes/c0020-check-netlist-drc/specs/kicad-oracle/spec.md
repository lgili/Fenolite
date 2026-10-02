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
- **Levels.** RT0 MUST hold: `tree_equal(parse(dumps(parse(t))), parse(t))`. RT1 and RT2 MUST hold: `run_checks` with the stages `roundtrip` and `roundtrip.rt2` and `KicadOracle(cli, rt2_normalise=…)` gives both stages status `ok`, and `roundtrip` reports `opaque_equal` true, so `opaque_count` reappears after the write. `rt2_normalise` MUST be false for `third-party-pcb-02`, whose two upgrades differ (`H-K-FMT-RESAVE`), and true otherwise.
- **Record.** For each board, the three verdicts, `opaque_count`, `normalised`, `before`, `after`, `unstable` and the seconds MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-rt2.md`, as ids and counts only.
- **Missing rows.** On major 9 with `kicad` in `FENOLITE_REQUIRE`, a cache that is present but lacks an `rt2-9` row MUST fail the test, naming the row, instead of skipping that row. An absent cache MUST keep the `needs_corpus` skip of corpus-policy "Skip markers"; in the `kicad-9` job the fetch step fails first when a row cannot be fetched (`ci-baseline`, "KiCad 9.0 oracle job").

#### Scenario: Every board on 10.0.6
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_corpus_rt.py -rA` runs
- **THEN** all 24 boards pass RT0, RT1 and RT2, and `third-party-pcb-02` reports `normalised` false

#### Scenario: The rt2-9 rows on 9.0.9
- **GIVEN** the `kicad-9` job with the `rt2-9` rows cached
- **WHEN** its `uv run pytest tests/kicad -q -rA` step runs the test
- **THEN** the five boards pass RT0, RT1 and RT2 with `normalised` false, and the other rows are skipped

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
