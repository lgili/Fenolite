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
`NOTICE` SHALL contain the project attribution line and one entry per third-party work from which code or design was actually derived, with its licence. Works consulted only as facts or used only as oracles SHALL NOT appear in `NOTICE`; they belong in `docs/evidence/sources.md`.

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

