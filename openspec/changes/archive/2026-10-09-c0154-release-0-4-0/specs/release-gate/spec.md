## ADDED Requirements

### Requirement: Release record of v0.4
`docs/release/v0.4.md` SHALL record, change by change, what `0.4.0` ships of v0.4, guarded by `tests/unit/test_release_record_v04.py`.
- `## Verdict per change` MUST hold the table `| change | what ships | proof | job | open tasks | result |`, a row per change.
- Proofs and jobs follow the record of v0.2; a result is `ships`, `ships with deferred tasks` or `pending`.
- The guard MUST refuse a verdict over a `pending` row or a `TODO(coordinator)` placeholder.

#### Scenario: Every change present
- **WHEN** `uv run pytest tests/unit/test_release_record_v04.py` reads the committed record
- **THEN** every change of v0.4 has one row, and every proof and every job exists

#### Scenario: Verdict over a placeholder
- **GIVEN** a copy of the record that holds `TODO(coordinator)` and the verdict `Released as v0.4.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the placeholder

### Requirement: Open tasks in the record of v0.4
The column `open tasks` of `docs/release/v0.4.md` SHALL follow the change's own `tasks.md`.
- Every unchecked task of that list MUST be named, and every number named MUST be a task of it.
- A row that `ships` names no task; a row `ships with deferred tasks` MUST have an entry under `## Deferred to the next release`, and a `pending` row one under `## Pending on the release branch`.

#### Scenario: An open task not named
- **GIVEN** a copy of the record whose row of c0081 does not name task 4.2
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0081` and `4.2`

### Requirement: Sections of the record of v0.4
`docs/release/v0.4.md` SHALL hold `## Altium write`, `## Not in 0.4.0`, `## Runs and versions`, `## Recorded limits`, `## Release build`, `## Archive order`, `## Deferred after v0.4` and `## Maintainer's steps`.
- The runs, the limits, the build and the steps MUST say what those of v0.3 say, for the tag `v0.4.0`, and the runs MUST name the `yardstick` job.

#### Scenario: The yardstick run not named
- **GIVEN** a copy of the record whose runs do not name the `yardstick` job
- **WHEN** the guard runs on it
- **THEN** it fails and names `yardstick`

### Requirement: Follow-ups of the record of v0.4
`## Follow-ups found on 2026-10-08` of `docs/release/v0.4.md` SHALL name c0110 with `route.escape-skipped`, c0105, c0108, c0109, c0112, c0081, c0091, c0148, X8, Part V, Part G, R2, the `.cmd` launcher of `agent_eval` and c0151.

#### Scenario: A follow-up missing
- **GIVEN** a copy of the record whose follow-ups do not name c0151
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0151`

### Requirement: Version 0.4.0
The version SHALL become `0.4.0` in the commit of change c0154, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.4.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.4.0] - <date>` under an empty `## [Unreleased]`, followed by `## [0.3.0]`, clean by the rules of `[0.2.0]`.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v04.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.4.0`, and the headings of `CHANGELOG.md` start `Unreleased`, `0.4.0` and `0.3.0`

### Requirement: History row and roadmap of 0.4.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.4.0` with the private gate `not run` and `0` hits, and `docs/roadmap.md` SHALL name the release change.
- The guard MUST fail at `0.4.0` without the row, or when it claims the private gate `on`.
- The milestone row of v0.4 MUST name `0.4.0` and MUST NOT say that its changes are not on `dev`.

#### Scenario: History row required
- **GIVEN** `__version__ == "0.4.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.4.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

## MODIFIED Requirements

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.4.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide, and KiCad's own checks of the schematic), MUST link to `docs/release/v0.4.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.4 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout, the reading of Altium files and the writing of Altium files, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading and writing.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.4`, links to `docs/release/v0.4.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.3.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.4`
