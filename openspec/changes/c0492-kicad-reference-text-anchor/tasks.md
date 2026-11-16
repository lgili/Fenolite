# Tasks: c0492-kicad-reference-text-anchor

Rules for every task:

- Public sources only. Each format fact goes in `docs/formats/altium/` with an S- id and an evidence label.
- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test documents are authored for Fenolite and written by Fenolite's own
  writer.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Reproduce: write the authored document of design D1, convert it with Fenolite and import it with
  `kicad-cli pcb import altium`, and compare the ink boxes of each text (today: off by half a box). Record the
  anchor rows with `H-A-IMP-TEXT-ANCHOR`.
  - Proof: `uv run --extra dev pytest tests/kicad/altium/test_text_anchor_oracle_c0492.py -q -n 0` (needs `kicad-cli`)
  - Result (2026-11-15, local `kicad-cli` 10.0.6): 2 passed. The authored document is `tests/_textanchor.py`
    (Fenolite's own two-layer sample, 18 texts). Before the change Fenolite's reading was centred, half a box
    away; after it every ink box lies within 0.1225 mm of KiCad's, along the text's height (below the 0.15 mm
    stroke). Rows in `pcb-records.md` ("Text anchor") and `import.md` with `H-A-IMP-TEXT-ANCHOR`, register row
    added. Only stroke texts were measured: KiCad draws a TrueType text with its own font.
- [x] 1.2 Set the justification on import (design D2); test for "A designator converted to KiCad" without
  the tool, against the recorded boxes.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_text_anchor_c0492.py tests/unit/backends/altium/test_pcb_text.py -q -n 0`
  - Decision (maintainer, 2026-11-15): the KiCad projection of a footprint's `fp_text` (`fpitems`) reads its
    justification too; without it the footprint texts came back from KiCad centred and 1.3 moved them.
- [x] 1.3 Write the corner from the justification in the Altium writer (design D3); test for "A centred
  designator from a script".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_text_anchor_c0492.py tests/unit/backends/altium/test_truetype_texts.py tests/unit/backends/altium/test_lower_empty_texts.py -q -n 0`
  - Decision (maintainer, 2026-11-15): a TrueType text of any justification is written, not refused, with
    the stroke font's box (design D3; the spec's requirement says so). Tested: a centred and a right-top
    TrueType free text at 90°.
  - Decision (maintainer, 2026-11-15): the writer bytes of `board6` change; the nine stale kit rows are set
    back (`docs/evidence/altium-kit/README.md`, "Stale rows after c0492"). Native kit rerun of K2.4 and K5.1
    to K5.5: maintainer runs in VM.
- [x] 1.4 Round-trip tests for the two scenarios of "Text anchors survive a round trip through KiCad".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_round_trip_texts.py -q -n 0`
- [x] 2.1 Run the tests that compare converted texts and fields, the triangle of equivalence included.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert -q -n 0 -k "text or field"`
  - Result (2026-11-15): run within a wider run of every test that reads a written PCB document (backends,
    convert, lens, cli, silk, verify, the KiCad oracles of texts): 17 569 passed, 8 failed, each fixed and
    rerun alone (the `H-A-IMP-*` evidence table, the import layering, a test text authored centred where the
    import gives left-bottom, the `board6` golden file and its digest in `docs/evidence/altium-pcb.md`, the
    packaged graduation snapshot, the evidence matrix).
- [x] 2.2 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
  - Result (2026-11-16): 25 435 passed, 2 failed (the layering of `backends` → `silk`, fixed by moving the
    estimator to `geometry.strokefont`; the recorded bytes of `acceptance_v03@altium`, whose PcbDoc alone
    moves, remeasured); both rerun alone and passed, with ruff, ruff format, pyright and the generators.
- [ ] 2.3 (maintainer runs in VM) Maintainer board (private, codes only): after conversion to KiCad, the counts of KiCad
  `silk_overlap` and `silk_over_copper` for designators match the silkscreen findings Altium reports for the
  same texts, or each difference is explained.
