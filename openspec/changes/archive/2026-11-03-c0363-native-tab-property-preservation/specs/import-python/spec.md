## ADDED Requirements
### Requirement: Native TAB value ownership is exact and bounded
The importer SHALL retain U+0009 TAB in a valid native custom footprint property value through existing native definition properties and slots without changing the printable public Part.properties contract. It SHALL preserve LF behavior and SHALL refuse other unsupported controls and names. No accepted differences or new comparison exclusions SHALL be introduced.

#### Scenario: Authored native TAB roundtrip
- **WHEN** an otherwise valid authored native footprint property value contains TAB
- **THEN** native9/10 import/build proofs preserve its exact value and presentation without generating a nonprintable Part.properties declaration

#### Scenario: Other controls stay refused
- **WHEN** a native property has TAB in its name or CR/NUL/another unsupported value control
- **THEN** import refuses before a write plan and the source remains unchanged
