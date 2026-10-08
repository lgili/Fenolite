## Context

- **Scope.** The second patch release of the series `0.2`: the record and the version. The model is c0133, the release change of `0.2.1`, whose rule is the living requirement "Patch releases of 0.2".
- **Decided by the maintainer on 2026-10-08.** A patch release `0.2.2` with the fix of the power flag of a design with catalog parts and a `Power` interface (c0143), released on the same day.
- **What exists.** The tag `v0.2.1` on `main`. The fix was written on the v0.4 line, carried onto `dev` as `5a54f502`, and written so that its code and its core test apply on `v0.2.1` (c0143, design Decision 4). `dev` holds the write side of the second backend and the several pads per pin of c0123, which are not released.
- **Constraints.** Clean-room. No behaviour in this change. The private residue gate is not run and nothing private is read or named. No `kicad-cli` where the branch is prepared.

## Goals / Non-Goals

**Goals:**
- A record of `0.2.2` that says what was wrong, what is proved, by which test, and what is not proved yet.
- The guard and its scenarios holding with two patch releases in the record.

**Non-Goals:**
- The fix itself (c0143).
- A new rule. "Patch releases of 0.2" stays as c0133 wrote it.

## Decisions

**Decision 1: the fix is a cherry-pick of the commit of `dev`, not a rewrite.** c0143 was written to apply on the tag, so the branch `release-0.2.2` starts at `v0.2.1` and its first commit is `5a54f502` picked onto it. Only `CHANGELOG.md` conflicts; the entry goes under `### Fixed` of `## [Unreleased]`, as the entry of c0135 did on `release-0.2.1`. The hand that c0143's Decision 4 asks for is made in the same commit and written under its task 3.3: the Altium test is not carried (`build_altium(authored_symbols=...)` is not in 0.2.x), and the MODIFIED deltas lose the clauses that come from c0123, so that the archive of c0143 on this line does not write unreleased requirements into the living specs. Alternative: a third commit for the hand. Rejected: the rule wants each fix to be a change of its own, and the commit of the fix should build and pass on its own.

**Decision 2: the row that needs `kicad-cli` is `pending`, not `met`.** The ERC test of c0143 passed on 10.0.6 on `dev`, not on this branch, and has never run on 9.0.9. The row names the jobs `kicad-9` and `kicad-10`, is `pending`, and has its entry under `## Open rows`; the guard refuses the verdict while it is `pending`. The steps of the subsection say to set it from the two jobs of the pull request. Alternative: `met` on the strength of `dev`. Rejected: the record of a release says what was run on what is released.

**Decision 3: the guard changes only in its tests.** The functions of `tests/unit/test_release_record_v02.py` already read the list of patch releases from the record (c0133, Decision 5). The checks of the rows run for every patch release the record names, and the changelog check gains the case of two patch sections in the wrong order and of a missing one. The scenarios of the requirement that named the record at `0.2.1` are rewritten to hold at `0.2.2` or at any patch release; the rule itself is not touched.

**Decision 4: residue.** `uv run python tools/residue/scan.py --history` with the public gate on the branch at the fix commit; one row `v0.2.2` in `docs/evidence/residue-history.md`; the first paragraph of that page says that the private gate was not run for v0.2.2 either.

**Decision 5: no placeholder for the verdict beyond the line the rule asks for.** `**Verdict of 0.2.2.** pending` is required by the guard; the CI run, the date of the tag and the archive of c0143 and c0149 come with the verdict, in a commit of their own after the pull request's checks and the maintainer's word, as for `0.2.1`.

## Risks / Trade-offs

- **The merge of `main` into `dev` conflicts** in `CHANGELOG.md`, where `dev` holds the entry of c0143 under its own `[Unreleased]`, and in the folder of c0143, whose deltas on `dev` keep the clauses of c0123. The merge keeps `dev`'s deltas (c0123 is archived first there) and takes the section `[0.2.2]` with the entry moved out of `[Unreleased]`.
- **The ERC fails on 9.0.9.** The row is then `not met`, the open entry says why, and the maintainer decides whether to release with it or without the fix.

## Migration Plan

None for users: `pip install -U fenolite`. A design that was refused builds; no other design changes.

## Open Questions

None.
