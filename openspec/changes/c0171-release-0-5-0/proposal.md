## Why

v0.5a (conversion between KiCad and the second backend with a report of what is kept or lost, the controlled KiCad downgrade and the public `equivalent`: c0158 to c0162) is on `dev`, with the changes written there after `0.4.0` (c0155, c0156, c0157, c0163, c0164 twice, c0165, c0166, and the graduation rule of c0092) and the two slot changes that the maintainer placed in `0.5.0` on 2026-10-15 (c0167, c0169). On 2026-10-15 the maintainer approved preparing the release `0.5.0`; its publication waits for his explicit yes. By his decision of the same day, c0168 and c0170 come after `0.5.0`.

No record says, change by change, what `0.5.0` ships, which tasks stay open, why, and what still waits for the CI of the release branch. Several tasks wait only for the full `tests/kicad/test_probe_results.py` gate of the `kicad-9` and `kicad-10` CI jobs, and the `kicad-10` job of the last runs of `dev` stopped before its tests: `tools/corpus_fetch.py` lost rows to HTTP 429 (Too Many Requests) when the cache key of the corpus changed and about 400 rows were fetched from one host (runs 38758153887 and 38767993162).

This change adds no feature: it adds the record of what ships and what is deferred, a guard that holds the record to the task lists, the version, and the retry of the corpus fetch that the CI evidence needs.

## What Changes

- `tools/corpus_fetch.py`: a download answered with 429 or a 5xx of 500, 502, 503 or 504 is asked again after a pause (the server's `Retry-After`, else a doubling pause from 5 s, at most 120 s, six attempts in all). `tests/corpus/test_manifest.py` tests it with a stand-in download.
- `docs/release/v0.5.md` (new): one row per change of the release with what ships, the test that proves it, its CI job, its open tasks and a result (`ships`, `ships with deferred tasks` or `pending`); an entry per deferred and pending row; the open changes of earlier releases (c0081, c0105, c0146); the Altium write, which stays experimental by c0092's verdict; what is not in `0.5.0` (c0168, c0170); the runs, with placeholders `TODO(coordinator)` for the runs of the release branch; the limits, the build, the archive order, the deferred list, the maintainer's steps and a verdict left `pending`.
- `tests/unit/test_release_record_v05.py` (new): the guard of the record, modelled on that of v0.4.
- `README.md`: the status paragraph names version 0.5 and links to the record; "What version 0.5 does" adds conversion, the downgrade, `equivalent`, slots and the edge check. `tests/unit/test_agent_skill.py` checks it.
- `docs/roadmap.md`: the status lines, the row of v0.5a and its section name the release change and say released as `0.5.0`, pending publication.
- `docs/evidence/residue-history.md`: the row `v0.5.0` of the history scan, public gate only.
- `openspec/README.md`: the row of c0171.
- Version `0.5.0` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `## [0.5.0] - 2026-10-15`, one `Added`, `Changed` and `Fixed` each, with an empty `## [Unreleased]` above; the subsections "Altium to KiCad" and "Native Altium templates" and the untitled entries of Unreleased are folded into them without losing text.
- The tasks of other changes whose proofs a green CI run on the current tree covers are ticked, citing the run; the changes whose tasks are then all ticked and whose archive order allows it are archived.

Size: 1 design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Release record of v0.5", "Open tasks in the record of v0.5", "Sections of the record of v0.5", "Version 0.5.0" and "History row and roadmap of 0.5.0"; MODIFIED "README describes the released version" (the version it names becomes 0.5).
- `corpus-policy`: MODIFIED "Fetch with verification" (a rate limit or a server error is asked again).

The requirements of v0.1 to v0.4 stay: their records are released and still guarded.

## Prerequisites

- `0.4.0` is released (c0154, archived) and merged into `dev`.
- The base is `origin/dev` at `5b86b6e`.

## Non-goals

- Any new command, flag, model field or format fact, and any task of another change that needs the maintainer, Altium Designer, a KiCad GUI save or a real AI agent.
- A task of another change ticked without its proof.
- c0168 and c0170 (after `0.5.0`, the maintainer's decision of 2026-10-15).
- The CI runs of the release branch, the full `make check`, the verdict, the merge, the tag and the publication: the coordinator's and the maintainer's.

## Evidence level required

- The rows carry the labels their changes gave them; nothing is raised by this change.
- Residue: public gate only; the private gate is not run for v0.5.0, and the record says so.

## Impact

- New: `docs/release/v0.5.md`, `tests/unit/test_release_record_v05.py`. Changed: `tools/corpus_fetch.py`, `tests/corpus/test_manifest.py`, `README.md`, `docs/roadmap.md`, `docs/evidence/residue-history.md`, `openspec/README.md`, `tests/unit/test_agent_skill.py`, `CHANGELOG.md`, the version strings, and the task lists of the changes whose proofs passed in CI.
- No runtime dependency. No hypothesis and no source is registered.
