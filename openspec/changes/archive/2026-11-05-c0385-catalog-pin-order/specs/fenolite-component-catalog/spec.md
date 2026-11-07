## ADDED Requirements

### Requirement: Catalog lands numbered counter-clockwise
Every shipped catalog package whose land has a perimeter numbering SHALL number its leads counter-clockwise in the top view (X right, Y down), and no shipped record SHALL waive `library.pin-order`. A single-row part whose body outline is asymmetric SHALL keep its pads and body in the orientation of its cited top view. Change c0385 mirrored 55 records about their X axis at version `1.1.0` and kept their pad numbers, sizes and kinds.

#### Scenario: No clockwise catalog land
- **WHEN** `uv run pytest tests/unit/library/test_rules.py -k shipped_catalog` checks every shipped package record
- **THEN** no `library.pin-order` finding is reported and no record waives it

#### Scenario: SOT-23 pad 1 at the upper left
- **WHEN** `get_footprint("Fenolite:SOT23_3")` is read
- **THEN** pad 1 is at (−1.05, −0.95) mm, pad 2 at (−1.05, +0.95) mm and pad 3 at (+1.05, 0) mm

## MODIFIED Requirements

### Requirement: Catalog footprints come from the generators
The catalog footprints SHALL be drawn only from their c0259 package records, without private land helpers or land tuples in `fenolite.catalog`, and every catalog `.kicad_mod` MUST keep the bytes recorded in `tests/data/catalog/footprints.sha256`, which changes only together with a record version in `VERSIONS.toml` (c0385 changed the 55 mirrored footprints).

#### Scenario: Catalog bytes unchanged
- **GIVEN** `tests/data/catalog/footprints.sha256`, the SHA-256 of every catalog footprint written for KiCad 9 and 10
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k golden` writes every footprint that `list_entries(kind="footprint")` names
- **THEN** all 100 digests equal the golden list for both targets

#### Scenario: No private land helper remains
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k helpers` searches the modules of `src/fenolite/catalog/`
- **THEN** none defines `_chip_footprint`, `_two_terminal_footprint`, `_row_pads`, `_quad_pads`, `_paste_grid`, `_thermal_paste`, `_pin1_index` or `_make_footprint`, and none holds a `_*_LANDS_UM` table

### Requirement: Family entries reproduced under drawing 0
c0259 stores each catalog footprint as an explicit pad list (`generator = "explicit"`); the family-shaped entries (chips, molded two-terminals, small-outline, QFN, DFN, QFP and DIP entries) MUST be reproduced exactly by `fenolite.catalog.footprints.generate` under `drawing = 0` from a record with a `[land]` holding the same numbers. `drawing = 0` keeps the 0.6 placement, which numbers the leads clockwise; since c0385 the catalog entry of a chiral land MUST equal the `drawing = 0` output mirrored about the X axis, and an achiral one the output itself. A record moves to its family only with `drawing = 1`, which numbers counter-clockwise.

#### Scenario: Drawing 0 reproduces the catalog
- **GIVEN** family records with `drawing = 0` and a `[land]` holding the numbers of `Chip_0603`, `SOIC14_TI_D0014A`, `LQFP48_TI_PT0048A`, `QFN16_Diodes_W3030_A1`, `DFN6_Diodes_W2020_US` and `DIP8_Microchip_P`
- **WHEN** `generate` draws each
- **THEN** `Chip_0603` equals `get_footprint` of its catalog entry, and each of the others mirrored about its X axis equals `get_footprint` of the catalog entry of the same name
