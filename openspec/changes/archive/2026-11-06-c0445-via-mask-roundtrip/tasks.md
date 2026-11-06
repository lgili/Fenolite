## 1. Model and KiCad writer

- [x] 1.1 `Board.mask_margin`, the regenerated board schema, and the KiCad writer's
  `pad_to_mask_clearance`. Proof: `uv run python tools/gen_schemas.py --check` and
  `uv run pytest tests/unit/convert/test_via_mask_c0445.py -k kicad_board -q -n 0`.
- [x] 1.2 The KiCad 10 opening of an untented via. Proof:
  `uv run pytest tests/kicad/vias/test_via_mask_margin_oracle.py -q -n 0`.

## 2. Conversions

- [x] 2.1 `openings.via_rule`, `openings.via_margin`, `altium_to_kicad.via_margins` and `board_mask`.
  Proof: `uv run pytest tests/unit/convert/test_via_mask_c0445.py -q -n 0`.
- [x] 2.2 `to_altium.with_mask_margin`, `PcbDocSpec.via_mask` and `via_record(mask=)`. Proof: the same
  file.

## 3. Public proof

- [x] 3.1 Row -01 converted to KiCad and back: `(pad_to_mask_clearance -0.1016)` and every via opens as
  in the source. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_via_mask_c0445.py -q -n 0`.

## 4. Close

- [x] 4.1 Docs (`pcb-copper.md`, KiCad `board.md`, `design-model.md`), sources S-2040 to S-2043,
  CHANGELOG, light checks and the touched test files alone with `-n 0`.
