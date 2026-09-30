# ip-hygiene Specification

## Purpose
Guarantee that Fenolite is developed clean-room: format knowledge comes only from public sources with recorded provenance, and no material from any organisation's non-public files, and no copyleft code, enters the repository.
## Requirements
### Requirement: Clean-room decision is recorded
`docs/adr/0003-clean-room-and-provenance.md` SHALL record that Fenolite is developed clean-room with respect to any organisation's non-public material, that no design files, constants, seeds, fixtures, statistics, vocabularies, templates or examples from such sources are reused, and that format knowledge comes only from public sources recorded in `docs/evidence/sources.md` and `docs/formats/`.

#### Scenario: ADR present and complete
- **WHEN** `pytest tests/unit/test_adrs.py` runs
- **THEN** ADR-0003 exists with the six MADR-lite sections and its Status is `Accepted`

### Requirement: Forbidden sources are enumerated
`LEGAL.md` block A MUST forbid: decompiling or disassembling vendor software; transcribing, compiling or converting GPL/AGPL parser sources or machine-readable grammar files into Fenolite code; using files the contributor is not entitled to read; using an employer's software licence for reverse engineering. It MUST state that reading public copyleft sources for facts is allowed only when the fact is recorded with its source.

#### Scenario: Legal text contains the four prohibitions
- **WHEN** `pytest tests/unit/test_legal_docs.py` runs
- **THEN** it finds the four prohibitions and the "facts with source" rule in `LEGAL.md`

### Requirement: Provenance file per backend
Every package `src/fenolite/backends/<x>/` MUST contain `PROVENANCE.md` with a table of columns `fact-or-area | public source | licence of source | date | how used`, and every page under `docs/formats/<x>/` MUST cite at least one public source.

#### Scenario: Backend without provenance fails
- **GIVEN** a new package `src/fenolite/backends/foo/` without `PROVENANCE.md`
- **WHEN** `pytest tests/unit/test_provenance.py` runs
- **THEN** the test fails naming `backends/foo`

### Requirement: Session log for format work
`LEGAL-ANNEX.md` MUST contain at least one session row (`date | area | files touched | public sources consulted | author`) for every calendar week in which files under `src/fenolite/backends/` or `docs/formats/` changed.

#### Scenario: Missing session row
- **GIVEN** a commit in week 2026-W41 changes `src/fenolite/backends/kicad/pcb.py`
- **AND** `LEGAL-ANNEX.md` has no row dated in that week
- **WHEN** `pytest tests/unit/test_provenance.py` runs
- **THEN** the test fails naming the week

### Requirement: No copyleft dependencies
`pyproject.toml` MUST NOT list, in `dependencies` or in any extra, a package from the closed copyleft list maintained in `tests/unit/test_no_copyleft_deps.py`.

#### Scenario: Copyleft extra rejected
- **GIVEN** a contributor adds `kiutils` to the `dev` extra
- **WHEN** `pytest tests/unit/test_no_copyleft_deps.py` runs
- **THEN** the test fails naming `kiutils`

### Requirement: No code ported from non-public projects
The repository MUST NOT contain commit trailers `Ported-From:` nor source markers claiming derivation from non-public projects.

#### Scenario: Ported-From trailer rejected
- **GIVEN** a commit whose message contains `Ported-From: <anything>`
- **WHEN** `pytest tests/unit/test_no_ported_code.py` runs
- **THEN** the test fails citing the commit hash

### Requirement: Official KiCad libraries are never committed
Files with extension `.kicad_mod`, `.kicad_sym`, `.step`, `.stp` or `.wrl` originating from the official KiCad library collections MUST NOT be committed; libraries SHALL be resolved from the local KiCad installation or fetched by tag at test time.

#### Scenario: Library file matches an official item
- **GIVEN** `tests/data/libs/R_0603.kicad_mod` is byte-identical to an item of the fetched official footprint library
- **WHEN** `pytest tests/residue` runs with the library cache present
- **THEN** the test fails naming the file

