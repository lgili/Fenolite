## ADDED Requirements

### Requirement: A computed pour depends only on its own inputs
The computed pour of a polygon SHALL depend only on the polygon's record, the rules that apply to it, the
objects within its outline grown by its largest clearance, and the polygons that pour before it on its
layer (`H-A-POUR-LOCAL`). Its written region records SHALL be byte-identical when anything else in the
document changes, apart from the polygon index in each record's prefix (change c0496).
- A written pour region MUST hold no zero-length edge, and the pour MUST write no zero-length track or
  arc.
- A polygon whose written pour changes with none of its inputs changed MUST be reported with
  `altium.pour-changed` (warning), naming the input that changed.

#### Scenario: A remote zone added
- **GIVEN** an authored PCB document with three polygons of three nets, and the same document with a
  fourth polygon of a fourth net 20 mm from the others
- **WHEN** both are written with the computed pour
- **THEN** the region records of the three polygons are byte-identical between the two documents, apart from
  the polygon index bytes, and no region holds a zero-length edge

#### Scenario: An overlapping zone added
- **GIVEN** the same document with the fourth polygon overlapping the first polygon's outline on its layer
- **WHEN** both are written with the computed pour
- **THEN** the region records of the second and third polygons are byte-identical, apart from the index
