## ADDED Requirements

### Requirement: Grid tolerance of an Altium document
The copper check of an Altium PCB document SHALL judge each clearance against the rule's value as the
document holds it, less `DesignRules.clearance_tolerance`. For an Altium rules view that tolerance is
`GRID_TOLERANCE_UNITS` file units of 2.54 nm, rounded up to whole nanometres (change c0490).
- The Altium rules view MUST NOT lower the rules' values.
- `GRID_TOLERANCE_UNITS` MUST be a whole number of units. It MUST be recorded in
  `docs/formats/altium/import.md` with the measured rounding it covers, its evidence label and hypothesis
  `H-A-CHK-GRID-TOL`.
- The tolerance MUST NOT cover copper that Fenolite's own pour computed. A shortfall made by Fenolite's
  reader or writer is fixed where it is made.
- `copper.clearance` and `copper.hole-clearance` MUST give the same verdicts with that tolerance as before
  for every pair whose gap is not within it.

#### Scenario: A gap a few units short
- **GIVEN** an authored PCB document with a 0.25 mm Clearance rule and two tracks of different nets whose
  gap is 0.25 mm less two file units
- **WHEN** `fenolite check` runs its `copper.clearance` stage on it
- **THEN** it reports no `copper.clearance`, and `summary.tolerated` is 1

#### Scenario: A gap beyond the tolerance
- **GIVEN** the same document with the gap 1 nm below 0.25 mm less the tolerance
- **WHEN** the stage runs
- **THEN** it reports one `copper.clearance` whose `value` is 250 000 nm

### Requirement: The tolerance is stated in the finding
Every `copper.clearance` and `copper.hole-clearance` finding judged with a positive tolerance SHALL end its
clearance clause with `, less a tolerance of <length> mm (<source>)`. The source is the rules view's
`tolerance_source`: `<n> units of the Altium grid` for an Altium document, `KiCad's DRC epsilon` for a
KiCad project (change c0490).
- The finding's `value` MUST be the rule's own value.
- `summary.tolerated` MUST count the pairs closer than the rule that the tolerance passed, and MUST be absent
  when there are none.
- A check run with a tolerance of 0 MUST give the messages it gave before, byte for byte.

#### Scenario: The message of a KiCad finding
- **GIVEN** an authored KiCad board with two tracks 600 nm closer than a 0.2 mm class clearance
- **WHEN** `check_copper` judges it with the KiCad rules view
- **THEN** the message names 0.2 mm and `less a tolerance of 0.0005 mm (KiCad's DRC epsilon)`
