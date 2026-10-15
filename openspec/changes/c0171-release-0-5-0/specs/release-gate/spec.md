## ADDED Requirements

### Requirement: Release record of v0.5
`docs/release/v0.5.md` SHALL record, change by change, what `0.5.0` ships, guarded by `tests/unit/test_release_record_v05.py`.
- `## Verdict per change` MUST hold the table `| change | what ships | proof | job | open tasks | result |`, a row per change named by its folder `cNNNN-<slug>`.
- A result is `ships`, `ships with deferred tasks` or `pending`.
- The guard MUST refuse a verdict over a `pending` row or a `TODO(coordinator)` placeholder.

#### Scenario: Every change present
- **WHEN** `uv run pytest tests/unit/test_release_record_v05.py` reads the committed record
- **THEN** every change of the release has one row, and every proof and every job exists

#### Scenario: Verdict over a placeholder
- **GIVEN** a copy of the record that holds `TODO(coordinator)` and the verdict `Released as v0.5.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the placeholder

### Requirement: Open tasks in the record of v0.5
The column `open tasks` of `docs/release/v0.5.md` SHALL follow the change's own `tasks.md`, open or archived.
- Every unchecked task MUST be named, and every number named MUST be a task of it.
- A row that `ships` names no task; a deferred or `pending` row MUST have its entry in the matching section.
- `## Open changes of earlier releases` MUST name each open task of c0081, c0105 and c0146.

#### Scenario: An open task not named
- **GIVEN** a copy of the record whose row of c0160 does not name task 5.3
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0160-convert-to-altium` and `5.3`

### Requirement: Sections of the record of v0.5
`docs/release/v0.5.md` SHALL hold the sections of the record of v0.4 for the tag `v0.5.0`, with `## Deferred after v0.5` in place of `## Deferred after v0.4`.
- `## Altium write` MUST say that every Altium write kind stays experimental.
- `## Not in 0.5.0` MUST name c0168 and c0170.
- `## Deferred after v0.5` MUST name Part T, the Altium executions of c0166, R1 to R5, c0092's tasks 5.2 and 6.2, the kit run, the agent run of c0081, c0105's GUI save and c0146's task 2.4.

#### Scenario: A deferred item missing
- **GIVEN** a copy of the record whose `## Deferred after v0.5` does not name Part T
- **WHEN** the guard runs on it
- **THEN** it fails and names `Part T`

### Requirement: Version 0.5.0
The version SHALL become `0.5.0` in the commit of change c0171, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.5.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.5.0] - <date>` under an empty `## [Unreleased]`, followed by `## [0.4.0]`, with exactly one `### Added`, `### Changed` and `### Fixed` and no entry before the first of them.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v05.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.5.0`, and the headings of `CHANGELOG.md` start `Unreleased`, `0.5.0` and `0.4.0`

### Requirement: History row and roadmap of 0.5.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.5.0` with the private gate `not run` and `0` hits, and `docs/roadmap.md` SHALL name the release change.
- The guard MUST fail at `0.5.0` without the row, or when it claims the private gate `on`.
- The milestone row of v0.5a MUST name `0.5.0`.

#### Scenario: History row required
- **GIVEN** `__version__ == "0.5.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.5.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

## MODIFIED Requirements

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.5.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide, KiCad's own checks of the schematic, and the conversion of a project between KiCad and Altium or to the older KiCad major), MUST link to `docs/release/v0.5.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.5 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout, the reading of Altium files, the writing of Altium files, `fenolite convert` with its report, the KiCad downgrade, the public `equivalent`, board slots and the copper-to-edge check, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading, writing and conversion.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.5`, links to `docs/release/v0.5.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.4.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.5`
