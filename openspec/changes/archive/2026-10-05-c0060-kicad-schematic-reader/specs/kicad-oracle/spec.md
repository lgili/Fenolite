## ADDED Requirements

### Requirement: Load checks for schematics and symbol libraries
`tools/kicad_token_fuzz.py` SHALL decide whether `kicad-cli` loads a schematic or a symbol-library case file with one command per kind, beside the four kinds of "Load check per file kind", and SHALL record the same outcomes:

| kind | command | outcome `load` when |
|---|---|---|
| schematic | `sch export netlist <file> -o <out>.net` | exit 0 and the netlist exists |
| symbol library | `sym export svg <file> -o <existing dir>` | exit 0 and an SVG exists |

- Any other result MUST be `reject`. A schematic case MUST be `inconclusive` when its skeleton did not load in the same run.
- The harness MUST hold one authored skeleton per kind and major (`skeleton.kicad_sch`, `skeleton.kicad_sym`), each loaded as the positive control.
- "Isolation and time limits" applies: a fresh temporary folder per case, holding only the case files, and a timeout per invocation.
- A symbol case that the tool cannot plot, although it loads the library, MUST be run embedded in the schematic skeleton instead, and its row MUST say which check gave its result.

#### Scenario: Schematic rejected
- **GIVEN** a schematic case that holds an invented root child
- **WHEN** the harness runs it on `kicad-cli` 10.0.6
- **THEN** the outcome is `reject`, and `exit_code` is `3`

#### Scenario: Skeletons load on their majors
- **WHEN** `uv run pytest tests/kicad/test_token_fuzz.py -k skeleton` runs on 9.0.9 and on 10.0.6
- **THEN** the schematic and symbol-library skeletons of the running major have the outcome `load`

#### Scenario: Missing output is not a load
- **GIVEN** a schematic run that exits 0 but writes no netlist
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fuzz_harness.py -k schematic` classifies it with a fake `kicad-cli`
- **THEN** the outcome is `reject`

### Requirement: Schematic components agree with kicad-cli
`tests/kicad/schematic/test_components_oracle.py` (marker `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that the components Fenolite reads from a schematic are those `kicad-cli` exports, and SHALL record each comparison as a probe of `PROBES`.
- **Runner.** `KicadCli.export_netlist(schematic, *, files=None) -> CliRun` MUST run `sch export netlist --format kicadsexpr -o <out>` through `KicadCli.run`, on copies, and MUST NOT raise for a non-zero exit.
- **Fixtures.** For the flat sheet, the units sheet and the two-sheet hierarchy of the running major's format, the set of `(ref, value, footprint)` of `sch.hierarchy_components(<root>)` MUST equal the `components` of the exported netlist, read by `tests/_netlist.py::components`, and MUST equal `sch.components(…, project=<stem>)` over the files of `sch.sheet_files` (probes `sch-components-flat`, `sch-components-units` and `sch-components-hier`, outcome `equal`).
- **Symbols left off the board.** The probe `sch-components-on-board` MUST record whether the netlist lists the symbol with `(on_board no)` of the flat sheet (`present` or `absent`). When it is `absent` on a major, the comparisons of that major MUST call `sch.components` with `on_board_only=True`, and the fact row MUST say so.
- **Corpus.** With the corpus cached, every project of the demo tree of tag 10.0.6 whose root row carries `sch-root` and none of whose sheets carries `sch-old` MUST give equal sets on major 10, `sch.hierarchy_components` against the netlist, multi-instance sheets included; on major 9, the projects of the demo tree of tag 9.0.9.1 (the rows with `sch-9`) whose sheets all have a format version of at most the 9.0 constant. A value or footprint that holds a text variable (`${…}`) matches any text, because the netlist lists it resolved. The counts MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-schematic.md`. The `kicad-9` job fetches the `sch-9` rows, so it runs the comparison of major 9 too.
- The test MUST read only the `components` of the netlist and MUST store no netlist.
- Both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Fixtures on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/schematic/test_components_oracle.py -k fixtures -rA` runs on each
- **THEN** the three `sch-components-*` probes of the fixtures record `equal`, and `sch-components-on-board` records one of `present` and `absent`

#### Scenario: Corpus projects on 10.0.6
- **GIVEN** the `sch` rows cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_components_oracle.py -k corpus -rA` runs
- **THEN** every selected project gives equal sets, and the census names the number of projects compared and of projects left out by reason

#### Scenario: Runner on copies
- **GIVEN** a fake `kicad-cli` that records its arguments and writes `<stem>.kicad_prl` next to its input
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k export_netlist` calls `KicadCli.export_netlist` on the flat sheet
- **THEN** the fake saw `sch export netlist --format kicadsexpr`, and the fixture folder is unchanged

### Requirement: Third-party schematics are read as upgraded copies
`tests/kicad/schematic/test_schematic_upgraded.py` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`) SHALL re-save each `third-party-sch-*` row once with `kicad-cli sch upgrade --force` in a temporary folder and SHALL run RT0 and RT1 on the copy.
- `KicadCli.upgrade_schematic(schematic, *, files=None) -> bytes` MUST run `sch upgrade --force` on a copy and return the re-saved bytes, as `upgrade_board` does for a board.
- The cache MUST NOT be written, and a copy MUST NOT be committed.
- The verdicts and `opaque_count` MUST be written through `tests/_boards.py::census` with origin `third-party`.

#### Scenario: Two upgraded copies
- **GIVEN** the two third-party rows cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_schematic_upgraded.py -rA` runs
- **THEN** both copies pass RT0 and RT1, and `git status --porcelain` and the SHA-256 of every cached file are unchanged

#### Scenario: Skipped on 9.0
- **GIVEN** `kicad-cli` 9.0.9, which has no `sch upgrade`
- **WHEN** the test is collected
- **THEN** it is skipped by its major marker
