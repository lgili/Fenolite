## ADDED Requirements

### Requirement: Release from a tag
`.github/workflows/release.yml` SHALL start on a pushed tag `v*.*.*` and by hand with a tag, and SHALL NOT start on a published GitHub Release. Before publishing it MUST refuse a tag whose commit is not on `main`, or that `tools/release.py check` refuses, and MUST run the residue scan, `twine check --strict` and an install of the wheel alone that prints `fenolite X.Y.Z`.

#### Scenario: A tag releases
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k release_flow` reads the workflow
- **THEN** it finds the tag trigger, the checks of the build and the job that creates the GitHub Release, and fails for a copy without the trigger, with a release trigger, without the check or without `--verify-tag`

#### Scenario: Versions disagree
- **GIVEN** a tree whose alias pins another version than the tag, or whose changelog has no section of it
- **WHEN** `tools/release.py check --tag vX.Y.Z` runs
- **THEN** it exits 1 and names each disagreement

### Requirement: Release notes and files
The workflow SHALL create the GitHub Release `Fenolite X.Y.Z` from the existing tag with notes from `tools/release.py notes`: the PyPI links, install lines, links to the release record, the diff and the changelog, the changelog section, and each attached file with its SHA-256. The attached files MUST be the ones PyPI serves for the version, each checked against PyPI's digest, with `SHA256SUMS`.

#### Scenario: Notes of a version
- **WHEN** `uv run pytest tests/unit/test_release_tool.py -k notes` writes the notes of `v1.2.0`
- **THEN** they hold the install line, the PyPI link of both packages, the diff from `v1.1.0`, the section of 1.2.0 only and the digest of each file, below GitHub's limit

#### Scenario: A file differs from PyPI
- **GIVEN** a downloaded file whose SHA-256 is not PyPI's
- **WHEN** `release.py pypi-files` runs
- **THEN** it fails naming the file

### Requirement: Release made again
A manual run for a tag SHALL end in the same release page: PyPI is not uploaded to when it holds the version, an existing release is edited with its files replaced, and the release is latest only for the highest final version.

#### Scenario: Latest only for the highest final version
- **WHEN** `uv run pytest tests/unit/test_release_tool.py -k latest` runs
- **THEN** `v0.5.0` among `v0.4.0` and `v0.5.0` is latest, `v0.4.1` is not, and `v0.6.0rc1` is not
