## 1. Copper tidy

- [x] 1.1 Add `tidy/graph.py` and `tidy/prune.py`, the import-graph row `tidy` and the bench `tests/_tidybench.py` (scenarios of "Prune dangling copper" and "Prune keeps the groups"). Proof: `uv run pytest tests/unit/tidy/test_prune.py tests/unit/test_import_graph.py -q`.
  - 2026-10-28: proof passed (8 and the import-graph tests).
- [x] 1.2 Add `tidy/chamfer.py` with the checked undo loop (scenarios of "Chamfer right-angle joints" and "Chamfers are checked"). Proof: `uv run pytest tests/unit/tidy/test_chamfer.py -q`.
  - 2026-10-28: proof passed (6 tests).
- [x] 1.3 Add the command `fenolite tidy`, its example board, the codes and their `explain` entries, and the contract section (scenarios of "Tidy command", "Tidy command checks the result" and "Tidy codes"). Proof: `uv run pytest tests/unit/cli/test_tidy_cmd.py tests/unit/cli/test_explain_cmd.py tests/unit/cli/test_hermetic_examples.py tests/consistency -q`.
  - 2026-10-28: proof passed.
- [x] 1.4 Prove the result with `kicad-cli` and register `H-K-TIDY-DRC` (scenario "KiCad finds nothing new"). Proof: `uv run pytest tests/kicad/tidy -rA` with the local `kicad-cli`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q`.
  - 2026-10-28: both cases passed with local `kicad-cli` 10.0.7; the 9.0.9 side runs in the `kicad-9` job.
- [x] 1.5 Teach it: `docs/copper.md` "Copper tidy", the guide's `routing` page, the generated `commands` page; CHANGELOG; move the requirements and tasks out of c0175. Proof: `uv run python tools/gen_agent_guide.py`, `uv run pytest tests/unit/agent -q`, and `openspec validate c0208-copper-tidy --strict --no-interactive`.
  - 2026-10-28: proof passed.
- [x] 1.6 `make check-fast` and CI on the integrated head. Proof: `make check-fast` and the required jobs (`kicad-9` and `kicad-10` among them) green on the head that carries this change. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
