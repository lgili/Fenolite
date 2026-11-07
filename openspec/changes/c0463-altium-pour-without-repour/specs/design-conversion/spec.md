## ADDED Requirements

### Requirement: Altium arc polygons are never dropped
A conversion or a rewrite of an Altium design SHALL give a polygon whose outline holds arc vertices the outline of its record, with each arc turned into chords within the polygon's `ARCRESOLUTION`. It MUST NOT drop such a polygon.

The conversion SHALL carry the record's arc vertices beside the zone. The way back to Altium SHALL write those arc vertices when the zone's outline still equals their chorded ring. Otherwise it SHALL write the outline's chords and report the zone `changed`.

#### Scenario: A rounded polygon goes to KiCad and back
- **GIVEN** an Altium document with one polygon whose outline has two corners rounded by arcs, and an `ARCRESOLUTION` of 0.0394 mil
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the KiCad zone's outline lies within 0.0394 mil of the rounded outline
- **AND** the written polygon holds the source's two arc vertices

#### Scenario: An edited outline comes back as chords
- **GIVEN** the same KiCad board with one vertex of the zone's outline moved
- **WHEN** it is converted to Altium
- **THEN** the written polygon holds line vertices only, and the report counts the zone `changed`

#### Scenario: A rewrite keeps the polygon
- **WHEN** the same Altium document is read and written again with `rewrite=True`
- **THEN** the written document holds the polygon
