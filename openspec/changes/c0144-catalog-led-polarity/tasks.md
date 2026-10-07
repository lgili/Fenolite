## 0. Entry check

- [x] 0.1 Read the two datasheets of S-0412 and S-0413 for the terminal numbers and the polarity, and the catalog for the other diode lands. Proof: `design.md`, Context.
  - 2026-10-08: terminal 1 is the cathode in both; the land's numbering and summary are right; the map is what was missing. The fetch tool returned the PDF files, not their text; page 1 of each was rendered and read.
- [x] 0.2 Find what pins the footprints' summary. Proof: `design.md`, Decision 1.
  - 2026-10-08: no committed digest, golden, schema or test; a build writes the summary into the footprint file, the board and `.fenolite/board.json`, so the summary is left as it is.

## 1. The warning

- [x] 1.1 The rows of the two LED lands and the polarity paragraph in `docs/catalog/sources.md`, and their entry in `docs/catalog/coverage.md`. Proof: `uv run pytest tests/unit/catalog/test_polarity_notes.py tests/unit/catalog -q`.
  - 2026-10-08: 548 passed (9 of them the new file).

## 2. The kit samples

- [x] 2.1 `examples/kit/{board6,flat,libs,routed}/design.py`: `pad_map={"1": "2", "2": "1"}` on `D1`, `d1["K"]` on `GND`, `d1["A"]` on `LED_A`. Proof: `uv run pytest tests/unit/catalog/test_polarity_notes.py -k kit`; `uv run pytest tests/unit/verify/kit tests/unit/cli/test_kit_cmd.py -q`.
  - 2026-10-08: 4 passed; the kit tests and the catalog tests together 589 passed before the pages were edited, and the catalog tests again after.
- [x] 2.2 Measure the boards and the schematics before and after. Proof: `design.md`, Decisions 2 and 3.
  - 2026-10-08: the eight Altium builds exit 0 and hold RT-A2; every pad net of the four boards is equal before and after; `fenolite kit build` before and after differ in five `SchDoc` files and `kit.json` only. No committed file holds a digest of the kit.

## 3. Documents

- [x] 3.1 `CHANGELOG.md`; `openspec validate --all --strict --no-interactive`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_evidence_matrix.py --check`. Proof: the three commands exit 0.
  - 2026-10-08: 103 items valid; both tools exit 0.
- [ ] 3.2 The coordinator amends the rows S-0412 and S-0413 of `docs/evidence/sources.md` with what was read on 2026-10-08 (`design.md`, Context).
  - Open (2026-10-08): the register is append-only in this batch, and the rows exist.
- [ ] 3.3 The maintainer answers the open question of `design.md` (a default map, a warning, or neither).
- [ ] 3.4 Run the kit's steps that read `D1` in Altium Designer 26 on the rebuilt kit (the sheets of `flat`, `routed`, `board6` and `libs` hold two new pin-map records each).
  - Open (2026-10-08): nothing was opened in Altium for this change; the documents are proved by Fenolite's readers only (RT-A2).
