## ADDED Requirements

### Requirement: ERC runs through the package runner
`KicadCli.erc(schematic, *, files=None, env=None) -> ErcRun` SHALL run `sch erc --format json --severity-all -o <out> <schematic>` through `KicadCli.run` on a copy, and SHALL return `ErcRun(run, report)`, `report` being `read_erc_report` of the written file, or `None` when no report was written.
- `--exit-code-violations` MUST NOT be passed: the exit code is a load signal, and every verdict comes from the report.
- `env` MUST be passed unchanged to `KicadCli.run`, as for `KicadCli.drc`.
- The method MUST NOT raise for a non-zero exit, and a timeout MUST surface as the runner's timeout outcome.
- `KicadCli.drc` SHALL accept the keyword `schematic_parity=False`; with `True` it MUST add `--schematic-parity` to its command, and with the default its command MUST be the one of "DRC verdicts come from the JSON report".

#### Scenario: Arguments
- **GIVEN** a fake `kicad-cli` that records its arguments and writes an authored ERC report
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k erc` calls `KicadCli.erc` on `tests/data/kicad/schematic/flat.kicad_sch`
- **THEN** the fake saw `sch erc --format json --severity-all -o` and no `--exit-code-violations`, `ErcRun.report` is an `ErcReport`, and the fixture folder is unchanged

#### Scenario: No report
- **GIVEN** a fake that prints `Failed to load schematic` and exits 3 without writing a file
- **WHEN** `KicadCli.erc` runs
- **THEN** `ErcRun.report` is `None` and `ErcRun.run.returncode` is 3

#### Scenario: Parity flag
- **WHEN** `KicadCli.drc(board, schematic_parity=True)` and `KicadCli.drc(board)` run with the recording fake
- **THEN** only the first run saw `--schematic-parity`

### Requirement: ERC oracle
`KicadOracle.erc(project) -> ErcOutcome` SHALL run `KicadCli.erc` on `<board stem>.kicad_sch` with the project's copy set and SHALL satisfy `ErcOracle` (`backend-protocol`, "ERC oracle protocol").
- It MUST fill each item's `where` with `erc.located(report, erc.item_locations(trees, project))`, the map being built from the parsed trees of the sheet files of the copy set and keyed by `(sheet id, uuid)`: `REF-PIN` for the uuid of a `pin` child of a symbol, `REF` for a symbol's uuid, and the label text for a label's uuid, the reference being the one the symbol's `instances` give for the violation's `sheet_id` (under the project's name when the symbol lists it, else under another project's use of the same path).
- KiCad lists the violations of a check that looks at a sheet file, not at one use of it, under the root sheet, whatever file the item lies in. The map MUST therefore also hold, under the sheet id `erc.ROOT_PATH` (`""`), the location on which every use of a uuid agrees, and `located` MUST fall back to it. An item whose uses give two references, and an item whose uuid the map lacks, MUST keep `where == ""`: a location is never guessed.
- A sheet file that Fenolite cannot parse MUST NOT fail the run: its items keep `where == ""`.
- `tool_writes` MUST name the files the tool created or changed in the copy, sorted, without the report. `message` MUST be the first line of the tool's stderr that is not blank, else of its stdout, without the time of day that `kicad-cli` writes before some error lines, so that the output of `check` repeats.
- `ErcOutcome.evidence` MUST be `Evidence.combine(erc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>` when a report exists, and `UNVERIFIED` otherwise. `erc.EVIDENCE` MUST start `INFERRED` (`H-K-ERC-JSON`, `H-K-ERC-POS`, `H-K-ERC-COPYSET`) and MUST become `KICAD-VERIFIED` only when the three rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- The method MUST NOT write under `project.root`, MUST NOT raise on a timeout, and MUST stage no canary.

#### Scenario: Pin uuid located
- **GIVEN** a fake `kicad-cli` whose report names, on sheet `/`, the uuid of pin 2 of `U1` of the built blink schematic
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k erc_where` runs `KicadOracle(cli).erc(project)`
- **THEN** that item's `where` is `U1-2`

#### Scenario: Two uses of one sheet
- **GIVEN** `tests/data/kicad/schematic/multi/` as a project, and a fake report with one violation per instance path of `cell.kicad_sch`, both naming the uuid of the same symbol, and a third violation that lists that symbol under the root sheet
- **WHEN** the oracle runs
- **THEN** the two items have different references, each the one of its instance path, and the third item keeps `where == ""`

#### Scenario: No writes in the project
- **GIVEN** a fake that writes `<stem>.kicad_prl` next to its input
- **WHEN** the oracle runs on a project folder
- **THEN** `tool_writes` names `<stem>.kicad_prl`, and the project snapshot is unchanged

### Requirement: ERC facts proved per major
`tests/kicad/check/test_erc_facts.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-ERC-JSON`, `H-K-ERC-POS` and `H-K-ERC-TYPES` on 9.0.9 and 10.0.6, with projects that `tests/kicad/check/_erccases.py` builds into temporary folders, and SHALL record each outcome as a probe of `PROBES`. A probe id spells a type with `-` for `_`.
- **Shape.** The report of the built blink MUST hold the keys that `erc.REQUIRED_KEYS` names (probe `erc-report-keys`, outcome `equal`); `ignored_checks` MUST be present on 10 and absent on 9 (probe `erc-ignored-checks`); a schematic with an invented root child MUST give no report and exit 3 (probe `erc-unloadable`, outcome `absent`); and the probe `erc-writes-prl` MUST record whether the run writes `<stem>.kicad_prl` beside its input (`present` on 10.0.6, `absent` on 9.0.9).
- **Positions.** For the built blink with five labels removed, the position that `read_erc_report` gives each `pin_not_connected` item MUST be the connection point of that pin in the schematic, in nm (probe `erc-position-scale`, outcome `equal`).
- **Types.** Five controls MUST each give their type: the built blink with a removed label (`pin_not_connected`), with a removed power flag (`power_pin_not_driven`), with a removed `sym-lib-table` (`lib_symbol_issues`) and with a label left on a single pin (`isolated_pin_label` on 10.0.6, `global_label_dangling` on 9.0.9; both probes run on both majors and record `present` or `absent`), and the blink built with two input pins of `U1` on a net of their own (`pin_not_driven`: the blink connects no input pin, so no edit of its sheet gives that type) (probes `erc-type-<type>`, outcome `present`). With the project's `erc.rule_severities` key of a control's type set to `ignore`, the run MUST give no entry of that type (`erc-type-<type>-ignored`, outcome `absent`), and with `warning`, every entry of it MUST have severity `warning` (`erc-sev-<type>-warning`, outcome `equal`); the two probes of the single-pin label are named `single-pin-label`.
- **Copy set** (`H-K-ERC-COPYSET`, `tests/kicad/check/test_erc_oracle.py::test_copy_set`). ERC on the copy set and ERC on a copy of the whole folder MUST give equal `entries()` for the built blink, the authored hierarchy and, with the corpus cached, three corpus projects (probe `erc-copyset`, outcome `equal`). Each folder MUST hold decoys that the run must not need: a text file, a schematic that the hierarchy does not reach, a symbol library that no table names and a `.kicad_prl`. The three corpus projects are the first three root rows of the acceptance list, by id, that the running major loads (`tests/kicad/check/test_erc_oracle.py::test_copy_set_corpus_projects`, marker `needs_corpus`). `H-K-CHECK-COPYSET` MUST be proved again with a schematic in the folder: DRC with the parity test on the copy set equals DRC on a copy of the whole folder, for the blink whose board disagrees with its schematic (probe `check-copyset-schematic`, outcome `equal`; `tests/kicad/check/test_copy_set.py`).
- Oracle tests MUST assert on reports read through `KicadCli.erc` and `read_erc_report`, and both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Shape and positions on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_erc_facts.py -k "shape or positions" -rA` runs on each
- **THEN** `erc-report-keys` and `erc-position-scale` record `equal`, and `erc-ignored-checks` records `present` on 10 and `absent` on 9

#### Scenario: Severities follow the project
- **GIVEN** the blink with one label removed and `pin_not_connected` set to `warning` in the project
- **WHEN** `uv run pytest tests/kicad/check/test_erc_facts.py -k types` runs on both majors
- **THEN** the violation has severity `warning`, and `fenolite check` reports `kicad.erc.pin-not-connected` as a warning

### Requirement: Parity in the DRC run
`KicadOracle.drc(project)` SHALL pass `schematic_parity=True` to every `KicadCli.drc` call of the run when `project.files` holds `<board stem>.kicad_sch`, and SHALL NOT pass it otherwise. When the flagged run exits without a report, the oracle SHALL run the DRC again without the flag, canary included, and SHALL return that report with `parity_judged` false and, as `message`, the first line of the flagged run: the copper verdict MUST NOT depend on the schematic. `tests/kicad/check/test_parity.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PARITY-RUN` on both majors.
- The parity entries of the counted report MUST be those of the run from which the canary's violations were removed; a canary entry MUST never be a parity entry.
- With the flag, the report of a project whose pads differ from the schematic MUST hold parity entries (probe `drc-parity-flag`, outcome `present`); without it, none (`drc-parity-noflag`, outcome `absent`).
- The staged canary run and the plain run MUST give equal parity entries (`drc-parity-canary`, outcome `equal`).
- `drc-parity-unloadable` MUST record, per major, what the tool writes when the flag is passed and the schematic does not load (`absent`: no report, on 9.0.9 and on 10.0.6); `DrcOutcome` MUST then say that parity was not judged, which the stage reports as `<oracle>.drc.parity-unchecked` (`verification-loop`, "Parity findings").
- A flagged run that writes its report and prints the line `oracle.PARITY_NOT_JUDGED` (`Failed to fetch schematic netlist`, which both majors print when they find no schematic to compare with) MUST also give `parity_judged` false, with that line as `message`.

#### Scenario: Flag follows the schematic
- **GIVEN** a recording fake `kicad-cli`, a project with `<stem>.kicad_sch` and one without
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k parity` runs `KicadOracle.drc` on each
- **THEN** every `pcb drc` run of the first saw `--schematic-parity`, and no run of the second did

#### Scenario: Flagged run without a report
- **GIVEN** a fake `kicad-cli` that exits 255 without a report when it gets `--schematic-parity`, printing an error line that starts with a time of day
- **WHEN** `KicadOracle.drc` runs on a project with a schematic
- **THEN** the last `pcb drc` run had no flag, the outcome holds a report and the canary state `fired`, `parity_judged` is false, and `message` is that line without the time

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_parity.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** `drc-parity-flag` records `present`, `drc-parity-noflag` `absent` and `drc-parity-canary` `equal`

### Requirement: Schematic RT2 over the corpus
`KicadOracle.rt2_erc(project) -> ErcRt2Outcome` SHALL produce the ERC reports that RT2 compares for schematics, and `tests/kicad/schematic/test_corpus_rt2.py` (markers `needs_kicad`, `needs_corpus`, `slow`) SHALL run it over the corpus for the v0.2a acceptance.
- **Runs.** ERC MUST run twice on the project as it is, and once on a copy in which every sheet file that `read_schematic` reads is replaced by `dumps(rebuild_schematic(read_schematic(text)))`, staged in a private temporary folder. A sheet that Fenolite cannot read stays as it is and is counted.
- **Verdict.** RT2 holds when the `entries()` of the re-dump's report equal those of the first report. When the two reports of the original differ, RT2 MUST be recorded as not judged for that project (`H-K-ERC-REPEAT`), never as failed.
- **Set.** On major 10: every corpus project whose root row carries `sch-root`. On major 9: those of tag 9.0.9.1 whose sheets are all at format `20250114` or older. Each project MUST be checked in a folder built in `tmp_path` from the cached files; the cache MUST NOT be written.
- **Folder.** A project is the folder of its root row in the demo tree, rebuilt from every cached row of that folder (`tests/_schprojects.py`), with an authored empty board of the root's stem when the folder has none, because a copy set is planned from a board.
- **Record.** For each project, the verdict, `judged`, the number of sheets re-dumped and left as they are, the violation counts and the seconds MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-schematic.md` as ids and counts only. The page MUST state the verdict of the acceptance list (rows without `sch-bus`, `sch-multi` and `sch-old`) apart from the other projects.
- **Evidence.** `ErcRt2Outcome.evidence` MUST be `Evidence.combine(erc.EVIDENCE, sch.EVIDENCE, oracle.EVIDENCE)`, and `UNVERIFIED` when a report is missing.
- RT2 MUST never fail on a project that was not judged, and MUST fail on a judged difference, naming the project row and the first differing entry.

#### Scenario: Corpus projects on 10.0.6
- **GIVEN** the `sch` rows cached and `kicad-cli` 10.0.6
- **WHEN** `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/schematic/test_corpus_rt2.py -rA` runs
- **THEN** RT2 holds or is not judged on every project and fails on none, and every project of the acceptance list is judged

#### Scenario: Rows of tag 9.0.9.1 on 9.0.9
- **GIVEN** the `kicad-9` job with the `sch` rows of tag 9.0.9.1 cached
- **WHEN** the test runs
- **THEN** the selected projects hold or are not judged, and the others are skipped

#### Scenario: Three runs and no write
- **GIVEN** a recording fake `kicad-cli` and the authored hierarchy as a project
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k rt2_erc` runs `KicadOracle.rt2_erc`
- **THEN** the fake saw three `sch erc` runs, the third on re-dumped sheets, and the project snapshot is unchanged

## MODIFIED Requirements

### Requirement: Check project copy set
`fenolite.backends.kicad.projectset` SHALL plan, without writing anything, the closed set of project files that `kicad-cli pcb drc` and `kicad-cli sch erc` read, and c0009's runner SHALL copy them through `KicadCli.drc(board, files=…)` and `KicadCli.erc(schematic, files=…)`.
- **Board.** `resolve_board(path) -> Path` MUST accept a `.kicad_pcb` file; a `.kicad_pro` file (the board of the same stem); or a folder holding exactly one `.kicad_pro` (the board of its stem), or else exactly one `.kicad_pcb`. A folder with several candidates or none MUST raise `ProjectResolutionError` (`cli_code` `FEN-2001`) whose `candidates` list them. A missing path or board MUST raise a `FenoliteError` with `cli_code` `FEN-3001`.
- **Included.** `project_set(path, *, max_bytes=MAX_COPY_BYTES) -> ProjectSet` MUST include, under names relative to the board's folder: the board; `<stem>.kicad_pro` and `<stem>.kicad_dru` when present (`has_project`, `has_rules`), because KiCad reads rules only with a project file next to the board (`H-K-TOK-RULES-SILENT`) and pairs them by stem (`H-K-CHECK-COPYSET`); the top-level `fp-lib-table`, read with c0008's `read_lib_table`, and each library folder that a row names as `${KIPRJMOD}/<rel>` inside the root, under `<rel>`; and the drawing sheet named at `WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"` of the project (read with c0010's `read_project` and `_json.get`) when it is a `${KIPRJMOD}` or relative path inside the root.
- **Schematic.** When `<stem>.kicad_sch` exists beside the board, the set MUST also include: that file; every file that `sch.sheet_files(<stem>.kicad_sch)` lists inside the root (`kicad-schematic`, "Sheet tree of a project"); the top-level `sym-lib-table` and each symbol library, a `.kicad_sym` file or a folder of them, that a row names as `${KIPRJMOD}/<rel>` inside the root; and the drawing sheet named at `SCHEMATIC_WORKSHEET_POINTER = "/schematic/page_layout_descr_file"` of the project, under the rule of the board's drawing sheet. A root schematic that Fenolite cannot read MUST still be included, alone, so that KiCad judges it. A sheet file outside the root MUST give a `SkippedFile` with reason `outside-root`, and a missing one `missing`.
- **Never included.** `.kicad_prl`, backups, `fp-info-cache`, `.fenolite/`, a `.kicad_sch` that the sheet tree of `<stem>.kicad_sch` does not reach, a `sym-lib-table` without that schematic, and every other file. Absolute library rows and an absolute drawing-sheet path MUST stay as written and be read in place by KiCad.
- **Skips.** Each named file or folder that is not copied MUST give a `SkippedFile(name, reason)`: `outside-root`, `variable` (a variable other than `${KIPRJMOD}`), `relative` (a library row without a variable), `missing`, `nested-table` (a `Table` row), `too-large`, or `reserved-name` (a name whose first path part is `config`, which c0009's runner reserves for `KICAD_CONFIG_HOME` and refuses in `files`).
- **Size.** `MAX_COPY_BYTES` MUST be `256 * 2**20`. The board, project, rules file, both tables and the root schematic MUST always be included. The drawing sheets, then the sheet files in tree order, then the footprint library folders and the symbol libraries in table order, MUST be skipped with `too-large` when adding them would bring the total over `max_bytes`.
- `H-K-CHECK-COPYSET` MUST be settled before `projectset.py` is final: DRC on the copy set gives the same violations and unconnected items as DRC on a copy of the whole project folder. If it is refuted, the missing kind MUST join the include list.

#### Scenario: Closed include list
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, decoys=True)`, with a `${KIPRJMOD}` library row, `notes.txt`, a `sym-lib-table` and a `.kicad_prl`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_projectset.py -k include` calls `project_set` on it
- **THEN** the keys of `files` are exactly the board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, `fp-lib-table` and the library folder, `skipped` is empty, and the folder snapshot is unchanged: the `sym-lib-table` is left out because the project has no `<stem>.kicad_sch`

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

#### Scenario: Schematic files included
- **GIVEN** the blink built with a schematic into `tmp_path`, with `notes.txt` and a `.kicad_prl` added
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_projectset.py -k schematic` calls `project_set` on it
- **THEN** the keys of `files` are exactly the triad, `blink.kicad_sch`, `fp-lib-table`, `sym-lib-table`, `lib/Mini.pretty`, `lib/Mini.kicad_sym` and `lib/fenolite.kicad_sym`, and `skipped` is empty

#### Scenario: Sheet files of a hierarchy
- **GIVEN** `tests/data/kicad/schematic/hier/` copied into `tmp_path` with a board and a project file of the stem `top`, and an unrelated `other.kicad_sch` beside them
- **WHEN** `project_set` runs
- **THEN** `files` holds `top.kicad_sch` and `child.kicad_sch`, and does not hold `other.kicad_sch`

#### Scenario: Unreadable root schematic
- **GIVEN** a project whose `<stem>.kicad_sch` holds `(`
- **WHEN** `project_set` runs
- **THEN** `files` holds that file, no error is raised, and no other `.kicad_sch` is in the set
