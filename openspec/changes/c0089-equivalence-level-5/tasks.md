## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `design-equivalence` and `verification-loop` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0089-equivalence-level-5 --strict --no-interactive` passes.

## 1. Registers

- [ ] 1.1 Add the three rows to `docs/hypotheses.md` (backend `general`, level `INFERRED`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Routing

- [ ] 2.1 Write `routing.py` with `pieces` (scenarios of "Routed connectivity of a net"). Proof: `uv run pytest tests/unit/checks/equivalence/test_routing.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 2.2 Write `level_routing`, the codes and their `explain.toml` entries (scenarios of "Level 5 compares routing per net"). Proof: `uv run pytest tests/unit/checks/equivalence/test_level5.py tests/unit/checks/equivalence tests/unit/cli/test_explain_cmd.py`.

## 3. Command

- [ ] 3.1 Accept level 5, `--tolerance-ppm` and the new default (scenarios of "Level 5 in the equivalent command"). Proof: `uv run pytest tests/unit/cli/test_equivalent_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 4. Triangle

- [ ] 4.1 Write `tests/kicad/equivalence/test_triangle_level5.py`, record the probe for both majors where the importer runs, and update `docs/evidence/equivalence-triangle.md`. Proof: `uv run pytest tests/kicad/equivalence/test_triangle_level5.py tests/kicad/test_probe_results.py -rA`.

## 5. Documentation

- [ ] 5.1 Document level 5 in `docs/equivalence.md` and `docs/cli-contract.md`, and set the roadmap's level table. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0089-equivalence-level-5 --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "`equivalent --level 5` compares routing per net: which pads the copper joins, the vias per layer pair and the routed length per layer". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
