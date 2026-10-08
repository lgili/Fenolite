## Context

- The release process is that of `0.2.0` (c0093) and `0.2.1` (c0133): a record under `docs/release/`, a guard under `tests/unit/`, the version in three strings, the changelog cut, the history row of the residue scan, and the maintainer's verdict before the tag.
- The acceptance block of v0.3 is a proposal approved as the working target on 2026-10-06 and not yet reviewed (c0092, task 5.2). Its item 5 asks for a recorded kit run and for the PCB document and schematic document writes out of `experimental`.
- The rule of c0092 (design, decision 1) has four conditions; the code of the rule is not written, because the entry check of c0092 finds c0083–c0091 open. The rule can still be applied by hand from the register and the write cells of `claims.py`, and the release needs that verdict.
- The maintainer decided on 2026-10-08 that the kit did not change since the run of 2026-10-07 and is accepted as validated by that run for this release, and that the kit run has to be revalidated with a recorded run after `0.3.0`, which also revalidates c0148.

## Decisions

1. **The id.** c0150: c0149 is the patch release `0.2.2` on its own branch, and the ids up to c0149 are taken. The two follow-ups the record names are proposed as c0151 (the bus of a `Repeat` entry) and c0152 (the clearance findings that Altium passes); neither folder is written.
2. **The graduation table is checked against the matrix.** The guard reads every Altium row of `claims.MATRIX` with a write cell, asks for one row of the table per kind, and refuses a verdict that disagrees with the row's `experimental` (a kind marked `graduated` while the matrix lists its write as experimental, or the reverse) and a count of ids that is not the write cell's. The counts of levels come from the register on the day of the record; they are data of the record, not re-computed by the guard, because a later relabelling may change them without changing the verdict.
3. **The exception is written as one.** The section says that the maintainer's decision waives condition (d) for 0.3.0 only, writes no run record and no `ALTIUM-VERIFIED(kit)`, and that the revalidation with `fenolite kit verify` and `fenolite kit record` is owed, also for c0148. The guard asks for those words.
4. **What is not in the release is a section of its own** ("Not in 0.3.0"): c0137 deferred, v0.4 parked, the two open defects with their proposed follow-ups, the owed Altium parts (G, X8, V, R2 to R4, the kit run). The guard asks for each. The residue waiver of `tests/data/model/v0.2.0/blink_2layer.board.json` (c0126), which waited for the maintainer's approval when this change started, was approved by him on 2026-10-08 and is recorded under the limit of the residue scan.
5. **Rows that are not met keep a proof that exists.** Item 5 names the test that shows the present state (the Altium writers listed as experimental); the row of the repeated sheet names the import's test on authored sheets. Each has its entry under "Open rows".
6. **The changelog heading carries the date the maintainer gave**, 2026-10-08, not `pending the tag`. The sections after `[0.3.0]` are those of the 0.2 series, the newest first: `[0.2.2]` arrives by the merge of `main` into `dev`, and the guard accepts it there.
7. **The guards of v0.1 and v0.2 stay as they are.** Both already accept a version of another series (`test_release_record_v02.py` tests the version `0.3.0`).

## Risks / Trade-offs

- [The merge of `main` with 0.2.2 conflicts in `CHANGELOG.md` and `docs/evidence/residue-history.md`] → both are insertions at the same place; the resolution keeps `[0.2.2]` below `[0.3.0]` and both history rows. The guards of v0.2 and v0.3 check the result.
- [The CI run of the release candidate does not exist yet] → the record links the run of `dev` at `4bf0c6fb` and the run of the branch of c0148, and names the run of the pull request from `dev` to `main` as the release candidate run, as the record of v0.2 did.
