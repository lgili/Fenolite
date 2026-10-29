## ADDED Requirements

### Requirement: Catalog definitions are data files
Every shipped catalog symbol and footprint SHALL be given by a record file under `src/fenolite/catalog/data/` (`pins/` or `packages/`), read with `fenolite.catalog.records`. The package MUST NOT hold symbol or footprint geometry in Python. `get_symbol`, `get_footprint`, `list_entries`, `ENTRIES`, `default_pad_map`, `ANODE_FIRST_SYMBOLS` and `CATHODE_FIRST_LANDS` SHALL keep their names and results.

#### Scenario: No geometry in code
- **WHEN** `uv run pytest tests/unit/catalog/test_data_only.py` runs
- **THEN** it finds no `_symbol_expansion.py` and no dimension table in `src/fenolite/catalog/*.py`, and every entry of `ENTRIES` has one record file

#### Scenario: Pad map from the records
- **WHEN** `default_pad_map("Fenolite:LED", "Fenolite:LED0603_Kingbright_APT1608SURCK")` is called
- **THEN** it returns `(("1", "2"), ("2", "1"))`, computed from `polarity` and `pad1` in the records

### Requirement: The move to data keeps every byte
`tests/data/catalog/golden.json`, written from the Python catalog before the move, SHALL hold per lib id the `output_digest` of its definition and the SHA-256 of each file built for the catalog examples. After the move every digest MUST be equal. The file SHALL change only together with a version change in `VERSIONS.toml`.

#### Scenario: Definitions equal the golden digests
- **WHEN** `uv run pytest tests/unit/catalog/test_golden.py` runs
- **THEN** every shipped symbol and footprint has the `output_digest` recorded in `golden.json`

#### Scenario: Built files are byte-identical
- **WHEN** the KiCad job builds `examples/catalog*` with `--seed 1` and a fixed `--timestamp`
- **THEN** every written file has the SHA-256 recorded in `golden.json`

### Requirement: Catalog entries show version and licence
`CatalogEntry` SHALL gain `version`, `licence` and `uid` with defaults. `fenolite catalog list` and `fenolite catalog show` SHALL add the keys `version`, `licence` and `uid` to each entry; every existing key and value MUST stay as before.

#### Scenario: Show a moved entry
- **WHEN** `fenolite catalog show Fenolite:Resistor --json` runs
- **THEN** the entry holds `version` `1.0.0`, its `licence`, its `uid`, and the same kind, category, summary, evidence and sources as on 0.6.0

## MODIFIED Requirements

### Requirement: Offline Fenolite-authored standard catalog
Fenolite SHALL ship a deterministic, offline catalog of Fenolite-authored generic schematic symbols
and reusable standard-package footprints under the reserved `Fenolite:` namespace. The catalog
MUST incrementally cover the common component families and standard package styles listed in its
coverage matrix, including passives, discrete and optoelectronic semiconductors, protection,
power/control ICs and electromechanical interfaces. Every entry MUST have a stable lib id, kind,
category, summary, evidence level and public source ids for factual electrical or physical claims.
Definitions MUST NOT be copied or vendored from a CC-BY-SA library, from another CAD library under any
licence other than CC0-1.0, or from a private project. Data from a library whose licence is CC0-1.0
MAY be used openly: each such record MUST carry `origin` (library name, release or commit, the original
element's id), `licence = "CC0-1.0"` and evidence `UNVERIFIED` until a review of its current digest
raises it. The catalog MUST NOT claim complete coverage of commercial parts, choose a package for a part,
or assert manufacturing qualification. Non-standard or proprietary geometry remains project-authored unless
it is separately specified as a reusable generic package with public evidence.

#### Scenario: Catalog covers the published family matrix
- **WHEN** the catalog coverage check runs
- **THEN** every family and standard package style marked in the current coverage matrix has at
  least one discoverable, Fenolite-authored entry or an explicit documented reason it is not
  representable by the current model
- **AND** no private project BOM row or third-party CAD definition is required to build those entries

#### Scenario: A custom package stays project-authored
- **GIVEN** a component package with a non-standard mechanical interface or insufficient public
  evidence
- **WHEN** the catalog coverage is extended
- **THEN** the generic catalog does not claim that geometry as a standard package
- **AND** the user can define it through the project-authored symbol and footprint APIs

#### Scenario: Generic symbols do not select a package
- **GIVEN** a part assigned to a generic catalog symbol that supports multiple package styles
- **WHEN** the design is built
- **THEN** package selection remains explicit on the part and no footprint is silently inferred

#### Scenario: A record from a CC0 library is labelled
- **GIVEN** a shipped record converted from a CC0-1.0 library element
- **WHEN** the catalog source check runs
- **THEN** it passes only if the record holds `origin` with library, version and element id, `licence = "CC0-1.0"`, and evidence `UNVERIFIED` or a review of its current digest

#### Scenario: A record from a CC-BY-SA library is refused
- **GIVEN** a shipped record whose `origin.licence` is `CC-BY-SA-4.0`
- **WHEN** the catalog source check runs
- **THEN** it fails naming the record and the licence

### Requirement: Source and evidence labels
Each factual symbol pin map, polarity claim or physical package dimension in the catalog SHALL cite
one or more public sources registered in `docs/evidence/sources.md`. A land pattern not explicitly
specified by those sources MUST be labelled `INFERRED` in catalog metadata and the definition
description. A writer/readback check MUST NOT upgrade an inferred dimension's evidence level.
Public sources MUST be sufficient for each claim; private board data and copied CAD library content
MUST NOT be used as provenance. A record taken from a CC0-1.0 library MAY name that library, registered
as a source with its licence, as its origin; that origin is not evidence of correctness, so the record
stays `UNVERIFIED` until it is reviewed.

#### Scenario: Every family pack has independent provenance
- **WHEN** the catalog source check runs
- **THEN** it fails for an unregistered source id, a factual claim without supporting provenance,
  or an inferred footprint without an inferred-land description
- **AND** it rejects catalog provenance that points to a private board artifact or third-party CAD
  library file, other than the registered origin of a CC0-1.0 record

#### Scenario: Origin is not evidence
- **GIVEN** a record whose only source is the registered CC0 library of its `origin`, without a review
- **WHEN** the catalog source check runs
- **THEN** it passes only if the record's evidence is `UNVERIFIED`
