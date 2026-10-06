## Context

- **Today.** `backend-protocol`, "Evidence matrix rows": "The `altium` rows MUST include one row for every write kind of the experimental features …, each with `write` set and listed in `experimental`." `cli-contract`, "Experimental features in capabilities" lists them. `altium-build`, "Altium build evidence": the envelope "stays `INFERRED` for every design". `verification-evidence`: author reports never promote; `release_verified` holds the kit level.
- **What the other changes leave.** c0090: RT-A3 over the corpus and the first round-trip notes in `claims.py`. c0091: the kit, the record and the label rule. c0084 to c0087: the author-report parts U, X, Y, V, W, which the kit's steps repeat as files.
- **The project plan's acceptance for this milestone is not in the repository's public pages.** The roadmap gives only its scope line ("write, equivalence level 5, verification kit") and seven bullets. The acceptance block that this change writes is therefore a proposal for the maintainer, derived from those bullets, and is marked so in the roadmap.

## Goals / Non-Goals

**Goals:**
- `experimental` means something precise, and comes off by evidence only.
- v0.4 has a written acceptance, a run of it, and a page with the result.
- No stale sentence about the Altium target remains in the user documentation.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Rule.** `base.graduated(row, register, runs)` is true for a write cell when: (a) the kind's own readback test is in the suite and passes (the kind names it in `claims.py`); (b) for the kinds with a model (PCB document, schematic documents, project), `H-A-VER-RTA3` or `H-A-VER-RTA3-PRJ` is release-verified; (c) every hypothesis id of the cell is release-verified; (d) at least one hypothesis of the cell is `ALTIUM-VERIFIED(kit)` from a run that is not stale. Libraries (schematic and PCB) need (a), (c) and (d). A cell that fails the rule must be listed in `experimental`, and a cell that passes must not be: the matrix test enforces both directions.
2. **No partial kinds.** A kind graduates as a whole. What a graduated kind does not write is in the written scope table and gives `altium.not-lowered`; that is a limit, not an experiment.
3. **Order of work.** (1) run the acceptance script; (2) the maintainer runs the kit; (3) record the run; (4) relabel rows; (5) apply the rule and regenerate the matrix; (6) rewrite the documentation from the result. If the run fails for a kind, the change is still completed: that kind stays experimental and the page says why.
4. **Acceptance project.** `examples/kit/` samples plus one design that uses everything v0.4 writes (the six-layer board with a module tree, rules of every exact kind, an output job and a drawing sheet). The acceptance script: build for KiCad and for Altium; `check` both; `equivalent` between the two at level 5; `roundtrip --level rta3` on the Altium project; `equivalent` between the KiCad board and KiCad's import of the Altium documents at level 5.
5. **Notice.** The build's `experimental` notice names the kinds, and is absent when none of the written kinds is experimental.
6. **Cut order.** Nothing is cut: this change is small and closes the milestone. If the kit run is not available, tasks 2 to 4 wait and say so; the milestone is then not done.

## Files and public API

- `src/fenolite/backends/base.py`: `graduated(row, register, runs) -> tuple[bool, tuple[str, ...]]` (the verdict and what is missing).
- `tools/acceptance_v04.py`: the acceptance script (runs `fenolite` commands; writes a JSON summary).
- `docs/evidence/altium-acceptance.md`.
- Tests: `tests/unit/backends/test_graduation.py`, `tests/unit/cli/test_capabilities_altium.py`, `tests/kicad/acceptance/test_v04_acceptance.py`.

## Sources registered by this change

- None.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-ACC-V04 | The acceptance project built for both targets is equal between them at level 5, passes `check` on both, holds RT-A3 on its Altium documents, and its Altium documents imported by KiCad equal the KiCad board at level 5 | `tests/kicad/acceptance/test_v04_acceptance.py` | probe `acceptance-v04` `equal` on KiCad 10.0.6; the exclusions are those of the triangle profile |
| H-A-ACC-KIT | A kit run on the acceptance tree passes every step of the groups K1 to K8 | the recorded kit run | the run record holds no failed step in those groups |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry | 0.25 |
| graduation rule and tests | 0.75 |
| acceptance project and script | 0.75 |
| kit run recorded, rows relabelled | 0.5 |
| capabilities, notice, matrix | 0.25 |
| documentation | 0.5 |
| closing | 0.25 |

Total: 3.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `backend-protocol`, "Evidence matrix rows"; `cli-contract`, "Experimental features in capabilities"; `altium-build`, "Altium build evidence": superseded in the sentences that fix every Altium write as experimental and the envelope as `INFERRED`. Task 0.1 writes them as MODIFIED from the living text.
- Archive order: last of v0.4.

## Risks / Trade-offs

- [The kit run fails on a group] → the rows of that group stay as they are, the kinds they belong to stay experimental, and the acceptance page lists them; a follow-up change repairs the writer.
- [A later writer change makes the run stale] → the guard of c0091 fails the register test until a new run or a demotion; graduation is then undone by the same rule, automatically.
- [Only one Altium version] → the label and the page name it; the README says "verified with AD <version>".

## Migration Plan

- `capabilities` gains write kinds for `altium`; scripts that read `experimental` to decide must read it per kind.
- Rollback: the rule cannot be rolled back independently; a failing kind is experimental again by the rule.

## Open Questions

- **Is one kit run on one Altium version enough to graduate a kind?** Decided by the maintainer on 2026-10-06: yes, with the version named everywhere the level is shown.
- **Should the release notes of v0.4 call the Altium target stable?** Default: no: "write kinds verified with AD <version>; see the written scope".
