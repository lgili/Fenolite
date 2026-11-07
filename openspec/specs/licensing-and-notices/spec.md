# licensing-and-notices Specification

## Purpose
Make the project's licence and provenance explicit from the first commit: Apache-2.0 text and metadata, SPDX headers, a NOTICE limited to real derivations, the two-block LEGAL.md, the clean-room session log and the Developer Certificate of Origin.
## Requirements
### Requirement: Apache-2.0 licence
The repository SHALL contain `LICENSE` with the verbatim Apache License, Version 2.0 text and `pyproject.toml` SHALL declare `license = "Apache-2.0"` (SPDX expression) with `license-files = ["LICENSE", "NOTICE"]`.

#### Scenario: Licence metadata in the wheel
- **WHEN** `uv build` produces a wheel
- **THEN** the wheel metadata contains `License-Expression: Apache-2.0` and includes `LICENSE` and `NOTICE`

### Requirement: SPDX header on every source file
Every file under `src/`, `tests/` and `tools/` with extension `.py` MUST start with the two lines `# SPDX-License-Identifier: Apache-2.0` and `# Copyright (c) 2026 Fenolite contributors`. Generated data files under `schemas/` and `tools/residue/` are exempt.

#### Scenario: Header test
- **GIVEN** a new file `src/fenolite/foo.py` without the header
- **WHEN** `pytest tests/unit/test_spdx_headers.py` runs
- **THEN** the test fails and prints the path of the offending file

### Requirement: NOTICE lists only real derivations
`NOTICE` SHALL contain the project attribution line and one entry per third-party work from which code or design was actually derived or whose code the package bundles, with its licence. Works consulted only as facts or used only as oracles SHALL NOT appear in `NOTICE`; they belong in `docs/evidence/sources.md`. Bundled code MUST also carry its licence notice in the file that bundles it.

#### Scenario: Bundled viewer code
- **GIVEN** the committed `src/fenolite/view/static/viewer.js`, which bundles Preact
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k notice` runs
- **THEN** `NOTICE` holds the attribution line and an entry naming Preact and the MIT licence, and `viewer.js` holds Preact's copyright and permission notice

#### Scenario: Bootstrap NOTICE
- **WHEN** the repository is bootstrapped
- **THEN** `NOTICE` contains exactly the line `Fenolite — Copyright (c) 2026 Fenolite contributors` and no third-party entries

### Requirement: LEGAL.md with two blocks
`LEGAL.md` SHALL contain a block A "Format analysis" stating that third-party file formats are learned only from public documentation and from files the project is entitled to read, that decompiling or disassembling vendor software is forbidden, and that every format fact is recorded with its public source; and a block B "Material from organisations" stating that the project is developed clean-room with respect to non-public material, and that no design files, constants, seeds, fixtures, statistics, vocabularies or templates belonging to or derived from any organisation are added.

#### Scenario: Blocks present
- **WHEN** `pytest tests/unit/test_legal_docs.py` runs
- **THEN** it finds headings `## A. Format analysis` and `## B. Material from organisations` in `LEGAL.md`

### Requirement: LEGAL-ANNEX.md session log
`LEGAL-ANNEX.md` SHALL define the clean-room session log table (`date | area | files touched | public sources consulted | author`) and SHALL start with an empty table.

#### Scenario: Annex format
- **WHEN** `pytest tests/unit/test_legal_docs.py` runs
- **THEN** it finds the table header with exactly those five columns in `LEGAL-ANNEX.md`

### Requirement: Developer Certificate of Origin
`CONTRIBUTING.md` SHALL require a `Signed-off-by:` trailer on every commit and SHALL link to the DCO 1.1 text.

#### Scenario: Contributing guide mentions the DCO
- **WHEN** a contributor reads `CONTRIBUTING.md`
- **THEN** it contains the string `Signed-off-by:` and a link to `https://developercertificate.org/`

### Requirement: ADR-0004 records the licence decision
`docs/adr/0004-licence-apache-2.0.md` SHALL exist in MADR-lite format (Status, Context, Decision, Alternatives, Consequences, Evidence) and SHALL state the rule "copyleft software only behind a process boundary or a published plugin API, never imported or vendored".

#### Scenario: ADR exists and is complete
- **WHEN** `pytest tests/unit/test_adrs.py` runs
- **THEN** ADR-0004 exists and contains all six section headings

### Requirement: Python headers follow the licensed role
Every Python file MUST begin with SPDX and copyright lines. Core implementation
SHALL use Apache-2.0; explicitly authored CC0 fixture and usage data SHALL retain
CC0-1.0. Header checks MUST validate the licensed role without permitting an
arbitrary licence in core code or weakening fixture authorship requirements.

#### Scenario: Authored executable data
- **GIVEN** an explicitly CC0-authored fixture or shipped usage design
- **WHEN** the repository header proof runs
- **THEN** its SPDX/copyright header and authored-data role pass without changing its dedication

#### Scenario: Unexpected core licence
- **WHEN** implementation code declares a licence outside its permitted role
- **THEN** the header proof fails

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

#### Scenario: Bundled viewer dependency is reviewed separately
- **GIVEN** the viewer bundles Preact
- **WHEN** the 1.0.0 review gate runs
- **THEN** its separate row binds the locked Preact version and the NOTICE SHA-256, the package and lock agree on MIT, and the bundled header retains the version and permission notice
- **AND** a missing row, changed binding or missing bundled notice holds the release without treating the Python metadata inventory as review of this asset

