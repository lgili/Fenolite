# Tasks: c0492-kicad-reference-text-anchor

Rules for every task:

- Public sources only. Each format fact goes in `docs/formats/altium/` with an S- id and an evidence label.
- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test documents are authored for Fenolite and written by Fenolite's own
  writer.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Reproduce: write the authored document of design D1, convert it with Fenolite and import it with
  `kicad-cli pcb import altium`, and compare the ink boxes of each text (today: off by half a box). Record the
  anchor rows with `H-A-IMP-TEXT-ANCHOR`.
  - Proof: `uv run --extra dev pytest tests/kicad/altium/test_text_anchor_oracle_c0492.py -q -n 0` (needs `kicad-cli`)
- [ ] 1.2 Set the justification on import (design D2); test for "A designator converted to KiCad" without
  the tool, against the recorded boxes.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_text_anchor_c0492.py tests/unit/backends/altium/test_pcb_text.py -q -n 0`
- [ ] 1.3 Write the corner from the justification in the Altium writer (design D3); test for "A centred
  designator from a script".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_text_anchor_c0492.py tests/unit/backends/altium/test_truetype_texts.py tests/unit/backends/altium/test_lower_empty_texts.py -q -n 0`
- [ ] 1.4 Round-trip tests for the two scenarios of "Text anchors survive a round trip through KiCad".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_round_trip_texts.py -q -n 0`
- [ ] 2.1 Run the tests that compare converted texts and fields, the triangle of equivalence included.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert -q -n 0 -k "text or field"`
- [ ] 2.2 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 2.3 Maintainer board (private, codes only): after conversion to KiCad, the counts of KiCad
  `silk_overlap` and `silk_over_copper` for designators match the silkscreen findings Altium reports for the
  same texts, or each difference is explained.
