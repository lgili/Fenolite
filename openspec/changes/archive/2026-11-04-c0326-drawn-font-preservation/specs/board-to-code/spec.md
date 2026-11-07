## ADDED Requirements

### Requirement: Strict imported drawn effects
Import SHALL preserve supported drawn effects through the actual written-byte self-check and reviewed replay. Unrepresentable effects MUST refuse before staging. Original source bytes, existing loss policy and accepted-difference records MUST remain unchanged by the font repair.

#### Scenario: Reviewed font conversion
- **GIVEN** an original authored project with styled fields and routed copper
- **WHEN** strict import, reviewed confirmation and verify-source run
- **THEN** all nine levels are equal with zero accepted differences and unchanged source bytes

#### Scenario: Unsupported font has no plan
- **WHEN** a source typed item has an unsupported native effect
- **THEN** strict import refuses before offering a write plan
