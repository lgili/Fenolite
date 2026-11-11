## ADDED Requirements

### Requirement: Resolved schematic connectivity
The optimizer SHALL bind circuit instances, resolved nets and logical pins to stable physical
pad identities, including hierarchical instances, multi-unit symbols, duplicate pad numbers
and bus members. It MUST preserve net ties, variants and domain boundaries as modeled. Drawing
coordinates, names and wire direction MUST NOT create connectivity or change an electrical role.

#### Scenario: Repeated schematic sheets
- **GIVEN** two instances of a sheet have the same local labels and distinct resolved signal and return nets
- **WHEN** the schematic is rearranged and topology suggestions are generated again
- **THEN** each relationship binds to its original instance and pad IDs, and drawing edits do not change the suggestions

### Requirement: Electronic intent provenance and review
The engine SHALL propose topology-based placement relationships with exact endpoints, rationale,
source, confidence, alternatives and missing facts. It SHALL distinguish explicit, confirmed
and suggested intent. Suggestions MUST NOT create constraints or objectives until reviewed.
Conflicting requirements MUST be reported and remain unresolved until the request resolves them.

#### Scenario: Shared rail capacitor ambiguity
- **GIVEN** a fitted capacitor shares supply and return nets with two IC banks and has no declared owner
- **WHEN** the topology recognizer visits it
- **THEN** it reports the ambiguous owners without selecting either by reference, value or current board proximity

#### Scenario: Explicit override
- **GIVEN** a user supplies a valid pad-level bypass binding that supersedes a suggestion
- **WHEN** the optimization request is evaluated
- **THEN** the explicit binding is used and the rejected suggestion remains identifiable in the report

### Requirement: Pad-level electrical objectives
Placement SHALL represent confirmed bypass, oscillator, switching loop, gate return, Kelvin,
signal chain and paired-escape relationships using exact endpoints and declared limits. It SHALL
evaluate both supply and return where applicable, use one pose for shared parts, and preserve
component values, net assignments and pin mapping. Missing reference, required dimensions or
verification MUST remain unknown. Geometric metrics MUST NOT be represented as EMC, thermal,
signal integrity or power integrity qualification.

#### Scenario: Bypass supply and return
- **GIVEN** two legal poses have similar supply-pad distances, but one obstructs the required return connection
- **WHEN** both candidates are checked against the same probe request
- **THEN** the blocked return remains visible and cannot satisfy the mandatory bypass relationship

#### Scenario: Multiple supply banks
- **GIVEN** two banks need independent fitted bypass capacitors, and an available capacitor is DNP
- **WHEN** ownership and poses are evaluated
- **THEN** the DNP footprint remains an obstacle, but cannot satisfy coverage and an unapproved shared capacitor cannot count twice

### Requirement: Protected geometry and hard legality
The optimizer SHALL preserve fixed, excluded and copper-attached parts in the first version.
It MUST use the effective board frame, supported poses, exact outline and cut-outs, keep-outs,
drill projections, required electrical spacing, and supplied assembly limits. Required checks
that are unavailable MUST prevent applicable results for the affected scope. Reused rigid
blocks MUST have compatible identities, exact transforms and a checked pose.

#### Scenario: Fixed connector and slot
- **GIVEN** a fixed connector, a locked track and a slot entirely covered by a candidate's courtyard
- **WHEN** a scope includes the connector and the movable footprint
- **THEN** the connector and track remain exact, and the slot-overlapping candidate is rejected

#### Scenario: No compatible pose transformation
- **GIVEN** a rotated candidate needs geometry the backend cannot represent safely
- **WHEN** the candidate is checked
- **THEN** it is excluded from the applicable shortlist with the unsupported pose reason

### Requirement: Bounded joint search
The engine SHALL generate and refine multiple candidate placements for the selected footprint
set and support block and regional planning. It MUST use fixed work budgets, stable identities,
stable tie-breaking and explicit seeds for randomized experiments. Partial assignments SHALL
be reported separately. Exhaustion, cancellation, unknown checks and complete search of a
finite candidate domain MUST be distinguishable.

#### Scenario: Reconsider an early pose
- **GIVEN** the first legal pose of a movable IC blocks the only viable pose of a decoupling group
- **WHEN** the joint solver has budget for both alternatives
- **THEN** it can present the legal complete combination found by retaining the other IC pose

#### Scenario: Reproducible budget exhaustion
- **GIVEN** equal inputs and a fixed work budget without a wall-clock cutoff
- **WHEN** the solver runs twice
- **THEN** candidates, diagnostics and termination reason agree, excluding elapsed-time telemetry

### Requirement: Routability objectives and fair comparison
The engine SHALL report per-layer directional demand and capacity estimates from actual pad
poses and supplied routing rules. It MUST report overflow and unknown coverage. Comparisons
MUST use equal required part and routing subject sets and show priorities and units. Missing
parts and unsupported checks MUST NOT be rewarded as improvements.

#### Scenario: Lower wire length with blocked escape
- **GIVEN** a shorter bounding-box estimate closes a pad exit that another legal pose leaves free
- **WHEN** both poses are scored and probed for the same pad escape
- **THEN** the reported measurements expose the trade-off and the blocked pose fails a mandatory escape check

### Requirement: Scoped routing probes
Routing probes SHALL run on disposable state without changing the board, fills or route
decisions. Report found, blocked within search, budget exhausted, unsupported and unattempted
subjects. A successful coupled check requires the group to coexist under the same provisional
resource state. Route evidence MUST name its subject scope, budget, versions and check results.

#### Scenario: Shared corridor competition
- **GIVEN** two subjects can each use the same narrow passage in isolation
- **WHEN** the shortlist is checked for coexisting routes
- **THEN** independent successful searches cannot be reported as a joint success and neither candidate writes copper

### Requirement: Fair benchmark and native evidence
Acceptance SHALL compare authored baselines and optimized candidates at the same scope,
limits, route settings and checker versions. It SHALL record safety invariants, opened and
closed connections, relevant findings and run costs, including regressions and unmeasured cases.
Native evidence MUST apply only to the geometry, routed scope and target actually checked.

#### Scenario: Incomplete baseline
- **GIVEN** the grid baseline leaves a required component staged
- **WHEN** completed alternatives are compared
- **THEN** the incomplete baseline is reported with its missing part and is excluded from equal-scope length comparisons
