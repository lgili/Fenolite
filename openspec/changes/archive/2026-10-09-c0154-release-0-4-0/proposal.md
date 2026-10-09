## Why

The changes of v0.4 (the agent track c0077–c0081, board authoring c0096–c0099, the complex board c0100–c0120, and c0137, c0140, c0141, c0145, c0152 and c0153, which were written on `v04` after `0.3.0`) are on the branch `v04`, and the maintainer asked on 2026-10-08 for the release `0.4.0`. His decision of that day sets the rule of the release: everything that depends on his own tests (KiCad GUI saves made by him, a run of a real AI agent, checks in Altium Designer) is deferred to the next release, and everything else ships.

The roadmap gives v0.4 no acceptance block: v0.4 is three groups of proposals, not a milestone of the project plan. No record says, change by change, what ships, which tasks stay open, why, and what still waits for the CI of the release branch. The record has to say that without raising any evidence.

This change adds no feature: it adds the record of what ships and what is deferred, a guard that holds the record to the task lists, and the version.

## What Changes

- `docs/release/v0.4.md` (new): one row per change of v0.4 with what ships, the test that proves it, its CI job, its open tasks and a result (`ships`, `ships with deferred tasks` or `pending`); an entry per change with deferred tasks (which, and why) and per pending change (what closes it); the follow-ups found on 2026-10-08; the Altium write, which stays experimental; what is not in `0.4.0`; the runs, with placeholders `TODO(coordinator)` for the runs of the release branch and the first run of the `yardstick` job; the limits, the build, the order in which the changes can be archived, the maintainer's steps and a verdict left `pending`.
- `tests/unit/test_release_record_v04.py` (new): every change of v0.4 has one row; every proof and job exists; every open task of a change's `tasks.md` is named by its row; a row that ships has no open task; each deferred and pending row has its entry; the follow-ups are named; no verdict while a row is `pending` or a placeholder stands; the changelog order at `0.4.0` and the history row.
- `README.md`: the status paragraph names version 0.4 and links to the record; "What version 0.4 does" adds the v0.4 work. `tests/unit/test_agent_skill.py` checks it.
- `docs/roadmap.md`: the status lines, the row of v0.4 and its section name the release change and say released as `0.4.0`, pending publication.
- `docs/evidence/residue-history.md`: the row `v0.4.0` of the history scan, public gate only.
- `openspec/README.md`: the row of c0154.
- Version `0.4.0` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `## [0.4.0] - 2026-10-08`, one `Added`, `Changed` and `Fixed` each, with an empty `## [Unreleased]` above.

Size: 1 design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Release record of v0.4", "Sections of the record of v0.4", "Version 0.4.0" and "History row and roadmap of 0.4.0"; MODIFIED "README describes the released version" (the version it names becomes 0.4).

The requirements of v0.1 to v0.3 stay: their records are released and still guarded.

## Prerequisites

- `0.3.0` is released (c0150, archived) and `v04` is rebased onto it.
- The base is `origin/v04` at `367cdf8`.

## Non-goals

- Any new command, flag, model field or format fact, and any task of another change that needs `kicad-cli`, a router, the maintainer or Altium Designer.
- A task of another change ticked by this one without its proof.
- A test written to make a row say `ships`.
- The archive of the changes of v0.4: c0150 left the changes it released open, and several of v0.4 cannot be archived before changes of 0.3.0 that are still open (c0084, c0123, c0126); the record gives the order.
- The CI runs of the release branch, the first run of the `yardstick` job, the verdict, the merge, the tag and the publication: the coordinator's and the maintainer's.
- c0151 (the bus of a repeated sheet): on its own branch, waiting for the maintainer's Altium step R5.

## Evidence level required

- The rows carry the labels their changes gave them; nothing is raised by this change.
- Residue: public gate only; the private gate is not run for v0.4.0, and the record says so.

## Impact

- New: `docs/release/v0.4.md`, `tests/unit/test_release_record_v04.py`. Changed: `README.md`, `docs/roadmap.md`, `docs/evidence/residue-history.md`, `openspec/README.md`, `tests/unit/test_agent_skill.py`, `CHANGELOG.md`, the version strings.
- No runtime dependency. No hypothesis and no source is registered.
