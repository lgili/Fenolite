## ADDED Requirements

### Requirement: Dependency licence inventory
`docs/licences.md` SHALL list each package of the runtime and of each extra, from `uv.lock`, with its version and the licence its metadata states (`License-Expression`, else `License`), one table per extra, or "not inspected" when it is not installed. `tools/gen_licences.py --check` MUST exit 1 when the page is stale. A GPL, AGPL or LGPL licence in the runtime, `geo`, `kicad-ipc` or `oracles` (imported in-process) MUST fail `tests/unit/test_legal_docs.py` (ADR-0004).

#### Scenario: The inventory names the geo extra
- **WHEN** `uv run python tools/gen_licences.py --check` runs in an environment synced with every extra
- **THEN** it exits 0, and `docs/licences.md` lists `shapely` with `BSD-3-Clause` and `pyclipper` with `MIT` under `geo`

#### Scenario: A stale inventory fails the check
- **GIVEN** a committed `docs/licences.md` that differs from a fresh generation
- **WHEN** `uv run python tools/gen_licences.py --check` runs
- **THEN** it exits 1

#### Scenario: A package that is not installed
- **GIVEN** a package of `uv.lock` that is not installed where the inventory is made
- **WHEN** the inventory is generated
- **THEN** the package is listed with its lock entry and "not inspected"

#### Scenario: A copyleft package in an extra fails
- **GIVEN** an inventory in which a package of `geo` states `GPL-3.0-or-later`
- **WHEN** the licence test reads it
- **THEN** it fails naming the package and the extra; copyleft tools stay behind a process boundary

### Requirement: Legal review before 1.0
`docs/release/v1.0-legal-review.md` SHALL hold one row per claim (each numbered statement and forbidden practice of `LEGAL.md`, `NOTICE`, the SPDX rule, the DCO, each fetched asset, the inventory) with where it is stated, what shows it and the reviewer's dated answer. It MUST state whether a lawyer read it; that is not a condition of the release. `LEGAL.md` MUST point to it and to the inventory. Every "shown by" MUST exist, and `1.0.0` MUST NOT be published while a row has no answer.

#### Scenario: Every row is shown by something that exists
- **WHEN** `uv run pytest tests/unit/test_legal_docs.py` runs
- **THEN** each row of the record names a test, a file of the repository or a source registered in `docs/evidence/sources.md` that exists

#### Scenario: Each fetched asset has a row
- **WHEN** the record is read
- **THEN** the KiCad libraries, the Freerouting jar and the corpus files each have a row with their licence and how they are kept out of the repository

#### Scenario: An unanswered row holds the release
- **GIVEN** a record with one row whose answer is empty
- **WHEN** the release gate of `1.0.0` is checked
- **THEN** it fails naming the row
