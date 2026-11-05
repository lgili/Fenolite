## ADDED Requirements

### Requirement: Level 3 compares hole widths
Level 3 SHALL compare the width of each pad's hole: `Pad.drill`, or for a slot with a length the shorter of `Pad.drill` and `Padstack.hole_length`. `pad-drill` MUST report the two widths.

#### Scenario: One slot held two ways
- **GIVEN** a slot held as drill 2.15 mm with length 1.0 mm on one side, and as drill 1.0 mm with length
  2.15 mm on the other
- **WHEN** the two designs are compared at level 3
- **THEN** no `pad-drill` difference is reported

#### Scenario: A wider slot
- **GIVEN** the same slot held as drill 1.2 mm with length 2.15 mm on the other side
- **WHEN** the two designs are compared at level 3
- **THEN** one `pad-drill` difference names 1000000 and 1200000
