## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-verification`, `backend-protocol`, `altium-pcb-writer` and `altium-build` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and whether c0084, c0085, c0086 and c0089 are archived (the tasks below need all four). Proof: `openspec validate c0090-altium-roundtrip-write --strict --no-interactive` passes.

## 1. Registers

- [ ] 1.1 Add the four rows to `docs/hypotheses.md`; `H-A-VER-RTA2-3` is registered as the successor of `H-A-VER-RTA2-2`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Lowering

- [ ] 2.1 Write `lower.py` and `AltiumBackend.write` for a design with a board (scenarios of "Altium write of a model" and "Imported boards are written from the model"). Proof: `uv run pytest tests/unit/backends/altium/test_lower.py tests/unit/backends/test_evidence_declared.py`; `uv run pyright src`.
- [ ] 2.2 Route the build through `from_design` and store the written board in `.fenolite/` (scenario "Build and write agree"; the committed samples stay byte-equal). Proof: `uv run pytest tests/unit/lens -k altium tests/corpus/test_manifest.py`.

## 3. Round-trip levels

- [ ] 3.1 Widen RT-A2 (scenario "Copper compared"). Proof: `uv run pytest tests/unit/lens/test_altium_rta2.py tests/unit/checks -k rta2`.
- [ ] 3.2 Write `rt_a3`, its stage and the two codes with their `explain.toml` entries (scenarios "Own sample" and "A writer defect is caught"). Proof: `uv run pytest tests/unit/checks/test_rta3.py tests/unit/checks tests/unit/cli/test_explain_cmd.py`.
- [ ] 3.3 Accept Altium input in `fenolite roundtrip`. Proof: `uv run pytest tests/unit/cli -k "roundtrip and altium" tests/consistency`.

## 4. Corpus and oracle

- [ ] 4.1 Write `tests/corpus/test_altium_rta3.py`; record the documents, the result and the unwritten counts per kind in `docs/evidence/altium-roundtrip.md`. A difference inside the scope is fixed in the writer or the reader, never in the test. Proof: `uv run pytest tests/corpus/test_altium_rta3.py -rA` with the corpus cached.
- [ ] 4.2 Write `tests/kicad/altium/test_rta3_oracle.py` and record the probe. Proof: `uv run pytest tests/kicad/altium/test_rta3_oracle.py tests/kicad/test_probe_results.py -rA` on KiCad 10.0.6.

## 5. Claims and documentation

- [ ] 5.1 Update `claims.py` and regenerate the matrix (scenario "Matrix follows the run"); write "Round trips" and "Written scope" in `docs/altium.md`. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/backends/test_evidence_declared.py tests/consistency tests/unit/test_repo_layout.py`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0090-altium-roundtrip-write --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "A model with a board can be written as Altium documents; RT-A2 compares footprints and copper, and the new level RT-A3 measures an import, write and re-import over the public corpus". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
