## ADDED Requirements

### Requirement: Native identity follow-up keeps the level-7 failure visible until proven
The native identity follow-up SHALL report the public RoyalBlue level-7 derived-cache difference as a
finding until an approved, complete identity/order correspondence makes the exact regenerated geometry
equal. It SHALL NOT pass level 7 through normalization, renumbering, cache removal, tolerance or waiver.

#### Scenario: Public RoyalBlue replay before an approved correspondence
- **GIVEN** the public RoyalBlue54L-Feather corpus board and native kicad-cli 10.0.6
- **WHEN** verify-source compares the source with the rebuilt board
- **THEN** levels 1–6, S and 8 compare equal and level 7 reports the regenerated geometry difference

#### Scenario: A step without an approved descriptor
- **GIVEN** a follow-up step whose descriptor the coordinator has not approved
- **WHEN** an agent would run it
- **THEN** the step does not run and its task stays open
