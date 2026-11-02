## ADDED Requirements

### Requirement: Native drawn bus identifiers preserve exact members
The Altium drawn writer SHALL convert a bus-only group or alias identifier to
a native vector only when its exact scalar member set is representable by a
contiguous canonical numeric range with a common nonempty prefix. It SHALL
report each changed identifier. It MUST preserve scalar wire labels, ordinary
vectors, coordinates and independent connectivity guards, and MUST refuse an
unrepresentable group with a source locator before planning output.

#### Scenario: Alias crosses a sheet boundary
- **GIVEN** a connected two-sheet bus whose group alias expands to D0 through D3
- **WHEN** binary or ASCII native files are produced
- **THEN** the parent label and sheet entry and child port use D[0..3]
- **AND** every scalar net and its code pin membership remain unchanged

#### Scenario: A group requires a harness
- **GIVEN** a bus-only group with unrelated or missing numeric members
- **WHEN** a native build is requested, including with allow-lossy
- **THEN** it refuses at the source identifier without writing files
- **AND** no widened native acceptance or suppressed compiler finding hides it

### Requirement: Native availability does not imply acceptance
Current native metadata SHALL name the actually measured tool and report while
retaining the original unmet acceptance criterion and inferred grade. Dated
earlier unavailable-tool observations MUST remain historical, not be reused as
the current reason or be turned into a successful native gate.

#### Scenario: Available tool with source findings
- **GIVEN** actual 22.2.1 native graph/save observations with remaining findings
- **WHEN** the current hypothesis and kit metadata are checked
- **THEN** the actual report is named and acceptance remains pending
- **AND** the deliberately broken native bus control remains a refused result
