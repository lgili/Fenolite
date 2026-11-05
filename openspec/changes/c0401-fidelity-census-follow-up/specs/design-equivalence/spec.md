## MODIFIED Requirements

### Requirement: Level 5 strict matching
Strict matching SHALL be deterministic: items of one kind are keyed by copper span and geometry (a track by its two ends as an unordered pair, an arc by its ends and mid, a via by its position), matched first on equal keys, then each unmatched item of side `a` in key order with the first unmatched item of side `b` within the length tolerance. Inside one equal key, an item of side `a` MUST pair first with the first unmatched item of side `b` whose strict-rule fields are all equal, and only then with the first unmatched item of that key, so equal keys match as a multiset of their compared fields. `where` MUST be `<net name>:<kind>:<span>:<points>`.

#### Scenario: Reversed track
- **GIVEN** a copy in which one track's start and end are exchanged
- **WHEN** level 5 runs with `strict=True` at tolerance 0
- **THEN** no difference is reported

#### Scenario: Tolerance
- **GIVEN** a copy with one via moved by 5 nm on x
- **WHEN** level 5 runs with `strict=True` at `length_nm` 4 and at 5
- **THEN** the first reports one `via-missing` per side, located `GND:via:top-bottom:<x>,<y>`, and the second reports nothing

#### Scenario: Coincident tracks in another order
- **GIVEN** two tracks with the same ends, widths 0.3 mm and 0.29997 mm, written in the other order on side `b`
- **WHEN** level 5 runs with `strict=True` at tolerance 0
- **THEN** no difference is reported, and changing one width on side `b` still reports one `track-width`
