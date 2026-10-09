# copper-rule-explanation Specification

## Purpose
TBD - created by archiving change c0097-copper-rule-explain. Update Purpose after archive.

## Requirements

### Requirement: Clearance rule explanation
The checker SHALL attach immutable candidate rows, subjects, backend switches and the governing
clearance to clearance findings. Rows SHALL hold source, value and severity; rule rows SHALL also
hold rule id, priority, layers and selectors, without entities. Explanations SHALL reuse the
resolver's candidates and helpers, without a second matcher or parsing source strings.
Metadata MUST NOT change numeric limits, severity, count, ordering, messages or CLI output.

#### Scenario: Overlapping selectors
- **GIVEN** two matching clearance rules and a class value
- **WHEN** the pair produces a finding
- **THEN** the rows identify each matching rule in existing precedence order and the governing limit

#### Scenario: Hashable explanation and grouping
- **GIVEN** a finding with a matching rule whose entity contains mutable metadata
- **WHEN** the finding, its explanation and its review group are hashed
- **THEN** hashing succeeds and the finding can be retained in a set

#### Scenario: Arc judged without the zone candidate
- **GIVEN** a class clearance of 1500 nm, a zone clearance of 2000 nm and an arc 2200 nm from its fill
- **WHEN** the widened arc violates the class clearance but the narrowed arc satisfies the zone
- **THEN** the explanation describes the subjects and zone argument of the actual class judgment
- **AND** resolving those explained inputs yields the finding's governing clearance and source

#### Scenario: Nonpositive zone clearance
- **GIVEN** a zone clearance of zero or a negative value
- **WHEN** the resolver explains the pair
- **THEN** no zone candidate is shown, as in the numeric resolver

#### Scenario: Item kinds and layer scopes
- **GIVEN** same-priority rules R and R/track-via, the latter for tracks and vias on F.Cu
- **WHEN** the resolver explains a track against a via
- **THEN** R/track-via governs on F.Cu and R governs on B.Cu
- **AND** an arc matches as a track under the existing subject normalization

### Requirement: Lossless relation grouping
Findings SHALL identify intrinsic, inter-component or routed/free relation and group by relation
and source. Grouping MUST preserve every original finding exactly once, unchanged, without advice
or exemptions. A finding MAY have no explanation.

#### Scenario: Intrinsic footprint spacing
- **GIVEN** two pads of one footprint violate a supplied clearance rule
- **WHEN** findings are grouped for review
- **THEN** the intrinsic group retains that finding with its original severity and limit

#### Scenario: Mixed findings without advice
- **GIVEN** findings of different relations and sources, including one without an explanation
- **WHEN** findings are grouped
- **THEN** every original finding appears once by identity and the groups carry no design advice
