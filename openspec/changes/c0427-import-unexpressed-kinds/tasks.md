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
- [x] 2.5 `outline`, `pad-net-unnumbered`, `copper-without-net`, zero-width mechanical arcs: not reproduced
  on public data; reported to the coordinator (design, "Open"). The private sweep at 332b79837 counts, as
  is: `outline` 4, `pad-net-unnumbered` 224, `copper-without-net` 6, zero-width mechanical arcs 0.
  Deferred to v0.8 (coordinator, 2026-11-07): the sweep at lote-29 `0a88720c1` gives the same counts
  (`drawing` 0 after task 2.6); none of the three kinds is reproduced on public or authored data yet.
  Progress 2026-11-10: `tests/unit/importer/test_remaining_unexpressed_c0427.py` reproduces a missing
  outline, a via on no net and a netted unnumbered pad using the authored two-sheet board. A zero-width
  user-layer arc also reproduces the reader/import `drawing` refusal (not a native Altium observation).
  All four cases refuse by default with exit 7, report one precise loss in an explicit lossy dry-run,
  preserve source bytes and write no output. Proof: `uv run pytest
  tests/unit/importer/test_remaining_unexpressed_c0427.py -q -n 0` (4 passed).
  This supplies reproducers, not support for the four cases; task 2.5 stays open.
  First implementation slice: import a truly netless via as a netless `via_table`, without changing
  how an unresolved nonempty net id is reported. Proof: authored import/build on KiCad targets 9 and 10,
  plus the existing named-copper and DSL table checks. Other remaining kinds are separate slices.
  Netless-via slice implemented: `test_netless_via_import_preserves_geometry_and_no_net` proves exact
  physical via fields and absent net on targets 9 and 10. KiCad 10.0.6 also saves a disposable copy of
  each target with the same via and no net. This does not claim a native KiCad 9 save.
  Regenerate `docs/cli-surface.json` after the signature change; the snapshot records that
  `via_table(net=...)` is optional. Proof: `uv run pytest tests/unit/cli/test_cli_surface.py -n 0`.
  Zero-width arc slice: preserve curved user-layer arcs through Python import and build.
  Proof: `uv run pytest tests/unit/importer/test_remaining_unexpressed_c0427.py -n 0`
  and a KiCad 10.0.6 native save comparison of source and rebuild.
  The rebuilt targets 9 and 10 keep width zero, the same layer and the same points. KiCad 10.0.6
  saves disposable copies of the source and each rebuild at 0.1 mm with the same arc geometry.
  A filled user arc with a negative stored width still reports one drawing loss.
  Open-outline slice: preserve a board without a closed ring and its supported individual edges,
  including mixed strokes, with `board(outline=())`. Run the authored import/build regression on
  both KiCad targets, a native save comparison, and the board and zone DSL tests.
  The import/build checks pass for both targets. KiCad 10.0.6 retained the edge counts, points
  and widths across eight native saves of copies (S-2295). Receipt SHA-256:
  `c256d30e48f24346d8ec88f1ac9bbabc1afa557a1c70a44a2b330b0cdf1a68b4`.
  Unnumbered pad slice: assign nets directly to the physical pads by their unnumbered index,
  without adding schematic pins. Test a footprint with mixed unnumbered pads, a pad-only net,
  and the same rebuilt pad geometry and connectivity on both KiCad targets. The focused tests
  confirm the build and repeat rebuild, the unique-geometry match after a native pad UUID change,
  and refusal of an absent pad without writing. Four KiCad 10.0.6 native saves of copies preserved
  all three pads and their nets (S-2296). Receipt SHA-256:
  `7e6f0241093b96de1351221ce3d9fa24cb5e2f93c06537900952e677869c53e4`.
  The proof is on authored cases. A net on a non-copper pad still reports a loss.
- [x] 2.6 Straight arcs: the same sweep counted 1107 user and mechanical arcs of width above 0 left out as
  `drawing` on 16 boards, each with its three points on one line. `_graphic_call` writes such an arc as the
  `design.line()` it draws when its middle point lies between its ends (design, section 6). Proof:
  `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -q -n 0`
  (`test_a_straight_arc_is_the_line_it_draws`).

## 3. Pins and docs

- [x] 3.1 `tests/corpus/test_altium_import_python.py` pins each public row.
- [x] 3.2 `docs/import.md`, `docs/dsl.md`, `docs/cli-contract.md`, `explain.toml`, `CHANGELOG.md`.
