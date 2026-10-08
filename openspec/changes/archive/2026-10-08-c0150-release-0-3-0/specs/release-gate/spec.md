## ADDED Requirements

### Requirement: Release record of v0.3
`docs/release/v0.3.md` SHALL record the v0.3 acceptance for `0.3.0`, guarded by `tests/unit/test_release_record_v03.py`.
- `## Acceptance of v0.3` and `## Also in this package` MUST hold the table `| item | statement | proof | job | result |`: a row per item 1 to 5 of "v0.3 acceptance", change ids in the second.
- Proofs, jobs, results, limits and open rows follow "Release record of v0.2".
- `## Verdict` is the maintainer's; the guard MUST refuse a verdict over a `pending` row.

#### Scenario: Every item present
- **WHEN** `uv run pytest tests/unit/test_release_record_v03.py` reads the committed record
- **THEN** the items 1 to 5 each have at least one row, and every proof and every job exists

#### Scenario: Missing item
- **GIVEN** a copy of the record without the rows of item 4
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.3 item 4`

#### Scenario: Verdict over a pending row
- **GIVEN** a copy of the record with one `pending` row and the verdict `Released as v0.3.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the pending row

### Requirement: Graduation table of v0.3
`## Graduation of the Altium write` of `docs/release/v0.3.md` SHALL hold a table whose header starts `| kind | file |`, one row per Altium matrix row with a write cell.
- The verdict, `experimental` or `graduated`, MUST agree with `claims.MATRIX`, and the count of ids MUST be the write cell's.
- The section MUST state the maintainer's exception (`exception`, `condition (d)`) and the revalidation it owes (`fenolite kit verify`, `fenolite kit record`, c0148).

#### Scenario: Graduation table agrees with the matrix
- **GIVEN** a copy of the record whose row of `altium_pcbdoc` says `graduated` while the matrix lists its write as experimental
- **WHEN** the guard runs on it
- **THEN** it fails and names `altium_pcbdoc`

### Requirement: Sections of the record of v0.3
`docs/release/v0.3.md` SHALL hold `## Not in 0.3.0`, `## Runs and versions`, `## Manual checks`, `## Recorded limits`, `## Release build`, `## Deferred after v0.3` and `## Maintainer's steps`.
- `## Not in 0.3.0` MUST name c0137, v0.4, c0151, c0152, Part G, X8 and Part V.
- The runs, the limits, the build and the steps MUST say what those of v0.2 say, for the tag `v0.3.0`, and the steps MUST end with the merge of `main` into `dev`.

#### Scenario: What is not in the release
- **GIVEN** a copy of the record whose section `## Not in 0.3.0` does not name c0137
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0137`

### Requirement: Version 0.3.0
The version SHALL become `0.3.0` in the commit of change c0150, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.3.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.3.0] - <date>` under an empty `## [Unreleased]`, followed by the 0.2 series, the newest patch first, and clean by the rules of `[0.2.0]`.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v03.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.3.0`, and the headings of `CHANGELOG.md` start `Unreleased`, `0.3.0` and a section of the 0.2 series

#### Scenario: A patch section above the release is refused
- **GIVEN** a changelog whose headings are `Unreleased`, `0.2.2`, `0.3.0`, `0.2.1`
- **WHEN** the changelog check of `tests/unit/test_release_record_v03.py` runs on it
- **THEN** it fails and names the order

### Requirement: History row and roadmap of 0.3.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.3.0` with the private gate `not run` and `0` hits, and `docs/roadmap.md` SHALL name the release change.
- The guard MUST fail at `0.3.0` without the row, or when it claims the private gate `on`.
- The milestone row of v0.3 MUST NOT say `proposed`.

#### Scenario: History row required
- **GIVEN** `__version__ == "0.3.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.3.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

## MODIFIED Requirements

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.3.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide on two-layer boards, and KiCad's own checks of the schematic), MUST link to `docs/release/v0.3.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.3 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout, the reading of Altium files and the writing of Altium files, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading and writing.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.3`, links to `docs/release/v0.3.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.2.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.3`
