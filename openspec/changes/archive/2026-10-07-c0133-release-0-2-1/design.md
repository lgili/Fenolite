## Context

- **Scope.** The first patch release of the series `0.2`: the rule, the record and the version. The model is c0093, the release change of `0.2.0`.
- **Decided by the maintainer on 2026-10-07.** A patch release `0.2.1` with the fix of the pin-to-pad map in the Altium build, the map on the board and in the schematic (c0135), and its publication after he has opened a built project in Altium and run its update of the board from the schematic.
- **What exists.** The tag `v0.2.0` on `main`. `dev` is 14 commits and more ahead with the write side of the second backend, which is not released. The living requirement "Version 0.2.0" pins the three version strings to `0.2.0` and the changelog headings to `Unreleased`, `0.2.0`, `0.1.0`; `tests/unit/test_release_record_v02.py` checks both whenever a `[0.2.0]` section exists.
- **Constraints.** Clean-room. No behaviour in this change. The private residue gate is not run and nothing private is read or named.

## Goals / Non-Goals

**Goals:**
- A written rule for a patch release, small enough to be followed again.
- A record of `0.2.1` that says what was wrong, what is proved, by which test, and what is not proved.
- A guard that keeps holding at any later version of the package.

**Non-Goals:**
- The fix itself (c0135).
- A second record page, a second guard file, or a rule for another series.

## Decisions

**Decision 1: a patch release is cut from the tag, never from `dev`.** `dev` holds work of a later milestone that is not finished and has no acceptance. The branch `release-0.2.1` starts at `v0.2.0`, holds the fix and this change, and reaches `main` by a pull request. Afterwards `main` is merged into `dev`, so that `dev` holds the fix, the version `0.2.1` and the section `[0.2.1]` below its own `[Unreleased]`. Alternative: cherry-pick the fix from `dev`. Rejected for this release because the code on `dev` has moved (the pin map is being widened to several pads per pin there), so the fix is written against the tag and `dev` takes it back by the merge.

**Decision 2: the fix is a change of its own; the release change adds no behaviour.** c0135 holds the code, the tests, the deltas of the two Altium capabilities and the changelog entry under Unreleased. c0133 holds the rule, the record, the guard and the version, as c0093 did. Two commits, each one change.

**Decision 3: one record per series.** The patch releases are recorded in `docs/release/v0.2.md`, under `## Patch releases`, after the verdict of `0.2.0`. A patch release adds no acceptance item, so it has no page of its own: a reader of the series finds on one page what `0.2.0` proved and what each patch repaired. The three acceptance tables are not edited. So that a fix is not smuggled into them, the guard refuses a patch row whose item is also an item of those tables.

**Decision 4: the rows of a patch release are rows of the same kind.** The subsection holds a table with the header of the acceptance tables. The item of a row is the id of the change that made the fix, so its limit and its open entry are found under `## Recorded limits` and `## Open rows` by that id, with the helper that already finds the entries of the later milestone's rows. The proof and the job are checked by the same code as every other row.

**Decision 5: the guard reads the list of patch releases from the record, not from the version.** `patches(record)` gives the subsections; the changelog order, the history rows and the row checks follow that list. The version adds one rule only: at `0.2.N` every patch release up to N has its subsection. So the checks still hold when the package is at `0.3.0`, where the guard of that release will own the top of the changelog: this guard then compares the headings from the first section of the series on, and requires `Unreleased` alone above them only while the version is of the series.

**Decision 6: "Version 0.2.0" keeps its name.** It describes the cut of `0.2.0`. Its first bullet is narrowed to that commit and gains the sentence that the three strings agree at every later commit; its changelog bullet allows the patch sections. Renaming it to a name without a version would touch every reference to it for no gain.

**Decision 7: what a patch release may hold.** Fixes only: no command, flag, model field or schema. An issue code is allowed in one case, where the fix refuses an input for which the release before wrote a wrong file: without the refusal the fix would trade a wrong net for a missing one, silently. c0135 has that case (`altium.pin-pad-map-invalid`), and the record names the code.

**Decision 8: the verdict of a patch release is a line, and it needs a linked run.** `**Verdict of 0.2.1.**` is `pending` when an agent commits it. The pull request's CI run exists only after the branch is pushed, so the run is linked in the commit that writes the verdict, and the guard refuses a verdict without one. As for `0.2.0`, a verdict is refused while a row of the subsection is `pending`.

**Decision 9: the maintainer's check in Altium is an author report.** It is recorded in the subsection with its date, the version of the tool and what was seen. It raises no evidence label and is no release claim, as the record of `0.2.0` says of such reports. It gates the publication because the maintainer asked for that order, not because the record needs it.

**Decision 10: residue.** `uv run python tools/residue/scan.py --history` with the public gate, before the version commit; one row `v0.2.1` in `docs/evidence/residue-history.md`; the first paragraph of that page says that the private gate was not run for v0.2.1 either.

## Risks / Trade-offs

- **The merge of `main` into `dev` conflicts** in the files c0135 touches, because `dev` has changed them. The session that owns the pin map on `dev` prepares the resolution; the record lists the merge as a step, and the patch release is not finished before it.
- **A reader takes the patch rows for acceptance rows.** The section says in its first sentence that the tables above stay those of `0.2.0`.
- **The guard grows.** About two hundred lines for the patch rules and their scenarios. They are written once for the series: a second patch release adds a subsection and no code.

## Migration Plan

None for users: `pip install -U fenolite`. A project built for Altium from a script that uses `pad_map` is built again.

## Open Questions

None.
