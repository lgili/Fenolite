## 1. Hypotheses for inferred evidence

- [x] 1.1 Register the eight hypotheses and cite one at each of the eighteen sites. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py tests/unit/verify -q`.
  - 2026-10-26: proof passed. the schematic layout row is named `H-A-LAYOUT-REPLAY`, with the author-report form (design, decision 3).
- [x] 1.2 Add the source test (scenarios of "Inferred evidence names a hypothesis"). Proof: `uv run pytest tests/unit/test_inferred_hypotheses.py -q`.
  - 2026-10-26: proof passed (3 tests); before 1.1 it listed the eighteen sites.
- [x] 1.3 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of `c0200-inferred-hypotheses`.
  - 2026-10-26: `make check-fast` passed (14,028 passed, 34 skipped) after three tests that compared the old evidence were updated. CI on the pushed head is recorded below.
  - 2026-10-27: CI run 40421574793 on `0e7c2cf`: every job green.
