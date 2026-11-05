# Tasks: c0407

## 1. Polygon cut-outs (B2) and copper keep-outs (B4)

- [x] 1.1 The adapter makes rule areas of `KIND=1` regions and of keep-out tracks, arcs, fills and regions
  on copper, free or of a component (`Context.keepouts`, `Board.keepouts`). Proof:
  `uv run pytest tests/unit/backends/altium/adapter/test_keepout_primitives.py -q`; the B2 and B4 tests
  fail on the old code, which made no rule area.
- [x] 1.2 The public rows `-01` and `-06` hold their polygon cut-outs as pour-only rule areas. Proof:
  `uv run pytest tests/corpus/test_convert_altium_census.py -q` (`test_polygon_cutouts_keep_pours_off`; the
  changed expectations are in design.md).

## 2. Keep-out track bands (B1)

- [x] 2.1 `geometry.bands` gives the band of a segment and of an arc in integers.
- [x] 2.2 `convert` makes one band per Keep-Out layer stroke, and one area per filled shape. Proof:
  `uv run pytest tests/unit/convert/test_to_kicad.py -q -k keepout`.
- [x] 2.3 KiCad 10.0.6's import of the authored document gives the same six areas. Proof:
  `uv run pytest tests/kicad/altium/test_keepout_import.py -q`; the rows are in `pcb-records.md`.

## 3. Slot drill widths (B3)

- [x] 3.1 Level 3 compares `norm.drill_width`. Proof:
  `uv run pytest tests/unit/checks/equivalence/test_levels.py -q` (`test_level3_slot_drill_compares_widths`
  fails on the old code).

## 4. Close

- [x] 4.1 ruff check, ruff format --check, `pyright src`, and the focused tests of the touched files; a
  CHANGELOG line; `openspec validate c0407-altium-keepouts-cutouts-slots --strict`.
- [ ] 4.2 `make check-fast` on the integrated batch and the full CI (coordinator).
