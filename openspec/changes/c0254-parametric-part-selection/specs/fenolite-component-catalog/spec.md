## ADDED Requirements

### Requirement: Parametric families in the shipped catalog
The shipped catalog SHALL hold family records (`fenolite.family.v0`) for E24 5 % and E96 1 % chip resistors and for C0G and X7R chip capacitors in the cases 0402, 0603, 0805 and 1206, each naming a shipped symbol and footprint. Every numeric attribute MUST cite a registered public source with a label no higher than the source allows; an attribute without a source MUST be absent, and no family MUST name a manufacturer part number.

#### Scenario: Every family number has a source
- **WHEN** `uv run pytest tests/unit/catalog/test_families.py` runs
- **THEN** every numeric attribute of every shipped family names a source id registered in `docs/evidence/sources.md`, no family has an MPN, and every symbol and footprint it names is a shipped entry

### Requirement: Catalog data version
`fenolite.catalog.CATALOG_VERSION` SHALL name the version of the catalog data and MUST change whenever a family's canonical text changes. `fenolite catalog list --kind family` and `fenolite catalog show <family id>` MUST show the families with their sources.

#### Scenario: The version follows the data
- **GIVEN** a shipped family whose canonical text differs from the one recorded for the current `CATALOG_VERSION` in `src/fenolite/catalog/families/VERSIONS.toml`
- **WHEN** the catalog test runs
- **THEN** it fails naming the family and asking for a new `CATALOG_VERSION`
