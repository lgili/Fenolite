## ADDED Requirements

### Requirement: Outline arcs end on their vertices
The Altium reader SHALL take an arc vertex k of the board outline as the arc from vertex k to vertex k+1.
When both ends computed from the arc's centre, radius and angles lie within 10 µm of those two vertices,
the arc's graphic MUST start and end exactly on the two vertices, its middle point coming from the centre
and the angles; otherwise it MUST keep its computed ends. The fact is recorded with its evidence in
`docs/formats/altium/pcb-document.md` ("Outline arcs").

#### Scenario: An arc whose end vertex lies off its circle
- **WHEN** a board outline holds an arc of 100 mil whose end vertex lies 0.2 mil off the arc's circle
- **THEN** the arc graphic ends on that vertex, where the next line starts
- **AND** the edge ring of the source equals the edge ring KiCad reads back from the written board

#### Scenario: An arc far from its vertices
- **WHEN** an arc's computed end lies more than 10 µm from its vertex
- **THEN** the arc keeps the ends of its centre, radius and angles
