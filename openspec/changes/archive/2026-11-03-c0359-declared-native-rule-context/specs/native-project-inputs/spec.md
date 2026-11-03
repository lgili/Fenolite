## ADDED Requirements

### Requirement: Native-only rule programs are preserved or refused
When the existing source reader leaves native rule items opaque, import SHALL preserve the complete original DRU bytes/order/comments only after qualifying the supported explicit selector attributes against the first emitted PCB. It SHALL bind the complete actual lowered model and final emitted PCB/project bytes for rebuilds. Fully modelled rule programs SHALL retain their existing editable DSL conversion and output bytes.

#### Scenario: Native-only rules survive an unchanged import
- **WHEN** an authored source contains modelled and native-only rule items in the bounded supported profile
- **THEN** the entire original rule program is retained byte-for-byte
- **AND** original-to-first-output referred native attributes and physical net partitions agree
- **AND** existing unjudged scope and findings remain visible without claiming cache or native DRC result equality

#### Scenario: Net identity is preserved independently of spelling
- **WHEN** generated singleton net names differ but the complete physical equivalence classes match
- **THEN** paired A.Net/B.Net comparisons preserve identity, NO_NET and multiplicities
- **AND** merge, split, swap or ambiguous physical memberships refuse
- **AND** this native-only fallback does not accept unproved NetName predicates

#### Scenario: A model or emitted native context changes
- **WHEN** any complete-model field other than header tool-version metadata changes, or actual emitted PCB/project bytes change
- **THEN** build refuses before a write plan rather than masking the change with original rules
- **AND** no additional schema/version/CAD field is normalized or omitted

#### Scenario: A declared native-rule input is missing or stale
- **WHEN** the generated script's DRU, receipt or both are missing on a fresh build
- **THEN** build returns existing input error FEN-3004 before planning
- **AND** changing an already reviewed input invalidates confirmation with FEN-4002

#### Scenario: A fully modelled program remains editable
- **WHEN** the reader models every native rule item, including supported NetName or NetClass conditions
- **THEN** the existing generated DSL remains editable and no immutable capsule is added
- **AND** ordinary no-DRU emission and default build bytes remain unchanged
