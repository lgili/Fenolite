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

### Requirement: Imported empty values stay empty
`import --to python` SHALL emit `value=""` for a source component whose value is empty, except a
board-only part, which keeps its own value without it. The import self-check SHALL NOT report
`import.unequal` for the value of such a component.

#### Scenario: An imported part with an empty value
- **WHEN** a source board holds a part with an empty value whose vendored symbol's Value is its name
- **THEN** the emitted `Part` call has `value=""`
- **AND** the rebuilt footprint's Value is empty and the self-check reports no value difference

### Requirement: TAB values of non-KiCad sources are declared losses
`import --to python` of a source whose backend is not KiCad SHALL count each component property whose
value holds U+0009 TAB as the unexpressed kind `property-tab` and SHALL go on with the import. The
emitted code SHALL NOT hold the property. The KiCad native TAB contract (c0363) SHALL NOT change.

#### Scenario: An Altium parameter with a TAB
- **WHEN** an Altium project holds a component parameter whose value contains a TAB
- **THEN** the import plans its files instead of exiting 3
- **AND** `result.unexpressed` lists `property-tab` with that reference and parameter name

### Requirement: 3D models of an Altium import
`import --to python` of an Altium project SHALL write the same 3D models as `convert --to kicad` of it: the vendored footprints hold the `(model` entries and the import writes the model files they name (change c0409, B9).

#### Scenario: A placed STEP body
- **GIVEN** the committed blink sample whose top-side LED footprint gets an authored body naming an authored STEP file
- **WHEN** `uv run pytest tests/unit/importer/test_altium_models.py -q` converts it and imports it
- **THEN** the converted board and library and the imported library hold one `(model` per placed body, at the same `${KIPRJMOD}` path, and the imported project holds the model file at that path

