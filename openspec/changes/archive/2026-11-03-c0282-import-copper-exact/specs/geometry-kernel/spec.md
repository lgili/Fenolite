## ADDED Requirements

### Requirement: Exact circular thick cores
`Thick` SHALL accept an optional `arc` core with integer stored points. Its box, touch and strict-distance decisions, positive integer gap floor and deterministic rounded witness MUST use exact rational and radical arithmetic for arc/point, arc/segment, arc/arc and arc/filled-ring pairs, including equality, without runtime dependencies.

#### Scenario: Tangent boundary and reflected arcs
- **WHEN** authored tangent, fractional-centre, shallow, major, concentric and intersecting arcs are checked, reversed, reflected and turned by quarter turns
- **THEN** touch and clearance decisions preserve exact equality and symmetry, gaps are floored exactly and boxes contain the curves
