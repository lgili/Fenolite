## ADDED Requirements

### Requirement: Certified final neck cut
The final neck-removal difference SHALL use exact signed selection and one half-even projection per exact boundary node. It SHALL preserve the existing quantization bound, integer source nonzero vertices, whole-ring orientation and certified retained topology/cleanup. Earlier opening operations SHALL remain unchanged. No fixture, digest or platform condition SHALL select this behavior.

#### Scenario: Original corner retained
- **WHEN** a final neck cut has an original nonzero boundary vertex
- **THEN** the certified result retains its exact integer coordinate and a nonzero turn, or refuses before writing

### Requirement: Existing debris order and certified refusal
The cut SHALL test piece net area before removing small holes. Every removed whole face SHALL have exact/integer eligibility and unique parent/child ownership; a collapsed loop SHALL have zero signed line currents. Uncertified topology, precision or resource limits SHALL refuse through existing GeometryError without an approximate fallback.

#### Scenario: Thin piece owns its hole
- **GIVEN** a simple area-9 outer square and an area-1 hole, with tolerance 3
- **WHEN** debris removal runs
- **THEN** the net area-8 piece disappears with its hole and cannot become a solid area-9 square

#### Scenario: Zero shoelace area is insufficient
- **WHEN** a projected bow tie has zero shoelace area and nonzero signed line currents
- **THEN** it is refused as an uncertified collapse

### Requirement: Certified repair of projected self-crossings
A bounded repair MAY omit implicated noninteger intersection nodes while preserving integer nodes and nonzero source turns. Every retained node SHALL keep its one shared half-even projection. Each changed loop SHALL have a complete exact bidirectional continuous boundary certificate within sqrt(2)/2 nm, with unchanged orientation, contacts, parentage and debris eligibility. Missing intervals or resource exhaustion SHALL refuse; samples alone SHALL NOT establish a certificate.

#### Scenario: Endpoint-only evidence is insufficient
- **GIVEN** a candidate whose original vertices are close to the target but whose edge interior exceeds the bound
- **WHEN** its certificate is checked
- **THEN** it is refused for lack of complete continuous interval coverage

#### Scenario: Many independent hairlines
- **GIVEN** seventeen independent projected hairlines with eligible noninteger intersections
- **WHEN** the one bounded all-implicated proposal is certified
- **THEN** every integer corner, retained topology and complete continuous error bound is preserved without enumerating all subsets

#### Scenario: Proposal exceeds its node cap
- **WHEN** the implicated proposal exceeds its declared 256-node bound
- **THEN** it is refused before constructing a candidate; no certificate or write is claimed

#### Scenario: Subnanometre cleanup has a complete continuous certificate
- **GIVEN** a rational 0.6-nm hairline whose projected zero-current spike is cleaned
- **WHEN** every integer canonical node stays on the curve and both complete boundary directions satisfy the existing bound
- **THEN** the continuous certificate may succeed although the stronger projected point-set fast gate differs

#### Scenario: Cleanup exceeds the continuous bound
- **GIVEN** the corresponding 0.9-nm hairline
- **WHEN** its cleaned boundary exceeds the existing bound
- **THEN** it is refused; integer nodes and source corners cannot be waived
