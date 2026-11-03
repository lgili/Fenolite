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


### Requirement: Explicit bounded source-input coverage

The private source-edge admission ceiling SHALL use the reviewed100,000edge structural envelope while retaining every other storage/work/coordinate/distance/deadline guard and the complete geometry certificate. This expands input coverage; it SHALL NOT imply a successful pour when another certificate or resource guard refuses.

#### Scenario: Sparse source above the former pilot ceiling
- **GIVEN**10,001independent authored source edges within every downstream limit
- **WHEN** the exact input is admitted
- **THEN** all source-edge provenance and signed multiplicity remain present; the former10,000pilot ceiling does not reject it

#### Scenario: Expanded input does not expand dense work
- **WHEN** an input exceeds100,000source edges or the unchanged candidate-pair ceiling
- **THEN** the operation refuses before intersection arithmetic and returns no partial graph


### Requirement: Exact boundary subdivision proposals

A bounded repair MAY subdivide an exact selected boundary edge at a rational interior point while retaining every original exact node and proving identical signed curve/current. Each new canonical node SHALL use the same shared prescribed half-even projection and existing coordinate/resource bounds. Endpoint or midpoint predicates SHALL be necessary pruning only; the unchanged complete GLOBAL continuous/source/topology/parentage/debris certificate SHALL judge every returned result. Rejected proposals SHALL NOT become unqualified fallbacks.

#### Scenario: Near-boundary authored notch
- **GIVEN** an original rational notch whose nearest projection is nonsimple and whose original omission exceeds the continuous bound
- **WHEN** an exact collinear subdivision permits a candidate with the same exact curve
- **THEN** the original global certificate protects every original integer corner and complete continuous bound, or the operation refuses

#### Scenario: Samples do not certify an edge interior
- **GIVEN** a proposed projection with plausible endpoint distances but an uncovered interior
- **WHEN** the builder presents it to the caller
- **THEN** the original full global verifier rejects it; necessary probes do not waive any interval


### Requirement: Complete bounded closed-box candidate enumeration

The exact arrangement index SHALL emit every unordered original source-ID pair whose CLOSED integer envelopes intersect exactly once, sorted by source IDs, including point/degenerate/endpoint contacts. Tree pruning SHALL use exact containing envelopes and SHALL NOT alter geometry, merge IDs or discard multiplicity. All node/leaf predicates within one index call SHALL share its existing comparison ceiling; query/component subdivisions SHALL NOT reset it. Storage, candidate-output, coordinate and shared deadline guards SHALL remain effective.

#### Scenario: False single-axis density is not an overlap
- **GIVEN** two independent authored box families which overlap separately inXandYbut have no2Doverlap
- **WHEN** hierarchical candidate enumeration completes within the same work cap
- **THEN** the complete candidate tuple is empty, with every source ID still represented

#### Scenario: Callback resource refusal remains a refusal
- **WHEN** a node/leaf/storage callback exhausts its work or memory bound
- **THEN** traversal propagates the refusal before returning any partial graph
