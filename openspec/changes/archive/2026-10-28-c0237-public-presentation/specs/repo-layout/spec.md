## MODIFIED Requirements

### Requirement: Package metadata

`pyproject.toml` SHALL declare `[project.urls]` with exactly the keys `Homepage`, `Source`, `Issues`, `Changelog` and `Documentation`. `Homepage` and `Source` MUST be `https://github.com/lgili/Fenolite`, `Issues` that address followed by `/issues`, `Changelog` that address followed by `/blob/main/CHANGELOG.md`, and `Documentation` that address followed by `/blob/main/docs/index.md`. The classifiers MUST hold exactly one `Development Status ::` entry, and it MUST be `Development Status :: 3 - Alpha` until a later change raises it.

#### Scenario: Metadata checked

- **WHEN** `uv run pytest tests/unit/test_pyproject_invariants.py -k "urls or classifier"` runs
- **THEN** it passes, and the checks report a problem for a missing Documentation link, an address outside the repository or the status `2 - Pre-Alpha`
