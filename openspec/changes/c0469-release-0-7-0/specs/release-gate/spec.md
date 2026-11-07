## ADDED Requirements

### Requirement: Release record of v0.7
`docs/release/v0.7.md` SHALL record, change by change, what `0.7.0` ships, guarded by `tests/unit/test_release_record_v07.py`.
- `## Verdict per change` MUST hold the table `| change | what ships | proof | job | open tasks | result |`, a row per change named by its folder.
- A result is `ships`, `ships with deferred tasks` or `pending`.
- The guard MUST refuse a verdict over a `pending` row or a `TODO(coordinator)` placeholder.

#### Scenario: Every change present
- **WHEN** `uv run pytest tests/unit/test_release_record_v07.py` reads the committed record
- **THEN** every change of the release has one row, and every proof and every job exists

#### Scenario: Verdict over a placeholder
- **GIVEN** a copy of the record that holds `TODO(coordinator)` and the verdict `Released as v0.7.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the placeholder

### Requirement: Open tasks in the record of v0.7
The column `open tasks` of `docs/release/v0.7.md` SHALL follow the change's own `tasks.md`, open or archived.
- Every unchecked task MUST be named, and every number named MUST be a task of it.
- A row that `ships` names no task; a deferred or `pending` row MUST have its entry in the matching section.

#### Scenario: An open task not named
- **GIVEN** a copy of the record whose row of c0389 does not name task 1.1
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0389-altium-native-rounds-follow-up` and `1.1`

#### Scenario: A pending row without its entry
- **GIVEN** a copy of the record without the entry of a `pending` row under `## Pending on the release branch`
- **WHEN** the guard runs on it
- **THEN** it fails and names that change

### Requirement: Sections of the record of v0.7
`docs/release/v0.7.md` SHALL hold the sections of the record of v0.6 for the tag `v0.7.0`, with `## Deferred after v0.7` in place of `## Deferred after v0.6`, and a section `## Left out of the rows`.
- `## Altium write` MUST say that every Altium write kind stays experimental.
- `## Left out of the rows` MUST name each change added after `v0.6.0` that shipped no code, with its reason, and the guard MUST refuse a row for such a change.
- `## Changes of earlier releases` MUST name each change of an earlier release closed since `0.6.0`.

#### Scenario: A change that shipped no code given a row
- **GIVEN** a copy of the record with a row for a change named under `## Left out of the rows`
- **WHEN** the guard runs on it
- **THEN** it fails and names that change

### Requirement: Scope of 0.7.0 of 2026-11-06
The record SHALL hold the scope that the maintainer approved on 2026-11-06: what is implemented since `0.6.0` on the base of lote-29.
- Every change folder added after the tag `v0.6.0` MUST have a row or an entry under `## Left out of the rows`.
- `## Not in 0.7.0` MUST name c0468 and v1.0, and no change of the release.

#### Scenario: c0468 named as a row
- **GIVEN** a copy of the record with a row for `c0468-library-generator-families`
- **WHEN** the guard runs on it
- **THEN** it fails and names it as not a change of 0.7.0

### Requirement: Version 0.7.0
The version SHALL become `0.7.0` in the last commit of change c0469, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.7.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.7.0] - <date>` under an empty `## [Unreleased]`, followed by `## [0.6.0]`, with exactly one `### Added`, `### Changed` and `### Fixed`.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v07.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.7.0`, the headings of `CHANGELOG.md` start `Unreleased`, `0.7.0` and `0.6.0`, and `tools/release.py check --tag v0.7.0` agrees

### Requirement: History row and roadmap of 0.7.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.7.0` with `0` hits and the private gate `not run` or `on`, and `docs/roadmap.md` SHALL name the release change.
- The milestone row of v0.7 MUST name c0469 and `docs/release/v0.7.md`.

#### Scenario: History row required
- **GIVEN** a copy of `docs/evidence/residue-history.md` without the `v0.7.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

## MODIFIED Requirements

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.7.**`, link to `docs/release/v0.7.md`, say what is experimental, and not hold `pre-alpha` or `being bootstrapped`.
- `## Install` MUST hold `pip install fenolite` and say that it installs no other package.
- The file MUST NOT claim byte identity with a file re-saved by KiCad (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` checks these textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.7`, links to `docs/release/v0.7.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: What the status says works
- **GIVEN** the committed `README.md`
- **WHEN** a reader reads the status paragraph and the workflow sections
- **THEN** they say that a design script becomes a KiCad 9 or 10 project with a board and a schematic, that the agent loop uses KiCad's checks, that projects convert between KiCad and Altium or to the older KiCad major, and they link the support and limits record and the documentation index; no shipped feature is described as a future plan

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.6.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.7`

#### Scenario: Byte identity rejected
- **GIVEN** a copy of `README.md` that says its output is byte-identical to KiCad's own files
- **WHEN** the README check runs on it
- **THEN** it fails and names byte identity
