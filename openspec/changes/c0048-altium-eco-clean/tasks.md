## 1. Sources, hypotheses, provenance and the fact pages

- [x] 1.1 Register the sources and the hypotheses (first commit of the implementation; c0038 must already be on the branch).
  - Add rows S-0310 to S-0313 to `docs/evidence/sources.md` from the design table, with the consultation date; widen the "used for" cells of S-0130, S-0185, S-0187, S-0188, S-0172, S-0175, S-0199 and S-0200 as the design says.
  - Add the five `H-A-ECO-*` rows to `docs/hypotheses.md` (backend `altium`, level `INFERRED`, result `pending (author report)`) and the paragraph "Change c0048 (Altium change order) adds …".
  - Add the stem `H-A-ECO-` and the five ids to the registered-rows check of `tests/unit/test_altium_rows.py`, a row to `src/fenolite/backends/altium/PROVENANCE.md` and a session row to `LEGAL-ANNEX.md` that names the maintainer's saved project file as read outside the repository.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py`; `grep -cE '^\| H-A-ECO-' docs/hypotheses.md` prints `5`; `grep -cE '^\| S-031[0-3] ' docs/evidence/sources.md` prints `4`.
- [x] 1.2 Write the facts in Fenolite's own words, before any code: a section "Net class directive" in `docs/formats/altium/schematic-ascii.md` (records 43 and 41, the keys, where the location lies, the orientation values, Fenolite's choices); a section "Class generation" in `docs/formats/altium/project.md` (the seven keys of `[PrjClassGen]`, the three keys per document, the values in the three saved files, the open question on the room key, Fenolite's choices); rows on component classes, rooms and "Supply Nets" in `docs/formats/altium/pcb-copper.md`, and the "Not written" list. Proof: `uv run pytest tests/unit/test_format_facts.py tests/residue`.

## 2. Net class directives in the schematic

- [x] 2.1 Add `layout.ClassMark` and `SheetPlan.class_marks`; write `project.net_class_names` and `project.class_marks`; fill the marks in `project.plan_sheet` and `hierarchy.plan_sheets`. Extend `tests/unit/backends/altium/test_project.py` and `test_hierarchy.py`. Proof: `uv run pytest tests/unit/backends/altium/test_project.py tests/unit/backends/altium/test_hierarchy.py -k "class_mark or net_class"`; covering the scenarios "One directive per sheet and net" and "Class name that a parameter cannot hold".
- [x] 2.2 Write the records in `schdoc.py` (`_Writer.class_mark`, after the No ERC directives), shared by both forms. Extend `tests/unit/backends/altium/test_schdoc.py` and `test_binary.py`. Proof: `uv run pytest tests/unit/backends/altium/test_schdoc.py tests/unit/backends/altium/test_binary.py -k "class"`; covering the scenario "Directive of the blink sample".
- [x] 2.3 Write `net_classes_from_sheet` in `tests/_altium_read.py` from the fact page alone, and its tests in `tests/unit/backends/altium/test_readback.py`. Proof: `uv run pytest tests/unit/backends/altium/test_readback.py -k "net_class"`; covering every scenario of "Net class directives read back".

## 3. Class generation keys of the project file

- [x] 3.1 Add `net_classes` to `prjpcb.write_prjpcb`, the three keys per schematic document with `sheets`, and the `[PrjClassGen]` section; pass `net_classes` from `project.write_project`. Update `tests/unit/backends/altium/test_prjpcb.py`, including the c0037 cases whose `.SchDoc` sections gain the keys. Proof: `uv run pytest tests/unit/backends/altium/test_prjpcb.py`; covering every scenario of "Class generation keys of the project file".

## 4. Component classes in the PCB document

- [x] 4.1 Write `pcbdoc.component_class_records` and append its records in `write_pcbdoc`; extend `read_classes` of `tests/_altium_pcb_read.py` with the member check. Extend `tests/unit/backends/altium/test_pcbdoc.py` and `test_altium_pcb_read.py`. Proof: `uv run pytest tests/unit/backends/altium/test_pcbdoc.py tests/unit/backends/altium/test_altium_pcb_read.py -k "class"`; covering every scenario of "Component class records".

## 5. The build, the golden files, the samples and Part E

- [x] 5.1 In `lens/altium.py`: the class-name check in `_check` and the new `altium.not-lowered` message. Write `tests/unit/lens/test_altium_eco.py` (the board example with module sheets and the routed sample, read back) and extend `tests/unit/lens/test_altium_issues.py`. Proof: `uv run pytest tests/unit/lens/test_altium_eco.py tests/unit/lens/test_altium_issues.py`; covering every scenario of "Classes in an Altium build".
- [x] 5.2 Rebuild the golden files with `FENOLITE_GOLDEN_WRITE=1` and update every SHA-256 that the evidence pages name for a rebuilt file. Proof: `uv run pytest tests/unit/lens -k golden`; `git status --short tests/data/altium/sample tests/data/altium/no_connect tests/data/altium/kicad_example` prints nothing; covering the scenario "Golden files after the rebuild".
- [x] 5.3 Write Part E in `docs/evidence/altium-pcb.md` (steps E1 to E4 with their hypotheses and expected outcome) and the section "Change order" in `docs/altium.md`, with the `altium.not-lowered` row. Proof: `grep -cE '^- \*\*E[1-4]' docs/evidence/altium-pcb.md` prints `4`; `grep -c "^## Change order" docs/altium.md` prints `1`; `uv run pytest tests/unit/lens -k "golden or protocol"`.
- [x] 5.4 Build the two samples for the maintainer outside the repository, each with a zip and a short README of what the change order should show: the `altium_hier_board` project with module sheets, and the routed sample. Proof: `uv run fenolite build examples/altium_hier_board/design.py --out "$(mktemp -d)/b" --target altium --altium-sheets modules --confirm --json` exits 0, and `git status --short` lists no sample file.
- [x] 5.5 Record the maintainer's report of Part E in the "Reports" section of `docs/evidence/altium-pcb.md` (tool as `AD <major>.<minor>`, the date, one generic outcome per step, no artefact) and set the five `H-A-ECO-*` rows from it. Proof: `uv run pytest tests/unit/test_altium_rows.py tests/unit/test_hypotheses_register.py`; `grep -c "Part E" docs/evidence/altium-pcb.md` prints `2` or more.

## 6. After the report of Part E (2026-10-04)

- [x] 6.1 Write a component class for every sheet: `pcbdoc.component_class_records` names the class of a component without a module after the sheet (the stem of the document's file name), so a flat build and a top sheet with parts get their class; `prjpcb.write_prjpcb` writes the three class keys in every schematic section when `pcb` is given. Update `tests/unit/backends/altium/test_pcbdoc.py`, `test_prjpcb.py` and `tests/unit/lens/test_altium_eco.py`. Proof: `uv run pytest tests/unit/backends/altium/test_pcbdoc.py tests/unit/backends/altium/test_prjpcb.py tests/unit/lens/test_altium_eco.py`; covering the scenarios "Class of a flat document", "Top sheet with parts", "Flat project with a PCB document" and "Flat routed sample".
- [x] 6.2 Rebuild the golden files of the blink and routed samples (documents and project files) and update their SHA-256 and that of `p0` on the evidence page; a sentence of an earlier report keeps its digest. Proof: `uv run pytest tests/unit/lens -k "golden or protocol"`.
- [x] 6.3 Record the report under "Reports", register `H-A-ECO-SHEETCLASS`, narrow `H-A-ECO-SUPPLY` to builds with module sheets, and update the fact pages, `docs/altium.md` and the changelog. Proof: `uv run pytest tests/unit/test_altium_rows.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`; `grep -cE '^\| H-A-ECO-' docs/hypotheses.md` prints `6`.
- [x] 6.4 Build the two samples again for the maintainer outside the repository, with their zips and READMEs. Proof: `uv run pytest tests/unit/lens/test_altium_eco.py`, and `git status --short` lists no sample file.
- [ ] 6.5 Record the maintainer's repeat of step E4 on the rebuilt routed sample and set `H-A-ECO-SHEETCLASS` from it; if a room is still listed, record whether "Generate Rooms" showed ticked. Proof: `uv run pytest tests/unit/test_altium_rows.py tests/unit/test_hypotheses_register.py`.

## 7. Closing

- [x] 7.1 Run the tests and the residue scan. Proof: `make check`; `uv run pytest tests/residue`. After the follow-up of group 6 the fast checks were run (`uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run pytest tests/unit tests/residue -q`); the full suite runs once at the merge.
- [x] 7.2 Update the evidence labels: every new fact row is `INFERRED` with its `H-A-ECO-*` id until task 5.5; `pcbdoc.EVIDENCE` and `project.EVIDENCE` name the new ids. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_altium_rows.py`; `grep -c "H-A-ECO-" src/fenolite/backends/altium/pcbdoc.py src/fenolite/backends/altium/project.py` prints a count above 0 for each file.
- [x] 7.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `grep -c "c0048" CHANGELOG.md` prints `1` or more; `openspec validate c0048-altium-eco-clean --strict`.
