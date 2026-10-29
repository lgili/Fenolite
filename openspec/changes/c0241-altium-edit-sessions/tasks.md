## 1. Hypotheses and kit phase A

Tasks 1.1 to 3.4 are tasks 6.1 to 6.7 of c0175 (`openspec/changes/c0175-board-engineering-tools/`), moved
here on 2026-10-29 and renumbered: 6.1 is 1.1, 6.2 is 1.2, 6.3 is 2.1, 6.4 to 6.7 are 3.1 to 3.4.

- [x] 1.1 Write the hypotheses of the edit session and of the integrity rules into `docs/hypotheses.md`, each with its kit case. Build kit phase A, with documents authored for Fenolite and the cases to open, save and reopen in Altium. No write code before this task is ticked. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_verification_docs.py -q`.
  - 2026-10-29, on the branch of `1559f1b`: 21 rows, `H-A-EDIT-*` (14) and `H-A-INTEG-*` (7), each `INFERRED` with its kit request (design, Decision 3); `H-A-INTEG-SUBPOLY` records the public evidence against it (8 of 81 polygons hold numbers with gaps). Part J of `docs/evidence/altium-edit.md`: phase A cases J1 to J22 and phase B cases J23 to J33, each with its expected outcome. The board `tests/data/altium_edit/edit.py` (authored, declared in `tests/data/MANIFEST.toml`) and the steps in Brazilian Portuguese (`tests/data/altium_edit/kit/README-phase-a.md`); `tests/unit/backends/altium/test_part_j.py -k phase_a` builds `board/`, `expected.md`, `README.md`, `PART-J.md` and `SHA256SUMS`, the same bytes on every run. No module of `backends/altium/edit/` exists. The proof passes (52 tests with `test_part_j.py`); `uv run python tools/gen_evidence_matrix.py --check` passes.
- [ ] 1.2 **Maintainer, in Altium Designer.** Build phase A with `FENOLITE_ALTIUM_PART_J=~/fenolite-altium-checks/session-7/J-edit uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_a`, run J1 to J22 and send back the folder, the version, the date and the SHA-256 of each saved file. Record the report under "Reports" of `docs/evidence/altium-edit.md` in the form of the native acceptance inventory, register its source, and write what each case measured into the result of its rows. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` by it. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.

## 2. Integrity check

- [ ] 2.1 Add the integrity check stage, with warnings for unconfirmed rules (scenarios "A gap in polygon sub-indices", "Two pads with one unique id", "Two layer fields that disagree"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_integrity.py -q`.

## 3. Edit session

- [ ] 3.1 Add the session with `delete`, `move`, `rotate` and `set_property`, the assertions, the cloning and the index upkeep, behind a gate that is off by default (scenarios "A move written and read back", "A move refused on a wrong old value", "No record to clone from", "A deleted component leaves no index behind", "An operation behind its gate"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_session.py -q`.
- [ ] 3.2 Add the commit gates (scenario "An undeclared connectivity change"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_commit.py -q`.
- [ ] 3.3 Add `flip`, `clone`, `add_component`, `remap_layer` and `set_rule`, each behind its own gate. Proof: `uv run pytest tests/unit/backends/altium/edit -q`.
- [ ] 3.4 Add the schematic session with the net-signature guard. Proof: `uv run pytest tests/unit/backends/altium/edit/test_schematic.py -q`.

## 4. Kit phase B

- [ ] 4.1 Build phase B (`written/`, `faults/`, `expected-b.md`) from the files of task 1.2 with each gate forced on for the kit only. Proof: `uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_b -q`.
- [ ] 4.2 **Maintainer, in Altium Designer.** Run J23 to J33 and give the report; record it as task 1.2 does and set the rows `H-A-EDIT-KIT` and `H-A-INTEG-*`. Set an operation's gate only when its case passes. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.

## 5. Teaching

- [ ] 5.1 Add a tested line for the stage `altium.integrity` and for the session to the closest page of the agent guide; run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch.
- [ ] 6.2 Update the evidence labels of the rows `H-A-EDIT-*` and `H-A-INTEG-*` and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q`.
