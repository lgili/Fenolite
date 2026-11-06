## MODIFIED Requirements

### Requirement: Exact circular thick cores
`Thick` SHALL accept an optional `arc` core with integer stored points. Its box, touch and strict-distance decisions, positive integer gap floor and deterministic rounded witness MUST use exact rational and radical arithmetic for arc/point, arc/segment, arc/arc and arc/filled-ring pairs, including equality, without runtime dependencies. Float bounds MAY leave out a segment of the other core from the exact evaluation only when its lower bound, less a slack of 1 nm plus 10⁻⁹ of the largest magnitude involved, exceeds the threshold of a decision or the smallest upper bound plus that slack; an upper bound SHALL come from the arc's stored points and points along the arc that lie within the slack of it, and MAY decide a touch or strict-distance test only when it plus the slack is below the threshold. Every answer SHALL equal the answer of the exact evaluation of every segment (change c0437).

#### Scenario: Tangent boundary and reflected arcs
- **WHEN** authored tangent, fractional-centre, shallow, major, concentric and intersecting arcs are checked, reversed, reflected and turned by quarter turns
- **THEN** touch and clearance decisions preserve exact equality and symmetry, gaps are floored exactly and boxes contain the curves

#### Scenario: Pruning changes no answer
- **WHEN** `uv run pytest tests/unit/geometry/test_arc_prune.py -q` compares seeded arcs against points, rings, polylines and arcs, with and without a spatial index and at board-scale coordinates
- **THEN** `closest` returns the same pair as the search over every segment, the threshold test agrees with that distance just below, at and above it, and every sample point lies within the slack of its arc
