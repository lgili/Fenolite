# Tasks: c0416

## 1. Comparison

- [x] 1.1 `norm.slot_form` and the level-3 `pad-slot` difference. Proof:
  `uv run pytest tests/unit/checks/equivalence/test_levels.py -q -k slot`; the length and axis tests fail
  on the old code, which reported nothing.
- [x] 1.2 The kind is public: the kinds table, `equiv.pad-slot`, the explain entry, `AT_REF`,
  `docs/equivalence.md`, `docs/cli-contract.md`, and `docs/cli-surface.json` regenerated. Proof:
  `uv run pytest tests/unit/checks/equivalence/test_codes.py tests/unit/cli/test_explain_cmd.py -q` and
  `uv run python tools/gen_cli_surface.py --check`.

## 2. Oracle

- [x] 2.1 `slot_library()` through `fp upgrade` 10.0.6 and through Fenolite's import give the same
  `slot_form` for every encoded slot; the fact goes to `pcb-records.md`. Proof:
  `uv run pytest tests/kicad/altium/test_slots_import.py -q -k upgrade`.

## 3. Close

- [x] 3.1 ruff check, ruff format --check, `pyright src`, the focused tests; a CHANGELOG line;
  `openspec validate c0416-level3-slot-length-axis --strict`.
- [ ] 3.2 `make check-fast` on the integrated batch and the full CI (coordinator).
