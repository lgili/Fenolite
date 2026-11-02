## ADDED Requirements

### Requirement: Derived footprints preserve safe interior spaces
Altium-to-KiCad conversion SHALL preserve interior ASCII spaces in a portable derived footprint name. The board link, component link, library filename and footprint header MUST agree. Project/symbol sanitization, reserved-name and path guards, and case-insensitive collision allocation SHALL remain unchanged. Name comparison MUST detect a real rename.

#### Scenario: Space and underscore are distinct names
- **GIVEN** authored footprints named `M Mount` and `M_Mount`
- **WHEN** their derived KiCad project is written and read
- **THEN** both names retain distinct matching board links and library files
- **AND** a deliberate rename still produces a footprint-name difference
