## Why

`fenolite build` of 0.2.0 and 0.2.1 refuses a design that names parts of the built-in catalog (library `Fenolite`) and declares a `Power(...)` interface whose nets need a power flag: the flag lies in a library `fenolite`, and two symbol libraries whose names differ only in letter case are refused with `build.vendor-unsafe-name`. Without the `Power` interface such a design builds, and KiCad's ERC then reports every power input fed from a connector as not driven. Change c0143 repairs it on `dev`. The maintainer decided on 2026-10-08 that the fix is carried back into a patch release of the series: `0.2.2`, with that one fix.

`release-gate`, "Patch releases of 0.2" (change c0133), already says what a patch release is. This change follows it a second time: the record of `0.2.2`, the version, and the scenarios of the guard that named `0.2.1` alone.

This change adds no behaviour.

## What Changes

- `docs/release/v0.2.md`: the subsection `### 0.2.2` under `## Patch releases`: the defect, one row per statement of c0143 with its test and CI job, the checks, the steps, and a verdict left `pending`. The row of KiCad's ERC is `pending` until the `kicad-9` and `kicad-10` jobs of the pull request have run it, with its entry under `## Open rows`.
- `tests/unit/test_release_record_v02.py`: the checks of the rows run for each patch release the record names, and the changelog check has the case of two patch releases. The guard needs no new rule.
- `release-gate`: the scenarios of "Patch releases of 0.2" that named the committed record at `0.2.1` name it at `0.2.2`, or hold for any patch release.
- `docs/evidence/residue-history.md`: the row `v0.2.2` of the history scan, public gate only.
- `docs/roadmap.md` and `openspec/README.md`: the status lines and the id table name the patch release and its two changes.
- Version `0.2.2` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `[0.2.2]`.

Budget: 0.25 design-day.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `release-gate`: MODIFIED "Patch releases of 0.2" (the scenarios "Patch release recorded", "Version without a subsection", "Patch row with a missing proof", "Patch row taken from the acceptance" and "Patch sections out of order"; the rule is unchanged).

## Prerequisites

- c0143 is the one commit on the branch `release-0.2.2` before this change, and the branch starts at the tag `v0.2.1`.

## Non-goals

- Any behaviour. The fix is c0143; this change does not edit a file under `src/fenolite` other than the version string.
- A change of the rule for patch releases, of the three acceptance tables of `0.2.0` or of the subsection of `0.2.1`.
- Anything else of `dev`. It reaches a release with `0.3.0`.
- The verdict, the tag, the pull request to `main`, the publication and the merge of `main` into `dev`: they are the maintainer's steps, listed in the record.

## Evidence level required

- The rows of the fix that need no tool are proved by unit tests (job `unit`): mechanical.
- That KiCad reads the flag in the catalog's library and takes the supply as driven is `ORACLE-VERIFIED(kicad-cli)` on 10.0.6 on the commit of c0143 on `dev`; on this branch the `kicad-9` and `kicad-10` jobs of the pull request run it, and the row stays `pending` until they have.
- Residue: public gate only; the private gate is not run for v0.2.2, and the record says so.

## Impact

- Changed: `docs/release/v0.2.md`, `tests/unit/test_release_record_v02.py`, `docs/evidence/residue-history.md`, `docs/roadmap.md`, `openspec/README.md`, `CHANGELOG.md`, the three version strings.
- Depends on c0133 (the rule) and c0143 (the fix).
- No runtime dependency. No hypothesis and no source is registered.
