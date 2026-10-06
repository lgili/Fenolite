## Why

v0.2a (c0060–c0068) and v0.2b (c0069–c0074) are implemented on `dev`, and no change proves their acceptance items together (`docs/roadmap.md`, "v0.2a acceptance" and "v0.2b acceptance"). The maintainer decided on 2026-10-06 to cut one release, `0.2.0`, from `dev` for both. `dev` also holds the read work of v0.3 (c0039–c0047) and changes pulled forward from v0.4, which ship in the same package: the record has to say so, and say what is and is not proved of them.

This change adds no feature: it adds the record of what was and was not proved, a guard that holds the record to what exists, and the version.

## What Changes

- `docs/release/v0.2.md` (new): one row per acceptance item of v0.2a and of v0.2b, with the test that proves it, its CI job and its result; the limits; the open rows; a section for the later milestone that ships in the package; the runs and versions; the maintainer's steps; a verdict left `pending`.
- `tests/unit/test_release_record_v02.py` (new): every proof names a test that exists, every job is a job of `ci.yml`, a result is one of four words, a limit has its entry, an open row has its reason, and no verdict is written over a `pending` row.
- `docs/roadmap.md`: the milestone table and the sentences under each phase say what is true on `dev` (v0.2a archived, v0.2b archived except c0070, v0.3 archived). The v0.4 rows are not touched.
- `README.md`: the status paragraph names version 0.2 and links to the record; a section says what the version does. `tests/unit/test_agent_skill.py` checks it.
- `tests/libs/test_build_official.py`: one test more, KiCad's ERC on the official-library blink, which had no automated proof.
- `docs/evidence/residue-history.md`: the row `v0.2.0` of the history scan, public gate only.
- Version `0.2.0` in the package, its alias and the alias pin; `CHANGELOG.md` cut into `[0.2.0]`, grouped and cleaned as `[0.1.0]` was. Last, in a commit of its own.

Budget: 2 design-days.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `release-gate`: RENAMED and MODIFIED "README describes v0.1" (now "README describes the released version") and "Version 0.1.0" (now "Version 0.2.0"); ADDED "Release record of v0.2".

The requirements "Release record" and "Release build and local checks" stay as they are: they describe the record of v0.1, which is released and still guarded by `tests/unit/test_release_record.py`.

## Prerequisites

- Every change of v0.2a is archived (c0060–c0068), and c0069 and c0071–c0074 of v0.2b.
- c0070 is implemented and not archived. This change does not wait for it: its row is `pending`, and the maintainer closes it with one edit.

## Non-goals

- Any new command, flag, model field or format fact.
- A test written to make a row say `met`: a row with no proof says `not met` or `pending`, with the reason. The one test added asserts what was measured on the example, and no row cites it.
- Fixing a defect found while reading the proofs: the owning change fixes it, and the record names it.
- The acceptance of v0.3: the roadmap states none, and the record claims none.
- The v0.4 rows of the roadmap, which another session writes.
- Archiving c0070; the verdict; the tag; the pull request from `dev` to `main`; the publication. They are the maintainer's.

## Evidence level required

- v0.2a items 1, 2 and 5 and v0.2b items 1 to 3: `KICAD-VERIFIED (9.0.x, 10.0.x)`, in `kicad-9`, `kicad-10` and `routing`.
- v0.2a item 3: `CORPUS-VERIFIED` for RT0 and RT1, `KICAD-VERIFIED (9.0.x, 10.0.x)` for RT2 under its limit (kinds of violations, not items).
- v0.2a item 4: mechanical for `diff`, `CORPUS-VERIFIED` for `fmt`.
- `H-K-SCH-UPDATE` stays `INFERRED`, and the record says so.
- The rows of v0.3 carry the labels their own changes gave them; most are `INFERRED`.
- Residue: public gate only; the private gate is not run for v0.2.0, and the record says so.

## Impact

- New: `docs/release/v0.2.md`, `tests/unit/test_release_record_v02.py`. Changed: `README.md`, `docs/roadmap.md`, `docs/evidence/residue-history.md`, `openspec/README.md`, `tests/unit/test_agent_skill.py`, `CHANGELOG.md`, the version strings.
- Depends on every v0.2a and v0.2b change.
- No runtime dependency. No hypothesis and no source is registered.
