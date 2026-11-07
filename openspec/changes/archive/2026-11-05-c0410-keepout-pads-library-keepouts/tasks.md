# Tasks: c0410

## 1. Keep-Out layer areas forbid pads

- [x] 1.1 `convert`'s Keep-Out layer rule areas set `no_pads`. Proof:
  `uv run pytest tests/kicad/altium/test_keepout_import.py -q` (`test_rule_areas_match_kicad_import`
  compares the restrictions of all six areas; it fails on c0407's code) and
  `uv run pytest tests/unit/convert/test_to_kicad.py -q -k keepout`.

## 2. Library keep-outs

- [x] 2.1 `definition_graphics` skips library keep-outs on copper and polygon cut-outs under
  `footprint-keepouts`, with the c0411 hint. Proof:
  `uv run pytest tests/unit/backends/altium/adapter/test_keepout_primitives.py -q`
  (`test_keep_outs_of_a_library_footprint_give_no_copper`).
- [x] 2.2 What `fp upgrade` 10.0.6 makes of the authored library is pinned. Proof:
  `test_library_keepouts_as_kicad_upgrades_them`; the rows are in `pcb-records.md`.

## 3. Close

- [x] 3.1 ruff check, ruff format --check, `pyright src`, the focused tests; a CHANGELOG line;
  `openspec validate c0410-keepout-pads-library-keepouts --strict`.
- [x] 3.2 `make check-fast` on the integrated batch and the full CI (coordinator).

  Closed on lote-23 CI 42081905514 (all jobs green, ci-complete with coverage audit) on 5ab9d6452, fast-forwarded to dev.
