## 0. Entry check

- [ ] 0.1 c0060 is archived, so `SchematicSheet`, `read_schematic` and the inventory rows of kinds `kicad_sch` and `kicad_sym` exist. Read the living text of the four `design-dsl` requirements and of "Assignment compare stage" that this change modifies; if another change modified one of them after 2026-10-04 (c0058 writes symbol libraries too), re-base the delta on the new text first and note it under this task. Proof: `openspec list` shows c0060 archived; `openspec validate c0061-kicad-schematic-writer --strict --no-interactive` passes after the re-base.

## 1. Registers and fact rows

- [ ] 1.1 Register the hypotheses and widen the sources. This is the first commit of the implementation.
  - Add the nine rows `H-K-SCH-MINIMAL`, `H-K-SCH-PINFRAME`, `H-K-SCH-UNCONNECTED`, `H-K-SCH-SLASH`, `H-K-SCH-PARITY`, `H-K-SCH-POWER`, `H-K-SCH-LIBTABLE`, `H-K-SCH-RESAVE` and `H-K-SCH-UPDATE` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context", per major.
  - Widen the "used for" cells of S-0020, S-0022, S-0037 and S-0046, each only with what it states or what was observed.
  - Re-check every name consumed from c0060 and from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-SCH-' docs/hypotheses.md` prints `13`.
- [ ] 1.2 Add to `docs/formats/kicad/schematic.md` the fact rows the generator is written from: the written form per target, the pin frame, the names of unconnected pins, label texts and the stored form, power flags and hidden power pins, library rows, parity matching. Each row has a source, a label and a hypothesis. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row; the power flag is recorded as authored for Fenolite. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Write `tests/_erc.py` and `tests/kicad/schematic/_gencases.py`: the probe sheets written by hand into `tmp_path` (an authored probe symbol library with the pin names of the character classes and two hidden power inputs is created in the test, never copied from a KiCad library). Proof: `uv run pytest tests/unit/test_kicad_probes.py tests/residue`.
- [ ] 2.2 Write `test_naming_probes.py::test_pin_frame` and `::test_unconnected_names`, with the probes of "Schematic naming facts are probed"; regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task each outcome that differs from design "Context" and the fallback applied. Proof: `uv run pytest tests/kicad/schematic/test_naming_probes.py -k "pin_frame or unconnected" tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 2.3 Write `::test_label_names`, `::test_power` and `::test_library_rows`; regenerate the probe files; write the outcomes per major into `docs/evidence/kicad-schematic.md`. Correct design Decisions 6 to 10 and the affected requirements where a probe contradicts them, before any generator code. Proof: `uv run pytest tests/kicad/schematic/test_naming_probes.py tests/kicad/test_probe_results.py -rA` on both majors.

## 3. Names and symbols

- [ ] 3.1 Write `src/fenolite/backends/kicad/netnames.py` and `tests/unit/backends/kicad/test_netnames.py` (scenarios of "Names of unconnected-pin nets" and the functions of "Net names in KiCad's stored form"), with `PROVED_PIN_CHARS` from the probes. Proof: `uv run pytest tests/unit/backends/kicad/test_netnames.py`; `uv run pyright src`.
- [ ] 3.2 Apply the stored form in `pcb.py`: created nets on write, `{slash}` names and the collision rule on read (scenarios of "Net names in KiCad's stored form"). Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_nets.py tests/unit/backends/kicad/test_pcb_write_nets.py tests/unit/backends/kicad/test_pcb_rebuild.py tests/unit/lens`; the corpus round trips stay green: `uv run pytest tests/corpus/test_board_rt1.py`.
- [ ] 3.3 Write `src/fenolite/backends/kicad/symembed.py`: flattening, pin-pad variants, shown power pins, the emit gate, the authored power flag and `write_symbol_library`, which gives a symbol that the design authors (c0058) the node of `sym.write_symbol_library`; both writers take the header version from `FORMAT_VERSIONS`. Write `tests/unit/backends/kicad/test_symembed.py` (scenarios of "Embedded symbols of a generated sheet"), with one test that an all-authored library has the same bytes with the schematic written and skipped. Proof: `uv run pytest tests/unit/backends/kicad/test_symembed.py tests/unit/backends/kicad/test_sym.py tests/unit/backends/kicad/test_check_emittable.py tests/residue`.

## 4. Layout and generator

- [ ] 4.1 Write `src/fenolite/backends/kicad/schlayout.py` with `pin_point`, `PROVED_FRAMES` and `layout_units`, and `tests/unit/backends/kicad/test_schlayout.py` (scenarios of "Pin connection points" and "Deterministic sheet layout"), with property tests: no two cells overlap, every origin is on the grid, every cell is inside the page. Proof: `uv run pytest tests/unit/backends/kicad/test_schlayout.py`; `uv run pyright src`.
- [ ] 4.2 Write `src/fenolite/backends/kicad/schgen.py` (design Decisions 4, 5, 7 and 16) and `tests/unit/backends/kicad/test_schgen.py` (scenarios of "Generated sheet content" and "Generated schematic issue codes"). Proof: `uv run pytest tests/unit/backends/kicad/test_schgen.py tests/unit/test_import_graph.py`.
- [ ] 4.3 Write `sch.write_schematic` for both targets (design Decision 15) and `tests/unit/backends/kicad/test_sch_write.py` (scenarios of "Schematic writing per target"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_write.py tests/unit/backends/kicad/test_sch_read.py`; `uv run pyright src`.

## 5. Build

- [ ] 5.1 Write `src/fenolite/lens/schplacements.py` and `tests/unit/lens/test_schplacements.py` (scenarios of "Schematic placements file"). Proof: `uv run pytest tests/unit/lens/test_schplacements.py`.
- [ ] 5.2 Add `schematic` and `symbol_placements` to `build_design`, `lower_for_schematic`, the symbol libraries and the table, and `summary["schematic"]`; write `tests/unit/lens/test_build_schematic.py` (scenarios of "Symbols of a built project" and "Board follows the schematic"). Update the tests that pin the built file set. Proof: `uv run pytest tests/unit/lens tests/unit/backends/kicad/test_write_triad.py`; `uv run pyright src`.
- [ ] 5.3 Add `--schematic` to `cmd_build`, the placements file, `result.schematic` and `build.schematic-replaced`; write `tests/unit/cli/test_build_schematic_cmd.py` (scenarios of "Schematic in a build" and of the four modified requirements). Add the option and the new issue codes to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli tests/consistency`.
- [ ] 5.4 Change the partition rule of `checks/assignment_compare.py` (MODIFIED "Assignment compare stage") and extend `tests/unit/checks/test_assignment_compare.py`. Proof: `uv run pytest tests/unit/checks`; `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/check -rA` on the local KiCad 10.0.6 shows no new difference on the native and built projects.

## 6. Oracle proofs (both majors)

- [ ] 6.1 Write `tests/kicad/schematic/test_generated_oracle.py::test_erc_clean` and the ERC controls for the blink and the units design; add the probes and regenerate the probe files. Proof: `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k erc tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 6.2 Write `::test_parity` with its four controls, the netlist comparison and `::test_check`. Run the copper guard on both examples before and after this change and note any new finding with its cause under this task. Proof: `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k "parity or netlist or check" -rA` on both majors.
- [ ] 6.3 Write `::test_resave` (major 10) and copy its census into `docs/evidence/kicad-schematic.md`. Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/kicad/schematic/test_generated_oracle.py -k resave -rA` on the local KiCad 10.0.6.
- [ ] 6.4 Add `update_from_schematic` to `tests/_layout_edit.py`, its unit scenarios to `tests/unit/lens/test_build_schematic.py`, and `tests/kicad/lens/test_update_stand_in.py` (requirement "Boards updated from the schematic keep their layout"). Proof: `uv run pytest tests/unit/lens/test_build_schematic.py -k stand_in`; `uv run pytest tests/kicad/lens/test_update_stand_in.py -rA` on both majors.

## 7. Documentation

- [ ] 7.1 Write `docs/schematic.md` (requirement "Generated schematics are documented"), link it from `README.md` and `docs/dsl.md`, add the licence note for symbol copies to `docs/dsl.md`, and update `examples/README.md` with the files a build now writes. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue`; `grep -c 'schematic-placements.toml' docs/schematic.md` prints at least `1`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0061-kicad-schematic-writer --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence labels: each of the nine hypotheses becomes `KICAD-VERIFIED` for the majors that proved it, or is refuted with a successor and the fallback applied; `H-K-SCH-RESAVE` records its census; `H-K-SCH-UPDATE` stays `INFERRED` and records the maintainer's report if there is one. Raise `schgen.EVIDENCE` only if `H-K-SCH-MINIMAL`, `H-K-SCH-UNCONNECTED` and `H-K-SCH-PARITY` hold on both majors. The rows of `docs/formats/kicad/schematic.md` follow. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite build` writes a schematic (`<name>.kicad_sch`, symbol libraries and `sym-lib-table`) that KiCad's ERC and parity test accept on 9.0 and 10.0; pads of unconnected pins and net names with a slash are written as KiCad stores them; `--schematic skip` keeps the previous output". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
