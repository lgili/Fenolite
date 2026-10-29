## ADDED Requirements

### Requirement: Catalog footprints come from the generators
The family-shaped catalog footprints (chips, molded two-terminals, small-outline, QFN, DFN, QFP and DIP entries) SHALL be drawn by `fenolite.catalog.footprints.generate` from their c0259 package records with `drawing = 0` and a `[land]` holding the 0.6 numbers. The private helpers and land tuples of `fenolite.catalog` MUST be removed, and every catalog `.kicad_mod` MUST keep its bytes.

#### Scenario: Catalog bytes unchanged
- **GIVEN** `tests/data/catalog/footprints.sha256`, the SHA-256 of every catalog footprint written for KiCad 9 and 10 before this change
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k golden` writes every footprint that `list_entries(kind="footprint")` names
- **THEN** all 100 digests equal the golden list for both targets

#### Scenario: No private land helper remains
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k helpers` searches `src/fenolite/catalog/__init__.py`
- **THEN** it defines none of `_chip_footprint`, `_two_terminal_footprint`, `_row_pads`, `_quad_pads`, `_paste_grid`, `_thermal_paste`, `_pin1_index` and no `_*_LANDS_UM` table
