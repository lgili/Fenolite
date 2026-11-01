## ADDED Requirements

### Requirement: Bottom chamfer corners follow the footprint mirror
Bottom placement and library derivation SHALL mirror pad chamfer tokens by swapping `top_left` with `bottom_left` and `top_right` with `bottom_right`, preserving ratios and other pad fields. Chamfer tokens MUST NOT cause a flip-unsupported refusal. The mapping MUST be an involution under the existing local-Y mirror.

#### Scenario: Authored corner subsets at rotated placements
- **WHEN** an authored chamfered pad is placed on the bottom at 0, 30 and 90 degrees and derived back
- **THEN** its stored corners mirror once and its derived corners and ratios equal the definition

### Requirement: Chamfer flip evidence stays inferred until measured
A build that places a chamfered definition on the bottom SHALL include inferred chamfer-flip evidence until its oracle is confirmed. Previously supported bottom definitions MUST retain their existing verified flip evidence, and a top placement MUST NOT add the chamfer-flip hypothesis.

#### Scenario: Feature-specific build evidence
- **WHEN** the same authored chamfered definition is built on either side
- **THEN** only the bottom build adds the inferred chamfer hypothesis, while a plain bottom definition keeps its prior flip evidence
