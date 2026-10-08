## MODIFIED Requirements

### Requirement: Patch releases of 0.2
A version `0.2.N` with `N` from 1 SHALL be a patch release: fixes of defects of the release before it, cut from that release's tag on a branch of its own, and never from `dev`. `docs/release/v0.2.md` SHALL record each one under `## Patch releases`, and `tests/unit/test_release_record_v02.py` SHALL guard that section, the changelog and the history page for every patch release the record names, at any later version of the package.
- **Content.** A patch release MUST hold fixes only. Each fix is a change of its own, with a test that fails on the tag of the release before and passes on the fix. A patch release MUST NOT add a command, a flag, a model field or a schema. It MAY add an issue code only where the fix refuses an input for which the release before wrote a wrong file, and its subsection of the record MUST name the code.
- **Branch.** The branch starts at the tag `v0.2.<N-1>` and reaches `main` by a pull request. After the tag `v0.2.N`, `main` MUST be merged into `dev`, so that `dev` holds the fix, the version and the changelog section.
- **Version.** The three version strings of "Version 0.2.0" change together, in the commit of the release change, which adds no behaviour.
- **Changelog.** `CHANGELOG.md` MUST hold `## [0.2.N] - <date>` between `## [Unreleased]` and the section of the release before, so that the sections of the series stand newest first and without a gap above `## [0.1.0]`; while the version is of the series, `## [Unreleased]` is the only section above them. A patch section MUST be clean by the rules of the `[0.2.0]` section. Until the tag, `<date>` is the words `pending the tag`.
- **Record.** `## Patch releases` MUST hold one subsection `### 0.2.N` per patch release, in rising order from `0.2.1` without a gap, and while `fenolite.__version__` is `0.2.N`, one for every patch release up to it. A subsection MUST hold:
  - the defect, in words a user understands: which releases have it, what was written wrong, and which designs are not affected;
  - a table with the header `| item | statement | proof | job | result |` and at least one row. The `item` of a row MUST be the id of the change that made the fix, and MUST NOT be an `item` of the three tables of `0.2.0`, which a patch release does not touch. `proof`, `job` and `result` are held to the rules of "Release record of v0.2": a row that is `met with a recorded limit` needs an entry under `## Recorded limits`, and a row that is `pending` or `not met` an entry under `## Open rows`, each named by the change id;
  - the words `cut from the tag` with the tag it starts from, and the step that merges `main` into `dev`;
  - a line that starts with `**Verdict of 0.2.N.**`, which an agent leaves as `pending`. The guard MUST fail for a verdict other than `pending` while a row of the subsection is `pending`, and for one without a linked CI run in the subsection.
- **Residue.** `docs/evidence/residue-history.md` MUST hold one row with the tag `v0.2.N`, the private gate `not run` and `0` hits for every patch release the record names, as it does for `v0.2.0`, and the guard MUST fail when a row is missing or claims the private gate `on`.

#### Scenario: Patch release recorded
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py -k patch` reads the committed record, changelog and history page at version `0.2.2`
- **THEN** the record holds `### 0.2.1` and `### 0.2.2`, each with its table, every proof and every job of them exists, the headings of the changelog are `Unreleased`, `0.2.2`, `0.2.1`, `0.2.0`, `0.1.0`, and the history page holds the rows `v0.2.1` and `v0.2.2`

#### Scenario: Version without a subsection
- **GIVEN** the committed record, whose last subsection is `### 0.2.N`, and the version `0.2.<N+1>`
- **WHEN** the guard runs on it
- **THEN** it fails and names `0.2.<N+1>`

#### Scenario: Patch row with a missing proof
- **GIVEN** a copy of the record whose table of one patch release names the proof `tests/unit/lens/test_missing.py`, for each patch release the record names
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Patch row taken from the acceptance
- **GIVEN** a copy of the record whose table of one patch release holds a row with the item `c0070`, which is an item of the table of v0.2b, for each patch release the record names
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0070`

#### Scenario: Patch sections out of order
- **GIVEN** a changelog whose headings are `Unreleased`, `0.2.0`, `0.2.1`, `0.1.0`, and one whose headings are `Unreleased`, `0.2.0`, `0.1.0` while the record names `0.2.1`; and, while the record names `0.2.1` and `0.2.2`, a changelog whose headings are `Unreleased`, `0.2.1`, `0.2.2`, `0.2.0`, `0.1.0`, and one without `0.2.2`
- **WHEN** the changelog check runs on each
- **THEN** each fails and names the sections it found

#### Scenario: Verdict of a patch release
- **GIVEN** a copy of the record whose table of `0.2.1` has a `pending` row and whose line says `**Verdict of 0.2.1.** Released as v0.2.1.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row; with that row `met` and no linked CI run in the subsection it fails and names the run; and with the run linked it passes

#### Scenario: History row of a patch release required
- **GIVEN** a copy of `docs/evidence/residue-history.md` without the row `v0.2.1`, and the committed record
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2.1`
