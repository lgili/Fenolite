## 0. Entry check

- [x] 0.1 c0060 is archived, so `SchematicSheet`, `read_schematic` and the inventory rows of kinds `kicad_sch` and `kicad_sym` exist. Read the living text of the four `design-dsl` requirements and of "Assignment compare stage" that this change modifies; if another change modified one of them after 2026-10-04 (c0058 writes symbol libraries too), re-base the delta on the new text first and note it under this task. Proof: `openspec list` shows c0060 archived; `openspec validate c0061-kicad-schematic-writer --strict --no-interactive` passes after the re-base.

  Note (2026-10-05): c0060 is on `dev` and not archived yet (24 of 25 tasks; its open task is the merge gate), so the proof reads "c0060 is on `origin/dev`": `SchematicSheet`, `read_schematic` and the inventory rows of kinds `kicad_sch` and `kicad_sym` exist there. The four `design-dsl` requirements and "Assignment compare stage" were compared with the living text line by line: each delta differs from it only by the lines this change means to change, so no re-base was needed. c0058's "Project-authored symbols" is a separate requirement and is named by the delta.

## 1. Registers and fact rows

- [x] 1.1 Register the hypotheses and widen the sources. This is the first commit of the implementation.
  - Add the nine rows `H-K-SCH-MINIMAL`, `H-K-SCH-PINFRAME`, `H-K-SCH-UNCONNECTED`, `H-K-SCH-SLASH`, `H-K-SCH-PARITY`, `H-K-SCH-POWER`, `H-K-SCH-LIBTABLE`, `H-K-SCH-RESAVE` and `H-K-SCH-UPDATE` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context", per major.
  - Widen the "used for" cells of S-0020, S-0022, S-0037 and S-0046, each only with what it states or what was observed.
  - Re-check every name consumed from c0060 and from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Note (2026-10-05): the count is `14`, not `13`: c0060 registered a fifth row, `H-K-SCH-COMPONENTS-2`, after this task was written. Divergences from design "Files and public API" and "Sources": the schematic format page is S-0367 and its keywords file S-0368 (S-0320 belongs to c0076 now), corrected in `proposal.md` and `design.md`; `build_design` has five keyword arguments more than the delta of "Built project files" lists (`copper_intents`, `fields`, `pad_zones`, `authored_footprints`, `authored_symbols`), which that requirement allows; `resolver.symbol` returns the flattened definition only, so the parent chain that the embedding needs is asked from the resolver by a new method (`LibraryResolver.symbol_chain`).

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-SCH-' docs/hypotheses.md` prints `14`.
- [x] 1.2 Add to `docs/formats/kicad/schematic.md` the fact rows the generator is written from: the written form per target, the pin frame, the names of unconnected pins, label texts and the stored form, power flags and hidden power pins, library rows, parity matching. Each row has a source, a label and a hypothesis. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row; the power flag is recorded as authored for Fenolite. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

  Note (2026-10-05): the rows were written after the probes ran, with the labels the probes give: "Generated sheets" in `docs/formats/kicad/schematic.md` (14 rows).

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [x] 2.1 Write `tests/_erc.py` and `tests/kicad/schematic/_gencases.py`: the probe sheets written by hand into `tmp_path` (an authored probe symbol library with the pin names of the character classes and two hidden power inputs is created in the test, never copied from a KiCad library). Proof: `uv run pytest tests/unit/test_kicad_probes.py tests/residue`.

  Note (2026-10-05): the probe symbols `Probe:Chars`, `Probe:Bare`, `Probe:Load` and `Probe:Supply` are written in `_gencases.py`; the 32-pin IC, the resistor and the dual gate are taken from the authored CC0 mini library. The `sch-lib-*`, `sch-parity-slash-*` and `sch-gen-*` probes run on projects that `build` wrote, because that is what they are about.

- [x] 2.2 Write `test_naming_probes.py::test_pin_frame` and `::test_unconnected_names`, with the probes of "Schematic naming facts are probed"; regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and the fallback applied. Proof: `uv run pytest tests/kicad/schematic/test_naming_probes.py -k "pin_frame or unconnected" tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Note (2026-10-05): no outcome differs from design "Context", and no fallback was applied. 9.0.9 (pinned image) and 10.0.6 (macOS): the twelve `sch-pin-frame-*` probes are `absent`; `sch-unconnected-plain`, `-unnamed`, `-units` and `-chars` are `equal`. Two things the context did not say: the pin `~` of the mini IC is nameless only in a 9.0-format sheet, so the pins without a name are probed with an authored symbol whose names are empty; and the unit letter, `{slash}` and `_` rules, measured on 10.0.6 at proposal time, hold on 9.0.9 too.

- [x] 2.3 Write `::test_label_names`, `::test_power` and `::test_library_rows`; regenerate the probe files; write the outcomes per major into `docs/evidence/kicad-schematic.md`. Correct design Decisions 6 to 10 and the affected requirements where a probe contradicts them, before any generator code. Proof: `uv run pytest tests/kicad/schematic/test_naming_probes.py tests/kicad/test_probe_results.py -rA` on both majors.

  Note (2026-10-05): `sch-label-plain`, `sch-label-chars` (20 texts) and `sch-label-slash` are `equal`, `sch-parity-slash-stored` `absent`, `sch-parity-slash-raw` `present`, `sch-power-flag` `absent`, `sch-hidden-power-joined` `present` (both pins end on `GND`, the first label), `sch-shown-power-separate` `equal`, `sch-lib-missing` `present`, `sch-lib-vendored` and `sch-lib-variant` `absent`, on both majors. No decision changed. Both probe files were regenerated with `FENOLITE_PROBES_WRITE=1`: 30 rows added to `10.0.6.json` and 29 to `9.0.9.json`, no other row changed.

## 3. Names and symbols

- [x] 3.1 Write `src/fenolite/backends/kicad/netnames.py` and `tests/unit/backends/kicad/test_netnames.py` (scenarios of "Names of unconnected-pin nets" and the functions of "Net names in KiCad's stored form"), with `PROVED_PIN_CHARS` from the probes. Proof: `uv run pytest tests/unit/backends/kicad/test_netnames.py`; `uv run pyright src`.

  Note (2026-10-05): `PROVED_PIN_CHARS` is filled by task 2.2. The functions were written before the probes, which call them (order: 3.1, 3.3, 4.1, 4.2, 4.3 and 5, then 2); no generator code was relied on before the measurements of 2026-10-05 on both majors.

- [x] 3.2 Apply the stored form in `pcb.py`: created nets on write, `{slash}` names and the collision rule on read (scenarios of "Net names in KiCad's stored form"). Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_nets.py tests/unit/backends/kicad/test_pcb_write_nets.py tests/unit/backends/kicad/test_pcb_rebuild.py tests/unit/lens`; the corpus round trips stay green: `uv run pytest tests/corpus/test_board_rt1.py`.

  Note (2026-10-05): the tests are in `tests/unit/backends/kicad/test_pcb_net_names.py`. A read net does not carry a `kicad` native id in this code base (its id is derived from `net:<stored name>`), so the writer tells read nets from created ones by that id, and the reader keeps the stored spelling of a `{slash}` net in the net's `kicad` bag (`stored`): the corpus round trip found a board whose net holds a sheet path and a label slash in one name (`/…/A{slash}B`), which the id alone cannot give back. `tests/corpus/test_board_rt1.py`: 22 passed, 2 skipped (heavy rows).

- [x] 3.3 Write `src/fenolite/backends/kicad/symembed.py`: flattening, pin-pad variants, shown power pins, the emit gate, the authored power flag and `write_symbol_library`, which gives a symbol that the design authors (c0058) the node of `sym.write_symbol_library`; both writers take the header version from `FORMAT_VERSIONS`. Write `tests/unit/backends/kicad/test_symembed.py` (scenarios of "Embedded symbols of a generated sheet"), with one test that an all-authored library has the same bytes with the schematic written and skipped. Proof: `uv run pytest tests/unit/backends/kicad/test_symembed.py tests/unit/backends/kicad/test_sym.py tests/unit/backends/kicad/test_check_emittable.py tests/residue`.

  Note (2026-10-05): `embed_symbol(definition, *, parents=…)` takes the resolved symbol and the as-written symbols it extends, which the new `LibraryResolver.symbol_chain` gives. With `allow_lossy` the node of the too-new token is removed (not a whole property or sub-symbol, which would remove a symbol's body). `show_name` and `do_not_autoplace` have no inventory row (c0060 left them unconfirmed); 9.0.9 loads a library symbol that holds them (measured: the blink built for target 9 from the 10.0 mini library with `--allow-lossy`, ERC 0 violations). An empty text that an older library writes `~` is embedded empty for target 10, where `~` is a tilde.

## 4. Layout and generator

- [x] 4.1 Write `src/fenolite/backends/kicad/schlayout.py` with `pin_point`, `PROVED_FRAMES` and `layout_units`, and `tests/unit/backends/kicad/test_schlayout.py` (scenarios of "Pin connection points" and "Deterministic sheet layout"), with property tests: no two cells overlap, every origin is on the grid, every cell is inside the page. Proof: `uv run pytest tests/unit/backends/kicad/test_schlayout.py`; `uv run pyright src`.

  Note (2026-10-05): the row packing is `geometry.shelf.shelf_pack`, which the Altium sheet layout now uses too; nothing else is shared with that backend. `UnitBox` holds `key`, `pins` (`UnitPin`: number, point, angle, label length), `body` and `symbol`; the label lengths are fields of the pins.

- [x] 4.2 Write `src/fenolite/backends/kicad/schgen.py` (design Decisions 4, 5, 7 and 16) and `tests/unit/backends/kicad/test_schgen.py` (scenarios of "Generated sheet content" and "Generated schematic issue codes"). Proof: `uv run pytest tests/unit/backends/kicad/test_schgen.py tests/unit/test_import_graph.py`.

  Note (2026-10-05): `examples/blink_2layer/design.py` now marks its 29 unused pins with `no_connect`, so the scenario "Blink" counts 29 flags: without the marks KiCad's ERC reports 29 `pin_not_connected` and 2 `pin_not_driven` errors on the example, which the proposal's own measurement shows too (the delta is corrected). The helpers of the tests that connect or mark those pins build on the blink without the marks (`_buildhelp.blink(marks=False)`), and the Altium samples of the author reports keep their bytes that way.

- [x] 4.3 Write `sch.write_schematic` for both targets (design Decision 15) and `tests/unit/backends/kicad/test_sch_write.py` (scenarios of "Schematic writing per target"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_write.py tests/unit/backends/kicad/test_sch_read.py`; `uv run pyright src`.

## 5. Build

- [x] 5.1 Write `src/fenolite/lens/schplacements.py` and `tests/unit/lens/test_schplacements.py` (scenarios of "Schematic placements file"). Proof: `uv run pytest tests/unit/lens/test_schplacements.py`.

  Note (2026-10-05): a table needs both `x` and `y`; a table with a rotation only is refused (`build.symbol-placement-invalid`), because a unit that stays in the flow has no fixed cell to turn in. `read_placements` takes an `issues` list.

- [x] 5.2 Add `schematic` and `symbol_placements` to `build_design`, `lower_for_schematic`, the symbol libraries and the table, and `summary["schematic"]`; write `tests/unit/lens/test_build_schematic.py` (scenarios of "Symbols of a built project" and "Board follows the schematic"). Update the tests that pin the built file set. Proof: `uv run pytest tests/unit/lens tests/unit/backends/kicad/test_write_triad.py`; `uv run pyright src`.

  Note (2026-10-05): `BuildOutput.schematic` holds the `GeneratedSchematic`. `build.global-library` and `build.vendor-unsafe-name` for symbol libraries are given by `lens.build`, which owns those codes. `lens.altium_copper` reads a single-pad net `unconnected-(…)` of a `--copper-from` board as no net, or every Altium build from a board built beside a schematic would be refused.

- [x] 5.3 Add `--schematic` to `cmd_build`, the placements file, `result.schematic` and `build.schematic-replaced`; write `tests/unit/cli/test_build_schematic_cmd.py` (scenarios of "Schematic in a build" and of the four modified requirements). Add the option and the new issue codes to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli tests/consistency`.
- [x] 5.4 Change the partition rule of `checks/assignment_compare.py` (MODIFIED "Assignment compare stage") and extend `tests/unit/checks/test_assignment_compare.py`. Proof: `uv run pytest tests/unit/checks`; `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/check -rA` on the local KiCad 10.0.6 shows no new difference on the native and built projects.

  Note (2026-10-05): the export side needed the same rule: IPC-D-356 labels every pad on no net `N/C`, so `padnets.export_netlist` reads that label as no net (unless a net of the board is named so). `tests/kicad/check` on KiCad 10.0.6: 128 passed.

## 6. Oracle proofs (both majors)

- [x] 6.1 Write `tests/kicad/schematic/test_generated_oracle.py::test_erc_clean` and the ERC controls for the blink and the units design; add the probes and regenerate the probe files. Proof: `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k erc tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

  Note (2026-10-05): `test_erc_clean` and `test_erc_controls` pass on 10.0.6 and on 9.0.9; both examples built by hand have 0 violations on both majors (`docs/evidence/kicad-schematic.md`).

- [x] 6.2 Write `::test_parity` with its four controls, the netlist comparison and `::test_check`. Run the copper guard on both examples before and after this change and note any new finding with its cause under this task. Proof: `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k "parity or netlist or check" -rA` on both majors.

  Note (2026-10-05): `test_parity`, `test_parity_controls`, `test_netlist` and `test_check` pass on both majors. Copper guard on `blink_2layer` and `board_40parts`, targets 9 and 10, with `--schematic skip` and `write`: 0 shorts and 0 clearance findings in all eight builds, and equal placement counts, so no new finding. `test_check` on the units design found that `model_netlist` named a mapped pin by its pin number; it now names the pad.

- [x] 6.3 Write `::test_resave` (major 10) and copy its census into `docs/evidence/kicad-schematic.md`. Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/kicad/schematic/test_generated_oracle.py -k resave -rA` on the local KiCad 10.0.6.

  Note (2026-10-05): `sch-gen-resave` is `equal` on 10.0.6; the census is in `docs/evidence/kicad-schematic.md` ("Re-save of a generated sheet").

- [x] 6.4 Add `update_from_schematic` to `tests/_layout_edit.py`, its unit scenarios to `tests/unit/lens/test_build_schematic.py`, and `tests/kicad/lens/test_update_stand_in.py` (requirement "Boards updated from the schematic keep their layout"). Proof: `uv run pytest tests/unit/lens/test_build_schematic.py -k stand_in`; `uv run pytest tests/kicad/lens/test_update_stand_in.py -rA` on both majors.

  Note (2026-10-05): the unit scenarios are `test_stand_in_*` and `test_rebuild_after_the_stand_in` of `tests/unit/lens/test_build_schematic.py`; `tests/kicad/lens/test_update_stand_in.py` passes on 10.0.6 and on 9.0.9 (parity 0, ERC 0).

## 7. Documentation

- [x] 7.1 Write `docs/schematic.md` (requirement "Generated schematics are documented"), link it from `README.md` and `docs/dsl.md`, add the licence note for symbol copies to `docs/dsl.md`, and update `examples/README.md` with the files a build now writes. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue`; `grep -c 'schematic-placements.toml' docs/schematic.md` prints at least `1`.

## 8. Closing

- [x] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0061-kicad-schematic-writer --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing. Done on 2026-10-05: every job of ci run https://github.com/lgili/Fenolite/actions/runs/37332434011 on dev e6fdabbb passed (unit on the five platforms, wheel, dco, kicad-9, kicad-10, routing on both majors); it runs the full suite, so no second local `make check` was started.

  Open (2026-10-05): `make check` and `gh pr checks` belong to the merge: the coordinator runs the full suite once, and the `kicad-9` and `kicad-10` jobs run on the pull request. Done here: `make check-fast` (lint, format, pyright, residue scan, the fast tests), `tools/gen_schemas.py --check`, `openspec validate --strict`, `tests/kicad/check` and the oracle folders that build projects on 10.0.6, and the schematic oracles on 9.0.9 in the pinned image.
- [x] 8.2 Update the evidence labels: each of the nine hypotheses becomes `KICAD-VERIFIED` for the majors that proved it, or is refuted with a successor and the fallback applied; `H-K-SCH-RESAVE` records its census; `H-K-SCH-UPDATE` stays `INFERRED` and records the maintainer's report if there is one. Raise `schgen.EVIDENCE` only if `H-K-SCH-MINIMAL`, `H-K-SCH-UNCONNECTED` and `H-K-SCH-PARITY` hold on both majors. The rows of `docs/formats/kicad/schematic.md` follow. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`. Maintainer's report recorded on 2026-10-05 (one run in KiCad 10.0.6 on the built blink example; `H-K-SCH-UPDATE` stays `INFERRED`).
- [x] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite build` writes a schematic (`<name>.kicad_sch`, symbol libraries and `sym-lib-table`) that KiCad's ERC and parity test accept on 9.0 and 10.0; pads of unconnected pins and net names with a slash are written as KiCad stores them; `--schematic skip` keeps the previous output". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
