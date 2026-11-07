## ADDED Requirements

### Requirement: Scoped local aliases for global power declarations
Under the KiCad scalar-alias policy, an actually global power declaration SHALL join a local scalar label of the same name in that sheet instance. A declaration elsewhere SHALL NOT by itself promote local labels on an undeclared sheet. Unequal names and generic/default resolution SHALL retain their existing rules. Complete native pin partitions and source content SHALL be preserved.

#### Scenario: Disconnected islands share a same-sheet power name
- **GIVEN** an authored local scalar label and a global power declaration of the same name on separate islands of one sheet
- **WHEN** KiCad-scoped connectivity is resolved
- **THEN** the complete partition agrees with the actual native export, without dropping pins

#### Scenario: Another sheet has only a local name
- **GIVEN** a local label on a child sheet with no corresponding power/global declaration on that sheet
- **WHEN** the same power name appears elsewhere
- **THEN** that child local net stays isolated according to the native scoped rule
