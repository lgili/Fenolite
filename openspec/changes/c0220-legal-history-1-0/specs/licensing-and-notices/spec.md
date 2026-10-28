## ADDED Requirements

### Requirement: Dependency licence inventory
`docs/licences.md` SHALL list every package of the runtime dependencies and of each extra of `pyproject.toml`, from `uv.lock`, with its version and the licence its distribution metadata states (`License-Expression`, else `License`), one table per extra; a package that is not installed where the inventory is made is listed as "not inspected". `tools/gen_licences.py --check` MUST exit 1 when the committed page differs from a fresh generation. A GPL, AGPL or LGPL licence in the runtime or in an extra whose packages Fenolite imports in its own process (`geo`, `kicad-ipc`, `oracles`) MUST fail `tests/unit/test_legal_docs.py`; copyleft tools stay behind a process boundary (ADR-0004).

#### Scenario: The inventory names the geo extra
- **WHEN** `uv run python tools/gen_licences.py --check` runs in an environment synced with every extra
- **THEN** it exits 0, and `docs/licences.md` lists `shapely` with `BSD-3-Clause` and `pyclipper` with `MIT` under `geo`

#### Scenario: A copyleft package in an extra fails
- **GIVEN** an inventory in which a package of `geo` states `GPL-3.0-or-later`
- **WHEN** the licence test reads it
- **THEN** it fails naming the package and the extra

### Requirement: Legal review before 1.0
`docs/release/v1.0-legal-review.md` SHALL hold one row per claim of `LEGAL.md` (each numbered statement and each forbidden practice), of `NOTICE`, the SPDX rule, the DCO, each asset that Fenolite fetches and never commits (the KiCad libraries, the Freerouting jar, the corpus files) with its licence and how it is kept out of the repository, and the inventory: where the claim is stated, what shows it (a test, a file of the repository or a public source of `docs/evidence/sources.md`), and the reviewer's answer with its date. The record MUST state whether a lawyer read it; a lawyer's review is not a condition of the release. `LEGAL.md` MUST point to the record and to the inventory. Every "shown by" MUST name something that exists, and the release of `1.0.0` MUST NOT be published while a row has no answer.

#### Scenario: Every row is shown by something that exists
- **WHEN** `uv run pytest tests/unit/test_legal_docs.py` runs
- **THEN** each row of the record names a test, a file or a registered source that exists

#### Scenario: An unanswered row holds the release
- **GIVEN** a record with one row whose answer is empty
- **WHEN** the release gate of `1.0.0` is checked
- **THEN** it fails naming the row
