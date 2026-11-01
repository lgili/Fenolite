## MODIFIED Requirements

### Requirement: NOTICE lists only real derivations
`NOTICE` SHALL contain the project attribution line and one entry per third-party work from which code or design was actually derived or whose code the package bundles, with its licence. Works consulted only as facts or used only as oracles SHALL NOT appear in `NOTICE`; they belong in `docs/evidence/sources.md`. Bundled code MUST also carry its licence notice in the file that bundles it.

#### Scenario: Bundled viewer code
- **GIVEN** the committed `src/fenolite/view/static/viewer.js`, which bundles Preact
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k notice` runs
- **THEN** `NOTICE` holds the attribution line and an entry naming Preact and the MIT licence, and `viewer.js` holds Preact's copyright and permission notice

#### Scenario: Bootstrap NOTICE
- **WHEN** the repository is bootstrapped
- **THEN** `NOTICE` contains exactly the line `Fenolite — Copyright (c) 2026 Fenolite contributors` and no third-party entries
