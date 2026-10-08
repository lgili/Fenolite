## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `backend-protocol`, `altium-build`, `cli-contract` and `verification-evidence` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and that c0083 to c0091 are archived (this change does not start before that). Proof: `openspec validate c0092-altium-write-graduation --strict --no-interactive` passes.
  - **2026-10-08 (release 0.3.0).** `openspec list` read; the living `backend-protocol`, `altium-build`, `cli-contract` and `verification-evidence` read. None of c0083 to c0091 is archived: each is open on `dev` with tasks left (c0083 9/14, c0084 11/13, c0085 13/16, c0086 13/16, c0087 10/12, c0088 11/13, c0090 12/13, c0091 12/14; c0089 is archived). By this task the change does not start, so no code of it is written for 0.3.0 (no `graduated`, no acceptance script, no new row) and the task stays open. What 0.3.0 needs of it, the verdict of the rule on each write kind, is taken by hand from the register and the matrix under task 4.1, without code. `openspec validate c0092-altium-write-graduation --strict --no-interactive` exits 1 on two warnings of its own deltas, the same before and after this note (two ADDED requirements longer than 500 characters); no error.

## 1. Graduation rule

- [ ] 1.1 Add the two rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `graduated` and its tests (scenarios of "Graduation of a write kind"); with no kit run recorded, every Altium write stays experimental and the matrix shows what is missing. Proof: `uv run pytest tests/unit/backends/test_graduation.py tests/unit/backends`; `uv run python tools/gen_evidence_matrix.py --check`.

## 2. Acceptance

- [ ] 2.1 Author the acceptance project and `tools/acceptance_v03.py`; run it and record the result in `docs/evidence/altium-acceptance.md` (scenario "Acceptance run"). Proof: `uv run pytest tests/kicad/acceptance/test_v03_acceptance.py tests/kicad/test_probe_results.py -rA`; `uv run pytest tests/corpus/test_manifest.py`.

## 3. Kit run

- [ ] 3.1 Build the kit from this tree and hand it to the maintainer with `docs/altium-kit.md`. When he returns the kit folder: `fenolite kit verify`, `fenolite kit record --confirm`, commit the run record, and publish the archive where the record's digest can be matched. Write under this task the run id, the Altium version, and every failed step. Proof: `fenolite kit status --json` lists the run and no stale row.
  - **2026-10-08 (release 0.3.0).** No kit run is recorded. The returned folder of 2026-10-07 is no run (`fenolite kit verify` failed it as returned, its form was empty, `fenolite kit record` would refuse it), and Part K of the maintainer's session 2 of 2026-10-08 was not made. **The maintainer decided on 2026-10-08** that the kit did not change since his run of 2026-10-07 and is accepted as validated by that run for 0.3.0 (S-0615). That decision is applied below (task 4.1) as an explicit exception to condition (d) of the rule, for 0.3.0 only; it writes no run record, no run id and no digest, and no row gets `ALTIUM-VERIFIED(kit)`. **Revalidation owed after 0.3.0:** a kit run on the kit that the tree builds, checked with `fenolite kit verify` and recorded with `fenolite kit record --confirm`; that run is also the revalidation of c0148 (every pin of every written schematic document and schematic library sets 0x20). The kit of the tree differs from the folder of 2026-10-07 in its schematic files (c0134, c0144, c0148), as `docs/evidence/altium-kit/README.md` records. The Altium version of the sessions: AD 26.5.0. Task open.
- [ ] 3.2 Relabel the rows that the run settles (`fenolite kit record` prints them), and write for each row that it did not settle what is missing. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - **2026-10-08 (release 0.3.0).** Nothing relabelled from a kit run: none is recorded. The rows that the author reports of session 2 meet by their own criteria are relabelled as author reports (`H-A-OUTJOB-RUN-2`, `H-A-SCHDOT-AREACOLOR`), which never count as release-verified; the others keep their level with a dated observation (`docs/evidence/altium-schematic.md` and `altium-pcb.md`, "Session 2 of 2026-10-08"). Task open.

## 4. Capabilities and notice

- [ ] 4.1 Apply the rule: update `claims.py` and `CAPABILITIES.write_kinds`, the build's notice and envelope, and `capabilities` (scenarios of "Experimental notice per kind" and "Altium kinds in capabilities"); regenerate the matrix. Proof: `uv run pytest tests/unit/backends tests/unit/cli/test_capabilities_altium.py tests/unit/lens -k altium tests/consistency`; `uv run python tools/gen_evidence_matrix.py --check`.
  - **2026-10-08 (release 0.3.0): the verdict of the rule, by hand, per write kind.** The four conditions of design decision 1: (a) an own-readback test (the kinds have one, but `claims.py` names none: the field does not exist before this change's code); (b) for a kind with a model, `H-A-VER-RTA3` (`CORPUS-VERIFIED`) or `H-A-VER-RTA3-PRJ` (`INFERRED`) release-verified; (c) every hypothesis id of the write cell release-verified (`ALTIUM-VERIFIED(kit)`, `KICAD-VERIFIED`, `ORACLE-VERIFIED`, `CORPUS-VERIFIED`; an author report never counts, `verification-evidence`, "Author reports never promote an operation"); (d) one `ALTIUM-VERIFIED(kit)` id from a run that is not stale, waived for 0.3.0 by the maintainer's decision (task 3.1). Counts from `docs/hypotheses.md` and `claims.MATRIX` on this tree:

    | kind | write cell ids | release-verified | author report | `INFERRED` | (b) | (c) | (d) | verdict |
    |---|---|---|---|---|---|---|---|---|
    | `altium_schlib` (SchLib) | 9 | 1 | 1 | 7 | not asked | no | waived | experimental |
    | `altium_pcblib` (PcbLib) | 15 | 3 | 6 | 6 | not asked | no | waived | experimental |
    | `altium_schdoc_ascii` (SchDoc, ASCII) | 17 | 0 | 5 | 12 | no (`H-A-VER-RTA3-PRJ`) | no | waived | experimental |
    | `altium_schdoc_binary` (SchDoc, binary) | 22 | 0 | 9 | 13 | no (`H-A-VER-RTA3-PRJ`) | no | waived | experimental |
    | `altium_pcbdoc` (PcbDoc) | 56 | 10 | 11 | 35 | yes (`H-A-VER-RTA3`) | no | waived | experimental |
    | `altium_prjpcb` (PrjPcb) | 17 | 0 | 5 | 12 | no (`H-A-VER-RTA3-PRJ`) | no | waived | experimental |
    | `altium_outjob` (OutJob) | 6 | 0 | 1 | 5 | not asked | no | waived | experimental |
    | `altium_schdot` (SchDot) | 3 | 0 | 0 | 3 | not asked | no | waived | experimental |
    | `altium_harness` (Harness) | 10 | 0 | 6 | 4 | not asked | no | waived | experimental |

    No kind graduates: every one fails (c), and the schematic and project kinds also fail (b). Among the `INFERRED` ids are the readback rows of seven kinds (`H-A-SCHX-READBACK`, `H-A-PCBX-READBACK`, `H-A-RULE-READBACK`, `H-A-OUTJOB-READBACK`, `H-A-SCHDOT-READBACK`), which a test proves with Fenolite's own code on both sides and which therefore stay `INFERRED` by the register's rule: as written, condition (c) cannot hold for those kinds while their write cell names such a row. The maintainer's exception removes (d) only, so it changes no verdict; the design's non-goal "no graduation by decision" leaves no other way. `claims.py`, `CAPABILITIES.write_kinds`, the notice and `capabilities` are unchanged: every Altium write stays in `experimental`, which the rule asks for a kind that does not graduate. The release record of 0.3.0 holds the same table (`docs/release/v0.3.md`, "Graduation of the Altium write"). Task open: the code of the rule is not written.

## 5. Documentation

- [ ] 5.1 Rewrite "Limits" of `docs/altium.md` from the written scope table; update the second backend's status in `README.md` and `agent/SKILL.md`; set the Phase 4 text, the milestone row and the acceptance block of `docs/roadmap.md` to what was measured. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
- [ ] 5.2 Put the v0.3 acceptance block of `docs/roadmap.md` to the maintainer for review, with the measured result of each of its points beside it; record his answer and the date under this task, and change the block's heading from a proposal to the accepted text or to what he asks. The change does not close before that. Proof: `grep -n "v0.3 acceptance" docs/roadmap.md` shows no "proposal" in the heading, or this task holds his dated refusal.
  - **2026-10-08 (release 0.3.0).** Not put to the maintainer as a review. The release record of 0.3.0 holds each point of the block with its measured result; point 5 (a recorded kit run, and the PCB document and schematic document writes out of `experimental`) is not met. The heading still says proposal. Task open.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0092-altium-write-graduation --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "v0.3: Altium write kinds leave `experimental` by a tested rule (own readback, RT-A3 over the corpus, a recorded kit run); the acceptance run and its result are in `docs/evidence/altium-acceptance.md`". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
