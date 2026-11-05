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

## 3. Altium kit case

- [x] 3.1 Part H of `docs/evidence/altium-pcb.md` defines the kit case for a slot shorter than its hole,
  cases H1 to H6, with `H-A-SLOT-SHORT` registered as `INFERRED`. `test_part_h.py` builds the files outside
  the repository, and checks the saved files of H4 and H6. Proof:
  `uv run pytest tests/unit/backends/altium/test_part_h.py tests/unit/test_hypotheses_register.py -q`.
- [x] 3.2 Run Part H in Altium Designer (altium-rounds-2, on the VM) and record the outcomes; revisit
  `norm.slot_form` and the Altium adapter if H2 or H3 differ.
  - 2026-11-05, done (S-1605). An agent ran H1 to H6 in AD 24.5.2.23 on the VM, on the kit built at
    `4ab835e1`. Every case came out as expected (`docs/evidence/altium-pcb.md`, "Reports", 2026-11-05 Part
    H). H2 and H3 match KiCad 10.0.6's axes (`P1` 0°, `P2` 90°, `P5` 135°, `P6` 120°), and `P3` and `P4`
    lie at 30° and 120°. So `norm.slot_form` and the Altium adapter stay as they are. The H4 and H6 readbacks
    pass (`FENOLITE_ALTIUM_H4=…`, `FENOLITE_ALTIUM_H6=… uv run pytest
    tests/unit/backends/altium/test_part_h.py -k h4|h6`, 1 passed each). `H-A-SLOT-SHORT` stays `INFERRED`,
    because an agent run moves no level.

## 4. Close

- [x] 4.1 ruff check, ruff format --check, `pyright src`, the focused tests; a CHANGELOG line;
  `openspec validate c0416-level3-slot-length-axis --strict`.
- [ ] 4.2 `make check-fast` on the integrated batch and the full CI (coordinator).
