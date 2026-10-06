## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `backend-protocol`, `altium-build`, `cli-contract` and `verification-evidence` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and that c0083 to c0091 are archived (this change does not start before that). Proof: `openspec validate c0092-altium-write-graduation --strict --no-interactive` passes.

## 1. Graduation rule

- [ ] 1.1 Add the two rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `graduated` and its tests (scenarios of "Graduation of a write kind"); with no kit run recorded, every Altium write stays experimental and the matrix shows what is missing. Proof: `uv run pytest tests/unit/backends/test_graduation.py tests/unit/backends`; `uv run python tools/gen_evidence_matrix.py --check`.

## 2. Acceptance

- [ ] 2.1 Author the acceptance project and `tools/acceptance_v04.py`; run it and record the result in `docs/evidence/altium-acceptance.md` (scenario "Acceptance run"). Proof: `uv run pytest tests/kicad/acceptance/test_v04_acceptance.py tests/kicad/test_probe_results.py -rA`; `uv run pytest tests/corpus/test_manifest.py`.

## 3. Kit run

- [ ] 3.1 Build the kit from this tree and hand it to the maintainer with `docs/altium-kit.md`. When he returns the kit folder: `fenolite kit verify`, `fenolite kit record --confirm`, commit the run record, and publish the archive where the record's digest can be matched. Write under this task the run id, the Altium version, and every failed step. Proof: `fenolite kit status --json` lists the run and no stale row.
- [ ] 3.2 Relabel the rows that the run settles (`fenolite kit record` prints them), and write for each row that it did not settle what is missing. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 4. Capabilities and notice

- [ ] 4.1 Apply the rule: update `claims.py` and `CAPABILITIES.write_kinds`, the build's notice and envelope, and `capabilities` (scenarios of "Experimental notice per kind" and "Altium kinds in capabilities"); regenerate the matrix. Proof: `uv run pytest tests/unit/backends tests/unit/cli/test_capabilities_altium.py tests/unit/lens -k altium tests/consistency`; `uv run python tools/gen_evidence_matrix.py --check`.

## 5. Documentation

- [ ] 5.1 Rewrite "Limits" of `docs/altium.md` from the written scope table; update the second backend's status in `README.md` and `agent/SKILL.md`; set the Phase 4 text, the milestone row and the acceptance block of `docs/roadmap.md` to what was measured. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0092-altium-write-graduation --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "v0.4: Altium write kinds leave `experimental` by a tested rule (own readback, RT-A3 over the corpus, a recorded kit run); the acceptance run and its result are in `docs/evidence/altium-acceptance.md`". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
