## ADDED Requirements

### Requirement: Catalog footprints come from the generators
The catalog footprints SHALL be drawn only from their c0259 package records, without private land helpers or land tuples in `fenolite.catalog`, and every catalog `.kicad_mod` MUST keep its bytes.

#### Scenario: Catalog bytes unchanged
- **GIVEN** `tests/data/catalog/footprints.sha256`, the SHA-256 of every catalog footprint written for KiCad 9 and 10 before this change
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k golden` writes every footprint that `list_entries(kind="footprint")` names
- **THEN** all 100 digests equal the golden list for both targets

#### Scenario: No private land helper remains
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k helpers` searches the modules of `src/fenolite/catalog/`
- **THEN** none defines `_chip_footprint`, `_two_terminal_footprint`, `_row_pads`, `_quad_pads`, `_paste_grid`, `_thermal_paste`, `_pin1_index` or `_make_footprint`, and none holds a `_*_LANDS_UM` table

### Requirement: Family entries reproduced under drawing 0
c0259 stores each catalog footprint as an explicit pad list (`generator = "explicit"`); the family-shaped entries (chips, molded two-terminals, small-outline, QFN, DFN, QFP and DIP entries) MUST be reproduced exactly by `fenolite.catalog.footprints.generate` under `drawing = 0` from a record with a `[land]` holding the same numbers, so that a later version of a record can move to its family without changing its bytes.

#### Scenario: Drawing 0 reproduces the catalog
- **GIVEN** family records with `drawing = 0` and a `[land]` holding the numbers of `Chip_0603`, `SOIC14_TI_D0014A`, `LQFP48_TI_PT0048A`, `QFN16_Diodes_W3030_A1`, `DFN6_Diodes_W2020_US` and `DIP8_Microchip_P`
- **WHEN** `generate` draws each
- **THEN** each `FootprintDef` equals `get_footprint` of the catalog entry of the same name

### Requirement: Records move to a family only with cited numbers
A record SHALL be re-expressed in its family only when the family keys the generator requires (span, lead length and width) come from the sources the record cites; numbers the 0.6 tables never held MUST NOT be invented.

#### Scenario: Span not in the sources
- **WHEN** the sources a catalog record cites give no span or lead length for its package
- **THEN** the record stays `generator = "explicit"` and no family key is added to it
