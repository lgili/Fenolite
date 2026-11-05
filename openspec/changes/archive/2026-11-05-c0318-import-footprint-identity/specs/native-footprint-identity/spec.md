## ADDED Requirements

### Requirement: Native identity and definition lookup
Imported parts SHALL preserve their native footprint identity separately from any internal variant definition reference. A build MUST resolve the selected physical definition and write the original native PCB footprint name. Ordinary parts without an override MUST retain their bytes. Comparators and strict schematic metadata/electrical guards MUST remain unchanged.

#### Scenario: Same ID with different geometry
- **GIVEN** two authored PCB footprints with one native ID and different pad geometry
- **WHEN** they are imported and rebuilt without loss or acceptance flags
- **THEN** distinct local definitions preserve both geometries, PCB names equal the originals, and public level 3 has no footprint-name difference

#### Scenario: Repeated physical sheet
- **GIVEN** a shared authored schematic used twice whose PCB instances use different geometry under one native footprint ID
- **WHEN** the emitted project is built twice
- **THEN** the one shared native footprint property remains consistent and both instance geometries are preserved

#### Scenario: Real conflicts remain errors
- **GIVEN** repeated instances whose native footprint, value or same-unit electrical metadata conflicts
- **WHEN** the existing guards and comparisons run
- **THEN** they retain their existing failures without normalized names, ignored differences or accepted loss

### Requirement: Optional definition override
`Component.footprint_definition_ref` SHALL default to empty and be omitted canonically when empty. `Part` MUST expose a keyword-only definition override requiring an explicit native footprint and explicit symbol. The override MUST select KiCad geometry independently of native identity and reject invalid types, device/query misuse and Altium builds. Existing ordinary build and import bytes MUST remain unchanged.

#### Scenario: Default omission
- **WHEN** an ordinary part is converted, serialized and built
- **THEN** the model field is omitted and complete planned file bytes equal the immutable baseline

#### Scenario: Invalid override
- **WHEN** an override has the wrong type, lacks explicit native identity or is supplied with a device/query
- **THEN** construction fails with the existing input-error path
