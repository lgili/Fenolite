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
- [x] 3.2 The coordinator amends the rows S-0412 and S-0413 of `docs/evidence/sources.md` with what was read on 2026-10-08 (`design.md`, Context).
  - Open (2026-10-08): the register is append-only in this batch, and the rows exist.
  - 2026-10-09: done. S-0412 and S-0413 of `docs/evidence/sources.md` now hold the reading of 2026-10-08 that `design.md` (Context) records: spec number, revision and date, page 1 rendered and read as a drawing, terminals numbered in the package drawing, the polarity from the diode symbol and the polarity mark, the soldering pattern unnumbered; their date column reads `2026-10-05; 2026-10-08`. `uv run pytest tests/unit/test_provenance.py tests/unit/catalog/test_polarity_notes.py` passes.
- [x] 3.3 The maintainer answers the open question of `design.md` (a default map, a warning, or neither).
  - 2026-10-08: the maintainer decided to apply the default map automatically. Implemented by change c0147 (`openspec/changes/c0147-catalog-default-pad-map/`), which applies `{"1": "2", "2": "1"}` to a part without a `pad_map`, keeps an explicit map, and reports every such part with the warning `build.pad-map-default`. That change replaces this spec's clause "The catalog MUST NOT apply a pin-to-pad map by itself" (its MODIFIED delta), so c0144 is archived first. Left unticked here: the answer is the maintainer's, recorded in c0147, not proved by a command of this change.
  - 2026-10-09: the maintainer's answer of 2026-10-08, a default map ("deixa padrão automático"), is recorded under "Open question for the maintainer" of `design.md`; change c0147 implements it.
- [x] 3.4 Run the kit's steps that read `D1` in Altium Designer 26 on the rebuilt kit (the sheets of `flat`, `routed`, `board6` and `libs` hold two new pin-map records each).
  - Open (2026-10-08): nothing was opened in Altium for this change; the documents are proved by Fenolite's readers only (RT-A2).
  - 2026-10-08, later: the maintainer's session 2 (Altium Designer 26.5.0, the pack built from `695574ba`, which holds this change; S-0615): on the board, pad 1 of `D1` on `GND` and pad 2 on `LED_A`, as expected (`docs/evidence/altium-pcb.md`, "Session 2 of 2026-10-08"). The schematic half of the step (`GND` on pin 2, `K`, of `D1` in `flat`) was not stated, and the kit run was not recorded, so the task stays open.
  - 2026-10-09: done. The maintainer's report of 2026-10-09 for his sessions of 2026-10-07 and 2026-10-08 (Altium Designer 26.5, S-0724): on a kit rebuilt after this change, the kit's steps that read `D1` as expected, `GND` on pin 2 (`K`) and pad 1, `LED_A` on pin 1 (`A`) and pad 2 (`docs/evidence/altium-schematic.md`, "Pin visibility bits", third report). No row moves; the kit run itself (c0091 task 5.3) is not part of the report.
