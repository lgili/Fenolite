## Why

The write part of v0.3 (c0083–c0092 and the follow-ups c0121–c0148) is on `dev`, and the maintainer asked on 2026-10-08 for the release `0.3.0` the same day. No change proves the acceptance block of v0.3 (`docs/roadmap.md`, "v0.3 acceptance") item by item, and nothing says, per Altium write kind, what the rule of c0092 gives. The maintainer's Altium Designer 26 sessions of 2026-10-07 and 2026-10-08 are author reports, and the kit run that c0092 needs was not recorded: the maintainer decided that the kit is accepted as validated by the run of 2026-10-07 for this release, with a revalidation owed afterwards. The record has to say all of that without raising any evidence.

This change adds no feature: it adds the record of what was and was not proved, a guard that holds the record to what exists, and the version.

## What Changes

- `docs/release/v0.3.md` (new): one row at least per item of the v0.3 acceptance, with the test that proves it, its CI job and its result; the verdict of the rule of c0092 per Altium write kind, with the maintainer's exception for the kit and the revalidation it owes; the open rows (the kit run, the bus of a repeated sheet); the changes outside the acceptance that ship in the package; what is not in `0.3.0`; the limits; the runs and versions; the manual checks; the build; the maintainer's steps; a verdict left `pending`.
- `tests/unit/test_release_record_v03.py` (new): the rules of the guard of v0.2 for the rows, plus the graduation table held to the Altium rows of the evidence matrix, the words of the exception, the list of what is not in the release, the changelog sections at `0.3.0` and the history row.
- `README.md`: the status paragraph names version 0.3 and links to the record; "What version 0.3 does" adds the write side. `tests/unit/test_agent_skill.py` checks it.
- `docs/roadmap.md`: the status lines and the row of v0.3 name the release change.
- `docs/evidence/residue-history.md`: the row `v0.3.0` of the history scan, public gate only.
- `openspec/README.md`: the row of c0150.
- Version `0.3.0` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `## [0.3.0] - 2026-10-08` (the date the maintainer gave), grouped and cleaned as `[0.2.0]` was, with an empty `## [Unreleased]` above.

Size: 1 design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Release record of v0.3" and "Version 0.3.0"; MODIFIED "README describes the released version" (the version it names becomes 0.3).

The requirements of v0.1 and v0.2 stay: their records are released and still guarded.

## Prerequisites

- c0148 is on the base of this branch (`c3e15ac3`, `dev` at `4bf0c6fb` plus c0148); it reaches `dev` when its CI passes.
- The patch release `0.2.2` (c0149, the backport of c0143) is prepared on its own branch and reaches `main` first; the coordinator merges `main` into `dev` before the pull request of `0.3.0`, and its changelog section `[0.2.2]` then stands below `[0.3.0]`.

## Non-goals

- Any new command, flag, model field or format fact, and the code of c0092 (its entry check finds c0083–c0091 open).
- A graduation by decision: the maintainer's decision waives the kit condition of c0092 for 0.3.0 and nothing else; every write kind that fails another condition stays `experimental`.
- A kit record, a run id or a digest for a run that was not recorded.
- A test written to make a row say `met`.
- Fixing the defects the record names (the bus of a repeated sheet, the rounding of the copper check against Altium's): their follow-ups are proposed as c0151 and c0152, not written.
- The verdict, the archive of the open changes, the pull request from `dev` to `main`, the tag and the publication: the maintainer's.

## Evidence level required

- The rows carry the labels their changes gave them; the Altium checks are author reports and raise none.
- Residue: public gate only; the private gate is not run for v0.3.0, and the record says so.

## Impact

- New: `docs/release/v0.3.md`, `tests/unit/test_release_record_v03.py`. Changed: `README.md`, `docs/roadmap.md`, `docs/evidence/residue-history.md`, `openspec/README.md`, `tests/unit/test_agent_skill.py`, `CHANGELOG.md`, the version strings.
- No runtime dependency. No hypothesis and no source is registered by this change (the session of 2026-10-08 registered S-0615 and S-0616 in the commit before it).
