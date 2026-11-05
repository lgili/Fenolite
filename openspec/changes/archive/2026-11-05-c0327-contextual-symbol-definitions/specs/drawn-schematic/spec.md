## ADDED Requirements

### Requirement: Contextual metadata definitions remain complete
Imported per-sheet definitions sharing a native ID MAY differ in property nodes only when the full non-property AST and protected Reference/Value/Footprint defaults are identical. Every occurrence MUST bind its complete source definition by context and digest. Emission SHALL preserve original native IDs and all property nodes, effects, order and opaque data. No model/S field or global cache normalization is allowed.

#### Scenario: Local descriptive default snapshot
- **GIVEN** two authored sheets with one native symbol ID and distinct Description nodes
- **WHEN** the reviewed context-aware import and build run
- **THEN** each written sheet retains its complete local definition and native ID with equal full pin partitions

### Requirement: Context conflicts remain closed
Pin, body, flag, unknown non-property semantic or protected core-default differences, same-file ambiguity, missing contexts and wrong digests MUST refuse before staging. A metadata match SHALL NOT waive electrical, geometry, semantic or written-byte fidelity checks. A wrong-sheet metadata selection MUST fail even when its pins match.

#### Scenario: An apparent metadata conflict changes a pin
- **WHEN** an authored variant changes one pin, its position, a fitted/exclusion flag or protected default
- **THEN** the import refuses and stages no file

#### Scenario: A compatible body uses another sheet's defaults
- **WHEN** a context points to a full property snapshot of another sheet
- **THEN** context fidelity refuses the result rather than accepting its connectivity alone

### Requirement: Nested source pages retain their module frame
Extraction MUST encode a child page sharing its parent's code-module frame with an empty relative module. Drawing readback SHALL preserve every complete component path and pin. A duplicated frame prefix MUST NOT be normalized in comparisons or used to omit pins. This adds no model/S field or net-name rule.

#### Scenario: Two pages share one code module
- **GIVEN** two owned parts m/R1 and m/R2 drawn on nested parent/child pages
- **WHEN** their source sheets are extracted and resolved
- **THEN** the child has an empty relative module and both complete paths survive without a repeated m prefix
