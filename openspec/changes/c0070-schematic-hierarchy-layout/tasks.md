## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `kicad-schematic`, `design-model`, `design-dsl` and `kicad-oracle` specs. Write under this task, with the date: whether c0060, c0061 and c0063 are archived (if one is not, stop: every MODIFIED requirement of this change is added by one of them); whether c0069 is archived (it owns the lens acceptance design used by tasks 5.1 and 6.2; without it, author a design with two modules under `tests/data/schematic/modules/` and use it instead); and any divergence between the names this change consumes (`schlayout.layout_units`, `PROVED_FRAMES`, `GRID`, `CHAR_ROOM`, `own_netlist`, `grammar_issues`, `update_from_schematic`) and the tree. Proof: `openspec validate c0070-schematic-hierarchy-layout --strict --no-interactive` passes after any re-base.
  - 2026-10-06, on `origin/dev` at 363b6738:
    - c0060, c0061 and c0069 are archived. c0063 is **implemented on `dev` and not archived** (16 of 17 tasks; its archive waits for a CI run). The maintainer asked for this change to go on: the code that the stop rule protects is in the tree. The four requirements that c0063 adds ("Own netlist of a generated sheet", "Netlist grammar check", "Schematic netlist guard in a build", "Netlist command") are therefore MODIFIED here from the text of c0063's own delta, and **this change archives after c0063**.
    - Every MODIFIED delta was regenerated from the living text (or from c0063's delta) and the changes of this proposal applied again; `design.md`, "Corrections on 2026-10-06", lists what the proposal had wrong.
    - Names: all seven exist as written. `sch_netlist.REASONS` also holds `undefined-symbol` (c0063), which the proposal's table had dropped; `sch_netlist.ISSUE_CODES` is its own closed set (the proposal said the code joins `sch.ISSUE_CODES`); `GeneratedSchematic` also holds `unvendored` and `power_flags`.
    - The lens acceptance design is `tests/data/lens/acceptance/design.py`: `U1` at the top, the modules `power` and `io`. Its 2-pin parts are in the modules and `U1` is on the root, so it has no satellite: tasks 5.1 and 6.2 use it for the hierarchy, and the generated designs for the satellites.

## 1. Probes and registers

- [x] 1.1 Add the rows `H-K-SCH-HIER-FILE`, `H-K-SCH-HIER-PATH` and `H-K-SCH-WIRE-END` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [x] 1.2 Write `tests/kicad/schematic/test_hierarchy_probes.py` (scenarios of "Hierarchy and wire facts are probed"), record the five outcomes, and write the facts to `docs/formats/kicad/schematic.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/schematic/test_hierarchy_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`. Stop by the stop rules of that requirement when an outcome differs.

## 2. Model and writer

- [x] 2.1 Add `Wire`, `SchematicSheet.wires` and the prefix `wir`; regenerate the schematic schema. Proof: `uv run pytest tests/unit/model tests/unit/test_schema_drift.py`; `uv run python tools/gen_schemas.py --check` exits 0.
- [x] 2.2 Write wires and sheet references in `sch.write_schematic`, and `sheet_instances` only for a sheet with pages (scenarios of "Schematic writing per target"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_write.py`; `uv run pyright src`.

## 3. Hierarchy

- [x] 3.1 Add `layout` to `generate_schematic`, the sheet tree, file names, sheet references, pages and use paths (scenarios of "Hierarchical sheets of a design" and the changed scenarios of "Generated sheet content"), with `sheet_ref_size` and the sheet-reference row of `layout_units` (scenario "Sheet references take a row"). Proof: `uv run pytest tests/unit/backends/kicad/test_schgen_hierarchy.py tests/unit/backends/kicad/test_schgen.py tests/unit/backends/kicad/test_schlayout.py`.
- [x] 3.2 Extend `own_netlist` and `grammar_issues` to the sheet tree (scenarios "Module sheets" and "Missing child"), and pass `children` in the build's guard. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/lens/test_build_netlist_guard.py`.
- [x] 3.3 Write the hierarchical footprint paths in `lower_for_schematic` (scenario "Path of a symbol in a child sheet"). Proof: `uv run pytest tests/unit/lens/test_build_schematic.py`.
- [x] 3.4 Add `--schematic-layout`, the child files, `build.sheet-stale`, `build.sheet-file-collision` and the new `result.schematic` keys; extend `update_from_schematic` to child sheets (scenarios of "Hierarchical sheets in a build"). Proof: `uv run pytest tests/unit/lens/test_build_hierarchy.py tests/unit/cli/test_build_cmd.py tests/consistency`.
  - 2026-10-06: there is no `tests/unit/cli/test_build_cmd.py`; the option's tests are in `tests/unit/cli/test_build_schematic_cmd.py`, beside those of `--schematic`, and the proof was run with that file. The scenario "Module removed later" is tested by giving the module `io` another name without `moved()`: its old sheet is stale in the same way, and the script stays one line away from the fixture.

## 4. Satellites

- [x] 4.1 Write `schlayout.snap_satellites` and `Cluster`, with the overlap rules, and `tests/unit/backends/kicad/test_schlayout_snap.py` (scenarios of "Readable sheet layout"). Proof: `uv run pytest tests/unit/backends/kicad/test_schlayout_snap.py`.
- [x] 4.2 Flow clusters in `layout_units`, emit snap wires and the pair's label in `generate_schematic`, and read wires in `own_netlist` and `grammar_issues` (scenarios "Snap wire" and "Wire through a pin"). Proof: `uv run pytest tests/unit/backends/kicad tests/unit/lens/test_build_netlist_guard.py`.
- [x] 4.3 Extend `tests/_gendesigns.py` with `modules=True` (nested modules and 2-pin parts on IC nets), keeping the designs of `modules=False` unchanged. Proof: `uv run pytest tests/unit/test_gendesigns.py`.

## 5. Oracles

- [x] 5.1 Write `tests/kicad/schematic/test_hierarchy_oracle.py` (scenarios of "Hierarchical schematics pass the oracles"), with the probes `sch-hier-oracle-acceptance` and `sch-hier-oracle-generated`. Proof: `uv run pytest tests/kicad/schematic/test_hierarchy_oracle.py -rA` on both majors; both probe files regenerated.
- [x] 5.2 Re-run c0061's and c0063's oracle tests with the default layout, so the flat examples with satellites still pass. Proof: `uv run pytest tests/kicad/schematic -rA` on both majors.

## 6. Documentation

- [x] 6.1 Update `docs/schematic.md` ("Generated schematics are documented") and `docs/cli-contract.md` (the option, the codes, the result keys). Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
- [ ] 6.2 Render the acceptance design's sheets with `kicad-cli sch export svg` into the pull request description, for a person to judge the readability. Proof: the pull request shows the root and two child sheets.
  - 2026-10-06, open: this session opens no pull request (it does not push). The sheets were rendered with `kicad-cli sch export svg` and `pdf` on 10.0.6 for the acceptance design (root, `io`, `power`), the blink and one generated design; the files are in the session's scratch folder (`c0070/render/`), and `c0070/render.py` there makes them again. The maintainer attaches them when the pull request is opened.

## 7. Closing

- [ ] 7.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0070-schematic-hierarchy-layout --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-06, open: the coordinator runs `make check` once at the merge, and there is no pull request yet. Run here: `make check-fast` (8441 passed, 16 skipped), the residue scan, `tools/gen_schemas.py --check`, `openspec validate --all --strict`, and the oracle tests of `tests/kicad` on 10.0.6 and of `tests/kicad/schematic` in the pinned 9.0.9 image.
- [x] 7.2 Update the evidence: the three rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with the runs (the update half of `H-K-SCH-HIER-PATH` stays `INFERRED` in its notes), or record the outcome that failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [x] 7.3 Add to `CHANGELOG.md` under Unreleased: "The schematic gets one sheet per module and puts 2-pin parts beside the IC pins they connect to, joined by a wire; `--schematic-layout grid` keeps the v0.2a form". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
