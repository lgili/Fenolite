# Tasks: c0483-altium-project-layout-kept

- [x] 1.1 Carry the document list in the root sheet's carrier and the bytes of the documents Fenolite does
  not model in `altium-carried/` (`prjpcb.documents_text`, `carried_kind`, `convert.schematic`,
  `to_kicad`), with unit tests.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_project_layout_c0483.py -q -n 0`
- [x] 1.2 Write the drawn sheets with their source names (`drawn.lower_drawn`) and the project in the
  source's layout (`prjpcb.laid_out`, `to_altium._source_layout`, the read-back), with a round-trip test.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_project_layout_c0483.py tests/unit/backends/altium/test_prjpcb_carried_c0479.py -q -n 0`
- [x] 1.3 Import and Altium build keep the folder (`cmd_import`, `cmd_build._through_conversion`), with a
  test; `CHANGELOG.md` and the fact pages.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_project_layout_c0483.py -q -n 0`
- [x] 1.4 Maintainer board (private, codes and counts only): the source, F2 and F5 list the same document
  paths in the same order, and the carried documents are byte-equal.
  - Result 2026-11-11: the source lists 22 documents; F2 and F5 list the same 22 paths in the same order,
    then 3 libraries Fenolite derives that the source does not list. Every listed file is on disk, the 11
    carried documents and the `.PrjPcbStructure` are byte-equal, no `_drawn_` sheet is written. F2, F3,
    F4 and F5 equivalence and the S comparisons exit 0 as before; S-srcA exits 2 as before.
- [x] 1.5 The F2 and F5 projects open and compile in Altium 24.5 as the source does.
  - Result 2026-11-11: Altium 24.5.2.23 opens the source (22 logical documents) and F2 and F5 (the same 22
    in the same order, then the 3 derived libraries); all three compile with "Compile successful, no errors
    found", 262 components and 103 nets each, every net with the same pins.
