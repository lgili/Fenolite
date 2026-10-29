## ADDED Requirements

### Requirement: Proposal file
`fenolite.library.proposals.parse_proposal(text, *, file)` SHALL read one TOML file of schema `fenolite.proposal.v0` with the tables `datasheet`, `proposer`, `device`, `package` (with an optional `land`), `pin`, `ratings`, `part` and `doubt`. Lengths and ratings MUST be parsed exactly as text with a unit, ranges as the quantity ranges define them, and no float MUST be created.

#### Scenario: An authored proposal is read
- **GIVEN** the authored file `tests/data/proposals/exb6202.proposal.toml`
- **WHEN** `uv run pytest tests/unit/library/proposals/test_parse.py -k read` parses it
- **THEN** it returns a proposal with 8 pin rows, the family `gullwing`, a pitch of 1 270 000 nm, and no field holds a float

### Requirement: Proposal keys are closed
An unknown key SHALL raise `FormatError` (`FEN-3004`) naming the file and the key, and a newer schema SHALL raise `FEN-3002`. A geometry key (`pads`, `pad`, `x`, `y`, `at`, `position`, `outline`, `polygon`, `courtyard`, `silkscreen`, `graphics`, `vertices`, `points`) outside the parameters of `package.land` MUST raise `FEN-3004` with a message saying that a proposal carries no geometry.

#### Scenario: Coordinates refused
- **WHEN** a proposal whose pin row holds `x = "1.2mm"`, and one with a `[[package.pads]]` table, are parsed
- **THEN** each raises `FEN-3004` and the message names the key and says that a proposal carries no geometry

### Requirement: Proposal citations and doubts
A `cite` table SHALL hold `page` (an integer of at least 1) and at most one of `table` and `figure`. A pin row, package, land, rating or part without `cite` MUST give `proposal.uncited` (warning). Each `[[doubt]]` (a field path and a reason) MUST give `proposal.doubt` (warning) naming the field.

#### Scenario: A doubt is reported
- **GIVEN** the authored proposal with one `[[doubt]]` on `package.lead.length`
- **WHEN** it is checked
- **THEN** one `proposal.doubt` warning names `package.lead.length`

### Requirement: Proposal skeleton
`fenolite library propose --datasheet FILE` without `--proposal` SHALL be read-only and exit 0 with `result.skeleton`, the TOML text of an empty proposal whose `datasheet.file` and `datasheet.sha256` are filled in, and `result.guide` = `datasheets`. A file that does not start with `%PDF-` MUST exit 3 with `FEN-3004`.

#### Scenario: Skeleton of the authored datasheet
- **WHEN** `fenolite library propose --datasheet tests/data/proposals/exb6202.pdf --json` runs
- **THEN** the exit code is 0, the skeleton holds the SHA-256 of that file, and it parses as a proposal with no pin rows

### Requirement: Proposal bound to its datasheet
`fenolite library propose` with `--proposal` SHALL compare each proposal's `datasheet.sha256` with the SHA-256 of `--datasheet`. A difference MUST give `proposal.datasheet-mismatch` (error), and nothing MUST be planned.

#### Scenario: Another datasheet
- **GIVEN** the authored proposal and another authored PDF
- **WHEN** `library propose --datasheet other.pdf --proposal exb6202.proposal.toml --out devices/proposed --dry-run` runs
- **THEN** the exit code is 5, the issues hold `proposal.datasheet-mismatch`, and nothing is planned

### Requirement: Proposal self-checks
A proposal SHALL be checked against itself and the family table of the footprint generators: an unknown family, a repeated pin number, a pin count other than the package's, a number the family cannot give, a depopulated ball used as a pin, or a reversed range MUST be an error (`proposal.unknown-family`, `-duplicate-pin`, `-pin-count`, `-pin-outside`, `-depopulated-used`, `-range`).

#### Scenario: One pin missing
- **GIVEN** the authored proposal with its row of pin 7 removed
- **WHEN** it is proposed with `--dry-run`
- **THEN** the exit code is 5 and one `proposal.pin-count` names 7 rows against 8 pins

#### Scenario: Ball outside the grid
- **GIVEN** an authored grid proposal with `row_labels` `A` to `H`, 8 columns and a pin row `J4`
- **WHEN** it is proposed with `--dry-run`
- **THEN** one `proposal.pin-outside` names `J4`

### Requirement: Proposal warnings
A pin named like an exposed pad while the package has no `ep`, or an `ep` that no pin names, SHALL give `proposal.exposed-pad` (warning). A four-sided family whose pin count does not divide by four and that gives no per-side counts SHALL give `proposal.sides` (warning).

#### Scenario: Exposed pad named but not declared
- **GIVEN** the authored proposal with a ninth row named `EP` and no `ep` in its package
- **WHEN** it is checked
- **THEN** one `proposal.exposed-pad` warning names the row

### Requirement: Dense packages need two proposals
A proposal of the family `grid`, or with more than 100 pins, SHALL be refused with `proposal.second-required` (error) unless a second `--proposal` is given. The two MUST name the same datasheet and differ in `proposer.name` or `proposer.kind`, else `proposal.not-independent` (error).

#### Scenario: One proposal for a grid
- **WHEN** the authored grid proposal is proposed alone with `--dry-run`
- **THEN** the exit code is 5 and the issues hold `proposal.second-required`

### Requirement: Two proposals agree
With two proposals, every pin row and every package parameter SHALL be equal after rows are sorted by number and units parsed; citations and doubts MUST be ignored. Each difference MUST be one `proposal.disagree` (error) naming the field, both values and the cited pages.

#### Scenario: Shifted rows caught
- **GIVEN** two authored grid proposals that differ only by the names of balls `C3` and `C4` swapped
- **WHEN** they are proposed together with `--dry-run`
- **THEN** the exit code is 5 and two `proposal.disagree` errors name `C3` and `C4`

### Requirement: Generators draw proposed devices
A proposal that passes its checks SHALL be converted into package, pins and device records with `evidence = "UNVERIFIED"` and an `[origin]` naming the tool, the datasheet and its SHA-256, the proposer and each proposal's SHA-256. The footprint and body MUST be drawn by the footprint generators and the symbol by the symbol generator; no geometry MUST come from the proposal.

#### Scenario: The device folder
- **WHEN** the authored proposal is proposed with `--out devices/proposed --dry-run --json`
- **THEN** the exit code is 4 and the plan writes the three records, the drawn symbol, footprint and body, and `proposal.toml` under `devices/proposed/EXB6202/`

#### Scenario: Same proposal, same bytes
- **WHEN** the authored proposal is proposed twice with the same `--timestamp`
- **THEN** the two plans have the same id

### Requirement: Library rules run on proposals
After drawing, `library propose` SHALL run the library rules on the drawn device and report their findings with the generator's. An error finding of either MUST stop the plan.

#### Scenario: Span smaller than the land needs
- **GIVEN** the authored proposal with a span shorter than its body width plus the lead length
- **WHEN** it is proposed with `--dry-run`
- **THEN** the exit code is 5 and a finding of the generator or of the library rules names the span

### Requirement: Proposal target and re-proposal
`--out` SHALL follow the target rule of the library import (relative, inside the project, never the shipped catalog or a pack). A corrected proposal over an unreviewed, unedited folder MUST replace it; over a reviewed or edited folder it MUST exit 7 with `FEN-7001`.

#### Scenario: Corrected proposal over a reviewed device
- **GIVEN** a proposed folder that a review accepted
- **WHEN** a corrected proposal is proposed into it
- **THEN** the exit code is 7 and nothing is written

### Requirement: Review gate of proposed devices
`fenolite.library.proposals.review_gate(folder, datasheet)` SHALL refuse the acceptance of a device whose `origin.tool` is `fenolite library propose` while a doubt remains (`proposal.review-doubt`), a row lacks a citation (`-uncited`), the datasheet is missing or has another SHA-256 (`-datasheet`), or the library check of the current files has not passed (`-unchecked`).

#### Scenario: Acceptance with an open doubt
- **GIVEN** a proposed folder whose `proposal.toml` holds one `[[doubt]]`
- **WHEN** the library review accepts it with the right datasheet and a reviewer name
- **THEN** the exit code is 5, the issues hold `proposal.review-doubt`, and the label stays `UNVERIFIED`

### Requirement: No model in the core
The proposal pipeline SHALL import no third-party package, start no subprocess and make no network request. The datasheet MUST be read only to compute its SHA-256 and check its first bytes.

#### Scenario: Import graph of proposals
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/library/proposals -q` runs
- **THEN** no module of `fenolite.library.proposals` imports a third-party package, `subprocess`, `socket` or `urllib`
