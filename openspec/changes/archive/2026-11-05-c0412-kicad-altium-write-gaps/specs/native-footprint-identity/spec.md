## MODIFIED Requirements

### Requirement: Optional definition override
`Component.footprint_definition_ref` SHALL default to empty and be omitted canonically when empty. `Part` MUST expose a keyword-only definition override requiring an explicit native footprint and explicit symbol. The override MUST select KiCad geometry independently of native identity and reject invalid types and device/query misuse. Existing ordinary build and import bytes MUST remain unchanged.
- An Altium build (`build --target altium`) MUST honour the override (change c0412): the part's footprint is resolved and written from the definition, its geometry and its footprint name, as the KiCad build resolves it. One Altium library holds one footprint per name, so the native name cannot carry two geometries there. A part whose written footprint differs from its native footprint MUST get one `altium.footprint-definition` info whose `where` is the part's path and whose message names both. A part without the override MUST be built as before.

#### Scenario: Default omission
- **WHEN** an ordinary part is converted, serialized and built
- **THEN** the model field is omitted and complete planned file bytes equal the immutable baseline

#### Scenario: Invalid override
- **WHEN** an override has the wrong type, lacks explicit native identity or is supplied with a device/query
- **THEN** construction fails with the existing input-error path

#### Scenario: Imported design built for Altium
- **GIVEN** a design from `import --to python` in which one part's `footprint_definition` differs from its native footprint
- **WHEN** it is built with `--target altium`
- **THEN** the build exits 0, the PCB library holds the definition's footprint with its pads, and one `altium.footprint-definition` info names that part, its native footprint and the written one
