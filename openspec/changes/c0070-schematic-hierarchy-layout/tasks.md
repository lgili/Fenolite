## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `kicad-schematic`, `design-model`, `design-dsl` and `kicad-oracle` specs. Write under this task, with the date: whether c0060, c0061 and c0063 are archived (if one is not, stop: every MODIFIED requirement of this change is added by one of them); whether c0069 is archived (it owns the lens acceptance design used by tasks 5.1 and 6.2; without it, author a design with two modules under `tests/data/schematic/modules/` and use it instead); and any divergence between the names this change consumes (`schlayout.layout_units`, `PROVED_FRAMES`, `GRID`, `CHAR_ROOM`, `own_netlist`, `grammar_issues`, `update_from_schematic`) and the tree. Proof: `openspec validate c0070-schematic-hierarchy-layout --strict --no-interactive` passes after any re-base.

## 1. Probes and registers

- [ ] 1.1 Add the rows `H-K-SCH-HIER-FILE`, `H-K-SCH-HIER-PATH` and `H-K-SCH-WIRE-END` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/kicad/schematic/test_hierarchy_probes.py` (scenarios of "Hierarchy and wire facts are probed"), record the five outcomes, and write the facts to `docs/formats/kicad/schematic.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/schematic/test_hierarchy_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`. Stop by the stop rules of that requirement when an outcome differs.

## 2. Model and writer

- [ ] 2.1 Add `Wire`, `SchematicSheet.wires` and the prefix `wir`; regenerate the schematic schema. Proof: `uv run pytest tests/unit/model tests/unit/test_schema_drift.py`; `uv run python tools/gen_schemas.py --check` exits 0.
- [ ] 2.2 Write wires and sheet references in `sch.write_schematic`, and `sheet_instances` only for a sheet with pages (scenarios of "Schematic writing per target"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_write.py`; `uv run pyright src`.

## 3. Hierarchy

- [ ] 3.1 Add `layout` to `generate_schematic`, the sheet tree, file names, sheet references, pages and use paths (scenarios of "Hierarchical sheets of a design" and the changed scenarios of "Generated sheet content"), with `sheet_ref_size` and the sheet-reference row of `layout_units` (scenario "Sheet references take a row"). Proof: `uv run pytest tests/unit/backends/kicad/test_schgen_hierarchy.py tests/unit/backends/kicad/test_schgen.py tests/unit/backends/kicad/test_schlayout.py`.
- [ ] 3.2 Extend `own_netlist` and `grammar_issues` to the sheet tree (scenarios "Module sheets" and "Missing child"), and pass `children` in the build's guard. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/lens/test_build_netlist_guard.py`.
- [ ] 3.3 Write the hierarchical footprint paths in `lower_for_schematic` (scenario "Path of a symbol in a child sheet"). Proof: `uv run pytest tests/unit/lens/test_build_schematic.py`.
- [ ] 3.4 Add `--schematic-layout`, the child files, `build.sheet-stale`, `build.sheet-file-collision` and the new `result.schematic` keys; extend `update_from_schematic` to child sheets (scenarios of "Hierarchical sheets in a build"). Proof: `uv run pytest tests/unit/lens/test_build_hierarchy.py tests/unit/cli/test_build_cmd.py tests/consistency`.

## 4. Satellites

- [ ] 4.1 Write `schlayout.snap_satellites` and `Cluster`, with the overlap rules, and `tests/unit/backends/kicad/test_schlayout_snap.py` (scenarios of "Readable sheet layout"). Proof: `uv run pytest tests/unit/backends/kicad/test_schlayout_snap.py`.
- [ ] 4.2 Flow clusters in `layout_units`, emit snap wires and the pair's label in `generate_schematic`, and read wires in `own_netlist` and `grammar_issues` (scenarios "Snap wire" and "Wire through a pin"). Proof: `uv run pytest tests/unit/backends/kicad tests/unit/lens/test_build_netlist_guard.py`.
- [ ] 4.3 Extend `tests/_gendesigns.py` with `modules=True` (nested modules and 2-pin parts on IC nets), keeping the designs of `modules=False` unchanged. Proof: `uv run pytest tests/unit/test_gendesigns.py`.

## 5. Oracles

- [ ] 5.1 Write `tests/kicad/schematic/test_hierarchy_oracle.py` (scenarios of "Hierarchical schematics pass the oracles"), with the probes `sch-hier-oracle-acceptance` and `sch-hier-oracle-generated`. Proof: `uv run pytest tests/kicad/schematic/test_hierarchy_oracle.py -rA` on both majors; both probe files regenerated.
- [ ] 5.2 Re-run c0061's and c0063's oracle tests with the default layout, so the flat examples with satellites still pass. Proof: `uv run pytest tests/kicad/schematic -rA` on both majors.

## 6. Documentation

- [ ] 6.1 Update `docs/schematic.md` ("Generated schematics are documented") and `docs/cli-contract.md` (the option, the codes, the result keys). Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
- [ ] 6.2 Render the acceptance design's sheets with `kicad-cli sch export svg` into the pull request description, for a person to judge the readability. Proof: the pull request shows the root and two child sheets.

## 7. Closing

- [ ] 7.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0070-schematic-hierarchy-layout --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 7.2 Update the evidence: the three rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with the runs (the update half of `H-K-SCH-HIER-PATH` stays `INFERRED` in its notes), or record the outcome that failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 7.3 Add to `CHANGELOG.md` under Unreleased: "The schematic gets one sheet per module and puts 2-pin parts beside the IC pins they connect to, joined by a wire; `--schematic-layout grid` keeps the v0.2a form". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
