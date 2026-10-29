## 1. Tidy straighten, T-joints, zone corners and the style report

Tasks 7.2 to 7.5 of c0175 (`openspec/changes/c0175-board-engineering-tools/`), moved here on 2026-10-28.

- [x] 1.1 Write this change, move tasks 7.2 to 7.5 and the `copper-tidy` delta out of c0175 (its task 7.6 stays), and add the row of `openspec/README.md`. Proof: `openspec validate c0214-tidy-straighten --strict --no-interactive` and `openspec validate c0175-board-engineering-tools --strict --no-interactive`.
  - 2026-10-28: c0214 is valid under `--strict` (with the note that its MODIFIED blocks need c0208 archived first). c0175 is valid without `--strict`; under `--strict` it keeps 15 warnings of long requirements of other packages, which it had before (16 at commit 01068dd, one of them the `copper-tidy` delta removed here).
- [x] 1.2 Add `tidy/straighten.py` with the runs, the shapes and the turn costs (scenarios of "Straighten runs", "Turn costs" and "Runs left alone"), and the code `tidy.straighten-skipped`. Proof: `uv run pytest tests/unit/tidy/test_straighten.py tests/unit/test_import_graph.py -q`.
  - 2026-10-28: proof passed (18 tests and the import-graph tests).
- [x] 1.3 Add T-joint entries and zone corners to `tidy/chamfer.py` (scenarios "A T-joint" and "A zone corner"). Proof: `uv run pytest tests/unit/tidy/test_chamfer.py tests/unit/tidy/test_prune.py -q`.
  - 2026-10-28: proof passed (19 tests).
- [x] 1.4 Add `tidy/style.py`, the style report, and the code `tidy.acute` (requirement "Style report"). Proof: `uv run pytest tests/unit/tidy/test_report.py -q`.
  - 2026-10-28: proof passed (5 tests).
- [x] 1.5 Add `--straighten`, `--zones`, `--report` and `--compare` to `fenolite tidy`, `result.style`, the `explain` entries and the contract section (scenarios "Dry run of the steps", "Acute joints reported", "A style compared" and "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_tidy_cmd.py tests/unit/cli/test_explain_cmd.py tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_paging.py tests/consistency -q`.
  - 2026-10-28: proof passed (606 passed, 30 skipped); the generated `commands` page grows by four lines.
- [x] 1.6 Prove the three steps with `kicad-cli` (`H-K-TIDY-DRC`, now with straightened runs and T-joint entries), and register `H-G-TIDY-STYLE`. Proof: `uv run pytest tests/kicad/tidy -rA` with the local `kicad-cli`; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-28: the four cases of `tests/kicad/tidy` pass with local `kicad-cli` 10.0.7 (the 9.0.9 side runs in the `kicad-9` job); the register tests pass (41); `gen_evidence_matrix.py --check` passes (the matrix holds no tidy row, so it is unchanged).
- [x] 1.7 Teach it: `docs/copper.md` "Copper tidy", the guide's `routing` page, the generated `commands` page, `CHANGELOG.md`. Proof: `uv run python tools/gen_agent_guide.py --check` and `uv run pytest tests/unit/agent -q`.
  - 2026-10-28: proof passed (`gen_agent_guide.py --check` and 95 tests of `tests/unit/agent`); `commands` is 594 lines here (590 at 01068dd), `routing` 199.
- [x] 1.8 `make check-fast` and CI on the integrated head. Proof: `make check-fast` and the required jobs (`kicad-9` and `kicad-10` among them) green on the head that carries this change. Done 2026-10-28: `make check-fast` passed on the integrated head b0ca6b9 (14856 passed, 44 skipped); the fixes after it (corpus census pins, KiCad 9 probe scopes) passed their focused tests, and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, mcp, viewer, wheel, dco) passed on `dev-c0225-c0227` at 171bb10 (run 40756504456).
