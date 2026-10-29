## 1. Diff gates (task 4.6 of c0175)

- [x] 1.1 Add `fenolite.checks.diffgate` and `diff --allow` (scenarios "A change outside the allowed set" and "The command exits 5"). Proof: `uv run pytest tests/unit/checks/test_diff_gate.py tests/unit/cli/test_diff_gates.py -k "outside or usage or kinds" -q`.
  - 2026-10-28: proof passed (7 tests).
- [x] 1.2 Add `fenolite.backends.kicad.merge`, the three-way merge of boards by root item, with its facts and `H-K-MERGE-ITEMS` (scenario "Changes of two sides are merged"). Proof: `uv run pytest tests/unit/backends/kicad/test_merge.py -q`.
  - 2026-10-28: proof passed (6 tests).
- [x] 1.3 Add `diff --three-way THEIRS --out FILE` under the mutation protocol, `diff.conflict` and `diff.unmergeable` (scenarios "The merge is a planned write" and "An item changed on both sides"). Proof: `uv run pytest tests/unit/cli/test_diff_gates.py tests/unit/cli/test_diff_cmd.py tests/unit/cli/test_paging.py -q`.
  - 2026-10-28: proof passed (43 tests).
- [x] 1.4 Classify resave records of Altium documents in the records view, with `H-A-RD-RESAVE` (scenario "A resaved record"). Proof: `uv run pytest tests/unit/backends/altium/test_resave.py tests/unit/backends/altium/test_diff_records.py -q`.
  - 2026-10-28: proof passed (87 tests).
- [x] 1.5 Document and teach: `docs/cli-contract.md`, `explain.toml`, the guide's `files` page and `tools/gen_agent_guide.py`, the format pages, `docs/hypotheses.md`, `CHANGELOG.md`. Proof: `uv run pytest tests/unit/agent tests/unit/cli/test_explain_cmd.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py tests/unit/test_import_graph.py tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py tests/unit/test_provenance.py tests/consistency -q`.
  - 2026-10-28: proof passed (644 passed, 28 skipped).
- [x] 1.6 `make check-fast` and the required CI jobs green on the integrated head. Proof: `make check-fast`, and the required jobs of the pushed commit. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
