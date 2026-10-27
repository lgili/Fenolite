## 1. Return paths

- [x] 1.1 Add `analysis/returns.py` with spans and vias, and share `CutLine` (scenarios of "Return paths"). Proof: `uv run pytest tests/unit/analysis/test_returns.py tests/unit/analysis/test_crossings.py -q`.
  - 2026-10-27: proof passed (6 and 8 tests); `H-G-RETURN-PATH` registered.
- [x] 1.2 Add the two codes to the table and to `fenolite explain` (scenario "Return codes in the table"). Proof: `uv run pytest tests/unit/analysis/test_findings.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-27: proof passed.
- [x] 1.3 Wire the kind `returns` into `analyze`; document it in `docs/analyses.md` and `docs/cli-contract.md`; teach it on `board-grounds`. Proof: `uv run pytest tests/unit/cli/test_analyze_returns.py tests/unit/cli/test_analyze_length.py tests/unit/cli/test_analyze_power.py tests/unit/agent -q`.
  - 2026-10-27: proof passed.
- [x] 1.4 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of `c0202-return-paths`.
  - 2026-10-27: `make check-fast` passed (14,109 passed, 38 skipped). CI on the pushed head is recorded below.
  - 2026-10-27: CI run 40426559720 on `07930b9`: every job green.
