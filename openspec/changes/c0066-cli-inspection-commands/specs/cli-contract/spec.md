## ADDED Requirements

### Requirement: Paged results
The dispatcher SHALL accept the global flags `--limit N` and `--cursor TOKEN` and SHALL cut the paged list of a command to one page, without keeping any state between calls.
- `fenolite.cli.api.Command` MUST have the fields `paged: str | None = None`, the dotted path of the command's main list in `result` or the literal `"issues"`, and `default_limit: int | None = None`.
- With a limit (the flag, or else `default_limit`), the dispatcher MUST keep the items `offset` to `offset + limit - 1` of the paged list and MUST set `result.page` to `{path, limit, offset, total, next}`: `total` is the length of the whole list, and `next` the cursor of the following page or `null` on the last. Without a limit the list is whole and `result.page` is absent.
- A cursor MUST be `<offset>.<digest>`, the digest being the first 8 hex digits of the SHA-256 of the canonical JSON of the whole list. `--cursor` MUST be refused with exit 2 (`FEN-2001`) when it is malformed, when its offset is past the end, when its digest is not that of the present list (the message says that the result changed since the cursor was issued), or when it is given without a limit in force.
- For `paged == "issues"` the envelope's `issues` list MUST be the page, and `result.page.path` MUST be `issues`.
- `ok`, the exit code, the error on stderr and every count in `result` MUST come from the whole result, never from the page.
- `--limit` MUST be at least 1; a value below 1, and `--limit` on a command whose `paged` is `None`, MUST exit 2 with `FEN-2001`.
- `--fields` MUST apply after paging and MUST be able to keep `page`.
- `capabilities` MUST list `paged` and `default_limit` for each command that has them. `check` MUST declare `paged = "issues"`.

#### Scenario: Two pages of issues
- **GIVEN** `_echo` producing five warnings
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py -k two_pages` runs it with `--limit 2`, and again with `--limit 2 --cursor <the first run's next>`
- **THEN** the first envelope holds issues 1 and 2 with `result.page.total` 5 and a `next`, and the second holds issues 3 and 4 with `offset` 2

#### Scenario: Exit code from the whole result
- **GIVEN** `_echo` producing three warnings followed by one error
- **WHEN** it runs with `--limit 2`
- **THEN** the page holds two warnings, the exit code is 5 and `ok` is `false`

#### Scenario: Stale cursor
- **GIVEN** a cursor issued for a list of five issues
- **WHEN** the command runs again with that cursor and now produces six issues
- **THEN** the exit code is 2, and stderr carries `FEN-2001` saying that the result changed

#### Scenario: Command without a list
- **WHEN** `fenolite capabilities --limit 5` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Paging is deterministic
- **WHEN** the same paged call runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`, cursors included

### Requirement: Concise output
The dispatcher SHALL accept the global flag `--format concise|detailed`, default `detailed`. With `concise` it MUST keep, for each issue code, only the first issue in the envelope's order, and MUST add `result.issues_summary`: one object per code, sorted by code, with `code`, `count` and `by_severity`.
- Paging (`paged == "issues"`) MUST apply to the list that `concise` leaves.
- `ok` and the exit code MUST come from the whole result.
- `detailed` MUST leave the envelope as it is without this requirement.

#### Scenario: One issue per code
- **GIVEN** `_echo` producing three issues of one code and one of another
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py -k concise` runs it with `--format concise`
- **THEN** `issues` holds two issues, and `result.issues_summary` gives the counts 3 and 1

#### Scenario: Detailed is the default
- **WHEN** the same command runs without `--format`
- **THEN** `issues` holds four issues, and `result` has no `issues_summary`

### Requirement: Diff command
`fenolite diff A B [--view model|tree] [--ext]` SHALL be registered by `src/fenolite/cli/cmd_diff.py` with `mutates=False`, `paged = "differences"` and `default_limit = 200`, and SHALL list the differences between two inputs without writing a file and without running any external tool.
- **Inputs.** `A` and `B` MUST each be a KiCad board, footprint file, symbol library or schematic (`.kicad_sch`, read with `sch.read_schematic`), or a folder that holds `.fenolite/meta.json` (the built model, loaded with `model.canonical.load_dir`). A missing path MUST exit 3 with `FEN-3001`, an input that nothing reads MUST exit 2 with `FEN-2001`, and a read error MUST exit 3 with its code.
- **Model view** (the default). Two designs MUST be compared with `checks.diff.diff_designs`, two libraries with `diff_libraries` and two sheets with `diff_sheets` (`verification-loop`, "Model difference report"). Inputs of two families MUST exit 2 with `FEN-2001`. `--ext` MUST pass `ext=True`.
- **Tree view.** `--view tree` MUST take two KiCad S-expression files of one kind and compare their parsed trees: `result.equal` is `tree_equal`, `result.first_difference` the locator of `sexpr.first_difference` or `null`, and `result.heads` the root child heads whose counts differ, each with its count in `a` and in `b`. Its `differences` list MUST be empty. A `.fenolite/` folder MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Result.** `result` MUST hold `view`, `equal`, `a` and `b` (each `{path, kind}`, `path` being the file or folder name without its parent), `summary` (per entity kind, the counts `added`, `removed` and `changed`), `differences` (objects `{path, change, a, b}`, in report order), `total` and `truncated` (true when the page is not the whole list).
- **Exit code.** A difference is a result, not a finding: the exit code MUST be 0 whether or not the inputs differ, and `issues` MUST hold only the readers' issues, those of `A` first.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; a `.fenolite/` model counts as `INFERRED`. `input` MUST describe `A`.
- **Determinism.** Two runs on the same inputs MUST give the same stdout apart from `elapsed_ms`, and the output MUST hold no absolute path.
- `example_args` MUST be `(EXAMPLE_BOARD, EXAMPLE_BOARD)` and MUST run no subprocess from any working directory. `docs/cli-contract.md` MUST have a section "diff" with the views, the result keys and the matching keys.

#### Scenario: A file against itself
- **WHEN** `uv run fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.view` is `model`, `result.equal` is `true`, `result.total` is 0 and `result.differences` is empty

#### Scenario: One footprint moved
- **GIVEN** a copy of `two_layer.kicad_pcb` in `tmp_path` whose first footprint is moved by 1 mm in X by a token edit
- **WHEN** `uv run pytest tests/unit/cli/test_diff_cmd.py -k moved` runs `fenolite diff <original> <copy> --json`
- **THEN** the exit code is 0, `result.equal` is `false`, and `result.differences` holds exactly one object, whose `change` is `changed` and whose `path` is `/footprint/<ref>/position`

#### Scenario: Built model against its board
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite diff <project> <project>/<board>.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.a.kind` is `fenolite_model`, and `result.b.kind` is `kicad_pcb`

#### Scenario: Two schematics
- **GIVEN** a copy of `tests/data/kicad/schematic/flat.kicad_sch` whose `R1` is moved by 2.54 mm
- **WHEN** `fenolite diff <original> <copy> --json` runs
- **THEN** `result.differences` holds exactly one object, with the path `/symbol/R1#1/position`

#### Scenario: Tree view sees opaque content
- **GIVEN** a copy of `flat.kicad_sch` with one more `wire`
- **WHEN** `fenolite diff <original> <copy> --json` runs, and again with `--view tree`
- **THEN** the model view reports `equal` true, and the tree view reports `equal` false with `result.heads.wire` holding the two counts

#### Scenario: Page of differences
- **GIVEN** two authored designs with five differences
- **WHEN** `fenolite diff A B --limit 2 --json` runs
- **THEN** `result.differences` holds two objects, `result.total` is 5, `result.truncated` is `true`, and `result.page.next` is not `null`

#### Scenario: Diff is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `diff` with its `example_args`
- **THEN** the exit code is 0

### Requirement: Roundtrip command
`fenolite roundtrip PATH [--level rt0|rt1|rt2] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_roundtrip.py` with `mutates=False`, and SHALL say up to which level Fenolite reads and writes a KiCad file back without loss. `--level` MUST default to `rt1`.
- **RT0.** For a `.kicad_pcb`, `.kicad_mod`, `.kicad_sch`, `.kicad_sym` or `.kicad_wks` file: `tree_equal(parse(dumps(parse(text))), parse(text))`. Any other file MUST exit 2 with `FEN-2001`.
- **RT1.** RT0, then `roundtrip.rt1` for a board and `sch.roundtrip_schematic` for a schematic. For another kind `result.rt1` MUST be `not-applicable` and the level reached `rt0`.
- **RT2.** RT1, then, for a `PATH` that `projectset.resolve_board` resolves, `KicadOracle.rt2` on the project's board and, when the project has a schematic, `KicadOracle.rt2_erc`. RT2 needs the tool: exit 6 with `FEN-6001` without it. A pair of reports that the oracle did not repeat MUST give `judged` false and MUST NOT fail the level.
- **Result.** `result` MUST hold `kind`, `level` (the highest level that holds, or `none`), and for each level asked `{passed, difference}`, with `opaque_count` for RT1 and `judged`, `normalised` and the report counts for RT2.
- **Verdict.** A level that fails MUST give one `roundtrip.failed` issue of severity `error` whose `where` is the first difference, and the exit code is then 5. A read error MUST exit 3 with its code.
- **Read-only.** The file and its folder MUST be unchanged; RT2 runs on copies.
- **Evidence.** The reader's evidence for RT0 and RT1; combined with the oracle's for RT2.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and MUST run no subprocess.

#### Scenario: Authored board
- **WHEN** `uv run fenolite roundtrip tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.level` is `rt1`, `result.rt1.passed` is `true`, and `result.rt1.opaque_count` equals `pcb.opaque_count` of the read design

#### Scenario: Schematic
- **WHEN** `fenolite roundtrip tests/data/kicad/schematic/flat.kicad_sch --json` runs
- **THEN** `result.kind` is `kicad_sch` and `result.level` is `rt1`

#### Scenario: Kind without a rebuild
- **WHEN** `fenolite roundtrip tests/data/libs/Mini.kicad_sym --json` runs
- **THEN** `result.level` is `rt0` and `result.rt1` is `not-applicable`

#### Scenario: Failure is an error
- **GIVEN** a `Validator` patched in the test so that RT1 fails with the difference `/kicad_pcb/footprint[0]/pad[1]`
- **WHEN** `uv run pytest tests/unit/cli/test_roundtrip_cmd.py -k failed` runs the command
- **THEN** the exit code is 5, and the issues hold one `roundtrip.failed` whose `where` is that locator

#### Scenario: RT2 through the tool
- **WHEN** `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -rA` runs `fenolite roundtrip <built blink> --level rt2 --json` on 9.0.9 and on 10.0.6
- **THEN** `result.level` is `rt2` or RT2 is not judged, the exit code is 0, and the project snapshot is unchanged

### Requirement: Fmt command
`fenolite fmt PATH [--check]` SHALL be registered by `src/fenolite/cli/cmd_fmt.py` with `mutates=True`, and SHALL give a KiCad S-expression file its canonical print (`kicad-sexpr`, "Canonical print check"), writing only through the mutation protocol.
- **Kinds.** `.kicad_pcb`, `.kicad_mod`, `.kicad_sch`, `.kicad_sym` and `.kicad_wks`. A `.kicad_pro`, a `.kicad_dru` and every other file MUST exit 2 with `FEN-2001`; the hint for `.kicad_pro` says that project files are kept byte for byte.
- **`--check`.** The command MUST plan no write. `result.formatted` MUST be true when the file equals its canonical print. When it does not, the command MUST report one `fmt.would-change` issue of severity `error` whose `where` is `<file name>:<the first differing line>`, and exit 5.
- **Without `--check`.** The command MUST return one `PlannedWrite` with the canonical text when it differs from the file, and none when it does not; `result.formatted` then says whether the file already was canonical.
- **Result.** `result` MUST hold `kind`, `formatted`, `lines` (of the file) and `first_difference` (a line number or `null`).
- A tree that `dumps` refuses (comments below the root) MUST exit 7 with `FEN-7001`; a file that does not parse MUST exit 3 with `FEN-3004`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--check")`; `mutation_example_args` MUST format a copy of an authored file that is not canonical, made by the suite in its empty folder. Both MUST run no subprocess.

#### Scenario: Canonical file
- **GIVEN** the text `dumps(parse(text))` of `two_layer.kicad_pcb` written to `tmp_path`
- **WHEN** `fenolite fmt <file> --check --json` runs
- **THEN** the exit code is 0 and `result.formatted` is `true`

#### Scenario: File that would change
- **GIVEN** the same file with two blanks added after the first `(kicad_pcb`
- **WHEN** `fenolite fmt <file> --check --json` runs, and then `fenolite fmt <file> --confirm --json`
- **THEN** the first exits 5 with `fmt.would-change` naming line 1 and writes nothing, and the second writes the canonical text and keeps a `.bak`

#### Scenario: Formatting twice
- **WHEN** `fenolite fmt <file> --confirm` runs a second time
- **THEN** it plans no write, and `result.formatted` is `true`

#### Scenario: Project file refused
- **WHEN** `fenolite fmt tests/data/kicad/project/empty_10.kicad_pro --check` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Explain command
`fenolite explain CODE` SHALL be registered by `src/fenolite/cli/cmd_explain.py` with `mutates=False`, and SHALL say what an error code or an issue code means and what to do about it, from data packaged with Fenolite.
- `src/fenolite/cli/data/explain.toml` MUST hold one table per code with `meaning` and `fix`, each a non-empty text of at most 400 characters, and `see`, a heading of `docs/cli-contract.md`.
- `fenolite.cli.explain.TABLES` MUST name every issue-code table of the package, and `all_codes()` MUST return every code of those tables and of the FEN registry of `cli/errors.py`.
- A code whose table key is a family (`<oracle>.drc.<type>`, `<oracle>.erc.<type>`) MUST be explained by the entry `<prefix>.*` of its family unless it has an entry of its own; `result.family` then names the family.
- `result` MUST hold `code`, `kind` (`error` or `issue`), `exit_code` (for a FEN code), `severities` (for an issue code), `meaning`, `fix`, `see` and `family`.
- An unknown code MUST exit 2 with `FEN-2001` and a hint that names the three closest codes (`difflib.get_close_matches`).
- A test MUST fail for a code of `all_codes()` without an entry, for an entry whose code is in no table and is not a family, and for a mapping in `src/fenolite` whose name ends in `ISSUE_CODES` and that `TABLES` does not name.
- `example_args` MUST be `("FEN-4001",)`.

#### Scenario: An error code
- **WHEN** `uv run fenolite explain FEN-4001 --json` runs
- **THEN** `result.kind` is `error`, `result.exit_code` is 4, and `result.fix` names `--confirm`

#### Scenario: An issue code of a family
- **WHEN** `fenolite explain kicad.drc.clearance --json` runs
- **THEN** the exit code is 0, `result.kind` is `issue`, and either the code has its own entry or `result.family` is `kicad.drc.*`

#### Scenario: Unknown code
- **WHEN** `fenolite explain check.read-refuse` runs
- **THEN** the exit code is 2, and the hint names `check.read-refused`

#### Scenario: Table is complete
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py -k complete` runs
- **THEN** every code of `all_codes()` has an entry, no entry is orphaned, and every `ISSUE_CODES` mapping of the package is in `TABLES`

### Requirement: Receipt identity
The receipt of a confirmed mutating command SHALL carry, beside `written` and `backup` ("Mutation protocol"), `id` and `undo`.
- `id` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of `{"written": …, "backup": …}`; it MUST NOT depend on a clock, a seed or the working directory.
- `undo` MUST be the string `fenolite restore - --confirm` when `backup` is not empty, and `null` otherwise.
- `schemas/fenolite.envelope.v0.json` MUST hold both fields, with defaults, so an envelope without them still validates.

#### Scenario: Identity of a write
- **WHEN** `_echo --write out.txt --confirm` runs twice in two empty folders with the same content
- **THEN** the two receipts have equal `id`s of 16 hex digits and `undo` `null`

#### Scenario: Undo offered after an overwrite
- **GIVEN** `out.txt` already exists
- **WHEN** `_echo --write out.txt --confirm` runs
- **THEN** `receipt.undo` is `fenolite restore - --confirm`

### Requirement: Restore command
`fenolite restore RECEIPT [--in DIR]` SHALL be registered by `src/fenolite/cli/cmd_restore.py` with `mutates=True`, and SHALL put back the backups of one confirmed write, described by the receipt that write returned. It MUST delete no file.
- **Receipt.** `RECEIPT` MUST be a file holding an envelope whose `receipt` is not `null`, or a bare receipt object; `-` MUST read it from stdin. Anything else MUST exit 3 with `FEN-3004`. The receipt's paths are relative to `--in DIR`, default the working directory.
- **Unchanged since.** Every file of `written` MUST exist with the recorded `sha256`; each one that does not MUST give `restore.changed-since` (error; `where` = the path), and the command MUST then plan nothing and exit 5.
- **Plan.** For every path of `backup`, the file `<path>.bak` MUST exist, else `restore.backup-missing` (error) and no plan. The plan MUST be one `PlannedWrite` per such path, at the written file's path, with the bytes of its `.bak` and the kind `restore`.
- **Kept files.** A written file without a backup MUST stay untouched and give one `restore.kept` info.
- **Nothing to restore.** A receipt whose `backup` is empty MUST give `restore.nothing` (error) and exit 5.
- **Undoable.** The mutation protocol applies: the content that the restore replaces becomes the new `.bak`, and the restore's own receipt restores it.
- **Result.** `result` MUST hold `id` (of the receipt read), `restored`, `kept` and, when refused, `changed`.
- The four codes MUST be documented in `docs/cli-contract.md`.
- `example_args` MUST pass a receipt that the suite prepares in its empty folder with `--dry-run`, and `mutation_example_args` the same without it; both MUST run no subprocess.

#### Scenario: Undo of an overwrite
- **GIVEN** `out.txt` holding `one`, then `_echo --write out.txt --confirm --json` writing `two`, its envelope saved as `r.json`
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** `out.txt` holds `one`, `out.txt.bak` holds `two`, and the exit code is 0

#### Scenario: Changed since the write
- **GIVEN** the same receipt after `out.txt` was edited by hand
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** the exit code is 5, the issues hold `restore.changed-since` naming `out.txt`, and no file changes

#### Scenario: Created files stay
- **GIVEN** the receipt of a build into an empty folder followed by a rebuild with a changed value, saved from the rebuild
- **WHEN** `fenolite restore <receipt> --in <cwd of the build> --confirm` runs
- **THEN** every file the rebuild overwrote has its previous bytes, no file is deleted, and the files that had no backup are reported with `restore.kept`

#### Scenario: Receipt from stdin
- **WHEN** the envelope of an overwrite is piped to `fenolite restore - --dry-run`
- **THEN** the exit code is 0 and `result.plan` lists the file

### Requirement: Net command
`fenolite net PATH [NAME]` SHALL be registered by `src/fenolite/cli/cmd_net.py` with `mutates=False` and `paged = "nets"`, and SHALL describe the nets of a board, or one net, from the board model, without running any tool.
- `PATH` MUST resolve with `projectset.resolve_board`; the board is read through `registry.for_path`, narrowed to `BoardFrame` for the pads.
- **Without `NAME`.** `result.nets` MUST be `analysis.views.net_list(design)`: one row per net, sorted by name, with `name`, `class`, `pads`, `tracks`, `vias`, `zones` and `length` (the summed centre-line length of its tracks and arcs, in nm).
- **With `NAME`.** `result.net` MUST be `analysis.views.net_view(design, NAME, pads=…)`: `name`, `class`, `pads` (each `where` as `REF-PIN`, `layers`, `position`), `copper` (per layer: `tracks`, `arcs`, `length`), `vias`, `zones` (each `layers` and `filled`) and `box` (the bounding box of its pads and copper, or `null`). The paged list is then `net.pads`.
- An unknown name MUST exit 2 with `FEN-2001` and the three closest net names in the hint.
- Lengths MUST be integer nanometres. The output MUST be deterministic and hold no absolute path.
- **Evidence.** `Evidence.combine` of the board read's evidence and `frame.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_BOARD,)`.

#### Scenario: Net list of the authored board
- **WHEN** `uv run fenolite net tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.nets` names `GND`, `LED_A` and `VCC` in this order, each with its pad and track counts

#### Scenario: One net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GND --json` runs
- **THEN** `result.net.pads` lists the pads of `GND` as `REF-PIN`, and `result.net.copper` gives a length in nm per layer that has tracks

#### Scenario: Unknown net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GDN` runs
- **THEN** the exit code is 2 and the hint names `GND`

### Requirement: Region command
`fenolite region PATH --box X1,Y1,X2,Y2 [--layer NAME] [--kinds a,b]` SHALL be registered by `src/fenolite/cli/cmd_region.py` with `mutates=False` and `paged = "items"`, and SHALL list what a rectangle of the board holds.
- `--box` MUST be four lengths with units (`10mm,5mm,30mm,20mm`), parsed with `core.units.parse_length`, in the board file's frame; the rectangle is closed and its corners may come in any order. A length without a unit, or a rectangle of zero area, MUST exit 2 with `FEN-2001`.
- `result.items` MUST be `analysis.views.region_view(…)`: objects `{kind, where, net, layer, box}` sorted by kind and then `where`, for the kinds `footprint`, `pad`, `track`, `arc`, `via`, `zone` and `text`, filtered by `--kinds` and, with `--layer`, to items on that layer.
- `result` MUST also hold `box`, `layer` and `counts` per kind.
- `example_args` MUST be `(EXAMPLE_BOARD, "--box", "0mm,0mm,300mm,200mm")`.

#### Scenario: Whole board
- **WHEN** `uv run fenolite region tests/data/kicad/board/two_layer.kicad_pcb --box 0mm,0mm,300mm,200mm --json` runs
- **THEN** `result.counts.footprint` is 2, and every item has a `box` inside or across the rectangle

#### Scenario: One layer and one kind
- **WHEN** the same command runs with `--layer B.Cu --kinds track`
- **THEN** every item is a track on `B.Cu`

#### Scenario: Box without units
- **WHEN** `fenolite region <board> --box 0,0,10,10` runs
- **THEN** the exit code is 2, and the hint says that lengths need a unit

### Requirement: Neighbors command
`fenolite neighbors PATH REF [--radius L]` SHALL be registered by `src/fenolite/cli/cmd_neighbors.py` with `mutates=False` and `paged = "neighbors"`, and SHALL list the footprints near one part.
- `--radius` MUST be a length with a unit, default `5mm`.
- `result.part` MUST hold `ref`, `position`, `rotation`, `side` and `box` (of its extent); `result.neighbors` MUST be the rows of `analysis.views.neighbors_view(…)`: `ref`, `distance` (nm; 0 when the extents touch or overlap), `overlap`, `side` and `shared_nets` (sorted names), sorted by distance and then reference.
- Only footprints on the part's side are neighbours; a through-hole part is on both sides.
- An unknown reference MUST exit 2 with `FEN-2001` and the closest references in the hint.
- `example_args` MUST be `(EXAMPLE_BOARD, "R1")`.

#### Scenario: Neighbours of a resistor
- **WHEN** `uv run fenolite neighbors tests/data/kicad/board/two_layer.kicad_pcb R1 --radius 50mm --json` runs
- **THEN** `result.part.ref` is `R1`, and `result.neighbors` lists the other footprint with its distance in nm and the nets it shares with `R1`

#### Scenario: Radius too small
- **WHEN** the same command runs with `--radius 0.01mm`
- **THEN** `result.neighbors` is empty and the exit code is 0

#### Scenario: Views are hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `net`, `region`, `neighbors`, `explain`, `roundtrip` and `fmt` with their `example_args`
- **THEN** each exits 0
