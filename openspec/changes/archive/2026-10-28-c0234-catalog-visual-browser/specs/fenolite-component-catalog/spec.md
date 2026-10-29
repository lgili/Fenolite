## ADDED Requirements

### Requirement: Installed catalog visual browser

`fenolite catalog view --out FILE [--kind symbol|footprint] [--query TEXT]` SHALL plan one standalone HTML page of the matching installed catalog definitions. It SHALL reuse the existing library and geometry viewer, work offline without an external CAD tool or intermediate CAD file, and use the normal dry-run, confirmation, staged replay and receipt protocol. Its viewer imports SHALL be lazy for list/show. Equal catalog definitions and filters SHALL produce equal page bytes.

#### Scenario: Review the installed catalog
- **WHEN** catalog view is confirmed without filters
- **THEN** one standalone page includes every installed symbol and footprint in stable ID order, grouped into two virtual library documents
- **AND** each item displays its exact lib ID, category, summary, evidence, public source IDs and pin or pad information, with existing measurement and selection tools
- **AND** no evidence level or generic-to-device compatibility claim is upgraded

#### Scenario: A filtered review
- **WHEN** view receives a kind or text filter
- **THEN** its entries equal list_entries with those filters, and only nonempty library documents are included

#### Scenario: No matching entry
- **WHEN** view filters match no entry
- **THEN** it returns FEN-3001 with a hint to change the filters, plans no write and preserves an existing target
- **AND** list with the same filters still succeeds with an empty list

#### Scenario: Review and replay
- **WHEN** view runs with --dry-run and is later confirmed with its plan ID
- **THEN** dry-run creates no output HTML and confirmation writes exactly the staged bytes with their receipt hash

#### Scenario: Invalid arguments do not write
- **WHEN** view has no --out or has a positional lib ID, or list/show has --out
- **THEN** it returns a usage error and writes nothing

#### Scenario: Existing inspection stays read-only
- **WHEN** catalog list or catalog show runs as before
- **THEN** it succeeds without confirmation, returns its existing metadata and creates no output

#### Scenario: Viewer consumes resolved model definitions
- **WHEN** the CLI prepares a catalog browser
- **THEN** it resolves entries into metadata and model definitions before calling the viewer
- **AND** the viewer imports no catalog package and performs no catalog lookup, preserving the existing package-layering rules and generated page bytes

#### Scenario: Catalog geometry remains readable
- **WHEN** a catalog symbol is displayed
- **THEN** metadata properties are shown in item details instead of over the body, and metadata text does not expand the drawing's fitted bounds
- **AND** body geometry, pin numbers and visible pin names remain drawn, without modifying the stored definition or ordinary library rendering
- **WHEN** a catalog footprint is displayed
- **THEN** fabrication and courtyard layers are initially visible, and the initial details omit an exhaustive pad-number list while pad selection retains exact pad information

#### Scenario: Details do not obscure the initial drawing
- **WHEN** a catalog item is selected
- **THEN** its metadata panel starts collapsed with evidence in its labelled summary
- **AND** keyboard or pointer activation expands and collapses the metadata without altering geometry or ordinary library panels
