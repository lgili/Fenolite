# import-python Specification

## Purpose
TBD - created by archiving change c0358-native-custom-property-preservation. Update Purpose after archive.
## Requirements
### Requirement: Source custom properties outside the public DSL remain native-owned
A native custom footprint property excluded by the existing Part.properties validation SHALL retain its original native name, value, pose and identity in the vendored footprint definition. The generated script SHALL NOT silently erase it or relax public DSL validation.

#### Scenario: Multiline native property survives import
- **WHEN** an authored native footprint contains a named custom property with line feeds
- **THEN** import and build retain the exact native field and complete strict geometry comparison equals
- **AND** directly passing that value to Part.properties remains refused

#### Scenario: Distinct retained properties remain distinct
- **WHEN** two source instances differ only in an unrepresentable custom property
- **THEN** their vendored definitions remain distinct exact variants
- **AND** no input, field comparison or public validation is suppressed

### Requirement: Native TAB value ownership is exact and bounded
The importer SHALL retain U+0009 TAB in a valid native custom footprint property value through existing native definition properties and slots without changing the printable public Part.properties contract. It SHALL preserve LF behavior and SHALL refuse other unsupported controls and names. No accepted differences or new comparison exclusions SHALL be introduced.

#### Scenario: Authored native TAB roundtrip
- **WHEN** an otherwise valid authored native footprint property value contains TAB
- **THEN** native9/10 import/build proofs preserve its exact value and presentation without generating a nonprintable Part.properties declaration

#### Scenario: Other controls stay refused
- **WHEN** a native property has TAB in its name or CR/NUL/another unsupported value control
- **THEN** import refuses before a write plan and the source remains unchanged
