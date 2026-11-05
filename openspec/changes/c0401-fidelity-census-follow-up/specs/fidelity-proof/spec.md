## ADDED Requirements

### Requirement: Census rows without a measured zero count stay visible until attributed
The fidelity census follow-up SHALL keep every corpus row that differs, is refused or is skipped as a
`pending` row with its recorded outcome until its differences are attributed and either fixed or accepted
with counts and a reason. It SHALL NOT reach a zero count through tolerance, normalization, a level subset
or an acceptance waiver.

#### Scenario: A differing row before attribution
- **GIVEN** a corpus row whose strict census reports a difference with no attribution
- **WHEN** the corpus round-trip test runs
- **THEN** the row is skipped as pending with its recorded outcome and is not counted as measured

#### Scenario: An accepted KiCad difference
- **GIVEN** a difference attributed to KiCad with evidence
- **WHEN** it is recorded in `accepted.toml` with its counts and reason
- **THEN** the ratchet fails on any count above the recorded one
