## Why

On 2026-10-29 the maintainer decided to hold the v1.0 freeze (c0216 to c0220 stay open and are not
implemented) and to release `0.6.0` now with what is implemented on `dev` since `0.5.0`, then a `0.7.0` with
improvements whose scope he decides later. Since the tag `v0.5.0`, `dev` gained the MCP server and
`fenolite edit` (c0195, c0196), the board engineering tools of c0175 and their packages (c0197 to c0214,
c0223 to c0229), the computed Altium pours (c0215, experimental), the release automation (c0221), the
reliability, viewer-review, catalog and presentation work (c0232 to c0240) and kit Part J of the Altium edit
sessions (c0241). `docs/roadmap.md` still names v0.6 as "the maintainer's tests deferred from `0.5.0`" and
v1.0 as the next freeze, and no record says what `0.6.0` ships.

This change adds no feature: it adds the record of what ships and what is deferred, its guard, the version,
the changelog cut, the history row, the README status and the roadmap, as c0171 did for `0.5.0`, and stops
at the maintainer's steps. Since c0221 the publication is a pushed tag; since c0220 tasks 1.1 and 1.2 the
release workflow scans the history before it builds.

## What Changes

- `docs/release/v0.6.md` (new): one row per change of the release (its folder, what ships, the test that
  proves it, its CI job, its open tasks and a result: `ships`, `ships with deferred tasks` or `pending`); an
  entry per deferred row; the open changes of earlier releases (c0081, c0105, and the open changes of
  `0.5.0`: c0092, c0160, c0166, c0168, c0170, c0172, c0173, c0177 to c0181, c0186); the Altium write and the
  experimental features; what is not in `0.6.0` (c0216 to c0220, c0222); the runs, with a
  `TODO(coordinator)` placeholder for the run of the release branch; the limits, the build, the archive
  order, "Deferred after v0.6" with every test the maintainer owes, the maintainer's steps and a verdict
  left `pending`.
- `tests/unit/test_release_record_v06.py` (new): the guard of the record, modelled on that of v0.5.
- Version `0.6.0` in the package, its alias and the alias pin; `CHANGELOG.md` cut into
  `## [0.6.0] - 2026-10-29` with one `Added`, `Changed` and `Fixed` each under an empty `## [Unreleased]`; one
  entry that sums up the release opens `Added`; the three merged copies of the c0212 entry become one.
- `README.md`: the status paragraph names version 0.6 and links to `docs/release/v0.6.md`; the MCP server is
  part of the package. `tests/unit/test_agent_skill.py` and `tests/unit/test_public_presentation.py` follow.
- `docs/roadmap.md`: the current status, the milestone rows (v0.6 released as `0.6.0`, a v0.7 row whose
  scope the maintainer decides, v1.0 held by his decision of 2026-10-29 with its table kept), and Open
  decisions row 50.
- `docs/evidence/residue-history.md`: the row `v0.6.0` of the public history scan.
- `openspec/README.md`: the row of c0242; new changes start at c0250.

Size: 1 design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Release record of v0.6", "Open tasks in the record of v0.6", "Sections of the
  record of v0.6", "Scope of 0.6.0 of 2026-10-29", "Version 0.6.0" and "History row and roadmap of 0.6.0";
  MODIFIED "README describes the released version" (the version it names becomes 0.6).

The requirements of v0.1 to v0.5 stay: their records are released and still guarded.

## Prerequisites

- `0.5.0` is released (tag `v0.5.0`, c0171 archived) and is an ancestor of the base.
- The base is `dev-c0241-b` at `ab73da4` (`dev` at `1559f1b` with the closing tasks of c0241 and c0175, the
  proposal c0222 and c0220 tasks 0.1 to 1.2).

## Non-goals

- Any new command, flag, model field or format fact; any task of c0216 to c0220 beyond what is on the base.
- Any task of another change that needs the maintainer, Altium Designer, a KiCad GUI save or a real AI agent,
  and any task ticked without its proof.
- The CI run of the release branch, the full `make check`, the private-gate history run, the verdict, the
  merge, the tag and the publication: the coordinator's and the maintainer's.

## Evidence level required

- The rows carry the labels their changes gave them; nothing is raised by this change.
- Residue: the public gate over the history; the private gate is c0220 task 1.3, the maintainer's.

## Impact

- New: `docs/release/v0.6.md`, `tests/unit/test_release_record_v06.py`. Changed: `CHANGELOG.md`,
  `src/fenolite/__init__.py`, `packaging/phenolite/pyproject.toml`, `README.md`, `docs/roadmap.md`,
  `docs/evidence/residue-history.md`, `openspec/README.md`, `tests/unit/test_agent_skill.py`,
  `tests/unit/test_public_presentation.py`.
- No runtime dependency. No hypothesis and no source is registered.
