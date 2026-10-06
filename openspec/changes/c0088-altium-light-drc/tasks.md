## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-verification`, `altium-build` and `verification-loop` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and whether c0084 is archived (else the rules source maps three kinds and the task says so). Proof: `openspec validate c0088-altium-light-drc --strict --no-interactive` passes.

## 1. Registers

- [ ] 1.1 Add the three rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Copper

- [ ] 2.1 Implement `design_rules` and `board_frame` on the Altium backend. Proof: `uv run pytest tests/unit/backends/altium -k "rules_source or frame"`; `uv run pyright src`.
- [ ] 2.2 Add `copper.clearance` to the document pipeline (scenarios of "Document stage order" and "Copper check on Altium boards"). Proof: `uv run pytest tests/unit/checks/test_document_copper.py tests/unit/checks tests/unit/cli/test_check_altium_copper.py tests/unit/test_import_graph.py`.

## 3. Parity

- [ ] 3.1 Write `adapter/parity.py` and `schematic_side` (scenario "Agreeing project"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_parity_side.py`.
- [ ] 3.2 Add `parity` to the document pipeline and Altium input to `fenolite parity` (scenarios of "Parity on Altium projects"). Proof: `uv run pytest tests/unit/checks/test_document_parity.py tests/unit/cli/test_parity_cmd.py tests/consistency`.

## 4. Guard

- [ ] 4.1 Add the copper guard to the Altium build (scenario "Short refused"). Proof: `uv run pytest tests/unit/lens -k "altium and guard"`.

## 5. Agreement and evidence

- [ ] 5.1 Write `tests/kicad/altium/test_copper_same.py` and `tests/corpus/test_altium_copper.py`; record the boards and their counts in `docs/evidence/altium-roundtrip.md`. Proof: `uv run pytest tests/kicad/altium/test_copper_same.py tests/corpus/test_altium_copper.py -rA` with KiCad 10.0.6 and the corpus cached.
- [ ] 5.2 Document the stages in `docs/cli-contract.md` and `docs/altium.md`; hand Part D to the maintainer when c0084's sample exists and record his report. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/unit/test_hypotheses_register.py`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0088-altium-light-drc --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite check` on Altium input runs the copper check (shorts, clearance, edge) and the parity comparison without a tool, and an Altium build refuses a board with a short". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
