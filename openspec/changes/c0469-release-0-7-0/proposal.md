## Why

On 2026-11-06 the maintainer approved releasing `0.7.0` once the CI of the integration batch lote-29
passes. Since the tag `v0.6.0` (2026-10-29) `dev` gained about two hundred changes: the circuits-as-code,
component-library, block-library and board-library batches (c0243 to c0282), the viewer (c0300 to c0305),
the import and drawn-schematic fidelity work (c0311 to c0364), the router track (c0365 to c0370), the
conversion scope, Altium import and CI-profile work (c0371 to c0389), and the Altium round trip through
KiCad (c0401 to c0467). Changes that were open at `0.6.0` closed since: the v1.0 machinery of c0216 to c0220
(the contract stays `v0` until `1.0.0`), the Altium kit runs of c0092, c0160, c0166, c0168, c0172, c0173,
c0215 and c0241, and the maintainer's reviews of c0081, c0105, c0177 to c0181 and c0186. `docs/roadmap.md`
names v0.7 as "improvements after `0.6.0`, scope to be decided", and no record says what `0.7.0` ships.

This change adds no feature: it adds the record of what ships and what is deferred, its guard, the history
row, the roadmap and the README row of the change, as c0242 did for `0.6.0`; the changelog cut, the version
and the README status are its last task, done once every change of lote-29 is in.

## What Changes

- `docs/release/v0.7.md` (new): one row per change of the release (its folder, what ships, the test that
  proves it, its CI job, its open tasks and a result: `ships`, `ships with deferred tasks` or `pending`); an
  entry per deferred and per pending row; the changes left out because they shipped no code, each with its
  reason; the changes of earlier releases closed since `0.6.0`; the Altium write and the experimental
  features; what is not in `0.7.0` (c0468, the library generator families, which goes to the next lote); the
  runs, with a `TODO(coordinator)` placeholder for the run of the release branch; the limits, the build, the
  archive order, "Deferred after v0.7", the maintainer's steps and a verdict left `pending`.
- `tests/unit/test_release_record_v07.py` (new): the guard of the record, modelled on that of v0.6.
- `docs/roadmap.md`: the milestone row of v0.7 names this change and the record; `openspec/README.md`: the
  row of c0469, and new changes start at c0470.
- `docs/evidence/residue-history.md`: the row `v0.7.0` of the history scan, run with the private lists.
- Last, once every change of lote-29 is in (the coordinator's commit): `CHANGELOG.md` cut into
  `## [0.7.0] - <date>` under an empty `## [Unreleased]`, version `0.7.0` in the package, its alias and the
  alias pin, and the README status paragraph naming version 0.7.

Size: 1 design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Release record of v0.7", "Open tasks in the record of v0.7", "Sections of the
  record of v0.7", "Scope of 0.7.0 of 2026-11-06", "Version 0.7.0" and "History row and roadmap of 0.7.0";
  MODIFIED "README describes the released version" (the version it names becomes 0.7).

The requirements of v0.1 to v0.6 stay: their records are released and still guarded.

## Prerequisites

- `0.6.0` is released (tag `v0.6.0`, c0242 archived) and is an ancestor of the base.
- The base is `cac/lote-29` at `89c5334d9` (2026-11-06).

## Non-goals

- Any new command, flag, model field or format fact.
- Any task of another change that needs the maintainer, Altium Designer, a KiCad GUI save or a real AI agent,
  and any task ticked without its proof.
- c0468 (library generator families): not in `0.7.0`.
- The CI run of the release branch, the verdict, the merge, the tag and the publication: the coordinator's
  and the maintainer's.

## Evidence level required

- The rows carry the labels their changes gave them; nothing is raised by this change.
- Residue: the history scan with the public patterns and the private lists of the maintainer's checkout.

## Impact

- New: `docs/release/v0.7.md`, `tests/unit/test_release_record_v07.py`. Changed: `docs/roadmap.md`,
  `docs/evidence/residue-history.md`, `openspec/README.md`, `CHANGELOG.md`; at the last task
  `src/fenolite/__init__.py`, `packaging/phenolite/pyproject.toml` and `README.md`.
- No runtime dependency. No hypothesis and no source is registered.
