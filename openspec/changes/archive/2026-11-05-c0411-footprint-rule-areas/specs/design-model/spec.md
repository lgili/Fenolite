## ADDED Requirements

### Requirement: Footprints hold rule areas
A footprint definition and a footprint instance SHALL hold rule areas (`keepouts`, `Keepout` entities) in addition to their pads and graphics, and placing a definition MUST carry its rule areas into the instance with the placement's frame and side. An empty tuple MUST be left out of the canonical JSON, so footprints without rule areas keep their bytes.

#### Scenario: A placed definition with a rule area
- **GIVEN** a footprint definition with one rule area on `F.Cu`
- **WHEN** it is placed on the bottom side of a board
- **THEN** the instance holds the rule area on `B.Cu`, and the board's checks see it in the board frame
