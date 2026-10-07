## Why

`fenolite build --target altium` of 0.1.0 and 0.2.0 ignores a part's `pad_map` on the board: a pad takes the net of the pin of its own number, whatever the map says. A part whose map renames pads is then wired the other way round in the PCB document, and nothing reports it. `design-dsl`, "Per-component pin-to-pad mapping", already requires the opposite; the KiCad target obeys it. Change c0135 repairs the Altium target. A board wired wrongly without a finding is a defect that cannot wait for `0.3.0`, so the maintainer approved a patch release on 2026-10-07: `0.2.1`, with that one fix.

Nothing in the repository says what a patch release is. `release-gate` pins the version to `0.2.0` and the first three headings of the changelog to `Unreleased`, `0.2.0`, `0.1.0` ("Version 0.2.0"), and the guard of the release record refuses anything else. `dev` cannot be released as it is: it holds the write side of the second backend, which is not finished.

This change adds no behaviour: it adds the rule for patch releases of the series, the record of this one, and the version.

## What Changes

- `release-gate`: a patch release `0.2.N` is cut from the tag of the release before it, holds fixes only, has its own changelog section and its own subsection in the record of the series, and returns to `dev` by a merge of `main`. "Version 0.2.0" allows the sections and the version of such a release.
- `docs/release/v0.2.md`: a section `## Patch releases` with the subsection `0.2.1`: the defect, one row per statement of the fix with its test and CI job, the limit, the checks, the steps, and a verdict left `pending`.
- `tests/unit/test_release_record_v02.py`: the guard reads the patch releases the record names and holds their rows, the order of the changelog sections and the rows of the history page to the rule; it accepts the version `0.2.1`.
- `docs/evidence/residue-history.md`: the row `v0.2.1` of the history scan, public gate only.
- `docs/roadmap.md` and `openspec/README.md`: the status lines and the id table name the patch release and its two changes.
- Version `0.2.1` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `[0.2.1]`.

Budget: 0.5 design-day.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `release-gate`: MODIFIED "Version 0.2.0" (the three version strings are pinned at the commit of c0093 and agree afterwards; patch sections may stand above `[0.2.0]`); ADDED "Patch releases of 0.2".

"Release record of v0.2" stays as it is: the three acceptance tables describe `0.2.0`, and a patch release adds rows under its own subsection only.

## Prerequisites

- c0135 is the one commit on the branch `release-0.2.1` before this change, and the branch starts at the tag `v0.2.0`.

## Non-goals

- Any behaviour. The fix is c0135; this change does not edit a file under `src/fenolite` other than the version string.
- A new claim about the acceptance of v0.2a or v0.2b, or a changed row of the three tables of `0.2.0`.
- Anything of `dev`: the write side of the second backend, the milestone names, the follow-up changes. They reach a release with `0.3.0`.
- The verdict, the tag, the pull request to `main`, the publication and the merge of `main` into `dev`: they are the maintainer's steps, listed in the record.
- A rule for patch releases of another series. The next release change writes its own, with this one as its model.

## Evidence level required

- The rows of the fix are proved by unit tests that need no tool (job `unit`): mechanical.
- That Altium applies the map records which the fix writes is a hypothesis of c0135 and keeps the level c0135 gives it. The maintainer's check of the built project in Altium is an author report: it is recorded with its date and raises no evidence label.
- Residue: public gate only; the private gate is not run for v0.2.1, and the record says so.

## Impact

- Changed: `docs/release/v0.2.md`, `tests/unit/test_release_record_v02.py`, `docs/evidence/residue-history.md`, `docs/roadmap.md`, `openspec/README.md`, `CHANGELOG.md`, the three version strings.
- Depends on c0135.
- No runtime dependency. No hypothesis and no source is registered.
