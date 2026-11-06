# Tasks: c0427

## 1. Build failures and lost texts of the public rows

- [x] 1.1 Sweep `import --to python` over the public Altium rows; record codes and counts only.
- [x] 1.2 Negative `silk_clearance` minimum in `rule()` (`NEGATIVE_MIN_KINDS`); KiCad probe on 9.0.9 and
  10.0.6; `tests/kicad/rules/test_negative_silk.py`; `docs/formats/kicad/rules.md`; `H-K-DRU-NEG-SILK`.
- [x] 1.3 Board cut-out across the board shape as a notch (`copper.notched`, `altium.import.cutout-notch`);
  `tests/unit/backends/altium/test_cutout_notch.py`; `docs/formats/altium/pcb-records.md`; `H-A-CUTOUT-NOTCH`.
- [x] 1.4 CR LF in texts (`copper.lines`); `H-A-TEXT-CRLF`.

## 2. Unexpressed kinds

- [x] 2.1 `custom-rule`: verbatim rules of the kinds the DSL cannot say (`Source.rule_texts`,
  `_native_kinds`, `_limits_said`); `tests/unit/importer/test_unexpressed_kinds.py`.
- [x] 2.2 `drawing`: nets that only copper graphics name get a variable.
- [x] 2.3 `drawing-layer`: drawings on paste layers; `H-K-PASTE-DRAWING`.
- [x] 2.4 `zone-outline`: with c0428, which owns the arc-ring reconstruction (closed by c0463 task 1.3).
  An arc polygon now has the outline of its arcs chorded within its `ARCRESOLUTION`, so `import --to python`
  writes it as code. Proof: `uv run pytest tests/unit/convert/test_altium_zone_arcs_c0463.py -q -n 0`
  (`test_import_to_python_expresses_the_zone`). The kind stays for a polygon without a readable
  `ARCRESOLUTION`, an arc that cannot be placed and a KiCad zone of fewer than three points.
- [ ] 2.5 `outline`, `pad-net-unnumbered`, `copper-without-net`, zero-width mechanical arcs: not reproduced
  on public data; reported to the coordinator (design, "Open").

## 3. Pins and docs

- [x] 3.1 `tests/corpus/test_altium_import_python.py` pins each public row.
- [x] 3.2 `docs/import.md`, `docs/dsl.md`, `docs/cli-contract.md`, `explain.toml`, `CHANGELOG.md`.
