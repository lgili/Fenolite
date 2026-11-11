## ADDED Requirements

### Requirement: Box of a STEP surface model
A STEP model that holds no edge SHALL get a box from its trimmed curves (change c0481), so a conversion
to Altium writes its body.
- `stepbox.model_box` MUST measure a representation that reaches no `EDGE_CURVE` by the points of its
  `TRIMMED_CURVE`s:
  - over a `LINE`: its two trims;
  - over a `CIRCLE` or an `ELLIPSE`: its two trims and each point within its span where a coordinate is
    extreme.
- A trim given as a point MUST be taken as that point.
- A trim given as a parameter MUST be read as follows:
  - on a line: pnt + u · magnitude · orientation;
  - on a conic: an angle in the plane angle unit of the representation's context, or the radian when
    the context names none.
- The span of a trimmed conic MUST run counter-clockwise from trim 1 to trim 2 when `sense_agreement` is
  `.T.`, and from trim 2 to trim 1 otherwise.
- A representation that reaches an edge MUST be measured by its edges alone, as before.

#### Scenario: Surface model
- **GIVEN** a model in millimetres and degrees holding a line from (0, 0, 0) of vector (0, 5, 0) trimmed at
  0 and 1, and a circle of radius 2 about (0, 5, 0) trimmed from 0 to 180
- **WHEN** `model_box` reads it
- **THEN** the box is (-2, 0, 0) to (2, 7, 0) mm

#### Scenario: Edges win
- **GIVEN** the same model with one edge from (0, 0, 0) to (0, 1, 0)
- **WHEN** `model_box` reads it
- **THEN** the box is (0, 0, 0) to (0, 1, 0) mm
