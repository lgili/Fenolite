## ADDED Requirements

### Requirement: A carried pour is kept per polygon
A conversion or build to Altium SHALL keep the carried pour of each polygon whose vertices, net and layer
match a carried one, and that no new or changed polygon of its layer meets or precedes. A new or changed
polygon SHALL NOT make the other polygons fall back to the computed pour. The written document's copper
check SHALL decide per polygon: a kept polygon that fails it where its source did not is computed, and
only that polygon (change c0496).

#### Scenario: A zone added in KiCad
- **GIVEN** an authored PCB document with three poured polygons, converted to KiCad, with one zone of a new
  net added 20 mm from the others
- **WHEN** it is converted back to Altium
- **THEN** the three polygons hold the source's region records, apart from the index bytes, and only the
  new polygon is computed
