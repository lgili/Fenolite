# library-rules Specification

## Purpose
Check library records and native definitions, produce reproducible review sheets and record explicit human reviews within their measured evidence scope.
## Requirements
### Requirement: Library check targets
`fenolite library check TARGET...` SHALL check c0259 records, folders of records walked in code-point order, and plain libraries (`.kicad_sym`, `.kicad_mod`, `.pretty`, `.SchLib`, `.PcbLib`), and report `library.*` findings. On a plain library item only rules that need no record MUST run, and each item MUST list its `rules_run`. An unreadable record MUST give `library.record-invalid` and the walk MUST continue.

#### Scenario: Mixed folder
- **GIVEN** the authored folder `tests/data/library_rules/mixed/` with a good device, a record with a TOML syntax error and a `.pretty` folder
- **WHEN** `fenolite library check tests/data/library_rules/mixed --json` runs
- **THEN** it exits 5, reports one `library.record-invalid` naming the broken file, and lists the `.pretty` footprints with `rules_run` that exclude `library.body-span`

#### Scenario: Clean records
- **WHEN** the check runs on `tests/data/library_rules/good/`
- **THEN** it exits 0 with no error or warning finding

### Requirement: Pad count rule
`library.pad-count` (error) SHALL fire when the pads reached by a device's map, the footprint's numbered electrical pads less `unused_pads`, and the pin table's numbers with `stacked` are not one set, or when a package's `pins` differs from its generated footprint's terminal count. The finding MUST list the missing numbers of each side in natural order.

#### Scenario: One pin short
- **GIVEN** an authored SOIC-8 device whose pin table lists pins 1 to 7
- **WHEN** it is checked
- **THEN** one `library.pad-count` names pad `8` as reached by no pin

### Requirement: Pin-1 rules
`library.pin1-location` (error) SHALL fire when pad `1` (or `A1` on a grid array) is not at or above-left of the centroid of the numbered pads (footprint frame, Y down, one inequality strict), for footprints of three or more numbered pads or polarized two-pad ones. `library.pin1-marker` (warning) SHALL fire when no silk or fab graphic is centred strictly nearer to pad 1 than to any other pad.

#### Scenario: Rotated footprint
- **GIVEN** a good SOIC-8 footprint rotated by 180° about its origin
- **WHEN** it is checked
- **THEN** one `library.pin1-location` is reported, naming pad `1`

#### Scenario: Non-polarized chip
- **WHEN** a two-pad resistor footprint without a marker is checked
- **THEN** neither pin-1 rule fires

### Requirement: Courtyard and clearance rules
`library.courtyard-missing` (error) SHALL fire for a footprint without a closed courtyard outline, `library.courtyard-containment` (error) when the courtyard does not contain every copper pad shape and the body outline, and `library.pad-clearance` (error) when two pads of different numbers touch or overlap. Containment MUST use `fenolite.geometry` in integer nanometres.

#### Scenario: Pad outside the courtyard
- **GIVEN** a good footprint with one pad moved 0.5 mm outwards
- **WHEN** it is checked
- **THEN** one `library.courtyard-containment` names that pad

### Requirement: Body against span rule
`library.body-span` (error) SHALL check package ranges exactly: for families with leads beyond the body, `body.width.max < span.min`; for no-lead families, a given `span` overlaps `body.width`; for all, `2 × lead.length.min < span.max − body.width.min + 2T` with `T` from `docs/formats/library/rules.md`, and every range has `min ≤ max`.

#### Scenario: Body wider than span
- **GIVEN** an authored gull-wing package with `body.width = 3.80mm..6.30mm` and `span = 5.80mm..6.20mm`
- **WHEN** it is checked
- **THEN** one `library.body-span` names `body.width` and `span`

### Requirement: Depopulated ball rule
`library.depopulated` (error) SHALL fire for a grid-array package when `rows × columns − depopulated` differs from `pins`, a depopulated position is outside the grid, the footprint has a pad at a depopulated position, or a ball name breaks the row-letter rule of `docs/formats/library/rules.md` (no `I`, `O`, `Q`, `S`, `X`, `Z`; `AA` after `Y`).

#### Scenario: Forgotten depopulated ball
- **GIVEN** an authored 10 × 10 grid with `pins = 96` and three depopulated positions
- **WHEN** it is checked
- **THEN** one `library.depopulated` reports 97 positions for 96 pins

### Requirement: Land pattern rules
For a package with a manufacturer `[land]`, `library.land-mismatch` SHALL be an error when a generated footprint differs from the pattern at all, and a warning when an imported or hand-authored one differs by more than `T` in pad size or position. `library.land-calculator-delta` (info) MUST give the largest difference between the pattern and the calculator's land.

#### Scenario: Imported footprint off by 0.1 mm
- **GIVEN** a package with a land pattern and an authored footprint whose pads are 0.1 mm longer
- **WHEN** both are checked
- **THEN** one `library.land-mismatch` warning names the pads, and one `library.land-calculator-delta` info is reported

### Requirement: Symbol rules
`library.pin-grid` SHALL be an error for a pin point or length off 0.254 mm and a warning off 2.54 mm. `library.hidden-power` (error) SHALL fire for a hidden `power_in` pin not stacked on a visible pin, `library.duplicate-pin` (error) for one number twice in a unit and body style except stacked pins, and `library.pin-group-type` (warning) for a group whose type disagrees with it.

#### Scenario: Half-grid pin
- **GIVEN** a hand-authored symbol with one pin at x = 1.27 mm and one at x = 0.127 mm
- **WHEN** it is checked
- **THEN** the first gives a `library.pin-grid` warning and the second a `library.pin-grid` error

#### Scenario: Generated symbols pass
- **WHEN** every symbol generated from `tests/data/pins` is checked
- **THEN** no symbol rule fires

### Requirement: Footprint filter rules
`library.footprint-filter-miss` (warning) SHALL fire when no `ki_fp_filters` pattern of a device's symbol matches the device's footprint name, case-sensitively, without the library. `library.footprint-filter-broad` (warning) SHALL fire for an empty pattern, `*`, or a pattern that matches every name.

#### Scenario: Stale filter
- **GIVEN** a device on footprint `SOIC-8_3.9x4.9mm_P1.27mm` whose symbol filters `TSSOP*`
- **WHEN** it is checked
- **THEN** one `library.footprint-filter-miss` names the filter and the footprint

### Requirement: Record envelope rules
`library.source-unknown` (error) SHALL fire for a source id missing from the tree's source register, with `library.sources-unchecked` (info) when there is none. `library.evidence-claim` (error) SHALL fire for `evidence` above `CORPUS-VERIFIED`, or `CORPUS-VERIFIED` without a `[[reviewed_by]]`.

#### Scenario: Self-promoted record
- **WHEN** a record with `evidence = "CORPUS-VERIFIED"` and no `[[reviewed_by]]` is checked
- **THEN** one `library.evidence-claim` is reported and the item's `effective_evidence` is `UNVERIFIED`

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

### Requirement: Effective evidence
Each checked item SHALL report `evidence` as written and `effective_evidence`: the lowest of its own label and, for a device, those of its pin table and package records; a stale or missing review MUST lower a `CORPUS-VERIFIED` label to the review's `previous_evidence`, or `UNVERIFIED` when there is no review.

#### Scenario: Device on an unreviewed package
- **GIVEN** a reviewed device whose package record is `INFERRED`
- **WHEN** it is checked
- **THEN** its `evidence` is `CORPUS-VERIFIED` and its `effective_evidence` is `INFERRED`

### Requirement: Review sheets
`library check --sheets DIR` SHALL plan one standalone HTML sheet per item, `DIR/index.html` and `DIR/sheets.json` (`fenolite.library_sheets.v0`, each sheet's SHA-256), using dry-run, confirmation, staged plans and receipts. A sheet MUST show the symbol units, footprint layers, body outline, pin table, dimensions with sources, pin-to-pad map, findings and review state. Equal inputs MUST give equal bytes.

#### Scenario: Sheet of a device
- **WHEN** `fenolite library check tests/data/library_rules/good/example_buck --sheets review --confirm --json` runs twice
- **THEN** both runs write `review/device/<safe-id-and-hash>.html`, `review/index.html` and `review/sheets.json` with equal bytes, and the sheet holds the six pin rows and every dimension's source id

#### Scenario: Dry run writes nothing
- **WHEN** the same command runs with `--dry-run`
- **THEN** no file is created and the plan lists the three files with their SHA-256

### Requirement: Old and new comparison
`library check --compare OLD` SHALL pair items by stable id (plain library items by lib id), report each pair as `added`, `removed`, `changed` or `same` with the changed record fields and whether the generated symbol and footprint changed, run `library.interface-changed` (error) and `library.removed` (warning), and put the `view --compare` overlay on the sheet of each changed item.

#### Scenario: Generator change
- **GIVEN** OLD and NEW trees with equal records, where NEW's package `land.pad.length` is 0.1 mm longer
- **WHEN** `library check NEW --compare OLD --sheets review --confirm` runs
- **THEN** the package is `changed` with the field path `land.pad.length` and `footprint_changed = true`, and its sheet holds the visual-diff overlay with the changed pads

#### Scenario: Pins renumbered under one id
- **WHEN** NEW changes a pin number of a device that keeps its id
- **THEN** one `library.interface-changed` error names the device and the pin

### Requirement: Review record
`fenolite library review TARGET --accept --reviewer NAME --sheet HEX` SHALL write, through plan and confirm, a `[[reviewed_by]]` table (who, date, digest, sheet_sha256, fenolite_version, previous_evidence, accepted_codes) into each target record and set `evidence` to `CORPUS-VERIFIED`. `--revoke` MUST remove the table and restore `previous_evidence`. Without either flag the command MUST only report the review state.

#### Scenario: Accept a clean device
- **GIVEN** a device with no error finding and evidence `UNVERIFIED`
- **WHEN** `library review` runs with `--accept --reviewer jdoe --sheet <12 hex of its sheet> --timestamp 2026-11-02T00:00:00Z --confirm`
- **THEN** the record holds `evidence = "CORPUS-VERIFIED"` and a `[[reviewed_by]]` with `who = "jdoe"`, `date = "2026-11-02"` and `previous_evidence = "UNVERIFIED"`, and the receipt lists the file

#### Scenario: Revoke
- **WHEN** `--revoke --confirm` runs on that record
- **THEN** the record equals its state before the review

### Requirement: Review preconditions
`library review --accept` MUST write nothing and exit 5 while the item has an error finding, exit 4 with `FEN-4002` when `--sheet` is not a prefix of at least 12 hex digits of the current sheet's SHA-256, exit 2 with `FEN-2001` for an empty `--reviewer` or one holding `@`, and exit 7 with `FEN-7001` for a record above `CORPUS-VERIFIED`.

#### Scenario: Sheet changed after it was opened
- **GIVEN** a reviewer who noted a sheet digest, then a record edit that changes the sheet
- **WHEN** `library review --accept` runs with the noted digest
- **THEN** it exits 4 with `FEN-4002` and the record is unchanged

#### Scenario: Error finding blocks the review
- **WHEN** `library review --accept` runs on the one-pin-short device
- **THEN** it exits 5 with `library.pad-count` and writes nothing

### Requirement: Stale reviews
The review digest SHALL be the SHA-256 of the canonical JSON of the record without `evidence` and `reviewed_by`, of its generated definitions and, for a device, of its pin table and package digests. `library.review-stale` (error) MUST fire when it or the sheet digest differs; reformatting MUST NOT change it.

#### Scenario: Edit after review
- **GIVEN** a reviewed pin table
- **WHEN** one pin name is changed and the table is checked
- **THEN** one `library.review-stale` is reported and `effective_evidence` is the review's `previous_evidence`

#### Scenario: Reformatting is not an edit
- **WHEN** the reviewed table is rewritten with other whitespace and key order and checked
- **THEN** no `library.review-stale` is reported

### Requirement: Reviews are a human step
The MCP server SHALL NOT expose `library review --accept` or `--revoke`, and the agent guide MUST state that an agent never runs them unless the person names themselves as reviewer and has opened the sheet. CI workflows documented by Fenolite MUST NOT run `--accept`.

#### Scenario: Not an MCP tool
- **WHEN** the MCP tool list is generated
- **THEN** it holds `library check` and no tool that accepts or revokes a review

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

