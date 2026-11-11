## ADDED Requirements

### Requirement: Zone locations in DRC findings
A DRC finding that names a zone SHALL locate it as `zone <name> (<net>, <layers>)`, or `zone (<net>,
<layers>)` for a zone without a name, from the board model. When two zones of the board give the same
text, each SHALL end with `#<k>`, its index in the model's zones counted from 1. A rule area SHALL be
`rule area <name> (<layers>)`. The file locator SHALL move to the finding's detail (change c0495).
- A waiver that names a zone by its old locator (`zone[N]`) MUST still match for one minor version and MUST
  give `check.waiver-location-old` (warning).

#### Scenario: Isolated copper of a named zone
- **GIVEN** an authored board with a rule area and two zones of net `GND` on `F.Cu`, one named `GND top`,
  where the unnamed one leaves an island
- **WHEN** `fenolite check` maps a KiCad DRC report with `isolated_copper` for that zone
- **THEN** the finding's `where` is `zone (GND, F.Cu)`, and holds no `zone[`
