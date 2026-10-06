## Context

- **Scope.** The release of v0.2a and v0.2b as one version, `0.2.0`, cut from `dev`. The model is c0025, the release change of v0.1: its record `docs/release/v0.1.md`, its guard `tests/unit/test_release_record.py`, and the way it cut `CHANGELOG.md`.
- **Decided by the maintainer on 2026-10-06.** One release for both milestones. The read work of v0.3 and the changes pulled forward from v0.4 are on `dev` and ship in the same package; the record says so plainly and claims no acceptance for them unless it is proved. The tag, the pull request from `dev` to `main` and the publication are his.
- **The acceptance items** (`docs/roadmap.md`, shortened from the project plan):
  - v0.2a: (1) KiCad's ERC exits clean on the example projects and its parity test has no finding; (2) Fenolite's netlist equals `kicad-cli`'s on every schematic Fenolite generates; (3) RT0, RT1 and RT2 through ERC on every demo schematic without buses and without symbols placed in several sheet instances; (4) `diff` of one footprint moved by 1 mm shows one change, and `fmt --check` is a fixed point over the corpus; (5) a BOM with the user's columns, and a manifest with SHA-256 and a state for every artefact.
  - v0.2b: (1) the lens test is fully preserved, also after the stand-in for "Update PCB from Schematic"; (2) two overlapping rules are resolved as the emission order predicts, also for a new rule kind; (3) parity reproduces the counts of KiCad's own parity test on public demos and authored edits.
- **What exists.** On the base of this change (`dev` at `2e826017` plus the two archive commits): every change of v0.2a is archived; of v0.2b, c0069 and c0071 to c0074 are archived and c0070 is implemented with two tasks open; c0039 to c0047 are archived. CI run 37395886697 of `2e826017` passed every job. The version is `0.1.0`.
- **What is open in c0070.** A fix for a text overlap in the sheet of the blink example is in progress in another worktree, and task 6.2 asks the maintainer to judge the rendered sheets by eye.
- **Constraints.** Clean-room. No new format fact. No full `make check` in this session: the coordinator runs it once at the merge.

## Goals / Non-Goals

**Goals:**
- One place that says, per acceptance item of v0.2a and v0.2b, which test proves it, in which job, and with what result.
- The limits written where a reader of the release finds them, with the numbers of the evidence pages.
- An honest statement of what else is in the package.
- A guard that fails when the record names a test or a job that does not exist.

**Non-Goals:**
- New tests of behaviour. The proofs are the tests of c0060 to c0074, read and named.
- Closing c0070, or deciding the verdict.
- The v0.4 rows of the roadmap.

## Decisions

**Decision 1: one record for two milestones, with one table each.** `docs/release/v0.2.md` holds `## Acceptance of v0.2a` and `## Acceptance of v0.2b`, with the header of v0.1's table. An entry under `## Recorded limits` names its row as `v0.2a item 3` or `v0.2b item 1`, because the item numbers of the two lists overlap. Alternative: two records. Rejected: there is one release, one verdict and one tag.

**Decision 2: a sibling guard, not a longer one.** `tests/unit/test_release_record_v02.py` guards the new record; `tests/unit/test_release_record.py` keeps guarding v0.1 and is not edited. The v0.1 guard holds limits that only v0.1 has (items 2 and 5, the container refill, the outlines), and a shared module would have to carry both sets. The few helpers that both need (the section reader, the table reader, the proof check) are small and are written again.

**Decision 3: the job column is checked.** The v0.1 guard does not read `ci.yml`. The new one reads the job ids textually, as `tests/unit/test_ci_workflow.py` does (the dev extra has no YAML parser), and refuses a job that is not there. A proof is assigned to a job by what the job runs: `unit` runs every test and skips those that need `kicad-cli` or the corpus; `kicad-10` runs `tests/kicad` and `tests/corpus` with both required; `kicad-9` runs `tests/kicad` only; `routing` runs `tests/routing` on both majors. So RT0 and RT1 of the corpus are `kicad-10` rows, although they need no tool.

**Decision 4: a `pending` row does not block the version; it blocks the verdict.** In c0025 the guard refused a `pending` row at version `0.1.0`. Here the maintainer asked for the version commit while c0070 is open. The release is the tag, and the tag follows the verdict, so the guard refuses a verdict other than `pending` while a row is `pending`. The version string in `dev` says which release the tree prepares, as it did between the version commit and the tag of v0.1.

**Decision 5: an open row says why.** A `pending` or `not met` row needs an entry under `## Open rows` that names it. The c0070 row is `pending`, with item `c0070`, because the roadmap's v0.2b acceptance has no item for the readable schematic: the change belongs to the milestone and its last proof is a person's eye. The maintainer closes it with one edit of the row (and removes the entry).

**Decision 6: proofs are read, not written.** For each item the archived changes and the test tree were read, and the row names the test whose assertions are the statement. Where the statement of the roadmap is wider than what a test covers, the row's statement says what the test covers and the result is `met with a recorded limit`:
- v0.2a item 1 says "the example projects". The loop's `check` judges `erc.kicad` on `blink_2layer` and `board_40parts` for both targets (`tests/routing/test_acceptance_loop.py`), and `blink_routed` is judged in the manifest oracle. `examples/blink_official` reported 29 ERC errors when this record was first written; its script was repaired on 2026-10-06 and it reports none on 10.0.6. Its build test, `tests/libs/test_build_official.py`, gains an ERC assertion, so the claim has a test; no CI job installs the official libraries, so that test runs locally only, and the limit says so.
- v0.2a item 3: 5 demo rows are older than the read floor and are not read; RT2 compares kinds of violations.
- v0.2a item 4: the 2 heavy rows are not measured in CI, and the test measures the canonical print, not the command.
- v0.2b item 1: `H-K-SCH-UPDATE` is `INFERRED`.
- v0.2b item 3: five KiCad types are compared, and one type of 10.0.6 has no Fenolite code.

**Decision 7: the later milestone gets a table and no claim.** The roadmap gives v0.3 a scope (Phase 4) and no acceptance list. `## Also in this package` holds one row per scope line, by change id, with the test that proves it, and says in words that the acceptance of that milestone is not claimed. The limits come from the evidence pages of those changes. The known defect is a row that is `not met`: the schematic import does not annotate a repeated sheet, so the components of its channels share one designator; its proof column names the test that asserts the present behaviour, and the entry under `## Open rows` says that the test proves the note and not the designators. A `not met` row there does not block the verdict: the maintainer reads it.

**Decision 8: the history scan is recorded, the build is not rehearsed.** `uv run python tools/residue/scan.py --history` ran on 2026-10-06 with the public gate: 5403 blobs reachable from any ref, 0 hits. The row `v0.2.0` joins `docs/evidence/residue-history.md`, and the guard refuses version `0.2.0` without it. c0025 also rehearsed the build in a throw-away worktree; since then the `wheel` job builds and installs both packages on every push, so the record states the rule and the commands and says that no rehearsal was made.

**Decision 9: README.** The status paragraph names version 0.2 and links to the new record (and to v0.1's). A section `## What version 0.2 does` replaces the paragraph that listed three pages. The Altium reading is described as present, with its evidence mostly `INFERRED`, and the reader is sent to the record. The requirement "README describes v0.1" is renamed "README describes the released version" and its text is copied from the living spec and changed. `agent/SKILL.md` and `AGENTS.md` are not touched: no command of the loop changed.

**Decision 10: the version requirement is renamed.** "Version 0.1.0" in the living spec says that the package holds `0.1.0`, which the version commit makes false. It is renamed "Version 0.2.0" and rewritten for this release. The cleanliness of the `[0.1.0]` section stays a rule and stays in the v0.1 guard.

**Decision 11: the changelog.** `[Unreleased]` holds about 75 entries, most of them before any `###` heading, in the order the changes landed. `[0.2.0]` regroups them under `### Added`, `### Changed` and `### Fixed`, user-facing first: one entry per feature, the later corrections of a feature merged into its entry; the entries that only say that a spec was archived, that a CI run was cited or how many catalog footprints existed on a given day are folded into one closing entry. No fact of a kept entry is changed. The date in the heading is `pending the tag` until the maintainer tags.

**Decision 12: the roadmap.** The milestone table and the sentences under Phase 3 and Phase 4 say what is on the tree. The guard checks three things: no row of v0.2a, v0.2b or v0.3 says `proposed`, every change of those milestones that is still a folder under `openspec/changes/` is named in the state of its row, and the release change is named. The v0.4 row is left as it is.

**Decision 13: the change id.** c0093. The numbers from c0083 to c0092 are reserved on another branch, c0077 to c0081 stay unused, and c0100 to c0120 are used by a proposed milestone on another branch (`openspec/README.md`).

## Files and public API

- New: `docs/release/v0.2.md`, `tests/unit/test_release_record_v02.py`.
- Changed: `tests/libs/test_build_official.py` (one ERC test), `README.md`, `docs/roadmap.md`, `docs/evidence/residue-history.md`, `openspec/README.md` (the id row), `tests/unit/test_agent_skill.py`, `CHANGELOG.md`, `src/fenolite/__init__.py`, `packaging/phenolite/pyproject.toml`.
- No public API changes.

## Sources registered by this change

None.

## Hypotheses registered by this change

None. The record cites rows that their own changes registered.

## Evidence level per behaviour (before merge)

| behaviour | level | where |
|---|---|---|
| the record names tests and jobs that exist | mechanical | `tests/unit/test_release_record_v02.py`, `unit` |
| the rows of v0.2a and v0.2b | as their own changes proved them | the jobs named in each row; CI run 37395886697 |
| ERC of `examples/blink_official` | `KICAD-VERIFIED (10.0.x)`, local runs only | `tests/libs/test_build_official.py` |
| the history residue scan | mechanical, public gate only | `docs/evidence/residue-history.md` |

## Budget (2 days)

| part | days |
|---|---|
| reading the proofs of c0060 to c0074 and of c0039 to c0047 | 0.75 |
| the record and its guard | 0.5 |
| roadmap, README | 0.25 |
| changelog and version | 0.5 |

## Risks / Trade-offs

- **A row says `met` for a statement wider than its test.** Mitigation: Decision 6; the statement column says what the test covers, and the maintainer reads the rows before the verdict.
- **The version says `0.2.0` on `dev` before the release exists.** Accepted (Decision 4). A package built from `dev` before the tag would carry the version; the release workflow runs only for a published GitHub Release or when it is started by hand.
- **The numbers of the record go stale** when an evidence page is measured again. They are dated, and the pages are named.
- **c0070 changes generated sheets after this record.** Its row is `pending`; the oracle tests of the hierarchy run in `kicad-9` and `kicad-10` on the release candidate commit.

## Migration Plan

None: no behaviour changes. After the maintainer's verdict and the tag, the change is archived.

## Open Questions

- Is the v0.3 scope to be called delivered with the repeated-sheet defect open, or does the defect get its own change before a v0.3 claim? Default: no claim in this release.
