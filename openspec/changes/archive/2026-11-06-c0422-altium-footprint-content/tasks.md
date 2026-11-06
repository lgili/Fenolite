## 1. Evidence

- [x] 1.1 `docs/formats/kicad/board.md`: the census row of the `fp_text` place in the 10.0.6 demos (S-0058,
  CORPUS-VERIFIED) and the row of a created footprint text (S-0020, KICAD-VERIFIED (10.0.x)); the "Created
  items" bullet. Proof: `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py -q`.

## 2. Footprint texts

- [x] 2.1 `pcb.py`: a created footprint writes its texts as `fp_text user` after its drawings and before its
  pads; `to_kicad.py` drops the blanket `footprint-text` loss. Proof:
  `uv run pytest tests/unit/convert/test_footprint_content.py tests/unit/convert/test_footprint_graphics.py -q`.
- [x] 2.2 KiCad: the converted board loads, and a 10.0 re-save keeps the texts. Proof:
  `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/convert/test_footprint_content_oracle.py -q` (10.0.6 and
  9.0.9).

## 3. The KiCad side of a comparison

- [x] 3.1 The KiCad side of the authored conversion projects every footprint drawing and text on the expected
  layer (what c0421's cross-backend completion compares; the comparison itself is c0421's). Proof:
  `uv run pytest tests/unit/convert/test_footprint_content.py -k projects -q`.

## 4. Census and docs

- [x] 4.1 `tests/corpus/test_convert_altium_census.py`: no `footprint-text` loss; the written counts per row.
  Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_convert_altium_census.py -k converted_reports -q`.
- [x] 4.2 `docs/conversion.md` ("Footprint drawings and texts"), `CHANGELOG.md`. Proof:
  `npx -y @fission-ai/openspec validate c0422-altium-footprint-content --strict`.

## 5. Hand-over

- [x] 5.1 Hand-over runs (2026-11-05): the focused unit consumers through the lock (5 343 passed; the two
  `test_pcb_write` token failures were fixed by the `fp_text` row of the board skeleton, on `F.Fab`, and the
  `fp_text` entry of `POSITIONAL`, then passed); the KiCad 10.0.6 consumers (convert, equivalence, importer,
  downgrade, the Altium oracle files: 319 passed); on 9.0.9 `test_buried_form` and the footprint text oracle;
  `tools/kicad_token_fuzz.py --write docs/evidence/kicad/token-fuzz` on 10.0.6 (136 cases) and 9.0.9 (130),
  0 problems; ruff, ruff format, `pyright src`, the `gen_*` `--check` tools and `model_review --check`. The
  corpus census, `make check-fast` and the 3.11 unit run go with the lote-24 heavy run (coordinator's
  decision). Proof: those runs.
