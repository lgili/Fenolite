## RENAMED Requirements

- FROM: `### Requirement: README describes v0.1`
- TO: `### Requirement: README describes the released version`

- FROM: `### Requirement: Version 0.1.0`
- TO: `### Requirement: Version 0.2.0`

## MODIFIED Requirements

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.2.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide on two-layer boards, and KiCad's own checks of the schematic), MUST link to `docs/release/v0.2.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.2 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout and the reading of Altium files, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.2`, links to `docs/release/v0.2.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.1.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.2`

### Requirement: Version 0.2.0
The version SHALL become `0.2.0` in one commit, the last of change c0093, after every row of `docs/release/v0.2.md` has a result, a `pending` row has its entry under `## Open rows`, and the history row is recorded.
- `src/fenolite/__init__.py` MUST hold `__version__ = "0.2.0"`, and `packaging/phenolite/pyproject.toml` MUST hold `version = "0.2.0"` and `dependencies = ["fenolite==0.2.0"]`.
- `CHANGELOG.md` MUST hold `## [0.2.0] - <date>` with the entries that were under Unreleased, an empty `## [Unreleased]` above it and `## [0.1.0]` below it, unchanged. Until the maintainer tags, `<date>` is the words `pending the tag`.
- The `[0.2.0]` section MUST hold each `###` heading at most once and no entry before its first `###` heading. Its entries MUST describe what a user of the CLI or the library sees: no entry names a module or function whose name starts with an underscore, the notes about archived specs are folded into one closing entry, and notes about tests, CI or the repository are merged into that entry or removed.
- The `[0.1.0]` section MUST stay clean by the same two rules (no repeated `###` heading, no underscore name), which `tests/unit/test_release_record.py` checks.
- `docs/roadmap.md` MUST NOT give the state `proposed` to v0.2a, v0.2b or v0.3 in its milestone table, MUST name every change of the three milestones that is not archived, and MUST name the release change.
- No task of this change MUST create a tag, a GitHub Release or a PyPI upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.2.0`, and the headings of `CHANGELOG.md` start with `Unreleased`, `0.2.0`, `0.1.0`

#### Scenario: Changelog section is clean
- **GIVEN** a changelog whose `[0.2.0]` section holds an entry before its first heading, `### Added` twice, two entries about archived specs and an entry naming `` `_private.name` ``
- **WHEN** the changelog check of `tests/unit/test_release_record_v02.py` runs on it
- **THEN** it names each of the four faults

#### Scenario: Section required at the version
- **GIVEN** `__version__ == "0.2.0"` and a changelog with no `[0.2.0]` section
- **WHEN** the same check runs
- **THEN** it fails and names the section

#### Scenario: Stale roadmap state rejected
- **GIVEN** a copy of `docs/roadmap.md` whose milestone row of v0.2a says `proposed on 2026-10-04`
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py -k roadmap` runs on it
- **THEN** it fails and names v0.2a

## ADDED Requirements

### Requirement: Release record of v0.2
`docs/release/v0.2.md` SHALL be the record of the v0.2a and v0.2b acceptance, for the one release `0.2.0` that carries both, and `tests/unit/test_release_record_v02.py` SHALL guard it.
- The record MUST hold three tables with the header `| item | statement | proof | job | result |`: under `## Acceptance of v0.2a`, with at least one row for each of the five items of "v0.2a acceptance" in `docs/roadmap.md`; under `## Acceptance of v0.2b`, with at least one row for each of its three items; and under `## Also in this package`, for the later milestone whose changes ship in the package. A row whose `item` is not a number of its acceptance MUST carry a change id.
- `proof` MUST be a path under `tests/`, optionally followed by `::` and a test name, and the guard MUST fail when the file or the function does not exist. A test MUST NOT be written to make a row pass: a row with no proof is `not met` or `pending`.
- `job` MUST be one or more job ids of `.github/workflows/ci.yml`, separated by commas, and the guard MUST fail for a name that is no job there.
- `result` MUST be one of `met`, `met with a recorded limit`, `not met`, `pending`. The guard MUST fail for a `met with a recorded limit` row with no entry for it under `## Recorded limits`, and for a `not met` or `pending` row with no entry for it under `## Open rows`. An entry names its row in its bold head: `v0.2a item 3`, `v0.2b item 1`, or the change id for a row of the later milestone.
- `## Verdict` MUST be written by the maintainer only; an agent leaves it `pending`. The guard MUST fail when the verdict is anything else while a row is `pending`. The version MAY become `0.2.0` while a row is `pending`: the release is the tag, which follows the verdict.
- The record MUST also hold `## Runs and versions` (a linked CI run, the versions of `kicad-cli`, and a line for the run of the release candidate commit), `## Manual checks`, `## Release build` (the rule and the commands of "Release build and local checks", for the tag `v0.2.0`), `## Deferred after v0.2`, and `## Maintainer's steps`: the open row, the verdict, the pull request from `dev` to `main`, the tag `v0.2.0` on the merge commit, the build from the tagged commit in a clean checkout, the publication.

The record MUST state these limits, and the guard MUST fail when one is missing or when its row says `met`:
- **v0.2a item 3 (RT2 of schematics).** KiCad's ERC is not repeatable item by item on 9.0.9 and 10.0.6, so RT2 compares the kinds of violations (`H-K-ERC-REPEAT-2`, `H-K-ERC-RT2-2`), and it does not see a violation that only moves to another pin of the same sheet and type. The entry MUST hold both ids and the words `kinds of violations` and `another pin`.
- **v0.2b item 1 (the update from the schematic).** `H-K-SCH-UPDATE` is `INFERRED`: one manual run of "Update PCB from Schematic" by the maintainer in 10.0.6. The entry MUST hold the id, `INFERRED` and the words `one manual run`.
- **The examples.** The record MUST say where the clean ERC of each KiCad example is proved, and that the one of `examples/blink_official` is asserted by `tests/libs/test_build_official.py`, which no CI job runs because it needs the official KiCad libraries.
- **Module sheets on 9.0.9.** The record MUST say that one generated design reports one `pin_not_connected` fewer on its readable sheets, and that the loss is inside KiCad's report.
- **Residue scan.** The record MUST say that the residue scan of v0.2.0 ran with the `public gate only` and that the private gate was not run for v0.2.0. `docs/evidence/residue-history.md` MUST hold one row with the tag `v0.2.0`, the private gate `not run` and `0` hits, and the guard MUST fail when `fenolite.__version__` is `0.2.0` and the row is missing, or when the row claims the private gate `on`.

`## Also in this package` MUST say that the record does not claim the acceptance of the later milestone, MUST state, per scope line of the roadmap's Phase 4, whether a test proves it, and MUST hold the known defect as a row that is `not met`: the schematic import gives the components of a repeated sheet no designator per channel, so they share one designator. Its entry under `## Open rows` MUST hold the words `share one designator`.

#### Scenario: Every item present
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py` reads the committed record
- **THEN** the items 1 to 5 of v0.2a and 1 to 3 of v0.2b each have at least one row, and every proof and every job exists

#### Scenario: Missing item
- **GIVEN** a copy of the record without the rows of v0.2b item 2
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2b item 2`

#### Scenario: Missing proof
- **GIVEN** a copy of the record with a `proof` naming `tests/unit/cli/test_missing.py`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Unknown job
- **GIVEN** a copy of the record with a row whose job is `kicad-11`
- **WHEN** the guard runs on it
- **THEN** it fails and names `kicad-11` and `ci.yml`

#### Scenario: Another word
- **GIVEN** a copy of the record with the result `mostly met`
- **WHEN** the guard runs on it
- **THEN** it fails and names the result

#### Scenario: Limit without an entry
- **GIVEN** a copy of the record whose entry for v0.2a item 4 under `## Recorded limits` has another head
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2a item 4`

#### Scenario: A row with a fixed limit cannot say met
- **GIVEN** a copy of the record whose RT2 row of v0.2a item 3 has the result `met`
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2a item 3`

#### Scenario: Limits are named
- **GIVEN** a copy of the record whose RT2 entry lacks the words `another pin`
- **WHEN** the guard runs on it
- **THEN** it fails and names the words

#### Scenario: Open row without a reason
- **GIVEN** a copy of the record with a `pending` row and no entry for it under `## Open rows`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Verdict over a pending row
- **GIVEN** a copy of the record with one `pending` row and the verdict `Released as v0.2.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the pending row; with that row `met` it does not

#### Scenario: The later milestone is not claimed
- **GIVEN** a copy of the record whose repeated-sheet row says `met`
- **WHEN** the guard runs on it
- **THEN** it fails and names the defect

#### Scenario: Maintainer's steps
- **GIVEN** a copy of the record whose steps do not name the pull request from `dev` to `main`
- **WHEN** the guard runs on it
- **THEN** it fails and names the section

#### Scenario: History row required
- **GIVEN** `__version__ == "0.2.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.2.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`
