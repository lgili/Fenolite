# Tasks: c0440

## 1. Find the cause

- [x] 1.1 Census the public documents' pad mask modes and rules, and round-trip `-01` and `-02`
  (S-1990, S-1991). Proof: the probe numbers recorded in `docs/evidence/sources.md`.

## 2. Fix

- [x] 2.1 Read the pad modes before `_clean`; keep a manual 0. Proof:
  `uv run pytest tests/unit/convert/test_pad_mask_c0440.py tests/unit/convert/test_pad_layers.py`.
- [x] 2.2 Write a pad's own margins as manual expansions. Proof: the same test,
  `test_a_pad_margin_survives_both_ways`.
- [x] 2.3 Compare the pad mask expansion at level 3. Proof:
  `uv run pytest tests/unit/checks/equivalence/test_codes.py tests/unit/convert/test_pad_mask_c0440.py`.
- [x] 2.4 Public proof. Proof: `uv run pytest tests/corpus/test_altium_pad_mask_c0440.py`.

## 3. Close

- [x] 3.1 `make check-fast`, the focused suites, the `gen_*` checks, CHANGELOG.
  Proof (2026-11-06): lote-28 CI run 42229338778 succeeded on abe1de83f (unit on 3.11 to 3.13 and three OSes, kicad-10 shards 0-3, kicad-9, coverage audit, ci-complete); dev fast-forwarded to it.
