## ADDED Requirements

### Requirement: Embedding preserves empty native pin identities
A checked native symbol's empty pin number SHALL remain empty on a newer target. Literal tilde
numbers SHALL remain literal on a target that represents them; an unrepresentable old-target number
SHALL refuse locally before emission unless explicit pad mapping supplies a representable number.
Neither ambiguous raw-to-canonical association nor count mismatch SHALL select the first pin.

#### Scenario: Native9 empty-marker pin embedded for10
- **GIVEN** an authored native9 symbol with an empty-number pin and unrelated numbered pins
- **WHEN** it is embedded into target10 and native tools export both sheets
- **THEN** every pin, named partition and unrelated field agrees, including the empty-number identity

#### Scenario: Literal tilde is distinct
- **GIVEN** an authored native10 literal tilde pin number
- **WHEN** target10 embeds it or target9 cannot represent it
- **THEN** target10 preserves the literal identity and target9 refuses without dropping or renaming it
