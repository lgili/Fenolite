## 0. Entry check

- [x] 0.1 Read the living `cli-contract` and `verification-loop` specs and `openspec list`. Write under this task, with the date: whether c0044 is archived (then "Model difference report" and "Diff command" exist: turn this change's two ADDED requirements into MODIFIED deltas that add sheets and the tree view, and start tasks 2.1 and 2.2 from its code); whether c0060 and c0062 are archived (else cut schematic inputs and `roundtrip --level rt2` for schematics, and say so); and that `src/fenolite/analysis/` holds c0047's modules, whose no-float test (`tests/unit/analysis/test_report.py -k no_float`) will also scan `views.py`. Proof: `openspec validate c0066-cli-inspection-commands --strict --no-interactive` passes after any re-base.
  - 2026-10-05: c0044 is not archived (proposed, 0/26 tasks), so "Model difference report" and "Diff command" are not in the living specs and this change's two requirements stay ADDED; c0044 re-bases on them. c0060 and c0062 are not archived (c0060 is being implemented in another worktree, c0062 is not started): schematic inputs of `diff`, `diff_sheets`, RT1 of a schematic in `roundtrip`, RT2 of a schematic (`rt2_erc`) and the schematic rows of the corpus test are cut from this run and stay open below (tasks 2.1b, 2.2b, 2.3b, 2.4b, 2.6b). `src/fenolite/analysis/` holds c0047's modules; `tests/unit/analysis/test_report.py -k no_float` scans every `*.py` of the package, `views.py` included.

## 1. Registers and contract page

- [x] 1.1 Add the row `H-K-FMT-IDEMPOTENT` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`), and one section stub per new command in `docs/cli-contract.md` so the consistency suite's documentation checks have a target. Re-check every name consumed from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`; `grep -c '^| H-K-FMT-IDEMPOTENT ' docs/hypotheses.md` prints `1`.
  - Done (2026-10-05). Divergences between the design's names and the working tree, for the pull request: `sch.read_schematic`, `sch.roundtrip_schematic`, `SchematicSheet` and `tests/data/kicad/schematic/flat.kicad_sch` do not exist before c0060, nor `KicadOracle.rt2_erc` before c0062; `tests/corpus/manifest.toml` holds no schematic rows yet; the envelope schema lists every wire field as required, so `tools/gen_schemas.py` gained an `optional` field mark (task 4.1); the consistency suite asserted an empty folder for mutation examples, so `tests/_cliexamples.py` prepares the files of `fmt` and `restore` (task 2.5). Every other name (`roundtrip.rt1`, `pcb.opaque_count`, `KicadOracle.rt2`, `projectset.resolve_board`, `core.units.parse_length`, `frame.EVIDENCE`, `canonical.load_dir`, `tests/_boards.py::census`, `tests/strategies.py::designs`) is as the design says.

## 2. First half: `diff`, `roundtrip`, `fmt`

- [x] 2.1 Write `src/fenolite/checks/diff.py` and `tests/unit/checks/test_diff.py` (scenarios of "Model difference report"), with property tests: a design against itself is equal whatever its ids; adding then removing an entity gives one `added` in one direction and one `removed` in the other. Proof: `uv run pytest tests/unit/checks/test_diff.py tests/unit/test_import_graph.py`; `uv run pyright src`.
  - Done for designs and libraries (2026-10-05). `diff_sheets` and its two scenarios are task 2.1b.
- [x] 2.1b Add `diff_sheets` for two `SchematicSheet`s (`symbol` by `<ref>#<unit>`, `sheet_ref` by name, `lib_symbol` by embedded name, `label` and `no_connect_flag` by content) with the scenarios "Sheets" and "Opaque content only with ext" on sheets. Proof: `uv run pytest tests/unit/checks/test_diff.py -k sheets`.
  - Done (2026-10-05, follow-up after c0060). The paper, the title block and the pages are the fields of the keyless kind `sheet` (`/sheet/<field>`, and `/sheet/ext` with `ext=True`); the sheet's name is not compared.
- [x] 2.2 Write `src/fenolite/cli/cmd_diff.py` with both views and `tests/unit/cli/test_diff_cmd.py` (scenarios of "Diff command", except the page scenario, which waits for task 6.1). Proof: `uv run pytest tests/unit/cli/test_diff_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
  - Done for boards, footprint files, symbol libraries, built models and the tree view of the five S-expression kinds (2026-10-05). A `.kicad_sch` in the model view exits 2 with a hint that names `--view tree` until task 2.2b. The scenario "Tree view sees opaque content" is tested on a board.
- [x] 2.2b Read `.kicad_sch` inputs of `diff` with `sch.read_schematic` and compare them with `diff_sheets`; add the scenarios "Two schematics" and "Tree view sees opaque content" on `flat.kicad_sch`. Proof: `uv run pytest tests/unit/cli/test_diff_cmd.py -k schematic`.
  - Done (2026-10-05, follow-up). Two schematics are one family; a schematic against a board or a library exits 2.
- [x] 2.3 Write `src/fenolite/cli/cmd_roundtrip.py` and `tests/unit/cli/test_roundtrip_cmd.py` (scenarios of "Roundtrip command" for RT0 and RT1), and add `roundtrip` to `tests/unit/cli/test_check_readonly.py`. Proof: `uv run pytest tests/unit/cli/test_roundtrip_cmd.py tests/unit/cli/test_check_readonly.py tests/consistency`.
  - Done for RT0 of the five kinds and RT1 of a board (2026-10-05). A level after a failed one is `not-run`. A `.kicad_sch` gives `rt1: not-applicable` until task 2.3b.
- [x] 2.3b RT1 of a schematic through `sch.roundtrip_schematic`, with the scenario "Schematic" (`result.kind` `kicad_sch`, `result.level` `rt1`). Proof: `uv run pytest tests/unit/cli/test_roundtrip_cmd.py -k schematic`.
  - Done (2026-10-05, follow-up).
- [x] 2.4 Add RT2 to `roundtrip` and write `tests/kicad/check/test_roundtrip_cmd.py`. Proof: `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
  - Done for the board of a project (2026-10-05), through `checks.rt2.rt2_stage`; passed on the local `kicad-cli` 10.0.6 (`1 passed`). `--level rt2` on a file that is not a board exits 2.
- [x] 2.4b RT2 of the project's schematic through `KicadOracle.rt2_erc`, when the project has one. Proof: `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -k schematic -rA` on both majors.
  - Done (2026-10-06, after c0062): `checks.rt2.erc_rt2` judges `KicadOracle.rt2_erc`; `result.rt2.schematic` holds the verdict. Corrected the same day: it compares `ErcReport.kinds()` in one attempt, without `ERC_RETRIES` and `attempts`, and records `exact` (design, Decision on RT2). Both tests of `tests/kicad/check/test_roundtrip_cmd.py` pass on the local `kicad-cli` 10.0.6 and inside the pinned 9.0.9 image.
- [x] 2.4c Confirm `tests/kicad/check/test_roundtrip_cmd.py` inside the pinned 9.0.9 image.
  - Done (2026-10-05, follow-up): `1 passed` inside the pinned image `kicad/kicad:9.0.9@sha256:e638b79b…` (the built blink for target 9: RT0, RT1 and RT2 hold, `normalised` false, the project folder untouched). The run passed `-p no:hypothesispytest`, because the host's virtual environment holds a macOS build of hypothesis that the Linux image cannot load; the test uses no hypothesis.
- [x] 2.5 Add `sexpr.canonical` and `sexpr.first_line_difference`, write `src/fenolite/cli/cmd_fmt.py` and `tests/unit/cli/test_fmt_cmd.py` (scenarios of "Fmt command" and the hermetic scenarios of "Canonical print check"). Proof: `uv run pytest tests/unit/cli/test_fmt_cmd.py tests/unit/backends/kicad/test_sexpr_dumps.py tests/consistency`.
  - Done (2026-10-05). The hermetic scenario runs on every authored S-expression file of `tests/data/`, the one authored `.kicad_sch` included.
- [x] 2.6 Write `tests/corpus/test_fmt_idempotent.py` and copy its census into `docs/evidence/kicad-fmt-identity.md`. Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_fmt_idempotent.py -rA` with the corpus cached; `git status --porcelain` lists no file under the cache.
  - Done (2026-10-05) on the local cache: 136 of 138 `rt0` rows measured (two heavy rows are not cached), 136 accepted, 0 failures; 94 of 106 authored files accepted, 0 failures. `git status --porcelain` lists no file under the cache.
- [x] 2.6b Run the corpus test again once the schematic rows of c0060 are in the manifest (they carry the use `rt0`, so the test measures them without a change) and copy the new counts into `docs/evidence/kicad-fmt-identity.md` and the `H-K-FMT-IDEMPOTENT` row.
  - Done (2026-10-05, follow-up): 267 of 269 `rt0` rows, 132 of them schematics, 0 failures. For the schematic rows the test checks the fixed point only: `tests/corpus/test_schematic_rt.py` already proves their RT0 row by row.

## 3. `explain`

- [x] 3.1 Write `src/fenolite/cli/explain.py` with `TABLES` and `all_codes`, and the completeness test of `tests/unit/cli/test_explain_cmd.py`, which fails until every code has an entry. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -k tables` passes; the completeness test lists the missing entries.
  - Done (2026-10-05): 27 tables; `all_codes()` spells `<oracle>` as `kicad` and a `<type>` key as the family `kicad.drc.*`.
- [x] 3.2 Write `src/fenolite/cli/data/explain.toml`: `meaning`, `fix` and `see` for every FEN code and every issue code, and one family entry per tool family. Texts are written for Fenolite from the code and its docs; no vendor text is copied. Declare the data file as package data. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -k complete tests/residue`; `uv build` lists `explain.toml` in the wheel.
  - Done (2026-10-05): 291 entries (17 FEN codes, 273 issue codes, the family `kicad.drc.*`). The wheel holds `fenolite/cli/data/explain.toml` without a declaration, because hatch packages every file under `src/fenolite`. No `kicad.erc.*` family yet: no table holds an ERC key before c0062.
- [x] 3.3 Write `src/fenolite/cli/cmd_explain.py` (scenarios of "Explain command"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
  - Done (2026-10-05). A change that adds an `ISSUE_CODES` table or a code (c0060, c0062, c0064, c0068) now fails `test_explain_cmd.py` until it names the table in `TABLES` and adds its entries.

## 4. `restore`

- [x] 4.1 Add `id` and `undo` to `Receipt`, regenerate `schemas/fenolite.envelope.v0.json`, and extend `tests/unit/cli` for "Receipt identity". Proof: `uv run pytest tests/unit/cli tests/consistency tests/unit/test_schema_drift.py`; `uv run python tools/gen_schemas.py --check` exits 0.
  - Done (2026-10-05). The envelope schema lists every field of a wire object as required, so `tools/gen_schemas.py` now leaves out of `required` a field whose metadata says `optional`; `Receipt.id` and `Receipt.undo` are the first two. An envelope written before this change still validates (tested).
- [x] 4.2 Write `src/fenolite/cli/cmd_restore.py` and `tests/unit/cli/test_restore_cmd.py` (scenarios of "Restore command"), with a test that walks a folder before and after and proves that no file was deleted. Proof: `uv run pytest tests/unit/cli/test_restore_cmd.py tests/consistency`.
  - Done (2026-10-05). A receipt path that is absolute or leaves the folder, and a backup that belongs to no written file, are refused as malformed (`FEN-3004`): the receipt is input, and a restore must not write outside `--in`.

## 5. Board views

- [x] 5.1 Write `src/fenolite/analysis/views.py` with `net_list` and `net_view`, leaving the package's `__init__.py` as c0047 wrote it, and `tests/unit/analysis/test_views.py` (net scenarios of "Board views"). Proof: `uv run pytest tests/unit/analysis tests/unit/test_import_graph.py`; `uv run pyright src`.
  - Done (2026-10-05). An arc's length is `r·θ` in fixed-point integers (160 fractional bits; the arctangent by its power series after three halvings), rounded half to even; `NetRow.tracks` counts tracks and arcs.
- [x] 5.2 Add `region_view` with its property test against brute force. Proof: `uv run pytest tests/unit/analysis/test_views.py -k region`.
  - Done (2026-10-05). Items are sorted by kind in the order of `ALL_KINDS`, then by `where`. An item on several layers (a pad, a via, a zone) gives one item, whose `layer` is the first of its layers that was asked for.
- [x] 5.3 Add `neighbors_view` (neighbour scenarios). Proof: `uv run pytest tests/unit/analysis/test_views.py -k neighbors`.
  - Done (2026-10-05). The gap is rounded up with the kernel's floor and one exact touch test of the shape grown by that floor.
- [x] 5.4 Write `src/fenolite/cli/cmd_net.py`, `cmd_region.py` and `cmd_neighbors.py`, and `tests/unit/cli/test_views_cmd.py` (scenarios of "Net command", "Region command" and "Neighbors command"). Proof: `uv run pytest tests/unit/cli/test_views_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
  - Done (2026-10-05). `neighbors` also returns `result.radius` in nm. The three commands share `cli/_boardview.py` (board read, frame records, lengths with units, records as JSON).

## 6. Paging and concise output

- [x] 6.1 Add `paged` and `default_limit` to `Command`, `--limit` and `--cursor` to the dispatcher, the `--issues N` option of the hidden `_echo` command, and `tests/unit/cli/test_paging.py` (scenarios of "Paged results"). Declare `paged` on `check`, `analyze` (its issues), `diff`, `net`, `region`, `neighbors` and, when they exist, `netlist`, `bom`, `pnp` and `manifest`; list the fields in `capabilities`. Proof: `uv run pytest tests/unit/cli/test_paging.py tests/unit/cli/test_capabilities.py tests/consistency`.
  - Done (2026-10-05). Paged: `_echo`, `check`, `analyze` (issues), `diff` (differences, default 200), `net` (`nets|net.pads`), `region` (items), `neighbors`. `netlist`, `bom`, `pnp` and `manifest` do not exist yet: c0063, c0064 and c0065 declare `paged` on them. The page scenario of `diff` (task 2.2) is in `test_paging.py`.
- [x] 6.2 Add `--format concise|detailed` (scenarios of "Concise output"). Proof: `uv run pytest tests/unit/cli/test_paging.py -k concise tests/consistency`.
  - Done (2026-10-05).

## 7. Documentation

- [x] 7.1 Complete `docs/cli-contract.md`: one section per command with its result keys, the paging rule with the cursor's form, concise output, the receipt fields, the `roundtrip.*`, `fmt.*` and `restore.*` codes. Update the agent guide if it exists (`agent/SKILL.md`): `roundtrip` before editing a file Fenolite did not write, `--format concise` for one fix per iteration. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
  - Done (2026-10-05). The page also gained the sections "Receipt identity", "Paged results" and "Concise output"; `agent/SKILL.md` gained "Small questions between the steps" outside the ten-line loop.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0066-cli-inspection-commands --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - Open (2026-10-05): this run ran `make check-fast` and the focused suites only. `make check` is the coordinator's, once, at the merge; `gh pr checks` needs the pull request (the `kicad-9` job also settles task 2.4c).
- [x] 8.2 Update the evidence labels: `H-K-FMT-IDEMPOTENT` becomes `CORPUS-VERIFIED` with the row counts, or records the rows that fail and why. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
  - Done (2026-10-05): `CORPUS-VERIFIED` on two origins (133 KiCad demo rows, 3 third-party), counts in the row; `fmt` reports that level.
- [x] 8.3 Add to `CHANGELOG.md` under Unreleased: "New commands `diff`, `roundtrip`, `fmt`, `explain`, `restore`, `net`, `region` and `neighbors`; `--limit` and `--cursor` page a command's main list, `--format concise` keeps one issue per code; receipts carry an `id` and the `undo` command". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - Done (2026-10-05).
