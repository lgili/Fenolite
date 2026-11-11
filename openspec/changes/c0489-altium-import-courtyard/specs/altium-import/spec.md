## ADDED Requirements

### Requirement: Derived courtyard of an imported footprint
The Altium import SHALL give each footprint that has no courtyard a derived courtyard on `F.CrtYd` or
`B.CrtYd` (the footprint's side), as one closed polygon in the footprint frame (change c0489).
- The courtyard MUST be taken, in this order: from the closed outline on a mechanical layer whose kind is
  courtyard; from the closed outline on a mechanical layer whose kind is assembly, grown by
  `DERIVED_COURTYARD_MARGIN`; else from the convex hull of the outlines of the footprint's component bodies
  of known geometry and its pads' copper, grown by `DERIVED_COURTYARD_MARGIN`.
- A mechanical layer's kind MUST be read only from a key that `docs/formats/altium/pcb-records.md` records
  with a public source. A layer's name MUST NOT decide its kind.
- `DERIVED_COURTYARD_MARGIN` MUST be 250 000 nm, a Fenolite choice recorded in
  `docs/formats/altium/import.md` with its evidence label.
- The derived graphic MUST carry evidence `INFERRED` with hypothesis `H-A-IMP-COURTYARD`, and the pair
  `derived=courtyard` in its `altium` bag.
- `backends.altium.frame.placed_extents` MUST give such a footprint the ring of its derived courtyard, with
  `source == "derived"` and `exact == False`.
- A footprint with a courtyard of its own MUST NOT get a derived one.

#### Scenario: Body larger than the pads
- **GIVEN** an authored PCB document with one footprint whose two pads span 2 mm and whose extruded body is
  a 6 mm by 3 mm rectangle around them
- **WHEN** it is imported
- **THEN** the footprint holds one `F.CrtYd` polygon that contains the body grown by 0.25 mm, marked
  `derived=courtyard`, and its placed extent has `source == "derived"`

#### Scenario: Two bodies that overlap
- **GIVEN** an authored PCB document with two such footprints whose bodies overlap by 1 mm and whose pads
  do not touch
- **WHEN** `fenolite place` judges the imported board
- **THEN** it reports `place.courtyard-overlap` for the two parts

#### Scenario: A footprint without a body
- **GIVEN** an authored footprint with pads only
- **WHEN** it is imported
- **THEN** its derived courtyard is the hull of its pads' copper grown by 0.25 mm
