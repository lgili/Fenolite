## ADDED Requirements
### Requirement: Typed L7 orientation follows the existing cyclic angle metric
L7 Text.rotation and FootprintField.rotation SHALL compare using the existing
360degree angle distance and angular tolerance. This SHALL not normalize model
values or erase canonical presence. Generic fields, noncyclic sweeps/ranges,
level6 and S SHALL remain unchanged.

#### Scenario: Exact equal cyclic orientation
- **WHEN** a text/field rotation differs only by a full turn, including0/360 or-90/270
- **THEN** L7 reports equal orientation at exact zero tolerance
- **AND** both original model values and canonical encodings remain unchanged

#### Scenario: True changes and noncyclic values remain visible
- **WHEN** rotations are90vs0,180vs0 or1microdegreevs0 at exact tolerance
- **THEN** L7 still reports a rotation difference regardless of length tolerance
- **WHEN** a noncyclic sweep is0vs360, or a leaf differs between None/false/zero
- **THEN** the new orientation path does not make it equal
