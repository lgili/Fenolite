## ADDED Requirements

### Requirement: Pin order rule
`library.pin-order` SHALL fire when the leads of a perimeter-numbered land are numbered clockwise in the top view (footprint frame, X right, Y down); JEDEC/IPC lands number counter-clockwise. Only electrical pads numbered `1`, `2`, ... count, the smallest pad of a number is its lead, and a pad over twice the median pad area is a tab or exposed pad. A row of leads on one line SHALL be judged only against one tab beside the middle of that row; otherwise the leads MUST outline the land (three leads in the SOT-23 shape, four in pairs 1-2 and 3-4 on opposite sides, five or more on the sides of their bounding box with each side one run of the numbering) and every turn from one lead to the next around the centre of the pads' extent MUST have one sign. Lands without such a numbering (zig-zag headers, grids, single rows without a tab, two-pad parts, switch pairs) MUST NOT be judged. The finding SHALL be an error for a record and a warning for a plain library item that has no record.

#### Scenario: Mirrored SOT-23
- **GIVEN** a SOT-23 land with pad 1 at the lower left, pad 2 at the upper left and pad 3 at the right
- **WHEN** it is checked
- **THEN** one `library.pin-order` error is reported for its pads

#### Scenario: Correct and turned lands pass
- **GIVEN** a SOIC-8 land numbered counter-clockwise from pad 1 at the upper left
- **WHEN** it is checked as drawn, turned 180° and turned 90°
- **THEN** no `library.pin-order` is reported

#### Scenario: Row beside a tab
- **GIVEN** a TO-252 land whose leads 1 and 3 sit below the tab pad 2, pad 1 at the right
- **WHEN** it is checked
- **THEN** one `library.pin-order` is reported, and none when pad 1 is at the left

#### Scenario: No perimeter numbering
- **WHEN** a 2×3 zig-zag header, a 2×2 grid, a single row, a two-row terminal block with two pads per number or a two-pad chip is checked, as drawn and mirrored
- **THEN** `library.pin-order` does not fire

#### Scenario: Plain library item
- **GIVEN** a `.kicad_mod` with no record whose SOIC-8 leads run clockwise
- **WHEN** `library check` checks it
- **THEN** `library.pin-order` is reported with severity `warning`

## MODIFIED Requirements

### Requirement: Waivers
A record SHALL be able to waive a code with `[[waiver]] code, reason`. A waived finding MUST be reported as `info` with `waived = true`, a waiver that matches no finding MUST give `library.waiver-unused` (warning), and a waiver of `library.record-invalid`, `library.evidence-claim` or `library.review-stale` MUST raise `FormatError` (`FEN-3004`). A waiver of `library.pin-order` MUST raise `FormatError` unless its reason names the S- or D- source (`S-NNNN` or `D-NNNN`) whose top view numbers the part clockwise.

#### Scenario: Waived connector pin 1
- **GIVEN** a connector record waiving `library.pin1-location` with a reason
- **WHEN** it is checked
- **THEN** the pin-1 finding has severity `info` and `waived = true`, and the exit code is 0

#### Scenario: Pin-order waiver without a source
- **GIVEN** a record waiving `library.pin-order` with the reason "Legacy drawing keeps its orientation."
- **WHEN** its waivers are applied
- **THEN** `FormatError` is raised naming the missing S- or D- source

#### Scenario: Pin-order waiver naming its source
- **GIVEN** a record waiving `library.pin-order` with a reason that names `S-0410`
- **WHEN** its clockwise finding is checked
- **THEN** the finding has severity `info` and `waived = true`
