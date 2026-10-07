## MODIFIED Requirements

### Requirement: Version 0.2.0
The version SHALL become `0.2.0` in one commit, the last of change c0093, after every row of `docs/release/v0.2.md` has a result, a `pending` row has its entry under `## Open rows`, and the history row is recorded.
- `src/fenolite/__init__.py` MUST hold `__version__ = "0.2.0"`, and `packaging/phenolite/pyproject.toml` MUST hold `version = "0.2.0"` and `dependencies = ["fenolite==0.2.0"]`.
- `CHANGELOG.md` MUST hold `## [0.2.0] - <date>` with the entries that were under Unreleased, an empty `## [Unreleased]` above it and `## [0.1.0]` below it, unchanged. Until the maintainer tags, `<date>` is the words `pending the tag`.
- The `[0.2.0]` section MUST hold each `###` heading at most once and no entry before its first `###` heading. Its entries MUST describe what a user of the CLI or the library sees: no entry names a module or function whose name starts with an underscore, the notes about archived specs are folded into one closing entry, and notes about tests, CI or the repository are merged into that entry or removed.
- The `[0.1.0]` section MUST stay clean by the same two rules (no repeated `###` heading, no underscore name), which `tests/unit/test_release_record.py` checks.
- `docs/roadmap.md` MUST NOT give the state `proposed` to v0.2a, v0.2b or v0.3 in its milestone table, MUST name every change of v0.2a, of v0.2b and of the read part of v0.3 (c0039–c0047) that is not archived, and MUST name the release change.
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
