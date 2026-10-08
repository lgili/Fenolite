## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `design-equivalence` and `verification-loop` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0089-equivalence-level-5 --strict --no-interactive` passes.
  - **2026-10-06, entry check.** `openspec list` shows c0089 with no task done and nine other proposed changes of v0.4 (c0083 to c0092); none of them holds a delta for `design-equivalence`. Dependencies: c0045 (`2026-10-05-c0045-design-equivalence`) and c0029 (`2026-10-04-c0029-copper-check`) are archived, so no task is stopped. `verification-loop` names no level of `equivalent`.
  - No other change modified a requirement that this one supersedes. The three requirements that the design names ("Equivalent command", "Tolerances and normalisation", "Equivalence documentation") are written as MODIFIED from the living text, with the changes of "Spec deltas and archive order" and their consequences: the scenario "A board equals itself" gives level 5, because `two_layer.kicad_pcb` holds tracks; the result gains `tolerances.length_ppm` and `notices`.
  - Three more living requirements say the opposite of this change and are MODIFIED too, with the smallest edit: "Equivalence package" (`LEVELS` is `(1, 2, 3, 4)`, `max_level` returns 4), "Differences are located" (the closed kinds table, `where`, the severity of an issue) and "Exclusion lists" (an unknown profile key raises, and a profile may now hold `tolerance_ppm`). The design did not list them; without them the archived spec would contradict itself.
  - The ADDED requirements gained bullets that fix what the proposal left open: the names of the copper spans, how a pad's copper is shaped (from the model alone: `checks` may not call a backend's board frame, and the Altium backend has none), how a length is rounded, what `pairing` is, that `route-stub` and `route-unjudged` are notices that never fail a comparison (the exit code of the command is 5 for errors only), and that the comparison rule is one table.

## 1. Registers

- [x] 1.1 Add the three rows to `docs/hypotheses.md` (backend `general`, level `INFERRED`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Routing

- [x] 2.1 Write `routing.py` with `pieces` (scenarios of "Routed connectivity of a net"). Proof: `uv run pytest tests/unit/checks/equivalence/test_routing.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [x] 2.2 Write `level_routing`, the codes and their `explain.toml` entries (scenarios of "Level 5 compares routing per net"). Proof: `uv run pytest tests/unit/checks/equivalence/test_level5.py tests/unit/checks/equivalence tests/unit/cli/test_explain_cmd.py`.

## 3. Command

- [x] 3.1 Accept level 5, `--tolerance-ppm` and the new default (scenarios of "Level 5 in the equivalent command"). Proof: `uv run pytest tests/unit/cli/test_equivalent_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 4. Triangle

- [x] 4.1 Write `tests/kicad/equivalence/test_triangle_level5.py`, record the probe for both majors where the importer runs, and update `docs/evidence/equivalence-triangle.md`. Proof: `uv run pytest tests/kicad/equivalence/test_triangle_level5.py tests/kicad/test_probe_results.py -rA`.
  - **2026-10-06.** Run with the local `kicad-cli` 10.0.6 (macOS): 20 tests of the triangle and the probe file pass. The probe `equiv-l5-triangle` is `equal` and is in `docs/evidence/kicad/probes/10.0.6.json` (written with `FENOLITE_PROBES_WRITE=1`; no other outcome moved). The importer does not run on major 9 (`pcb import` exists from 10.0), so the probe is registered for major 10 only and `9.0.9.json` does not hold it.
  - The profile `kicad-import` 10.0 gains `tolerance_ppm = 20` (measured: 20 nm and 18 ppm at most) and no rule. One `route-stub` notice on one public row is caused by Fenolite's Altium adapter, which drops the holes of a poured region; it gets no rule and is recorded in the evidence page as an open fault outside this change.

## 5. Documentation

- [x] 5.1 Document level 5 in `docs/equivalence.md` and `docs/cli-contract.md`, and set the roadmap's level table. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py`.
  - **2026-10-06.** `docs/equivalence.md` gains "Level 5: routing" and loses the sentence that level 5 is not built; `docs/cli-contract.md`, "equivalent", gains `--tolerance-ppm`, `result.notices`, `tolerances.length_ppm` and the six codes. Examples that compare boards without their copper name `--level 4`.

## 6. Closing

- [x] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0089-equivalence-level-5 --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-07: done by the coordinator on `dev` a343cf87 (the v0.4 batch that holds this change): full `make check` 11729 passed, 66 skipped (macOS, Python 3.13, kicad-cli 10.0.6, with the routing loop); the KiCad 9.0.9 set in the pinned image with the corpus 307 passed, 285 skipped; CI run https://github.com/lgili/Fenolite/actions/runs/37565535455 green on every job (unit on Python 3.11, 3.12 and 3.13 on Linux, macOS and Windows, wheel, dco, kicad-9, kicad-10, routing on KiCad 9 and 10). `openspec validate --all --strict` passed on the same tree.
- [x] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
  - **2026-10-06.** The three rows hold their result in `docs/hypotheses.md`: `H-G-EQ-L5` confirmed and `INFERRED` (no oracle), `H-G-EQ-L5-TRIANGLE` `ORACLE-VERIFIED(kicad-cli) (10.0.6)` on the routed sample, `H-G-EQ-L5-SPLIT` refuted in its bound and superseded by the new row `H-G-EQ-L5-SPLIT-2`. This change does not change what the Altium backend writes or reads, so `backends/altium/claims.py` is not touched; `uv run python tools/gen_evidence_matrix.py` leaves `docs/evidence/matrix.md` as it is.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "`equivalent --level 5` compares routing per net: which pads the copper joins, the vias per layer pair and the routed length per layer". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - **2026-10-06.** The entry also names the change of the default level. `docs/roadmap.md`: the level table marks level 5 as delivered by c0089 and the row of c0089 says what was run; decision 25 (how strict level 5 is) stays the maintainer's.
